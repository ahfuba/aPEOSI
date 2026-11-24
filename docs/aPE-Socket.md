# aPE Socket specification

The motherboard doesn't know what devices do. It offers **sockets**: standard
connectors with a fixed contract. Anything that follows a socket's contract
can be plugged into it, with any logic inside. This document is that
contract, for modders who build devices and for the OS that talks to them.

Code: `sys/board.py` (the motherboard), `sys/devlogic.py` (device logic),
`sys/apedesc.py` (descriptors). Devices are built with [aPE-DevKit](aPE-DevKit.md).

## 1. Sockets vs functions

Every device has two separate properties:

- **socket**: *how it connects*. It decides the file extension.
- **function**: *what it does*. It is stored inside the file.

A network card can sit in a PCI slot or on a USB port; a disk can be an
internal drive or a USB stick. Same function, different socket.

## 2. Socket types

| Socket | Code | Extension | Like on a real PC | Talks by | IRQ | Status |
|---|---|---|---|---|---|---|
| CPU socket | `CPU` | `.apecpu` | the CPU socket | instructions | (receives them) | spec: Stage 6 |
| Memory slot | `RAM` | `.aperam` | SODIMM / DIMM slot | plain reads and writes | no | ✅ |
| Motherboard | `MB` | `.apemb` | the board itself | (owns the others) | interrupt controller | ✅ |
| System bus | `BUS` | `.apebus` | on-board chips: timer, UART, interrupt controller | **registers** at I/O ports | yes | ✅ |
| Expansion slot | `PCI` | `.apepci` | PCI slots: GPU, sound and disk-controller cards | **registers** at I/O ports | yes | ✅ (no cards yet) |
| Serial port | `SER` | `.apeser` | RS-232 COM ports | a **byte stream** | through its controller | ✅ |
| USB port | `USB` | `.apeusb` | USB | **packets**, polled by the host | through its controller | spec only |

Media are not sockets: they are what a device *uses*.

| Medium | Code | Extension | Lifetime |
|---|---|---|---|
| Storage | `DISK` | `.apedisk` | **persistent**: the file is the data, never recreated automatically |
| Network | `NET` | `.apenet` | a shared cable or "air" between computers |

All device files are **volatile**: rebuilt at every boot. Only media persist.

## 3. Device files *are* the devices

When aPEOSI boots, each plugged-in device gets its own file in `motherboard/`,
named after its socket:

```
motherboard/board0.apemb    the motherboard: socket table, interrupt controller
motherboard/ram0.aperam     the RAM in memory slot 0
motherboard/bus0.apebus     the device in system-bus socket 0 (a timer)
motherboard/bus1.apebus     the device in system-bus socket 1 (a UART)
motherboard/com1.apeser     the device on serial port COM1 (an echo plug)
```

A device file is the device's **whole state**: its descriptor (what it is),
then its registers and memory (what it is doing right now). The file is
memory-mapped while aPEOSI runs, so every register change lands in the file
immediately. Watch one live:

```bash
python ape_devkit.py info --watch motherboard/bus0.apebus
```

Logic must keep its state in registers and regions, not in Python variables,
so that what the file shows is the truth.

## 4. The motherboard

`board.json` lists the sockets:

```json
"sockets": [
  { "id": "bus0", "type": "bus", "device": "bus/ape-t1-timer.py" },
  { "id": "bus1", "type": "bus", "device": "bus/ape-u1-uart.py" },
  { "id": "pci0", "type": "pci", "device": null },
  { "id": "com1", "type": "ser", "device": "serial/ape-e1-echo.py", "controller": "bus1" },
  { "id": "usb0", "type": "usb", "device": null }
]
```

- `id`: 2–5 lowercase letters + a number (`bus0`, `pci1`, `com1`). It also names the device file.
- `device`: a device source (`.py` with logic, or `.json`), a compiled module, or `null` for an empty socket.
- `controller` (serial ports): the `bus` or `pci` socket whose UART drives this port.

At boot the BIOS **enumerates** the sockets: it loads each device, checks it
fits its socket (a `BUS` device can't go in a `PCI` slot), gives it an I/O
window and an IRQ line, wires serial ports to their controllers, and prints
the result. `lsdev` shows the same table at any time.

### I/O address space

Register-based sockets (`BUS`, `PCI`) are reached through a 16-bit **I/O port
space**, separate from RAM, as on x86 PCs (BASIC's `INP` and `OUT`).

- Each device gets a **window** the size of its data area, rounded up to a
  power of two (at least 16 bytes), aligned to its size.
- System-bus windows start at `0x0000`; PCI windows start at `0x1000`.
- A port inside a window reaches the byte at that offset of the device's data area.
- Reading a port nothing answers returns `0xFF`, as a real floating bus does; writes to it are ignored.

### Register access

- **At a register's first port**, a read or write moves the **whole register**
  (8, 16 or 32 bits): `OUT T + 4, 1000` sets a 32-bit `LOAD` register to 1000.
- **At its other ports**, it moves a single byte of it.
- Reads and writes go through the device's logic (`read`/`write` hooks), so
  they can have side effects: reading a UART's `DATA` takes a byte out of its FIFO.
- Writes to read-only registers are ignored. Ports in `buffer`/`data` regions
  read and write raw memory (writes only if the region is writable).

### Interrupts

Each `BUS`/`PCI` device has one **level-triggered** IRQ line, numbered in
socket order (0–15). The interrupt controller lives in `board0.apemb`:

| Register | Meaning |
|---|---|
| `IRQ_LINES` | the current level of every line |
| `IRQ_MASK` | 1 = that line is disabled |
| region `irq_counts` | interrupts delivered, per line (u32) |

Level-triggered means the line stays high until the device lowers it,
usually when the OS acknowledges the event (for example by writing 1 to a
status bit). The kernel delivers each pending IRQ to the **driver** for the
device's function. If there is no driver, nobody will ever acknowledge it,
so the kernel **masks** the line and says so, as real kernels do.

### Clocks

A device with a `clock_hz` parameter gets `tick()` called that many times per
second of real time. If the host falls behind, at most 5000 ticks are caught
up per device per step. `clock_hz` 0 or missing means no clock.

## 5. Device logic: the hooks

A device source may define `LOGIC`, a subclass of `DeviceLogic`:

| Hook | Called when | Default |
|---|---|---|
| `reset()` | power-on | nothing |
| `read(name) → value` | the OS reads register `name` | the stored value |
| `write(name, value)` | the OS writes register `name` | store it, unless read-only |
| `tick()` | one tick of the device clock | nothing |
| `on_serial(byte)` | a byte arrives on this device's serial line | nothing |

Helpers available inside the logic:

| Helper | Does |
|---|---|
| `reg(name)`, `set(name, value)` | read/store a register (the device's own side: no access rules) |
| `field("CTRL.ENABLE")`, `set_field("STATUS.FIRED", 1)` | read/store a bit field |
| `param(name)` | a descriptor parameter |
| `region_read(name, offset, n)`, `region_write(name, offset, data)` | the device's memory |
| `irq(True / False)` | raise or lower the IRQ line |
| `serial_send(byte)` | send a byte down the serial line |

A device with no `LOGIC` is a set of plain registers. A device whose logic
raises an exception is marked **faulted** and stops; the OS keeps running.

## 6. Socket protocols

### System bus and PCI (register sockets)
Signals: `CLK` (tick), `RESET`, `READ(addr)`, `WRITE(addr, value)`, `IRQ`.
The device's descriptor is its **ID** at enumeration, like a PCI card's
configuration space. PCI and the system bus behave the same today; they
differ in where they sit (on-board chips vs cards) and where their windows
start. Planned for PCI: DMA (a card reading and writing RAM within limits the OS grants).

### Serial (byte-stream sockets)
Serial devices have **no addresses and no registers the OS can reach**: they
only see bytes, one at a time, through `on_serial()`, and answer with
`serial_send()`. The OS talks to them through a **UART** in a register socket,
which times every byte at its baud rate: 1 start bit + 8 data bits + 1 stop
bit = 10 bits, so at 9600 baud a byte takes about 1 ms, and at 300 baud about 33 ms.

### USB (specified, not built)
USB is different from both: the **host** controller polls every device on a
schedule; devices never speak first. A device has a **descriptor** (vendor,
product, class), **endpoints** (numbered channels), and transfer types:
*control* (setup), *interrupt* (small, regular: keyboards, mice), *bulk*
(large: storage) and *isochronous* (timed: audio). Devices can be plugged in
and out while running. A USB host controller will be a `PCI` card, and USB
devices will plug into its ports; a USB keyboard is the planned first device.

### Memory slot
No registers and no IRQ: the RAM module is plain memory, managed by the OS's
memory manager (`.aperam`, see [formats](aPE-hardware.md)). Its descriptor
plays the role of a real DIMM's SPD chip: the small ROM that tells the BIOS
the module's size and timings.

### CPU socket (Stage 6)
The CPU socket will hold the virtual CPU: registers, program counter and
flags in `cpu0.apecpu`, receiving the IRQ line from the interrupt controller.

## 7. Building a device for a socket

```bash
python ape_devkit.py new BUS "aPE-T9 MyTimer" --function TIMER
```

Edit the generated file (registers, then `LOGIC`), add it to a socket in
`board.json`, boot aPEOSI, and talk to it from BASIC:

```basic
10 T = IOBASE("bus2")
20 OUT T, 1
30 PRINT INP(T + 1)
```

Real devices to read first:

| Device | Socket | Shows |
|---|---|---|
| [`bus/ape-t1-timer.py`](../motherboard/bus/ape-t1-timer.py) | system bus | a clocked state machine, IRQs, write-1-to-clear |
| [`bus/ape-u1-uart.py`](../motherboard/bus/ape-u1-uart.py) | system bus | read side effects, a FIFO, baud timing, driving a serial port |
| [`serial/ape-e1-echo.py`](../motherboard/serial/ape-e1-echo.py) | serial port | a byte-stream device with no addresses |

**Safety:** a `.py` device runs as code inside aPEOSI, so it deserves the same
trust as any program: only trusted devices should be plugged in. JSON specs and
compiled modules have no logic and are safe.
