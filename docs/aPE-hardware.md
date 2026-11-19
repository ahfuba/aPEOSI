# aPE hardware file formats

Every piece of simulated hardware in aPEOSI is a binary file. All of them
share one **common device header**, followed by a header for that **device
class**. A tool can read the first 32 bytes of any aPE device file and know
what it is.

The class code says which **socket** a device plugs into ([aPE Socket spec](aPE-Socket.md));
what the device does is its **function**, stored in its descriptor.

| Extension | Socket / medium | Class code | Lifetime | Status |
|---|---|---|---|---|
| `.apecpu` | CPU socket | `CPU\0` | volatile | spec: Stage 6 |
| `.aperam` | memory slot (SODIMM) | `RAM\0` | volatile | implemented |
| `.apemb` | the motherboard: socket table, interrupt controller | `MB\0\0` | volatile | implemented |
| `.apebus` | on-board system bus (timer, UART, ...) | `BUS\0` | volatile | implemented |
| `.apepci` | PCI expansion slot (GPU, sound, disk controller cards) | `PCI\0` | volatile | implemented, no cards yet |
| `.apeser` | serial port (byte-stream devices) | `SER\0` | volatile | implemented |
| `.apeusb` | USB port | `USB\0` | volatile | spec only |
| `.apedisk` | storage medium | `DISK` | **persistent** | reserved |
| `.apenet` | network medium (cable or "air") | `NET\0` | volatile | reserved |

The extension is always `.ape` + the class code in lowercase. Naming rules,
including module vs instance files, are in [`NAMING.md`](../NAMING.md).

All numbers are little-endian. Code: `devices/internal/A/apeos/system2/sys/apedev.py`.

## Common device header (32 bytes)

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 4 | magic | `41 50 45 1A` = `"APE"` + `0x1A` |
| 4 | 4 | device class | see table above |
| 8 | 2 | format version | version of the class-specific layout (or of the descriptor) |
| 10 | 2 | header size | where the device's own data starts, in bytes |
| 12 | 4 | device size | size of the whole instance, in bytes |
| 16 | 2 | flags | bit 0 `MODULE`: a compiled description, not a running device; bit 1 `PERSISTENT`: holds data, never recreated (disks) |
| 18 | 14 | device name | the model name, ASCII, zero-padded |

## Device descriptors

New device classes describe themselves. Right after the common header comes a
**descriptor**: a list of chunks saying what the device's parameters, regions
and registers are. aPE-DevKit writes descriptors ([guide](aPE-DevKit.md));
aPEOSI and the tools read them (`sys/apedesc.py`). RAM predates descriptors
and keeps its own fixed header (below).

```
0             common header (32 bytes)
32            descriptor chunks
header_size   data area: the regions (instances only; modules stop after the descriptor)
```

Each chunk is `tag (4 bytes)`, `length (u32)`, the payload, then padding to
4 bytes. Readers skip tags they don't know, so the format can grow.

| Tag | Payload |
|---|---|
| `INFO` | model (string), description (string), device version (u16), function (string) |
| `PARM` | count (u16), then per parameter: name (string), type (u8: 0 int, 1 float, 2 string, 3 bool), value (i64 / f64 / string / u8) |
| `RGNS` | count (u16), then per region: name, offset (u32), size (u32), kind (u8), access (u8), description |
| `REGS` | count (u16), then per register: name, region index (u16), offset (u32), width in bits (u8), access (u8), reset (u32), description, field count (u8), then per field: name, lsb (u8), width (u8), description |
| `INIT` | count (u16), then per block: region index (u16), offset (u32), length (u32), bytes |
| `END\0` | empty: end of the descriptor |

Strings are a u16 length followed by UTF-8. Region kinds: 0 data, 1 registers,
2 vram, 3 buffer, 4 rom, 5 state. Access bits: 1 read, 2 write, 4 execute.
Offsets of regions are relative to the data area; offsets of registers are
relative to their region. The data area starts on a 64-byte boundary.

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

## Socket files

How each socket uses its file. Behaviour and protocols are in the
[aPE Socket spec](aPE-Socket.md).

### `.apemb`: the motherboard (`board0.apemb`)

Built at boot from `board.json`. Its descriptor has three regions:

- `ic`: the interrupt controller: `IRQ_LINES` (u16, current level of every line) and `IRQ_MASK` (u16, 1 = disabled)
- `irq_counts`: interrupts delivered per IRQ line (16 × u32)
- `sockets`: the socket table, 32 bytes per socket: id (8), class code (4), I/O base (u16),
  I/O size (u16), IRQ (u8, `0xFF` = none), present (u8), model (14)

### `.apebus`, `.apepci`: register sockets (`bus0.apebus`, `pci0.apepci`)

A descriptor followed by the device's data area: its registers and buffers,
reachable from the OS through the device's I/O window. Implemented devices:
**aPE-T1 Timer** and **aPE-U1 UART** on the system bus. Planned cards:

- **aPE-G1 GPU**: VRAM (the framebuffer) plus display registers; aPE-Display draws it at `refresh_hz`.
  **aPE-G2** adds shader cores, each with its own registers and program counter in its own region.
- **aPE-S1 sound**: control registers plus a sample buffer the OS refills before it runs dry.
- **aPE-N1 network card**: send and receive buffers, its address and link state, using an `.apenet` medium.

### `.apeser`: serial devices (`com1.apeser`)

A descriptor plus the device's own registers. Serial devices have no I/O
window: they exchange bytes with the UART that drives their port.
Implemented: **aPE-E1 Echo**, a loopback plug.

### `.apeusb`: USB devices (spec only)

USB devices will plug into the ports of a USB host-controller card. Planned
first device: **aPE-K1**, a USB keyboard.

### `.apecpu`: CPU (Stage 6)

The CPU's state once aPEOSI has a virtual CPU: general registers, program
counter, flags, privilege bit, interrupt state, the cycle counter, and the
cache as its own region.

## Media files

### `.apedisk`: storage (reserved)

A whole disk in one file: a superblock, a file table (FAT or inodes) and data
blocks. Unlike device files, a disk is **persistent**:

- deleting the file deletes the data on it; copying the file is a complete backup
- aPEOSI never creates or overwrites a disk file at boot; a separate format tool makes new disks
- disk files are git-ignored, because they hold personal data

### `.apenet`: network (reserved)

A shared medium, e.g. `air0.apenet`. Two aPEOSI computers whose network cards
point at the same medium file can exchange packets. The medium can add noise,
drop packets and produce collisions, so retransmission and collision handling
can be observed.

## Adding a class

Pick a class code of up to 4 letters for the new socket or medium, register its
extension in `apedev.py`, and describe its protocol in the [socket spec](aPE-Socket.md). Naming rules are in [`NAMING.md`](../NAMING.md).
