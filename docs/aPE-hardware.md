# aPE hardware file formats

Every piece of simulated hardware in aPEOSI is a binary file. All of them
share one **common device header**, followed by a header for that **device
class**. A tool can read the first 32 bytes of any aPE device file and know
what it is.

| Extension | Device class | Class code | Lifetime | Status |
|---|---|---|---|---|
| `.aperam` | RAM module (SODIMM) | `RAM\0` | volatile | implemented in 1.2 |
| `.apemb` | Motherboard: the device list | `MB\0\0` | rebuilt at boot | reserved |
| `.apebus` | Bus devices (keyboard controller, sound chip, timers, ...) | `BUS\0` | volatile | reserved |
| `.apegpu` | GPU: VRAM, display registers, later shader cores | `GPU\0` | volatile | reserved |
| `.apecpu` | CPU: registers, flags, cycle counter, cache | `CPU\0` | volatile | reserved |
| `.apedisk` | Disk: persistent file storage | `DISK` | **persistent** | reserved |
| `.apenet` | Network card, or a shared network medium | `NET\0` | volatile | reserved |

The extension is always `.ape` + the class code in lowercase. Naming rules,
including module vs instance files, are in [`NAMING.md`](../NAMING.md).

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

## Reserved classes

These formats are planned; their exact layouts are designed when the first
software that uses them is built.

### `.apemb`: motherboard (reserved)

The device list the OS reads at boot to discover its hardware: which GPU,
bus devices, disks and network cards are plugged in, and which file each one
lives in. It plays the role of PCI enumeration, without the full PCI detail.
The motherboard *lists* devices; each device keeps its own state in its own file.

### `.apebus`: bus devices (reserved)

A container for small memory-mapped I/O devices. Each device on the bus gets
its own region of registers (and buffers), plus a way to raise interrupts:

- **aPE-K1 keyboard controller**: key codes and a "key waiting" flag, for reading keys without Enter
- **aPE-S1 sound chip**: control registers plus a sample buffer the OS must refill before it runs dry

### `.apegpu`: GPU (reserved)

- **aPE-G1**: VRAM (the framebuffer) plus display registers. aPE-Display draws it at the GPU's `refresh_hz`.
- **aPE-G2**: adds shader cores. Each core has its own registers and program
  counter in its own region and runs aPE-VM bytecode on its own pixel, so the
  Watchdog can show every core working.

### `.apecpu`: CPU (reserved)

The CPU's state once aPEOSI has a virtual CPU: general registers, program
counter, flags, privilege bit, interrupt state, the cycle counter, and the
cache as its own region.

### `.apedisk`: disk (reserved)

A whole disk in one file: a superblock, a file table (FAT or inodes) and data
blocks. Unlike every other device file, a disk is **persistent**:

- deleting the file deletes the data on it; copying the file is a complete backup
- aPEOSI never creates or overwrites a disk file at boot; a separate format tool makes new disks
- disk files are git-ignored, because they hold personal data

### `.apenet`: network (reserved)

- **`net0.apenet`**: a network card (aPE-N1): send and receive buffers, its address and link state.
- **`air0.apenet`**: a shared medium. Two aPEOSI computers whose cards point at the same
  medium file can exchange packets. The medium can add noise, drop packets and
  produce collisions, so retransmission and collision handling can be observed.

## Adding a class

Pick a class code of up to 4 letters, write the class header after the common
header, and register the extension in `apedev.py`. Naming rules are in [`NAMING.md`](../NAMING.md).
