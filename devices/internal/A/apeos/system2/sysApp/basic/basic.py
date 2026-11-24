"""
aPE-BASIC: a small line-numbered BASIC for aPEOSI, in the style of the
home computers of the late 1970s and 80s.

How it works, in four parts:

1. Program store: numbered lines, kept in this process's aPE-RAM as text.
2. Tokenizer:     turns  IF X > 10 THEN 50  into  [IF] [X] [>] [10] [THEN] [50].
3. Expressions:   a recursive-descent parser: one method per precedence
                  level, each calling the next-tighter level (see _expr).
4. Runner:        a "program counter" (line index + token position) that
                  executes one statement at a time, like a CPU executing
                  one instruction at a time.

aPEOSI integration:
* Every statement counts as one "instruction". After QUANTUM statements the
  interpreter yields, so BASIC programs multitask with everything else.
  Even  10 GOTO 10  cannot freeze the OS.
* INPUT uses the ReadLine system call, SLEEP uses Sleep.
* Variables, arrays and the program text live in this process's memory, so
  the aPE-Watchdog shows them. PEEK and POKE read and write
  that memory directly, like on a Commodore 64.
* aPE system keywords let a program look at the motherboard (CPU$, RAMSIZE),
  the process table (PSLOT, PSTATE, PNAME$), the MMU (FRAME, PHYS), and
  control other processes (SPAWN, KILL, WAIT, YIELD, SHELL).

Virtual memory map of a BASIC process:
    0x0000  header: magic "BAS1", statement counter (u32), current line (u16),
            variable count (u16), program length (u32), array heap top (u32)
    0x0100  variable table: 64 slots x 128 bytes
    0x2100  array heap
    0x4000  program text
    0x8000  free: for programs' own PEEK and POKE
"""

import math
import os
import random
import re
import struct
import time

from devices.internal.A.apeos.system2.sys import sys_cmd_exec
from devices.internal.A.apeos.system2.sys.aperam import OFF_TICK
from devices.internal.A.apeos.system2.sys.mem_mgr import OutOfMemory, PageFault
from devices.internal.A.apeos.system2.sys.process_mgr import ReadLine, Sleep

# --- memory map -----------------------------------------------------------------
H_MAGIC, H_STMTS, H_LINE, H_NVARS, H_PROGLEN, H_HEAP = 0x00, 0x04, 0x08, 0x0A, 0x0C, 0x10
VARS, VAR_SIZE, MAX_VARS = 0x0100, 128, 64
HEAP, HEAP_END = VARS + VAR_SIZE * MAX_VARS, 0x4000
PROG, PROG_END = 0x4000, 0x8000
USER_MEM = 0x8000

NAME_MAX = 8          # significant characters in a variable name
STR_MAX = 112         # longest string a variable can hold
ARR_STR_MAX = 39      # longest string an array element can hold (40-byte elements)

T_NUM, T_STR, T_NUMARR, T_STRARR = 1, 2, 3, 4
NO_LINE = 0xFFFF

QUANTUM = 100         # statements per time slice before yielding to the scheduler
ZONE = 14             # PRINT , moves to the next 14-column zone

KEYWORDS = {
    "PRINT", "LET", "INPUT", "IF", "THEN", "ELSE", "GOTO", "GOSUB", "RETURN",
    "FOR", "TO", "STEP", "NEXT", "END", "STOP", "DIM", "POKE", "SLEEP", "CLS",
    "RANDOMIZE", "AND", "OR", "NOT", "MOD",
    "RUN", "LIST", "NEW", "SAVE", "LOAD", "BYE", "EXIT",
    "KILL", "WAIT", "YIELD", "SHELL", "OUT",
}

TOKEN_RE = re.compile(r"""
     (?P<ws>\s+)
    |(?P<hex>&[Hh][0-9A-Fa-f]+)
    |(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)
    |(?P<str>"[^"]*"?)
    |(?P<name>[A-Za-z][A-Za-z0-9_]*\$?)
    |(?P<op><=|>=|<>|[-+*/^=<>(),;:])
    |(?P<rem>')
""", re.VERBOSE)


class BasicError(Exception):
    """A BASIC runtime or syntax error, e.g. ?SYNTAX ERROR IN 30."""


def tokenize(text):
    """Splits one line of BASIC into (kind, value) tokens."""
    toks = []
    i = 0
    while i < len(text):
        m = TOKEN_RE.match(text, i)
        if not m:
            raise BasicError("SYNTAX")
        kind, val, i = m.lastgroup, m.group(), m.end()
        if kind == "ws":
            continue
        if kind == "hex":
            toks.append(("num", float(int(val[2:], 16))))
        elif kind == "num":
            toks.append(("num", float(val)))
        elif kind == "str":
            closed = len(val) > 1 and val.endswith('"')
            toks.append(("str", val[1:-1] if closed else val[1:]))
        elif kind == "name":
            up = val.upper()
            if up == "REM":
                toks.append(("rem", text[i:]))
                break
            toks.append(("kw", up) if up in KEYWORDS else ("name", up))
        elif kind == "op":
            toks.append(("op", val))
        else:  # ' comment
            toks.append(("rem", text[i:]))
            break
    return toks


def fmt(value):
    """How PRINT shows a value."""
    if isinstance(value, str):
        return value
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return f"{value:.9g}"


class _Input:
    def __init__(self, prompt, targets):
        self.prompt = prompt
        self.targets = targets


class _Wait:
    def __init__(self, pid):
        self.pid = pid


_YIELD = object()


class Basic:
    """The aPE-BASIC interpreter, run as an aPEOSI process."""

    def __init__(self, kernel, filename=None, *_):
        self.kernel = kernel
        self.filename = filename
        self.lines = {}        # line number -> source text (mirrored into RAM)
        self.tokens = {}       # line number -> tokens (cache, rebuilt on edit)
        self.var_index = {}    # variable name -> slot number in the RAM table
        self.col = 0
        self.started = time.monotonic()
        self.quit = False

    # ======================================================== memory helpers ===
    def _u16(self, addr):
        return struct.unpack("<H", self.mem.load(addr, 2))[0]

    def _set_u16(self, addr, value):
        self.mem.store(addr, struct.pack("<H", value & 0xFFFF))

    def _init_memory(self):
        self.mem.store(H_MAGIC, b"BAS1")
        self.mem.store_u32(H_STMTS, 0)
        self._set_u16(H_LINE, NO_LINE)
        self.mem.store_u32(H_PROGLEN, 0)
        self._clear_variables()

    def _clear_variables(self):
        count = self._u16(H_NVARS)
        if count:
            self.mem.store(VARS, bytes(count * VAR_SIZE))
        self._set_u16(H_NVARS, 0)
        self.mem.store_u32(H_HEAP, HEAP)
        self.var_index = {}
        self.for_stack = []
        self.gosub_stack = []

    # --- program text ------------------------------------------------------
    def _sync_program(self):
        """Writes the whole program into RAM as text."""
        text = "".join(f"{n} {self.lines[n]}\n" for n in sorted(self.lines)).encode("latin-1", "replace")
        if len(text) > PROG_END - PROG:
            raise BasicError("PROGRAM TOO LARGE")
        old = self.mem.load_u32(H_PROGLEN)
        self.mem.store(PROG, text + bytes(max(0, old - len(text))))
        self.mem.store_u32(H_PROGLEN, len(text))

    def _program_text(self):
        length = self.mem.load_u32(H_PROGLEN)
        return self.mem.load(PROG, length).decode("latin-1") if length else ""

    def _edit_line(self, number, source, sync=True):
        if not 0 < number < 65530:
            raise BasicError("ILLEGAL LINE NUMBER")
        source = source.strip()
        if not source:
            self.lines.pop(number, None)
            self.tokens.pop(number, None)
        else:
            self.tokens[number] = tokenize(source)  # syntax-checks the line now
            self.lines[number] = source
        if sync:
            self._sync_program()

    def _load(self, filename):
        if "." not in os.path.basename(filename):
            filename += ".bas"
        content = self.kernel.fs_manager.read_file(filename)
        if isinstance(content, str) and content.startswith("Error"):
            raise BasicError(f"FILE NOT FOUND: {filename}")
        self.lines, self.tokens = {}, {}
        for n, raw in enumerate(content.splitlines(), 1):
            if not raw.strip():
                continue
            m = re.match(r"\s*(\d+)\s?(.*)$", raw)
            if not m:
                raise BasicError(f"LINE NUMBER MISSING ON LINE {n} OF {filename}")
            try:
                self._edit_line(int(m.group(1)), m.group(2), sync=False)
            except BasicError as e:
                raise BasicError(f"{e} IN {m.group(1)}")
        self._sync_program()
        return filename

    # --- variables -----------------------------------------------------------
    def _slot_addr(self, slot):
        return VARS + slot * VAR_SIZE

    def _new_slot(self, key, vtype):
        if len(key.rstrip("(")) > NAME_MAX:
            raise BasicError(f"NAME TOO LONG ({key.rstrip('(')}, max {NAME_MAX})")
        slot = self._u16(H_NVARS)
        if slot >= MAX_VARS:
            raise BasicError("TOO MANY VARIABLES")
        addr = self._slot_addr(slot)
        self.mem.store(addr, key.rstrip("(").encode("ascii").ljust(8, b"\x00") + bytes([vtype]))
        self._set_u16(H_NVARS, slot + 1)
        self.var_index[key] = slot
        return slot

    def _get_var(self, name):
        slot = self.var_index.get(name)
        is_str = name.endswith("$")
        if slot is None:
            return "" if is_str else 0.0  # unset variables read as 0 / ""
        addr = self._slot_addr(slot)
        if is_str:
            length = self.mem.load(addr + 9, 1)[0]
            return self.mem.load(addr + 16, length).decode("latin-1") if length else ""
        return struct.unpack("<d", self.mem.load(addr + 16, 8))[0]

    def _set_var(self, name, value):
        is_str = name.endswith("$")
        self._check_type(value, is_str)
        slot = self.var_index.get(name)
        if slot is None:
            slot = self._new_slot(name, T_STR if is_str else T_NUM)
        addr = self._slot_addr(slot)
        if is_str:
            data = value.encode("latin-1", "replace")
            if len(data) > STR_MAX:
                raise BasicError(f"STRING TOO LONG (max {STR_MAX})")
            self.mem.store(addr + 9, bytes([len(data)]))
            self.mem.store(addr + 16, data)
        else:
            self.mem.store(addr + 16, struct.pack("<d", value))

    @staticmethod
    def _check_type(value, want_str):
        if isinstance(value, str) != want_str:
            raise BasicError("TYPE MISMATCH")

    # --- arrays ----------------------------------------------------------------
    def _dim(self, name, dims):
        key = name + "("
        if key in self.var_index:
            raise BasicError("REDIM'D ARRAY")
        if not 1 <= len(dims) <= 2 or any(d < 0 or d > 65534 for d in dims):
            raise BasicError("BAD SUBSCRIPT")
        is_str = name.endswith("$")
        elem = ARR_STR_MAX + 1 if is_str else 8
        count = 1
        for d in dims:
            count *= d + 1
        base = self.mem.load_u32(H_HEAP)
        if base + count * elem > HEAP_END:
            raise BasicError("OUT OF MEMORY")
        slot = self._new_slot(key, T_STRARR if is_str else T_NUMARR)
        d1, d2 = dims[0], (dims[1] if len(dims) > 1 else 0)
        self.mem.store(self._slot_addr(slot) + 16, struct.pack("<IHHB", base, d1, d2, len(dims)))
        self.mem.store_u32(H_HEAP, base + count * elem)
        if count * elem:
            self.mem.store(base, bytes(count * elem))  # arrays start zeroed

    def _element_addr(self, name, idx):
        key = name + "("
        if key not in self.var_index:
            self._dim(name, [10] * len(idx))  # classic BASIC: auto DIM 10
        base, d1, d2, ndims = struct.unpack(
            "<IHHB", self.mem.load(self._slot_addr(self.var_index[key]) + 16, 9))
        if len(idx) != ndims:
            raise BasicError("BAD SUBSCRIPT")
        i = idx[0]
        j = idx[1] if ndims == 2 else 0
        if not (0 <= i <= d1 and 0 <= j <= d2):
            raise BasicError("BAD SUBSCRIPT")
        elem = ARR_STR_MAX + 1 if name.endswith("$") else 8
        return base + (i * (d2 + 1) + j) * elem

    def _get_elem(self, name, idx):
        addr = self._element_addr(name, idx)
        if name.endswith("$"):
            length = self.mem.load(addr, 1)[0]
            return self.mem.load(addr + 1, length).decode("latin-1") if length else ""
        return struct.unpack("<d", self.mem.load(addr, 8))[0]

    def _set_elem(self, name, idx, value):
        is_str = name.endswith("$")
        self._check_type(value, is_str)
        addr = self._element_addr(name, idx)
        if is_str:
            data = value.encode("latin-1", "replace")
            if len(data) > ARR_STR_MAX:
                raise BasicError(f"STRING TOO LONG FOR ARRAY (max {ARR_STR_MAX})")
            self.mem.store(addr, bytes([len(data)]) + data)
        else:
            self.mem.store(addr, struct.pack("<d", value))

    # ============================================================= output ===
    def _out(self, text):
        print(text, end="", flush=True)
        if "\n" in text:
            self.col = len(text) - text.rfind("\n") - 1
        else:
            self.col += len(text)

    # ============================================================= tokens ===
    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else (None, None)

    def _at_op(self, op):
        return self._peek() == ("op", op)

    def _at_kw(self, kw):
        return self._peek() == ("kw", kw)

    def _at_end(self):
        kind, val = self._peek()
        return kind is None or kind == "rem" or (kind, val) in (("op", ":"), ("kw", "ELSE"))

    def _expect_op(self, op):
        if not self._at_op(op):
            raise BasicError("SYNTAX")
        self.pos += 1

    def _expect_kw(self, kw):
        if not self._at_kw(kw):
            raise BasicError("SYNTAX")
        self.pos += 1

    def _name(self):
        kind, val = self._peek()
        if kind != "name":
            raise BasicError("SYNTAX")
        self.pos += 1
        return val

    # ======================================================== expressions ===
    # Precedence, loosest first: OR, AND, NOT, comparison, + -, * / MOD,
    # unary minus, ^. Each level parses the next-tighter level for its operands.
    # True is -1 and false is 0, as in Microsoft BASIC.

    def _expr(self):
        left = self._and()
        while self._at_kw("OR"):
            self.pos += 1
            left = float(self._int(left) | self._int(self._and()))
        return left

    def _and(self):
        left = self._not()
        while self._at_kw("AND"):
            self.pos += 1
            left = float(self._int(left) & self._int(self._not()))
        return left

    def _not(self):
        if self._at_kw("NOT"):
            self.pos += 1
            return float(~self._int(self._not()))
        return self._compare()

    def _compare(self):
        left = self._add()
        kind, op = self._peek()
        if kind == "op" and op in ("=", "<>", "<", ">", "<=", ">="):
            self.pos += 1
            right = self._add()
            if isinstance(left, str) != isinstance(right, str):
                raise BasicError("TYPE MISMATCH")
            result = {"=": left == right, "<>": left != right, "<": left < right,
                      ">": left > right, "<=": left <= right, ">=": left >= right}[op]
            return -1.0 if result else 0.0
        return left

    def _add(self):
        left = self._mul()
        while self._at_op("+") or self._at_op("-"):
            op = self.toks[self.pos][1]
            self.pos += 1
            right = self._mul()
            if isinstance(left, str) or isinstance(right, str):
                if op == "-" or not (isinstance(left, str) and isinstance(right, str)):
                    raise BasicError("TYPE MISMATCH")
                left = left + right
            else:
                left = left + right if op == "+" else left - right
        return left

    def _mul(self):
        left = self._unary()
        while self._at_op("*") or self._at_op("/") or self._at_kw("MOD"):
            op = self.toks[self.pos][1]
            self.pos += 1
            right = self._unary()
            a, b = self._num(left), self._num(right)
            if op == "*":
                left = a * b
            elif b == 0:
                raise BasicError("DIVISION BY ZERO")
            elif op == "/":
                left = a / b
            else:
                left = float(math.fmod(a, b))
        return left

    def _unary(self):
        if self._at_op("-"):
            self.pos += 1
            return -self._num(self._unary())
        if self._at_op("+"):
            self.pos += 1
            return self._num(self._unary())
        return self._power()

    def _power(self):
        base = self._atom()
        if self._at_op("^"):
            self.pos += 1
            exponent = self._num(self._unary())
            try:
                result = self._num(base) ** exponent
            except (OverflowError, ZeroDivisionError):
                raise BasicError("OVERFLOW")
            if isinstance(result, complex):
                raise BasicError("ILLEGAL QUANTITY")
            return float(result)
        return base

    def _atom(self):
        kind, val = self._peek()
        if kind == "num" or kind == "str":
            self.pos += 1
            return val
        if self._at_op("("):
            self.pos += 1
            value = self._expr()
            self._expect_op(")")
            return value
        if kind == "name":
            self.pos += 1
            if val in FUNCTIONS and self._at_op("("):
                return self._call(val, self._args())
            if val in SYSVARS:
                return SYSVARS[val](self)
            if self._at_op("("):
                return self._get_elem(val, self._indices())
            return self._get_var(val)
        raise BasicError("SYNTAX")

    def _args(self):
        self._expect_op("(")
        args = [self._expr()]
        while self._at_op(","):
            self.pos += 1
            args.append(self._expr())
        self._expect_op(")")
        return args

    def _indices(self):
        return [self._int(a) for a in self._args()]

    @staticmethod
    def _num(value):
        if isinstance(value, str):
            raise BasicError("TYPE MISMATCH")
        return value

    def _int(self, value):
        value = self._num(value)
        if not -2**31 <= value < 2**31:
            raise BasicError("ILLEGAL QUANTITY")
        return int(value)

    def _call(self, name, args):
        spec = FUNCTIONS[name]
        if not spec[0] <= len(args) <= spec[1]:
            raise BasicError("SYNTAX")
        try:
            return spec[2](self, *args)
        except (ValueError, OverflowError):
            raise BasicError("ILLEGAL QUANTITY")

    # ============================================================ runner ===
    def _find_line(self, number):
        for i in range(self.prog_len):
            if self.code[i][0] == number:
                return i
        raise BasicError(f"UNDEF'D STATEMENT {number}")

    def _goto(self, number):
        self.idx = self._find_line(int(number))
        self.pos = 0
        self.jumped = True

    def _next_line(self):
        if self.idx >= self.prog_len - 1:
            self.idx = None  # end of program (or of a direct command)
        else:
            self.idx += 1
        self.pos = 0
        self.jumped = True

    def _execute(self, direct=None):
        """
        Generator that runs a direct command, or the program from the start.
        The (idx, pos) pair is BASIC's program counter.
        """
        self.code = [(n, self.tokens[n]) for n in sorted(self.lines)]
        self.prog_len = len(self.code)
        if direct is not None:
            self.code.append((None, direct))
            self.idx = self.prog_len  # direct line sits after the program
        else:
            self._clear_variables()
            self.idx = 0 if self.prog_len else None
        self.pos = 0
        self.request = None
        self.cur_line = None
        count = 0
        try:
            while self.idx is not None:
                self._statement()
                count += 1
                self.mem.store_u32(H_STMTS, self.mem.load_u32(H_STMTS) + 1)
                if self.request is not None:
                    req, self.request = self.request, None
                    if isinstance(req, _Input):
                        yield from self._do_input(req)
                    elif isinstance(req, _Wait):
                        while req.pid in self.kernel.proc_manager.processes:
                            yield Sleep(0.05)
                    elif req is _YIELD:
                        yield
                    else:
                        yield req
                elif count % QUANTUM == 0:
                    yield  # time slice used up: let other processes run
        except BasicError as e:
            self._error(str(e))
        except PageFault:
            self._error("PAGE FAULT")  # touched memory this process doesn't have
        except OutOfMemory:
            self._error("OUT OF MEMORY")
        except RecursionError:
            self._error("FORMULA TOO COMPLEX")
        finally:
            self._set_u16(H_LINE, NO_LINE)

    def _error(self, message):
        if self.col:
            self._out("\n")
        where = f" IN {self.cur_line}" if self.cur_line is not None else ""
        self._out(f"?{message} ERROR{where}\n")

    def _statement(self):
        """Executes one statement at the program counter."""
        number, self.toks = self.code[self.idx]
        while self._at_op(":"):
            self.pos += 1
        if self.pos >= len(self.toks):
            self._next_line()
            return
        self.cur_line = number
        self._set_u16(H_LINE, NO_LINE if number is None else number)
        self.jumped = False
        kind, val = self._peek()
        if kind == "rem" or (kind, val) == ("kw", "ELSE"):
            self._next_line()  # comment, or the ELSE part of a true IF
            return
        if kind == "kw":
            handler = STATEMENTS.get(val)
            if handler is None:
                raise BasicError("SYNTAX")
            self.pos += 1
            handler(self)
        elif kind == "name":
            self._st_let()
        else:
            raise BasicError("SYNTAX")
        if self.jumped or self.idx is None:
            return
        kind, val = self._peek()
        if kind is None or kind == "rem" or (kind, val) == ("kw", "ELSE"):
            self._next_line()
        elif (kind, val) == ("op", ":"):
            self.pos += 1
        else:
            raise BasicError("SYNTAX")

    # ======================================================== statements ===
    def _lvalue(self):
        """Parses a variable or array element; returns (name, indices or None)."""
        name = self._name()
        if name in FUNCTIONS or name in SYSVARS:
            raise BasicError(f"{name} IS RESERVED")
        return name, (self._indices() if self._at_op("(") else None)

    def _assign(self, target, value):
        name, idx = target
        if idx is None:
            self._set_var(name, value)
        else:
            self._set_elem(name, idx, value)

    def _st_let(self):
        target = self._lvalue()
        self._expect_op("=")
        self._assign(target, self._expr())

    def _st_print(self):
        newline = True
        while not self._at_end():
            if self._at_op(";"):
                self.pos += 1
                newline = False
            elif self._at_op(","):
                self.pos += 1
                self._out(" " * (ZONE - self.col % ZONE))
                newline = False
            else:
                self._out(fmt(self._expr()))
                newline = True
        if newline:
            self._out("\n")

    def _st_input(self):
        prompt = "? "
        if self._peek()[0] == "str":
            text = self._peek()[1]
            self.pos += 1
            if self._at_op(";"):
                prompt = text + "? "
            elif self._at_op(","):
                prompt = text
            else:
                raise BasicError("SYNTAX")
            self.pos += 1
        targets = [self._lvalue()]
        while self._at_op(","):
            self.pos += 1
            targets.append(self._lvalue())
        self.request = _Input(prompt, targets)

    def _do_input(self, req):
        while True:
            self.col = 0
            line = yield ReadLine(req.prompt)
            parts = line.split(",") if len(req.targets) > 1 else [line]
            if len(parts) < len(req.targets):
                self._out("?REDO FROM START\n")
                continue
            try:
                values = [p if name.endswith("$") else float(p.strip())
                          for (name, _), p in zip(req.targets, parts)]
            except ValueError:
                self._out("?REDO FROM START\n")
                continue
            for target, value in zip(req.targets, values):
                self._assign(target, value)
            return

    def _st_if(self):
        cond = self._num(self._expr())
        if self._at_kw("THEN"):
            self.pos += 1
        elif not self._at_kw("GOTO"):
            raise BasicError("SYNTAX")
        if cond:
            if self._peek()[0] == "num":
                self._goto(self._peek()[1])
            else:
                self.jumped = True  # carry on with the statements after THEN
            return
        for k in range(self.pos, len(self.toks)):
            if self.toks[k] == ("kw", "ELSE"):
                self.pos = k + 1
                if self._peek()[0] == "num":
                    self._goto(self._peek()[1])
                else:
                    self.jumped = True
                return
        self._next_line()

    def _st_goto(self):
        kind, val = self._peek()
        if kind != "num":
            raise BasicError("SYNTAX")
        self._goto(val)

    def _st_gosub(self):
        kind, val = self._peek()
        if kind != "num":
            raise BasicError("SYNTAX")
        self.pos += 1
        if len(self.gosub_stack) >= 64:
            raise BasicError("OUT OF MEMORY (GOSUB NESTING)")
        self.gosub_stack.append((self.idx, self.pos))
        self._goto(val)

    def _st_return(self):
        if not self.gosub_stack:
            raise BasicError("RETURN WITHOUT GOSUB")
        self.idx, self.pos = self.gosub_stack.pop()
        self.jumped = True

    def _st_for(self):
        name = self._name()
        if name.endswith("$"):
            raise BasicError("TYPE MISMATCH")
        self._expect_op("=")
        start = self._num(self._expr())
        self._expect_kw("TO")
        end = self._num(self._expr())
        step = 1.0
        if self._at_kw("STEP"):
            self.pos += 1
            step = self._num(self._expr())
        self._set_var(name, start)
        self.for_stack = [f for f in self.for_stack if f[0] != name]
        if (step >= 0 and start > end) or (step < 0 and start < end):
            self._skip_loop()  # the loop runs zero times
            return
        self.for_stack.append((name, end, step, self.idx, self.pos))

    def _skip_loop(self):
        """Moves the program counter past the NEXT that matches this FOR."""
        depth = 0
        idx, pos = self.idx, self.pos
        while idx is not None and idx < len(self.code):
            toks = self.code[idx][1]
            while pos < len(toks):
                tok = toks[pos]
                pos += 1
                if tok == ("kw", "FOR"):
                    depth += 1
                elif tok == ("kw", "NEXT"):
                    if depth == 0:
                        # skip the variable names after NEXT
                        while pos < len(toks) and (toks[pos][0] == "name" or toks[pos] == ("op", ",")):
                            pos += 1
                        self.idx, self.pos, self.jumped = idx, pos, True
                        return
                    depth -= 1
            idx = idx + 1 if idx < self.prog_len - 1 else None
            pos = 0
        raise BasicError("FOR WITHOUT NEXT")

    def _st_next(self):
        names = []
        if self._peek()[0] == "name":
            names.append(self._name())
            while self._at_op(","):
                self.pos += 1
                names.append(self._name())
        for name in names or [None]:
            while self.for_stack and name is not None and self.for_stack[-1][0] != name:
                self.for_stack.pop()  # leaving inner loops, like real BASIC
            if not self.for_stack:
                raise BasicError("NEXT WITHOUT FOR")
            var, end, step, idx, pos = self.for_stack[-1]
            value = self._get_var(var) + step
            self._set_var(var, value)
            if (step >= 0 and value <= end) or (step < 0 and value >= end):
                self.idx, self.pos, self.jumped = idx, pos, True
                return
            self.for_stack.pop()

    def _st_end(self):
        self.idx = None

    def _st_stop(self):
        self._out(f"BREAK IN {self.cur_line}\n" if self.cur_line is not None else "BREAK\n")
        self.idx = None

    def _st_dim(self):
        while True:
            name = self._name()
            self._dim(name, self._indices())
            if not self._at_op(","):
                return
            self.pos += 1

    def _st_poke(self):
        addr = self._int(self._expr())
        self._expect_op(",")
        value = self._int(self._expr())
        if not 0 <= value <= 255:
            raise BasicError("ILLEGAL QUANTITY")
        self.mem.store(addr, bytes([value]))

    def _st_sleep(self):
        seconds = self._num(self._expr())
        if seconds < 0:
            raise BasicError("ILLEGAL QUANTITY")
        self.request = Sleep(seconds)

    def _st_cls(self):
        if os.name == "nt":
            os.system("cls")
        else:
            print("\033[2J\033[H", end="", flush=True)
        self.col = 0

    def _st_randomize(self):
        random.seed()

    # --- aPE system statements ----------------------------------------------------
    def _st_kill(self):
        pid = self._int(self._expr())
        if not self.kernel.proc_manager.terminate(pid, "killed by BASIC"):
            raise BasicError(f"NO PROCESS {pid}")
        if pid == self.pid:
            self.idx = None  # killed ourselves: the kernel ends us after this step

    def _st_wait(self):
        pid = self._int(self._expr())
        if pid == self.pid:
            raise BasicError("CAN'T WAIT FOR MYSELF")
        self.request = _Wait(pid)

    def _st_yield(self):
        self.request = _YIELD

    def _st_out(self):
        """OUT port, value: write a byte (or a whole register) to a device's I/O port."""
        port = self._int(self._expr())
        self._expect_op(",")
        value = self._int(self._expr())
        if not 0 <= port <= 0xFFFF or value < 0:
            raise BasicError("ILLEGAL QUANTITY")
        mb = self.kernel.motherboard
        if mb is not None:
            mb.io_write(port, value)

    def _st_shell(self):
        command = _str_arg(self._expr()).strip()
        info = _command_info(self, command)
        if info is None:
            raise BasicError(f"UNKNOWN COMMAND: {command.split()[0] if command else ''}")
        if info.get("category") == "app":
            raise BasicError("USE SPAWN TO START PROGRAMS")
        if self.col:
            self._out("\n")
        self.kernel.io_manager.handle_input(command)
        self.col = 0

    # --- commands --------------------------------------------------------------
    def _st_run(self):
        self._clear_variables()
        if self._peek()[0] == "num":
            self._goto(self._peek()[1])
        elif self.prog_len:
            self.idx, self.pos, self.jumped = 0, 0, True
        else:
            self.idx = None

    def _st_list(self):
        lo, hi = 0, 65535
        if self._peek()[0] == "num":
            lo = hi = int(self._peek()[1])
            self.pos += 1
            if self._at_op("-"):
                self.pos += 1
                hi = int(self._peek()[1]) if self._peek()[0] == "num" else 65535
                if self._peek()[0] == "num":
                    self.pos += 1
        for line in self._program_text().splitlines():  # read back from RAM
            if lo <= int(line.split(" ", 1)[0]) <= hi:
                self._out(line + "\n")

    def _st_new(self):
        self.lines, self.tokens = {}, {}
        self._sync_program()
        self._clear_variables()
        self.code = self.code[self.prog_len:]
        self.prog_len = 0
        self.idx = None

    def _filename_arg(self):
        kind, val = self._peek()
        if kind != "str" or not val:
            raise BasicError('SYNTAX (use SAVE "NAME")')
        self.pos += 1
        return val if "." in os.path.basename(val) else val + ".bas"

    def _st_save(self):
        filename = self._filename_arg()
        result = self.kernel.fs_manager.write_file(filename, self._program_text())
        if result:
            raise BasicError(result)
        self._out(f"SAVED {filename}\n")

    def _st_load(self):
        if self.cur_line is not None:
            raise BasicError("ILLEGAL IN PROGRAM")
        filename = self._load(self._filename_arg())
        self._clear_variables()
        self._out(f"LOADED {filename} ({len(self.lines)} LINES)\n")
        self.idx = None

    def _st_bye(self):
        self.quit = True
        self.idx = None

    # ============================================================== main ===
    def run(self):
        self._init_memory()
        if self.filename:  # script mode: basic game.bas
            try:
                self._load(self.filename)
            except BasicError as e:
                self._error(str(e))
                return
            yield from self._execute()
            return

        free = self.kernel.mem_manager.usage()[0] * self.kernel.mem_manager.ps
        print("\n    **** aPE-BASIC 1.0 ****")
        print(f" {free:,} BYTES OF aPE-RAM FREE  (PID {self.pid})")
        print(" Commands: RUN LIST NEW SAVE \"F\" LOAD \"F\" BYE\n")
        print("READY.")
        while not self.quit:
            self.col = 0
            line = (yield ReadLine("")).strip()
            if not line:
                continue
            m = re.match(r"(\d+)\s?(.*)$", line)
            try:
                if m:  # a numbered line edits the program
                    self._edit_line(int(m.group(1)), m.group(2))
                    continue
                toks = tokenize(line)
            except BasicError as e:
                self._error(str(e))
                continue
            self.cur_line = None
            yield from self._execute(direct=toks)
            if not self.quit:
                if self.col:
                    self._out("\n")
                print("READY.")


def _str_arg(value):
    if not isinstance(value, str):
        raise BasicError("TYPE MISMATCH")
    return value


def _left(self, x, n):
    return _str_arg(x)[:max(0, self._int(n))]


def _right(self, x, n):
    n = max(0, self._int(n))
    return _str_arg(x)[len(x) - n:] if n else ""


def _mid(self, x, start, length=None):
    x, start = _str_arg(x), self._int(start)
    if start < 1:
        raise ValueError
    end = None if length is None else start - 1 + max(0, self._int(length))
    return x[start - 1:end]


def _val(self, x):
    m = re.match(r"\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", _str_arg(x))
    return float(m.group()) if m else 0.0


def _chr(self, x):
    code = self._int(x)
    if not 0 <= code <= 255:
        raise ValueError
    return chr(code)


def _asc(self, x):
    if not _str_arg(x):
        raise ValueError
    return float(ord(x[0]))


def _peek_fn(self, addr):
    return float(self.mem.load(self._int(addr), 1)[0])


def _hex(self, x):
    value = self._int(x)
    if value < 0:
        raise ValueError
    return f"{value:X}"


# --- aPE system functions ---------------------------------------------------------
def _pcb_of(self, pid):
    pid = self._int(pid)
    for _, pcb in self.kernel.mem_manager.all_pcbs():
        if pcb["used"] and pcb["pid"] == pid:
            return pcb
    return None


def _pcb_field(field, missing):
    def fn(self, pid):
        pcb = _pcb_of(self, pid)
        if pcb is None:
            return missing
        value = pcb[field]
        return value if isinstance(value, str) else float(value)
    return fn


def _pslot(self, slot):
    slot = self._int(slot)
    if not 0 <= slot < self.kernel.mem_manager.layout.max_procs:
        raise ValueError
    pcb = self.kernel.mem_manager.read_pcb(slot)
    return float(pcb["pid"]) if pcb["used"] else 0.0


def _frame(self, vaddr):
    paddr = self.mem.physical(self._int(vaddr))
    return -1.0 if paddr is None else float(paddr // self.kernel.mem_manager.ps)


def _phys(self, vaddr):
    paddr = self.mem.physical(self._int(vaddr))
    return -1.0 if paddr is None else float(paddr)


def _command_info(self, command):
    parts = command.split()
    if not parts:
        return None
    io = self.kernel.io_manager
    name = io.aliases.get(parts[0].lower(), parts[0].lower())
    return io.commands.get(name)


def _spawn(self, command):
    """Starts an aPEOSI program in the background. Returns its PID."""
    command = _str_arg(command).strip()
    info = _command_info(self, command)
    if info is None or info.get("category") != "app":
        raise BasicError(f"NOT A PROGRAM: {command.split()[0] if command else ''}")
    if info.get("allow_bg", "").lower() != "true":
        raise BasicError(f"{info['command'].upper()} CAN'T RUN IN THE BACKGROUND")
    if self.col:
        self._out("\n")
    io = self.kernel.io_manager
    process = sys_cmd_exec._launch_app(info, command.split()[1:], self.kernel, io, True)
    self.col = 0
    if process is None:
        raise BasicError("SPAWN FAILED")
    return float(process.pid)


def _board(self):
    return self.kernel.board


def _inp(self, port):
    """INP(port): read a device's I/O port. Empty ports read &HFF, as on a real bus."""
    port = self._int(port)
    if not 0 <= port <= 0xFFFF:
        raise ValueError
    mb = self.kernel.motherboard
    return float(mb.io_read(port) if mb is not None else 0xFF)


def _iobase(self, socket_id):
    """IOBASE("bus0"): the first I/O port of a socket's device, or -1."""
    mb = self.kernel.motherboard
    sock = mb.by_id.get(_str_arg(socket_id).lower()) if mb is not None else None
    return -1.0 if sock is None or sock.io_base is None or not sock.present else float(sock.io_base)


def _irqcount(self, socket_id):
    """IRQCOUNT("bus0"): interrupts delivered from a socket's device so far."""
    mb = self.kernel.motherboard
    sock = mb.by_id.get(_str_arg(socket_id).lower()) if mb is not None else None
    return 0.0 if sock is None or sock.irq is None else float(mb.irq_counts[sock.irq])


# Names that read like variables but ask the system for a value.
SYSVARS = {
    "RND": lambda s: random.random(),
    "TIMER": lambda s: round(time.monotonic() - s.started, 2),
    "PID": lambda s: float(s.pid),
    "TICK": lambda s: float(s.kernel.mem_manager.ram.read_u32(OFF_TICK)),
    "NPROC": lambda s: float(sum(1 for _, p in s.kernel.mem_manager.all_pcbs() if p["used"])),
    "FREEMEM": lambda s: float(s.kernel.mem_manager.usage()[0] * s.kernel.mem_manager.ps),
    "RAMSIZE": lambda s: float(_board(s).ram.size),
    "PAGESIZE": lambda s: float(_board(s).ram.page_size),
    "CPUHZ": lambda s: float(_board(s).cpu.clock_hz),
    "CPU$": lambda s: _board(s).cpu.name,
    "RAM$": lambda s: _board(s).ram.name,
    "BOARD$": lambda s: _board(s).name,
}


# name: (min args, max args, function(interpreter, *args))
FUNCTIONS = {
    "ABS": (1, 1, lambda s, x: abs(s._num(x))),
    "INT": (1, 1, lambda s, x: float(math.floor(s._num(x)))),
    "SGN": (1, 1, lambda s, x: float((s._num(x) > 0) - (s._num(x) < 0))),
    "SQR": (1, 1, lambda s, x: math.sqrt(s._num(x))),
    "SIN": (1, 1, lambda s, x: math.sin(s._num(x))),
    "COS": (1, 1, lambda s, x: math.cos(s._num(x))),
    "TAN": (1, 1, lambda s, x: math.tan(s._num(x))),
    "ATN": (1, 1, lambda s, x: math.atan(s._num(x))),
    "EXP": (1, 1, lambda s, x: math.exp(s._num(x))),
    "LOG": (1, 1, lambda s, x: math.log(s._num(x))),
    "RND": (0, 1, lambda s, *x: random.random()),
    "LEN": (1, 1, lambda s, x: float(len(_str_arg(x)))),
    "LEFT$": (2, 2, _left),
    "RIGHT$": (2, 2, _right),
    "MID$": (2, 3, _mid),
    "STR$": (1, 1, lambda s, x: fmt(s._num(x))),
    "VAL": (1, 1, _val),
    "CHR$": (1, 1, _chr),
    "ASC": (1, 1, _asc),
    "PEEK": (1, 1, _peek_fn),
    "HEX$": (1, 1, _hex),
    # aPE system functions
    "PSLOT": (1, 1, _pslot),
    "PSTATE": (1, 1, _pcb_field("state", 0.0)),
    "PNAME$": (1, 1, _pcb_field("name", "")),
    "PRUNS": (1, 1, _pcb_field("sched_count", 0.0)),
    "PPAGES": (1, 1, _pcb_field("pages_mapped", 0.0)),
    "FRAME": (1, 1, _frame),
    "PHYS": (1, 1, _phys),
    "SPAWN": (1, 1, _spawn),
    # devices
    "INP": (1, 1, _inp),
    "IOBASE": (1, 1, _iobase),
    "IRQCOUNT": (1, 1, _irqcount),
}

STATEMENTS = {
    "LET": Basic._st_let, "PRINT": Basic._st_print, "INPUT": Basic._st_input,
    "IF": Basic._st_if, "GOTO": Basic._st_goto, "GOSUB": Basic._st_gosub,
    "RETURN": Basic._st_return, "FOR": Basic._st_for, "NEXT": Basic._st_next,
    "END": Basic._st_end, "STOP": Basic._st_stop, "DIM": Basic._st_dim,
    "POKE": Basic._st_poke, "SLEEP": Basic._st_sleep, "CLS": Basic._st_cls,
    "RANDOMIZE": Basic._st_randomize, "RUN": Basic._st_run, "LIST": Basic._st_list,
    "NEW": Basic._st_new, "SAVE": Basic._st_save, "LOAD": Basic._st_load,
    "BYE": Basic._st_bye, "EXIT": Basic._st_bye,
    "KILL": Basic._st_kill, "WAIT": Basic._st_wait, "YIELD": Basic._st_yield,
    "SHELL": Basic._st_shell, "OUT": Basic._st_out,
}
