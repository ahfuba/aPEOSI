# aPE hardware file formats

Every piece of simulated hardware in aPEOSI is a binary file. All of them
share one **common device header**, followed by a header for that **device
class**. A tool can read the first 32 bytes of any aPE device file and know
what it is.

| Extension | Device class | Class code | Status |
|---|---|---|---|
| `.aperam` | RAM module (SODIMM) | `RAM\0` | implemented in 1.2 |
| `.apemb` | Motherboard / PCI configuration space | `MB\0\0` | reserved |
| `.apebus` | Bus devices (I/O ports, timers, keyboard controller, ...) | `BUS\0` | reserved |

All numbers are little-endian. Code: `devices/internal/A/apeos/system2/sys/apedev.py`.

## Common device header (32 bytes)

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 4 | magic | `41 50 45 1A` = `"APE"` + `0x1A` |
| 4 | 4 | device class | see table above |
| 8 | 2 | format version | version of the class-specific layout |
| 10 | 2 | header size | common + class header, in bytes |
| 12 | 4 | device size | size of the whole file, in bytes |
| 16 | 16 | device name | ASCII, zero-padded |

## `.aperam`: RAM

Code: `sys/aperam.py` (format), `sys/mem_mgr.py` (who puts what where).

The file is the whole RAM: `page_size × num_pages` bytes, split into frames.
aPEOSI memory-maps it read/write; the Watchdog maps it read-only.

### Physical layout

| Frame | Contents |
|---|---|
| 0 | header (below) |
| 1 | frame table |
| 2 … | process table (16 PCBs × 32 bytes; 2 frames with 256-byte pages) |
| next | keyboard buffer |
| first_user_frame … N−1 | free frames, given to processes on demand |

### RAM header (frame 0, after the common header)

| Offset | Size | Field |
|---|---|---|
| 32 | 2 | page_size |
| 34 | 2 | num_pages |
| 36 | 2 | frame_table_page |
| 38 | 2 | proc_table_page |
| 40 | 2 | proc_table_pages |
| 42 | 2 | kbd_page |
| 44 | 2 | first_user_frame |
| 46 | 2 | max_procs (16) |
| 48 | 2 | current_pid: PID on the CPU right now, `0xFFFF` = kernel |
| 50 | 4 | tick: +1 every time the scheduler runs a process |
| 54 | 4 | write_seq: +1 on every write to RAM |
| 58 | 4 | boot_time (Unix seconds) |
| 62 | 16 | os_version |

### Frame table

One byte per physical frame: `type << 4 | owner_slot`.

| type | meaning |
|---|---|
| 0 | free |
| 1 | kernel |
| 2 | page table (owner = PCB slot) |
| 3 | user data page (owner = PCB slot) |

### Process Control Block (32 bytes each)

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | used (0/1) |
| 1 | 1 | state: 1 RUNNING, 2 WAIT_INPUT, 3 TERMINATED, 4 SLEEPING |
| 2 | 2 | pid |
| 4 | 2 | pt_frame: physical frame of this process's page table |
| 6 | 2 | pages_mapped |
| 8 | 4 | sched_count: how many times it has been scheduled |
| 12 | 4 | last_tick |
| 16 | 16 | name |

### Page table

Each process has one page-table frame. Entry *i* (1 byte) is the physical
frame that virtual page *i* maps to; `0` = not mapped.

```
virtual address = virtual page × page_size + offset
physical address = page_table[virtual page] × page_size + offset
```

Writing to an unmapped page allocates a zeroed frame (demand paging).
Reading one is a page fault and the process is terminated.

### Keyboard buffer

`u16 length` followed by the last line typed into aPEOSI (UTF-8).

## `.apemb`: motherboard / PCI (reserved)

Planned: a PCI-style configuration space. One 256-byte config block per slot
(vendor ID, device ID, class code, base address registers), so the kernel can
*enumerate* the hardware at boot like a real BIOS does, instead of reading
`board.json` directly. Class code `MB\0\0`.

## `.apebus`: bus devices (reserved)

Planned: memory-mapped I/O devices (keyboard controller, timer, text screen)
sitting on a bus. Each device exposes a few registers; writing a register
makes the device do something, and devices can raise interrupts. Class code
`BUS\0`.

To add a new class, pick a 4-byte class code, write the class header after
the common header, and register the extension in `apedev.py`.
