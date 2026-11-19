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

## 3. Hardware modules: `aPE-<letter><model>`

Each kind of device has one letter, so model names never collide with each
other or with product names.

| Letter | Device | Examples | Spec file |
|---|---|---|---|
| **B** | motherboard | aPE-B1 Classic | `motherboard/board.json` |
| **P** | processor (CPU) | aPE-P1, aPE-P0 Turtle | `motherboard/cpu/ape-p1.json` |
| **R** | RAM | aPE-R16K, aPE-R64K, aPE-R256K | `motherboard/ram/ape-r16k.json` |
| **G** | GPU | aPE-G1 (framebuffer), aPE-G2 (shader cores) | `motherboard/gpu/ape-g1.json` |
| **D** | disk | aPE-D1 | `motherboard/disk/ape-d1.json` |
| **N** | network card | aPE-N1 | `motherboard/net/ape-n1.json` |
| **K** | keyboard controller (bus device) | aPE-K1 | `motherboard/bus/ape-k1.json` |
| **S** | sound chip (bus device) | aPE-S1 | `motherboard/bus/ape-s1.json` |

- The model is a number, or a size for RAM (`16K`). An optional nickname can follow: `aPE-P0 Turtle`.
- A model name is at most **14 characters** (it is stored in every device file's header).
- The spec file name is the model name in lowercase, with spaces as hyphens: `aPE-P0 Turtle` → `ape-p0-turtle.json`.
- Mods follow the same pattern. A modded CPU could be `aPE-P7 Rocket` in `cpu/ape-p7-rocket.json`.

## 4. Device files: `<class><n>.ape<class>`

At runtime each device instance is one binary file. Every file starts with
the common aPE device header ([formats](docs/aPE-hardware.md)), whose class
code matches the extension: the extension is always `.ape` + the class code in lowercase.

| Class code | Extension | Instance file | Holds | Lifetime | Status |
|---|---|---|---|---|---|
| `RAM` | `.aperam` | `ram0.aperam` | all memory: kernel tables, processes | volatile | implemented |
| `MB` | `.apemb` | `board0.apemb` | the list of devices the OS discovers at boot | rebuilt at boot | reserved |
| `BUS` | `.apebus` | `bus0.apebus` | registers of every bus device (keyboard, sound, ...) | volatile | reserved |
| `GPU` | `.apegpu` | `gpu0.apegpu` | VRAM, display registers, later shader cores | volatile | reserved |
| `CPU` | `.apecpu` | `cpu0.apecpu` | registers, PC, flags, cycle counter, cache | volatile | reserved |
| `DISK` | `.apedisk` | `disk0.apedisk` | **files: user data** | **persistent** | reserved |
| `NET` | `.apenet` | `net0.apenet`, `air0.apenet` | a network card's buffers and link state, or a shared medium | volatile | reserved |

Rules:

- **The motherboard file lists devices; each device keeps its own state.** `board0.apemb`
  says "there is a sound chip and a network card"; their registers and buffers live in their own files.
- **The bus is a container.** Small devices (keyboard, sound, later a timer) share
  `bus0.apebus`, each in its own region. They need no class of their own.
- **New classes are rare.** A device gets its own class only when its state is too big or
  too different for the bus. Until then it is a bus device.
- **Volatile files** are wiped and recreated at every boot. They are safe to delete.
- **Disks are persistent.** A `.apedisk` file *is* the disk: deleting it deletes the data,
  and copying it is a complete backup. aPEOSI never creates or overwrites a disk file on
  its own; new disks are made by a separate format tool.
- **Modules vs instances.** A compiled device module (from aPE-DevKit) uses the same
  extension as its instances, told apart by the name: `ape-g1.apegpu` is the module
  (model name), `gpu0.apegpu` is the running instance (`<class><n>`).

All device files are git-ignored: volatile ones because they are recreated at boot,
compiled modules because they are build outputs (commit the `.py` or `.json` source),
disks because they hold personal data. A new device class needs a class code of up to
4 letters, a matching `.ape<code>` extension, and an entry in `apedev.py`.

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
