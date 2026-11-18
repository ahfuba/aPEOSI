"""
aPE-RAM: the simulated physical memory of aPEOSI.

The RAM is a plain file (``*.aperam``) that is memory-mapped with ``mmap``.
Memory-mapping makes the operating system share the same physical pages
between every program that maps the file, so when aPEOSI writes a byte,
the aPE-Watchdog (a completely separate program) sees that byte change
immediately. This is real shared memory, not a copy.

This module only knows the *format* of the RAM: where things are and how to
read/write raw bytes. It does NOT decide what goes where; that is the job of
the memory manager (mem_mgr.py). Keep this file free of aPEOSI imports so the
Watchdog can use it on its own.

Physical layout (P = page size, N = number of pages, both from the RAM module):

    frame 0                 header: common aPE device header (apedev.py),
                            then layout, tick, write counter, ...
    frame 1                 frame table: 1 byte per physical frame
    frame 2 .. 2+k-1        process table: 16 PCBs of 32 bytes each
    next frame              keyboard buffer: last line typed into aPEOSI
    first_user_frame .. N-1 free frames, handed out to processes

Everything is little-endian.
"""

import mmap
import os
import struct

from .apedev import CLASS_RAM, COMMON_SIZE, pack_common, parse_common

FORMAT_VERSION = 1

# ---------------------------------------------------------------- header ---
# Frame 0 starts with the common 32-byte aPE device header (see apedev.py),
# followed by the RAM-specific header:
#   page_size, num_pages, frame_table_page, proc_table_page, proc_table_pages,
#   kbd_page, first_user_frame, max_procs, current_pid,
#   tick, write_seq, boot_time, os_version
RAM_FMT = "<9H3I16s"
HEADER_SIZE = COMMON_SIZE + struct.calcsize(RAM_FMT)  # 78 bytes

OFF_CURRENT_PID = COMMON_SIZE + 2 * 8      # 48
OFF_TICK = OFF_CURRENT_PID + 2             # 50
OFF_WRITE_SEQ = OFF_TICK + 4               # 54

KERNEL_PID = 0xFFFF  # value of current_pid while the kernel/shell is running

# ----------------------------------------------------------- frame table ---
# One byte per frame:  high nibble = frame type, low nibble = owner PCB slot.
FT_FREE = 0
FT_KERNEL = 1
FT_PAGETABLE = 2
FT_USER = 3

FT_NAMES = {FT_FREE: "free", FT_KERNEL: "kernel", FT_PAGETABLE: "page table", FT_USER: "user"}


def ft_entry(frame_type, slot=0):
    return ((frame_type & 0xF) << 4) | (slot & 0xF)


def ft_decode(entry):
    """Returns (frame_type, owner_slot)."""
    return entry >> 4, entry & 0xF


# --------------------------------------------------------- process table ---
MAX_PROCS = 16  # limited by the 4-bit owner field in the frame table

# used, state, pid, pt_frame, pages_mapped, sched_count, last_tick, name
PCB_FMT = "<BBHHHII16s"
PCB_SIZE = struct.calcsize(PCB_FMT)  # 32 bytes

STATE_NAMES = {0: "FREE", 1: "RUNNING", 2: "WAIT_INPUT", 3: "TERMINATED", 4: "SLEEPING"}

# ---------------------------------------------------------- page tables ---
# Each process owns one page-table frame. Entry i (1 byte) holds the physical
# frame number that virtual page i maps to; 0 means "not mapped" (frame 0 is
# the header and can never be given to a process).
VPAGES = 256


class Layout:
    """Where everything lives, computed from the RAM module's geometry."""

    def __init__(self, page_size, num_pages):
        if page_size < 256 or page_size & (page_size - 1):
            raise ValueError("page_size must be a power of two and at least 256")
        if not 16 <= num_pages <= 256:
            raise ValueError("num_pages must be between 16 and 256")
        self.page_size = page_size
        self.num_pages = num_pages
        self.size = page_size * num_pages
        self.frame_table_page = 1
        self.proc_table_page = 2
        self.proc_table_pages = -(-MAX_PROCS * PCB_SIZE // page_size)  # ceil
        self.kbd_page = self.proc_table_page + self.proc_table_pages
        self.first_user_frame = self.kbd_page + 1
        self.max_procs = MAX_PROCS
        if self.first_user_frame + 4 > num_pages:
            raise ValueError("RAM too small: not enough frames left for processes")

    @classmethod
    def from_header(cls, header):
        return cls(header["page_size"], header["num_pages"])

    def kernel_frame_role(self, frame):
        """Human-readable name of a kernel frame (for tools like the Watchdog)."""
        if frame == 0:
            return "header"
        if frame == self.frame_table_page:
            return "frame table"
        if self.proc_table_page <= frame < self.proc_table_page + self.proc_table_pages:
            return "process table"
        if frame == self.kbd_page:
            return "keyboard buffer"
        return "kernel"

    def pcb_addr(self, slot):
        return self.proc_table_page * self.page_size + slot * PCB_SIZE


def pack_header(layout, current_pid, tick, write_seq, boot_time, os_version, ram_name):
    common = pack_common(CLASS_RAM, FORMAT_VERSION, HEADER_SIZE, layout.size, ram_name)
    ram = struct.pack(RAM_FMT, layout.page_size, layout.num_pages, layout.frame_table_page,
                      layout.proc_table_page, layout.proc_table_pages, layout.kbd_page,
                      layout.first_user_frame, layout.max_procs, current_pid,
                      tick, write_seq, boot_time, os_version.encode("ascii", "replace")[:16])
    return common + ram


def parse_header(buf):
    """Parses an .aperam header from any bytes-like object. Returns None if invalid."""
    common = parse_common(buf)
    if common is None or common["device_class"] != CLASS_RAM or len(buf) < HEADER_SIZE:
        return None
    names = ("page_size", "num_pages", "frame_table_page", "proc_table_page",
             "proc_table_pages", "kbd_page", "first_user_frame", "max_procs", "current_pid",
             "tick", "write_seq", "boot_time", "os_version")
    header = dict(zip(names, struct.unpack_from(RAM_FMT, buf, COMMON_SIZE)))
    header["os_version"] = header["os_version"].rstrip(b"\x00").decode("ascii", "replace")
    header["ram_name"] = common["name"]
    header["format_version"] = common["format_version"]
    return header


def parse_pcb(buf, offset):
    used, state, pid, pt_frame, pages, sched, last_tick, name = struct.unpack_from(PCB_FMT, buf, offset)
    return {
        "used": used, "state": state, "pid": pid, "pt_frame": pt_frame,
        "pages_mapped": pages, "sched_count": sched, "last_tick": last_tick,
        "name": name.rstrip(b"\x00").decode("ascii", "replace"),
    }


class PhysicalRAM:
    """
    The RAM chip: a memory-mapped .aperam file with byte-level read/write.

    Every write bumps the ``write_seq`` counter in the header, so observers
    can tell that something changed.
    """

    def __init__(self, path, size):
        self.path = path
        self.size = size
        self._file = None
        self._mm = None
        self._attach()

    def _attach(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path) or os.path.getsize(self.path) != self.size:
            # Build a fresh zero-filled file next to the old one, then swap it in.
            # Swapping (instead of resizing in place) keeps a running Watchdog
            # safe: it keeps reading the old file until it notices the new one.
            tmp = self.path + ".new"
            with open(tmp, "wb") as f:
                f.write(b"\x00" * self.size)
            try:
                os.replace(tmp, self.path)
            except PermissionError:
                os.remove(tmp)
                raise RuntimeError(
                    f"Cannot resize {self.path}: it is in use. "
                    "Close the aPE-Watchdog and boot again.")
        self._file = open(self.path, "r+b")
        self._mm = mmap.mmap(self._file.fileno(), self.size, access=mmap.ACCESS_WRITE)

    def close(self):
        if self._mm is not None:
            self._mm.flush()
            self._mm.close()
            self._mm = None
        if self._file is not None:
            self._file.close()
            self._file = None

    # --- raw access -------------------------------------------------------
    def _check(self, addr, n):
        if addr < 0 or addr + n > self.size:
            raise IndexError(f"physical address 0x{addr:05X} (+{n}) is outside RAM")

    def read(self, addr, n):
        self._check(addr, n)
        return self._mm[addr:addr + n]

    def write(self, addr, data):
        self._check(addr, len(data))
        self._mm[addr:addr + len(data)] = data
        seq = struct.unpack_from("<I", self._mm, OFF_WRITE_SEQ)[0]
        struct.pack_into("<I", self._mm, OFF_WRITE_SEQ, (seq + 1) & 0xFFFFFFFF)

    def fill(self, addr, n, value=0):
        self.write(addr, bytes([value]) * n)

    def read_u8(self, addr):
        return self.read(addr, 1)[0]

    def write_u8(self, addr, value):
        self.write(addr, bytes([value & 0xFF]))

    def read_u16(self, addr):
        return struct.unpack("<H", self.read(addr, 2))[0]

    def write_u16(self, addr, value):
        self.write(addr, struct.pack("<H", value & 0xFFFF))

    def read_u32(self, addr):
        return struct.unpack("<I", self.read(addr, 4))[0]

    def write_u32(self, addr, value):
        self.write(addr, struct.pack("<I", value & 0xFFFFFFFF))
