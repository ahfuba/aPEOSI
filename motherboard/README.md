# /motherboard: aPEOSI's hardware

This folder is the computer that aPEOSI boots on. Every part is a small JSON
file, so you can swap parts or make your own.

```
motherboard/
├── board.json          which parts are plugged in
├── cpu/                CPU modules
│   ├── ape-p1.json         200 Hz, the default
│   └── ape-p0-turtle.json  4 Hz, slow enough to follow every context switch
├── bus/                on-board devices (timer, UART)
├── serial/             serial-port devices (echo plug)
├── ram/                RAM modules (SODIMMs)
│   ├── ape-r16k.json       64 frames x 256 B, the default (easy to watch)
│   ├── ape-r64k.json       256 frames x 256 B
│   └── ape-r256k.json      256 frames x 1 KiB
├── ram0.aperam         the RAM itself, created at boot (not committed)
└── bus0.apebus, ...    every plugged-in device, created at boot (not committed)
```

## Sockets

Besides the CPU and RAM, the board has **sockets** that devices plug into: the
on-board system bus (`bus`), expansion slots (`pci`), serial ports (`ser`) and
USB ports (`usb`, not built yet). They are listed in `board.json`:

```json
"sockets": [
  { "id": "bus0", "type": "bus", "device": "bus/ape-t1-timer.py" },
  { "id": "bus1", "type": "bus", "device": "bus/ape-u1-uart.py" },
  { "id": "pci0", "type": "pci", "device": null },
  { "id": "com1", "type": "ser", "device": "serial/ape-e1-echo.py", "controller": "bus1" }
]
```

| Device | File | Socket |
|---|---|---|
| aPE-T1 Timer | `bus/ape-t1-timer.py` | system bus |
| aPE-U1 UART | `bus/ape-u1-uart.py` | system bus (drives a serial port) |
| aPE-E1 Echo | `serial/ape-e1-echo.py` | serial port |

At boot every device gets its own live file next to the RAM: `bus0.apebus`,
`bus1.apebus`, `com1.apeser`, and `board0.apemb` for the board itself. The
socket rules and how to write your own device are in the
[aPE Socket spec](../docs/aPE-Socket.md).

## Swapping parts

Edit `board.json`:

```json
{
  "name": "aPE-B1 Classic",
  "cpu": "cpu/ape-p0-turtle.json",
  "ram": "ram/ape-r64k.json",
  "ram_file": "ram0.aperam"
}
```

Or keep several boards side by side and pick one at boot:

```bash
python main.py --board my_board.json
```

```bash
python ape_watchdog.py --board my_board.json
```

Give each board its own `ram_file` if you want to run two at once.

## Making your own parts

### CPU module

```json
{
  "type": "cpu",
  "name": "My CPU",
  "clock_hz": 50,
  "description": "anything you like"
}
```

| field | meaning | allowed |
|---|---|---|
| `clock_hz` | scheduler rounds per second: how often every ready process gets a step | 1 – 100000 |

### RAM module

```json
{
  "type": "ram",
  "name": "My RAM",
  "page_size": 512,
  "num_pages": 128,
  "description": "anything you like"
}
```

| field | meaning | allowed |
|---|---|---|
| `name` | shown in `sysinfo` and the Watchdog | up to 14 characters |
| `page_size` | bytes per page/frame | power of two, at least 256 |
| `num_pages` | number of physical frames | 16 – 256 |

Size = `page_size × num_pages`. The limits come from the format: page-table
entries and frame numbers are 1 byte each, so there are at most 256 frames.
The first few frames always go to the kernel (header, frame table, process
table, keyboard buffer).

Modules can also be **compiled** with [aPE-DevKit](../docs/aPE-DevKit.md)
(`python ape_devkit.py build ram/my-ram.json` → `ape-r32k.aperam`), and
`board.json` can point to the compiled file instead of the JSON.

aPEOSI checks every file at boot ("BIOS") and tells you exactly what is wrong
if a part is invalid.

The file formats are described in [`docs/aPE-hardware.md`](../docs/aPE-hardware.md).
