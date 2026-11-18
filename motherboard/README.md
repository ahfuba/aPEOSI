# /motherboard: aPEOSI's hardware

This folder is the computer that aPEOSI boots on. Every part is a small JSON
file, so you can swap parts or make your own.

```
motherboard/
├── board.json          which parts are plugged in
├── cpu/                CPU modules
│   ├── ape-c1.json         200 Hz, the default
│   └── ape-c0-turtle.json  4 Hz, slow enough to follow every context switch
├── ram/                RAM modules (SODIMMs)
│   ├── ape-r16k.json       64 frames x 256 B, the default (easy to watch)
│   ├── ape-r64k.json       256 frames x 256 B
│   └── ape-r256k.json      256 frames x 1 KiB
└── ram0.aperam         the RAM itself, created at boot (not committed)
```

## Swapping parts

Edit `board.json`:

```json
{
  "name": "aPE-Board Classic",
  "cpu": "cpu/ape-c0-turtle.json",
  "ram": "ram/ape-r64k.json",
  "ram_file": "ram0.aperam"
}
```

Or keep several boards side by side and pick one at boot:

```bash
python main.py --board my_board.json
```

```bash
python aperam_watchdog.py --board my_board.json
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
| `name` | shown in `sysinfo` and the Watchdog | up to 16 characters |
| `page_size` | bytes per page/frame | power of two, at least 256 |
| `num_pages` | number of physical frames | 16 – 256 |

Size = `page_size × num_pages`. The limits come from the format: page-table
entries and frame numbers are 1 byte each, so there are at most 256 frames.
The first few frames always go to the kernel (header, frame table, process
table, keyboard buffer).

aPEOSI checks every file at boot ("BIOS") and tells you exactly what is wrong
if a part is invalid.

The file formats are described in [`docs/aPE-hardware.md`](../docs/aPE-hardware.md).
