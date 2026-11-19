# aPEOSI naming scheme

One format for everything in the aPEOSI ecosystem. Use it for new modules,
programs and files, including mods.

## 1. The brand

- **aPEOSI** (ahfuba's Python Emulated Operating System Interface) is the one name
  for the project and the OS. Not "aPEOS", not "aPEOS-I".
- **aPE** is always written with a lowercase **a**. It is the creator's nickname, stylized on purpose.
  - in prose and display names: `aPE`
  - in file names and code: `ape`
  - in binary headers: `APE`

## 2. Products and tools: `aPE-<Name>`

| Kind | Names |
|---|---|
| Languages | aPE-BASIC, aPE-C |
| Bytecode virtual machine | aPE-VM |
| Simulated RAM | aPE-RAM |
| Host-side tools | aPE-Watchdog, aPE-Display |

Host-side tools are Python programs at the repo root named `ape_<tool>.py`:
`ape_watchdog.py`, `ape_display.py`.

## 3. Hardware models: `aPE-<letter><model>`

The letter says the device's **function** (what it does), so model names never
collide with each other or with product names.

| Letter | Function | Examples | Plugs into |
|---|---|---|---|
| **B** | motherboard | aPE-B1 Classic | (it *is* the board) |
| **P** | processor | aPE-P1, aPE-P0 Turtle | CPU socket |
| **R** | RAM | aPE-R16K, aPE-R64K, aPE-R256K | memory slot |
| **T** | timer | aPE-T1 Timer | system bus |
| **U** | UART (serial port controller) | aPE-U1 UART | system bus or PCI |
| **G** | GPU | aPE-G1, aPE-G2 | PCI |
| **S** | sound | aPE-S1 | PCI, or the system bus |
| **K** | keyboard | aPE-K1 | USB, or a serial port |
| **D** | disk | aPE-D1 | PCI (a controller) or USB |
| **N** | network card | aPE-N1 | PCI or USB |
| **E** | echo / loopback plug | aPE-E1 Echo | serial port |
| **L** | front panel (example) | aPE-L1 Panel | system bus |

- The model is a number, or a size for RAM (`16K`). An optional nickname can follow: `aPE-P0 Turtle`.
- A model name is at most **14 characters** (it is stored in every device file's header).
- Device source files are the model name in lowercase with hyphens, in the folder of their socket:
  `aPE-T1 Timer` → `motherboard/bus/ape-t1-timer.py`.
- A new function picks an unused letter. A modded timer could be `aPE-T7 Rocket`.

## 4. Device files: the extension says the socket

A device file's extension names **the socket it plugs into**; what the device
does is its *function*, stored inside the file. (Full spec: [aPE Socket](docs/aPE-Socket.md).)

| Code | Extension | Socket | Example instance |
|---|---|---|---|
| `CPU` | `.apecpu` | CPU socket | `cpu0.apecpu` |
| `RAM` | `.aperam` | memory slot (SODIMM) | `ram0.aperam` |
| `MB` | `.apemb` | the motherboard itself | `board0.apemb` |
| `BUS` | `.apebus` | on-board system bus | `bus0.apebus` (a timer), `bus1.apebus` (a UART) |
| `PCI` | `.apepci` | expansion slot | `pci0.apepci` (a GPU card) |
| `SER` | `.apeser` | serial port | `com1.apeser` (an echo plug) |
| `USB` | `.apeusb` | USB port | `usb0.apeusb` |

Media are not sockets but what devices use:

| Code | Extension | Medium | Example |
|---|---|---|---|
| `DISK` | `.apedisk` | storage | `disk0.apedisk` |
| `NET` | `.apenet` | network cable or "air" | `air0.apenet` |

Rules:

- **Instance files are named after their socket:** `<socket id>.<extension>`, e.g. `bus0.apebus`.
- **Compiled modules are named after their model:** `ape-t1-timer.apebus`. Same extension, told apart by name.
- **Device files are volatile:** rebuilt at every boot, safe to delete.
- **Media are persistent:** a `.apedisk` file *is* the data. Deleting it deletes the data, copying it
  is a complete backup, and aPEOSI never creates or overwrites one on its own.
- **The extension = `.ape` + the code in lowercase.** A new socket type needs a code of up to
  4 letters, its extension, and an entry in `apedev.py`.

All device and media files are git-ignored: device files because they are rebuilt at boot,
compiled modules because they are build outputs (commit the `.py` or `.json` source),
disks because they hold personal data.

## 5. Program and file types

| Kind | Extension |
|---|---|
| aPE-BASIC source | `.bas` |
| aPE-C source | `.c` |
| aPE assembly | `.aps` |
| aPE executable (bytecode or machine code) | `.apx` |

Standard languages keep their usual extensions. Formats that are aPE's own use `.ap*`.

## 6. Inside aPEOSI

| Thing | Rule | Examples |
|---|---|---|
| Shell commands | short lowercase words; aliases allowed | `basic`, `banana`, `ps` (alias of `list_tasks`) |
| App display names | plain words | Banana Editor, aPE-BASIC |
| OS subsystems (Python) | `<name>_mgr.py` | `mem_mgr.py`, `process_mgr.py` |
| Hardware formats (Python) | `ape<class>.py` | `apedev.py`, `aperam.py` |
| Python code | PEP 8: `snake_case` functions, `CapWords` classes | `alloc_frame()`, `MemoryManager` |
| Version | `aPEOSI <major>.<minor>`, with a stage label while unstable | aPEOSI 1.2 (alpha) |
| Shell prompt | `aPEOSI <version> <drive>:/<path>>` | `aPEOSI 1.2 A:/basic>` |
| Drives | one capital letter | `A:` |

The folders `sysApp/` and `system2/` predate this scheme. They keep their names
for now, because renaming them touches every import; that cleanup is part of
the packaging work on the [roadmap](ROADMAP.md).
