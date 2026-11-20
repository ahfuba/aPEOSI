# aPEOSI Roadmap

aPEOSI is turning into an **ecosystem of modules**: simulated hardware parts,
the OS that runs on them, software that runs on the OS, and tools that watch
it all. Each part has a clear interface, so anyone can swap it, mod it, or
build a new one. Names follow the [naming scheme](NAMING.md).

Legend: ✅ done · 🔨 current stage · 💡 planned · 🐞 known issue

---

## The ecosystem at a glance

```
┌──────────────────────────────── TOOLS ────────────────────────────────┐
│  aPE-Watchdog ✅ (recording & replay 💡)   aPE-Display 💡               │
│  aPE-DevKit ✅   Benchmarks 💡                                          │
└───────────────────────────────────────────────────────────────────────┘
┌────────────────────────────── SOFTWARE ───────────────────────────────┐
│  aPE-BASIC ✅   Banana Editor ✅   aPE-VM 💡   aPE-C 💡   .apx 💡       │
└───────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────── aPEOSI ───────────────────────────────┐
│  kernel · scheduler · memory manager · system calls ✅                │
│  file system on a disk image 💡 · users & permissions 💡              │
└───────────────────────────────────────────────────────────────────────┘
┌──────────────────────── HARDWARE (/motherboard) ──────────────────────┐
│  RAM .aperam ✅   CPU ✅ clock only (.apecpu 💡)   board .apemb ✅     │
│  bus .apebus ✅   PCI .apepci ✅   serial .apeser ✅   USB .apeusb 💡   │
│  media: disk .apedisk 💡  network .apenet 💡   cache 💡                 │
└───────────────────────────────────────────────────────────────────────┘
```

---

## The plan: six stages

Each stage builds what the next one needs.

| Stage | Goal | Builds toward |
|---|---|---|
| ✅ **0** | aPEOSI 1.2: aPE-RAM, motherboard modules, aPE-Watchdog, aPE-BASIC | everything |
| 🔨 **1** | Finish 1.x: sockets and devices with logic, then graphics and games | complete 1.x hardware |
| 💡 **2** | Understand the system: review and document every subsystem | owning the code before it grows |
| 💡 **3** | A compiled language and **aPE-VM**, a bytecode machine that runs code from aPE-RAM | aPEOSI's first compiler, and a CPU-like target |
| 💡 **4** | Learn C | designing aPE-C |
| 💡 **5** | **aPE-C**, compiling to aPE-VM | a systems language for aPEOSI |
| 💡 **6** | Full hardware simulation: aPE-VM grows into a real CPU with interrupts | a complete simulated computer |
| 💡 *lab* | After Stage 3: lab devices (GPU cores, sound, networking) for course topics | hands-on signals, graphics and networking |

---

## ✅ Stage 0: aPEOSI 1.2 (done)

### Hardware
- [x] `/motherboard` folder: `board.json` picks swappable CPU and RAM module files (JSON)
- [x] Hardware files checked at boot ("BIOS"), with clear errors for bad mods
- [x] Common 32-byte aPE device header for every hardware file ([spec](docs/aPE-hardware.md))
- [x] RAM modules aPE-R16K, aPE-R64K, aPE-R256K
- [x] CPU modules aPE-P1 (200 Hz) and aPE-P0 Turtle (4 Hz)

### OS
- [x] RAM is a memory-mapped `.aperam` file that other programs can watch
- [x] Frame table, process table (PCBs), page tables and keyboard buffer stored in RAM
- [x] Virtual memory: per-process page tables, demand paging, page faults
- [x] Non-blocking keyboard; round-robin scheduler throttled by the CPU clock
- [x] System calls: `Sleep`, `ReadLine`
- [x] Ctrl+C kills the foreground app; clean shutdown; a process killing itself is ended safely after its time slice
- [x] Commands: `ps`, `kill`, `fg`, `mem`, `peek`, `counter`, `basic`
- [x] v1 bugs fixed: hard-coded path, endless EOF loop, `list_tasks` crash, `cmd_info` aliases

### Software
- [x] **aPE-BASIC**: line-numbered BASIC with program, variables and arrays in RAM, `PEEK`/`POKE` ([reference](docs/aPE-BASIC.md))
- [x] aPE system keywords in BASIC: hardware info (`CPU$`, `RAMSIZE`), process table (`PSLOT`, `PSTATE`), MMU (`FRAME`, `PHYS`), process control (`SPAWN`, `KILL`, `WAIT`, `YIELD`, `SHELL`)
- [x] Example programs in `A:/basic/`: `hello`, `guess`, `primes`, `bits`, `taskman`, `mmu`
- [x] Banana Editor keeps its text in RAM

### Tools and docs
- [x] **aPE-Watchdog**: live frames, bits, hex and process table
- [x] [How aPEOSI 1.2 works](docs/how-aPEOSI-1.2-works.md), [hardware formats](docs/aPE-hardware.md), [modding guide](motherboard/README.md), [naming scheme](NAMING.md)

---

## 🔨 Stage 1: finish 1.x (devices, graphics, games)

> **Feature freeze:** no new features until the presentable-release checklist is done
> (tests ✅, CI ✅, README ✅, a Windows try-out, merge into `main`).
> After that: **no new feature without its tests** ([TESTING.md](TESTING.md)).

Goal: 1980s-style games in aPE-BASIC, on the first real devices.
Rule: **every device arrives together with the software that uses it.**

### Toolkit (first)
- [x] **aPE-DevKit** (`apedk` package, `ape_devkit.py` tool): describe a device in Python
      (parameters, registers, memory regions) and compile it into a `.ape<class>` module file.
      Validates the design at build time; the compiled file is pure data, so device mods are safe to share.
      Can compile the existing JSON specs too
- [x] Device descriptors: every device file declares its named regions, so tools can show any device without device-specific code
- [x] aPEOSI boots from compiled CPU and RAM modules as well as JSON specs
- [x] [Guide](docs/aPE-DevKit.md), example device (`docs/examples/ape-l1-panel`), and tests (`python -m unittest discover tests`)

### Sockets ([spec](docs/aPE-Socket.md))
- [x] Socket types: CPU, memory slot, motherboard, on-board system bus, PCI slots, serial ports, USB (spec only).
      **The extension names the socket**; the device's function is stored inside the file
- [x] Media separate from devices: `.apedisk` (persistent) and `.apenet`
- [x] Motherboard runtime: enumeration at boot, I/O port windows, level-triggered IRQs with an
      interrupt controller in `board0.apemb`, device clocks, serial links, faulted devices isolated
- [x] Device logic: `LOGIC` classes with `reset`/`read`/`write`/`tick`/`on_serial` hooks; device files
      *are* the live devices (`bus0.apebus`, `com1.apeser`)
- [x] First devices: **aPE-T1 Timer** (interrupts), **aPE-U1 UART** (baud-timed serial), **aPE-E1 Echo** (serial loopback plug)
- [x] Kernel: interrupt dispatch to drivers by function, a timer driver, masking of unhandled IRQs
- [x] `lsdev`; BASIC `INP`, `OUT`, `IOBASE`, `IRQCOUNT`; `timer.bas`, `serial.bas`
- [x] `ape_devkit.py info --watch`: live view of any device file
- [ ] USB: a host-controller PCI card and the **aPE-K1 USB keyboard**, for reading keys without Enter
- [ ] PCI DMA: cards reading and writing RAM within limits the OS grants

### Hardware
- [ ] **aPE-G1 GPU** card in a PCI slot (`pci0.apepci`): `width`, `height`, `colors`, `buffers`, `refresh_hz`.
      Example: 160 × 120, 16 colours, 30 Hz; VRAM and display registers in the card's file

### Software
- [ ] BASIC graphics: `SCREEN`, `PSET x, y, c`, `LINE`, `COLOR`, `POINT(x, y)`
- [ ] BASIC `INKEY$` (read a key without waiting)
- [ ] BASIC BREAK key: stop a running program without killing BASIC
- [ ] Example games: Snake, Pong, Breakout

### Tools
- [ ] **aPE-Display**: a window that draws VRAM at the GPU's `refresh_hz`
- [ ] aPE-Watchdog can open any aPE device file, not just RAM, using its region descriptors
- [ ] **Recording and slow-motion replay** (snapshot level): aPE-Watchdog saves what changed each frame
      into a recording and plays it back at any speed

### Cleanup
- [ ] Fix the [known issues](#-known-issues) below

---

## 💡 Stage 2: understand the system

Goal: every part of aPEOSI is understood by its maintainer and explained in the docs
before the system grows further.

- [ ] Walk through [How aPEOSI 1.2 works](docs/how-aPEOSI-1.2-works.md) with aPE-Watchdog open
- [ ] Trace one context switch, one page fault and one system call end to end
- [ ] Extend the docs to cover the Stage 1 devices
- [ ] Fix at least one known issue without AI assistance

---

## 💡 Stage 3: a compiled language and aPE-VM

Goal: aPEOSI's first compiler, plus a machine for it to compile to.

- [ ] **aPE-VM**: a stack-based bytecode virtual machine (instructions like `PUSH 5`, `ADD`, `STORE x`, `JUMP`)
      that runs bytecode stored in aPE-RAM, one aPEOSI process per program
- [ ] System calls from bytecode through a `SYSCALL` instruction
- [ ] `.apx` executable format: an aPE device-style header plus bytecode
- [ ] A language with a compiler that runs **inside aPEOSI** and produces `.apx` files.
      Either a new language or aPE-BASIC compiled to bytecode (to be decided)
- [ ] aPE-Watchdog shows the bytecode, the VM's stack and its program counter in RAM

---

## 💡 Stage 4: learn C

Prerequisite for designing aPE-C: pointers, arrays, structs, the stack, and how C maps to memory.

---

## 💡 Stage 5: aPE-C

Goal: a compiler for a small subset of C, the way HolyC is TempleOS's own C.

- [ ] Compiles to aPE-VM bytecode (`.c` → `.apx`)
- [ ] Step 1: integers, expressions, `if`, `while`, functions
- [ ] Step 2: arrays and pointers
- [ ] Step 3: structs, strings

---

## 💡 Stage 6: full hardware simulation

Goal: programs are machine code in RAM, run by a virtual CPU.

Approach: **Nachos style** (as Berkeley's teaching OS does). The Python kernel
stays the kernel, running in "kernel mode"; user programs run as machine code
on the simulated CPU, and a trap instruction hands control to the kernel. This
needs **no BIOS, no bootloader and no kernel rewrite**: `main.py` already does
the BIOS's job, and the kernel loads programs straight into memory (like
`qemu -kernel`).

### CPU
- [ ] aPE-VM grows into a register CPU. Choose the instruction set:
  - [ ] **RISC-V RV32I**: open standard, has user/kernel mode and interrupts, and real C compilers target it
  - [ ] 6502-style: very 80s, but no OS features
  - [ ] An original aPE instruction set
- [ ] **Timer interrupt** every N cycles → real preemptive multitasking
- [ ] **Trap instruction** for system calls; **privilege bit** for protected instructions
- [ ] Context switches save real registers into the PCB (visible in aPE-Watchdog)
- [ ] CPU state lives in `cpu0.apecpu`: registers, PC, flags, privilege bit, cycle counter

### Timing
- [ ] **Simulated time**: a cycle counter independent of Python's real speed
- [ ] RAM modules get `latency_cycles`; CPU modules get cycle costs per instruction
- [ ] **Cache module**: shows the "memory wall" (a 3 GHz CPU waits about 45 cycles for DRAM); a region of `cpu0.apecpu`
- [ ] **Deterministic replay**: record only the inputs, re-run the simulation exactly; perfect slow motion and rewind

### Software
- [ ] **Assembler**: `.aps` source → `.apx` machine code
- [ ] **Loader**: `exec` an `.apx` file into a new process
- [ ] aPE-C gets a back end for the new CPU
- [ ] aPE-BASIC keeps running as built-in "ROM BASIC"

### Modding levels for CPU modules
- [ ] **Spec mods (JSON)**: clock, timer interval, cycle costs. Safe to share.
- [ ] **Core mods (Python class)**: a whole new CPU with `reset()`, `step() → cycles`, `interrupt(n)`.
  ⚠️ This is code that runs on your machine: only install core mods from people you trust.

### Beyond Stage 6 (optional)
- [ ] OS/161 style: move parts of the kernel onto the virtual CPU, written in aPE-C, with a tiny boot ROM

---

## 💡 Lab devices (after Stage 3)

Devices that turn course topics into experiments. Each arrives with programs that use it,
and with something to observe in aPE-Watchdog.

- [ ] **aPE-G2 GPU with shader cores**: N cores, each with its own registers and program counter in
      the card's file (`pci0.apepci`), all running the same aPE-VM shader on different pixels. Watch the image being drawn core by core
- [ ] **aPE-S1 sound card** (PCI): sample buffer + DAC registers.
      Topics: sampling, the Nyquist rate, quantization, buffer underruns, interrupts
- [ ] **aPE-N1 network card** (PCI) and a **shared medium** (`air0.apenet`):
      two aPEOSI computers exchange packets through one file. The medium can add noise, drop packets
      and cause collisions. Topics: packets, MAC addresses, collisions, retransmission

---

## Side quests (any stage)

### OS
- [ ] Own **file system** on an aPE-D1 disk, `disk0.apedisk` (superblock, FAT or inodes, blocks), instead of host folders.
      Disks are persistent: never created or overwritten at boot, made by a separate format tool, backed up by copying the file
- [ ] Move drives from `/devices` to disk modules under `/motherboard/disk/`, so the whole computer lives in one folder
- [ ] Shell: pipes `|`, redirection `>` `<`, batch scripts, environment variables, quoted arguments
- [ ] **Users and permissions**: login, file ownership, using the `level` column in `sys_cmd.csv`
- [ ] Real logging to a file (`logtime`, `logdate`)

### Software
- [ ] Full-screen Banana Editor (`curses`)
- [ ] A GUI (`gui.py` is still empty)

### Engineering
- [ ] Package layout, run with `python -m apeosi`; rename `sysApp/` and `system2/` to match [NAMING.md](NAMING.md)
- [x] System tests that boot aPEOSI and drive the shell from a script ([TESTING.md](TESTING.md))
- [x] GitHub Actions CI: every push tested on Windows, Linux and macOS, Python 3.10/3.12/3.13
- [ ] **Benchmarks**: measure context-switch, system-call and memory costs, to prove the README's "Python is too heavy" claim
- [ ] **Write-log recording**: the simulator logs every write (time, address, old, new), so recordings miss nothing

---

## 🐞 Known issues

- [ ] The shell's `sleep` command freezes everything while it runs (it should be a process or a system call)
- [ ] `cd` to another drive (`cd B:/foo`) works out the path against the current drive
- [ ] `force_dlt` can delete the OS's own files, because drive `A:` is the OS folder
- [ ] Windows: the automated tests pass there in CI; Ctrl+C and the Watchdog window still need the [manual check](TESTING.md#manual-check-about-5-minutes)
- [ ] On Windows, close aPE-Watchdog before booting with a different RAM size

---

## Making your own module

Name it by the [naming scheme](NAMING.md).

| Module type | What you write | Where | Guide |
|---|---|---|---|
| RAM | a JSON spec, e.g. `ape-r32k.json` | `motherboard/ram/` | [modding guide](motherboard/README.md) |
| CPU | a JSON spec, e.g. `ape-p2.json` | `motherboard/cpu/` | [modding guide](motherboard/README.md) |
| App | a Python class with `run()` that yields system calls | `sysApp/` + a line in `sys_cmd.csv` | [how it works](docs/how-aPEOSI-1.2-works.md) |
| BASIC program | a `.bas` file | anywhere on a drive | [aPE-BASIC](docs/aPE-BASIC.md) |
| Device module | a Python or JSON description compiled with aPE-DevKit | `motherboard/<class>/` | [aPE-DevKit](docs/aPE-DevKit.md) |
| New hardware class | a class code, a `.ape<class>` extension and a header after the common header | `apedev.py` | [formats](docs/aPE-hardware.md) |
