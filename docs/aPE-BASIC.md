# aPE-BASIC

A small line-numbered BASIC for aPEOSI, in the style of 1980s home computers.
Code: `devices/internal/A/apeos/system2/sysApp/basic/basic.py`.
Examples: `A:/basic/` (`hello.bas`, `guess.bas`, `primes.bas`, `bits.bas`).

```
basic                    open the BASIC prompt
basic basic/guess.bas    run a program file, then return to aPEOSI
basic loop.bas &         run it in the background
```

At the prompt, a line that starts with a number is stored in the program
(typing just the number deletes that line). Anything else runs immediately.

```
10 PRINT "HELLO"
20 GOTO 10
RUN
```

Ctrl+C ends the BASIC process (it is aPEOSI's "kill the foreground app").

## Commands

| Command | Does |
|---|---|
| `RUN [line]` | clear variables and run, from the start or from `line` |
| `LIST [a[-b]]` | show the program (read back from aPE-RAM) |
| `NEW` | erase the program and variables |
| `SAVE "name"` | save to the current aPEOSI directory (`.bas` added if missing) |
| `LOAD "name"` | load a program |
| `BYE` / `EXIT` | leave BASIC |

## Statements

Several statements can share a line, separated by `:`.

| Statement | Example |
|---|---|
| `LET` (optional) | `LET A = 5` &nbsp; `B$ = "HI"` |
| `PRINT` | `PRINT "X="; X` (`;` joins, `,` jumps to the next 14-column zone, a trailing `;` stays on the line) |
| `INPUT` | `INPUT "NAME"; N$` &nbsp; `INPUT A, B` |
| `IF … THEN … ELSE` | `IF X > 3 THEN PRINT "BIG" ELSE PRINT "SMALL"` &nbsp; `IF X THEN 100` |
| `GOTO` / `GOSUB` / `RETURN` | `GOSUB 500` … `500 PRINT "SUB" : RETURN` |
| `FOR … NEXT` | `FOR I = 10 TO 0 STEP -2 : PRINT I : NEXT I` |
| `DIM` | `DIM A(100), M(15, 15), N$(10)` (1 or 2 dimensions; indexes start at 0) |
| `POKE` | `POKE &H8000, 255` (write one byte of this process's memory) |
| `SLEEP` | `SLEEP 0.5` (seconds; other processes run meanwhile) |
| `CLS` | clear the screen |
| `RANDOMIZE` | reseed `RND` |
| `END` / `STOP` | end the program (`STOP` prints where) |
| `REM` or `'` | comment |

## Values and operators

* Numbers are 64-bit floats. `&HFF` is hexadecimal.
* Variables ending in `$` hold strings (up to 112 characters; array
  elements up to 39). Names are up to 8 characters. Unset variables are
  `0` or `""`.
* Arithmetic: `+ - * / ^ MOD`. Strings join with `+`.
* Comparisons: `= <> < > <= >=`. True is `-1`, false is `0`.
* Logic (bitwise on whole numbers): `AND OR NOT`.

## Functions

| Numbers | Strings | System |
|---|---|---|
| `ABS INT SGN SQR` | `LEN(s$)` | `PEEK(addr)` |
| `SIN COS TAN ATN` | `LEFT$(s$, n)` `RIGHT$(s$, n)` | `RND` / `RND(1)`: 0 ≤ x < 1 |
| `EXP LOG` | `MID$(s$, start[, len])` | `TIMER`: seconds since BASIC started |
| | `STR$(n)` `VAL(s$)` `CHR$(n)` `ASC(s$)` | |

## Errors

Errors look like the originals: `?SYNTAX ERROR IN 30`,
`?TYPE MISMATCH ERROR`, `?UNDEF'D STATEMENT 999 ERROR`,
`?BAD SUBSCRIPT ERROR`, `?OUT OF MEMORY ERROR`, and one that only aPEOSI
has: `?PAGE FAULT ERROR`, when you `PEEK` memory your process was never
given.

## BASIC and aPE-RAM

Everything BASIC keeps lives in its process's memory, at these virtual
addresses:

| Address | Contents |
|---|---|
| `&H0000` | header: `BAS1`, statements executed (u32), current line (u16), variable count, program length, array heap top |
| `&H0100` | variable table: 64 slots × 128 bytes (name, type, value) |
| `&H2100` | arrays |
| `&H4000` | the program, as text |
| `&H8000` | free for your own `POKE`s |

Open the aPE-RAM Watchdog while a program runs: the statement counter
ticks in the header page, and variables change in the variable table.
`POKE` into `&H8000` and a new page appears (demand paging); `bits.bas`
draws an animation there.

`POKE` can write anywhere in BASIC's own memory, including its variables and
program. That is how it worked on 1980s machines too, so poking the wrong
address can crash the program.

## Multitasking

The interpreter yields to aPEOSI after every 100 statements, after `SLEEP`,
and while waiting in `INPUT`. So a BASIC program can't freeze the system,
even `10 GOTO 10`. Run `basic loop.bas &` and the shell stays responsive.
How fast BASIC runs depends on the CPU module in `/motherboard`.
