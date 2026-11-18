"""
Memory manager: decides what lives where in aPE-RAM.

It plays three roles that real hardware/kernels split up:

* Frame allocator: hands out free physical frames and takes them back,
  using the frame table stored in RAM.
* Process table keeper: reads/writes the 32-byte PCBs stored in RAM.
* MMU: translates a process's *virtual* address into a *physical* address
  through that process's page table (also stored in RAM).

The rule of aPEOSI 1.2: if the OS needs to remember something about memory
or processes, it is stored in aPE-RAM, so the Watchdog can see it.
"""

import struct
import time

from . import aperam
from .aperam import (FT_FREE, FT_KERNEL, FT_PAGETABLE, FT_USER, KERNEL_PID,
                     PCB_FMT, PCB_SIZE, VPAGES, Layout, ft_decode, ft_entry)
from .time_mgr import DELAY


class PageFault(Exception):
    """A process touched a virtual address that is not mapped."""


class OutOfMemory(Exception):
    """No free physical frames (or process slots) are left."""


class MemoryManager:
    def __init__(self, ram: aperam.PhysicalRAM, page_size, num_pages):
        self.ram = ram
        self.layout = Layout(page_size, num_pages)
        self.ps = page_size

    # ------------------------------------------------------------ boot ---
    def write_header(self, os_version, ram_name):
        """Writes the header first, so tools know the layout even during POST."""
        header = aperam.pack_header(self.layout, KERNEL_PID, 0, 0, int(time.time()),
                                    os_version, ram_name)
        self.ram.fill(0, self.ps, 0)
        self.ram.write(0, header)

    def power_on_self_test(self, total_ms=800):
        """
        Like a BIOS memory test: writes a pattern to every frame (except the
        header), reads it back, then clears it. Watch it sweep in the Watchdog.
        Returns the number of bytes tested.
        """
        delay = total_ms / self.layout.num_pages
        pattern = bytes([0xAA, 0x55]) * (self.ps // 2)
        for frame in range(1, self.layout.num_pages):
            addr = frame * self.ps
            self.ram.write(addr, pattern)
            if self.ram.read(addr, self.ps) != pattern:
                raise RuntimeError(f"Memory test failed at frame {frame}")
            self.ram.fill(addr, self.ps, 0)
            DELAY(delay)
        return (self.layout.num_pages - 1) * self.ps

    def format(self):
        """Builds empty kernel tables: frame table, process table, keyboard buffer."""
        lay = self.layout
        for frame in range(1, lay.num_pages):
            self.ram.fill(frame * self.ps, self.ps, 0)
        table = bytearray(lay.num_pages)
        for frame in range(lay.first_user_frame):
            table[frame] = ft_entry(FT_KERNEL)
        self.ram.write(lay.frame_table_page * self.ps, bytes(table))

    # ------------------------------------------------- header helpers ---
    def set_current_pid(self, pid):
        self.ram.write_u16(aperam.OFF_CURRENT_PID, pid)

    def tick(self):
        """Advances the system clock tick stored in the header. Returns it."""
        t = (self.ram.read_u32(aperam.OFF_TICK) + 1) & 0xFFFFFFFF
        self.ram.write_u32(aperam.OFF_TICK, t)
        return t

    def keyboard(self, line):
        """Copies a typed line into the keyboard buffer frame."""
        data = line.encode("utf-8", "replace")[: self.ps - 2]
        addr = self.layout.kbd_page * self.ps
        self.ram.fill(addr, self.ps, 0)
        self.ram.write_u16(addr, len(data))
        self.ram.write(addr + 2, data)

    # ------------------------------------------------ frame allocator ---
    def frame_table(self):
        return self.ram.read(self.layout.frame_table_page * self.ps, self.layout.num_pages)

    def _set_frame_entry(self, frame, entry):
        self.ram.write_u8(self.layout.frame_table_page * self.ps + frame, entry)

    def alloc_frame(self, frame_type, slot):
        table = self.frame_table()
        for frame in range(self.layout.first_user_frame, self.layout.num_pages):
            if ft_decode(table[frame])[0] == FT_FREE:
                self._set_frame_entry(frame, ft_entry(frame_type, slot))
                self.ram.fill(frame * self.ps, self.ps, 0)  # never leak old data
                return frame
        raise OutOfMemory("out of memory: no free frames")

    def free_frame(self, frame):
        self.ram.fill(frame * self.ps, self.ps, 0)  # scrub before reuse
        self._set_frame_entry(frame, ft_entry(FT_FREE))

    # -------------------------------------------------- process table ---
    def read_pcb(self, slot):
        return aperam.parse_pcb(self.ram.read(self.layout.pcb_addr(slot), PCB_SIZE), 0)

    def all_pcbs(self):
        return [(slot, self.read_pcb(slot)) for slot in range(self.layout.max_procs)]

    def _write_pcb(self, slot, pcb):
        data = struct.pack(PCB_FMT, pcb["used"], pcb["state"], pcb["pid"], pcb["pt_frame"],
                           pcb["pages_mapped"], pcb["sched_count"], pcb["last_tick"],
                           pcb["name"].encode("ascii", "replace")[:16])
        self.ram.write(self.layout.pcb_addr(slot), data)

    def update_pcb(self, slot, **fields):
        pcb = self.read_pcb(slot)
        pcb.update(fields)
        self._write_pcb(slot, pcb)

    def create_process_entry(self, pid, name, state):
        """Finds a free PCB slot and gives it an empty address space. Returns the slot."""
        for slot in range(self.layout.max_procs):
            if not self.read_pcb(slot)["used"]:
                break
        else:
            raise OutOfMemory(f"process table full ({self.layout.max_procs} processes)")
        pt_frame = self.alloc_frame(FT_PAGETABLE, slot)
        self._write_pcb(slot, {"used": 1, "state": state, "pid": pid, "pt_frame": pt_frame,
                               "pages_mapped": 0, "sched_count": 0, "last_tick": 0, "name": name})
        return slot

    def destroy_process_entry(self, slot):
        """Frees every frame the process owned and clears its PCB."""
        table = self.frame_table()
        for frame in range(self.layout.first_user_frame, self.layout.num_pages):
            ftype, owner = ft_decode(table[frame])
            if ftype in (FT_USER, FT_PAGETABLE) and owner == slot:
                self.free_frame(frame)
        self.ram.fill(self.layout.pcb_addr(slot), PCB_SIZE, 0)

    # ------------------------------------------------------------- MMU ---
    def translate(self, slot, vaddr, write=False):
        """
        Virtual -> physical address translation.

            vaddr = [ virtual page | offset ]
            page table[virtual page] -> physical frame
            paddr = frame * page_size + offset

        Writing to an unmapped page triggers *demand paging*: the kernel
        allocates a fresh zeroed frame on the spot. Reading an unmapped page
        is a page fault (like a segmentation fault).
        """
        vpage, offset = divmod(vaddr, self.ps)
        if vaddr < 0 or vpage >= VPAGES:
            raise PageFault(f"virtual address 0x{vaddr:X} is outside the address space")
        pcb = self.read_pcb(slot)
        entry_addr = pcb["pt_frame"] * self.ps + vpage
        frame = self.ram.read_u8(entry_addr)
        if frame == 0:
            if not write:
                raise PageFault(f"page fault: read from unmapped address 0x{vaddr:X}")
            frame = self.alloc_frame(FT_USER, slot)
            self.ram.write_u8(entry_addr, frame)
            self.update_pcb(slot, pages_mapped=pcb["pages_mapped"] + 1)
        return frame * self.ps + offset

    def load(self, slot, vaddr, n):
        out = bytearray()
        while n > 0:
            chunk = min(n, self.ps - vaddr % self.ps)  # stay inside one page
            out += self.ram.read(self.translate(slot, vaddr), chunk)
            vaddr += chunk
            n -= chunk
        return bytes(out)

    def store(self, slot, vaddr, data):
        data = bytes(data)
        while data:
            chunk = min(len(data), self.ps - vaddr % self.ps)
            self.ram.write(self.translate(slot, vaddr, write=True), data[:chunk])
            vaddr += chunk
            data = data[chunk:]

    # ----------------------------------------------------------- stats ---
    def usage(self):
        """Counts frames by type. Returns a dict."""
        counts = {FT_FREE: 0, FT_KERNEL: 0, FT_PAGETABLE: 0, FT_USER: 0}
        for entry in self.frame_table():
            counts[ft_decode(entry)[0]] = counts.get(ft_decode(entry)[0], 0) + 1
        return counts


class AddressSpace:
    """
    What an application sees: its own private memory, addressed from 0.
    Apps get one of these as ``self.mem``.
    """

    def __init__(self, mm: MemoryManager, slot):
        self._mm = mm
        self._slot = slot

    def load(self, vaddr, n):
        return self._mm.load(self._slot, vaddr, n)

    def store(self, vaddr, data):
        self._mm.store(self._slot, vaddr, data)

    def physical(self, vaddr):
        """The physical address behind vaddr, or None if it is not mapped."""
        try:
            return self._mm.translate(self._slot, vaddr)
        except PageFault:
            return None

    def load_u32(self, vaddr):
        return struct.unpack("<I", self.load(vaddr, 4))[0]

    def store_u32(self, vaddr, value):
        self.store(vaddr, struct.pack("<I", value & 0xFFFFFFFF))
