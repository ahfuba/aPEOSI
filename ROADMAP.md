# aPEOSI Roadmap

aPEOSI is turning into an **ecosystem of modules**: simulated hardware parts,
the OS that runs on them, software that runs on the OS, and tools that watch
it all. Each part has a clear interface, so anyone can swap it, mod it, or
build a new one.

Legend: ✅ done · 🔨 next · 💡 idea · 🐞 known issue

---

## The ecosystem at a glance

```
┌──────────────────────────────── TOOLS ────────────────────────────────┐
│  aPE-RAM Watchdog ✅      aPE-Display 💡      Benchmarks 💡           │
└───────────────────────────────────────────────────────────────────────┘
┌────────────────────────────── SOFTWARE ───────────────────────────────┐
│  aPE-BASIC ✅   BananaEditor ✅   counter ✅   machine-code programs 💡│
└───────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────── aPEOS ────────────────────────────────┐
│  kernel · scheduler · memory manager · system calls ✅                │
│  file system on a disk image 💡 · users & permissions 💡              │
└───────────────────────────────────────────────────────────────────────┘
┌──────────────────────── HARDWARE (/motherboard) ──────────────────────┐
│  RAM .aperam ✅   CPU ✅ (clock only)   GPU 💡   bus devices .apebus 💡│
│  motherboard / PCI .apemb 💡   cache 💡                                │
└───────────────────────────────────────────────────────────────────────┘
```

---

## ✅ aPEOSI 1.2 (done)

### Hardware
- [x] `/motherboard` folder: `board.json` picks swappable CPU and RAM module files (JSON)
- [x] Hardware files checked at boot ("BIOS"), with clear errors for bad mods
- [x] Common 32-byte aPE device header for every hardware file ([spec](docs/aPE-hardware.md))
- [x] `.aperam` RAM modules: 16K, 64K and 256K included
- [x] CPU modules: `ape-c1` (200 Hz) and `ape-c0-turtle` (4 Hz)

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
- [x] BananaEditor keeps its text in RAM

### Tools
- [x] **aPE-RAM Watchdog**: live frames, bits, hex and process table

### Docs
- [x] [How aPEOSI 1.2 works](docs/how-aPEOSI-1.2-works.md): guided tour of the code
- [x] [Hardware file formats](docs/aPE-hardware.md)
- [x] [Modding guide](motherboard/README.md)

---

## 🔨 aPEOSI 1.3: graphics and games

Goal: write simple 1980s-style games in aPE-BASIC.

### Hardware
- [ ] **GPU module**, specs in JSON (e.g. `motherboard/gpu/ape-g1.json`), not in the filename:
  `width`, `height`, `colors`, `buffers`, `refresh_hz`. Example: 160 × 120, 16 colours, 30 Hz (9.6 KB of VRAM)
- [ ] GPU registers in the motherboard's PCI configuration space: first use of **`.apemb`**
- [ ] VRAM as its own memory region the GPU owns
- [ ] **Keyboard controller** on the I/O bus: first use of **`.apebus`**, for reading keys without Enter

### Software
- [ ] BASIC graphics: `SCREEN`, `PSET x, y, c`, `LINE`, `COLOR`, `POINT(x, y)`
- [ ] BASIC `INKEY$` (read a key without waiting)
- [ ] BASIC BREAK key: stop a running program without killing BASIC
- [ ] Example games: Snake, Pong, Breakout

### Tools
- [ ] **aPE-Display**: a window that draws VRAM at the GPU's `refresh_hz`

---

## 💡 aPEOSI 2.0: a real (simulated) computer

Goal: programs become machine code in RAM, run by a virtual CPU.

### Hardware
- [ ] **Virtual CPU** that fetches, decodes and executes instructions from aPE-RAM. Choose one:
  - [ ] **RISC-V RV32I** (recommended): open standard, has user/kernel mode and interrupts, and real C compilers target it
  - [ ] 6502: the C64/NES CPU, very 80s, but no OS features
  - [ ] An original aPE instruction set
- [ ] **Timer interrupt** every N cycles → real preemptive multitasking
- [ ] **Privilege bit**: user vs kernel mode, protected instructions
- [ ] Context switches save real registers into the PCB (visible in the Watchdog)
- [ ] **Simulated time**: a cycle counter independent of Python's real speed
- [ ] RAM modules get `latency_cycles`; CPU modules get cycle costs per instruction
- [ ] **Cache module**: shows the "memory wall" (a 3 GHz CPU waits about 45 cycles for DRAM)

### Modding levels for CPU modules
- [ ] **Spec mods (JSON)**: clock, timer interval, cycle costs. Safe to share.
- [ ] **Core mods (Python class)**: a whole new CPU with `reset()`, `step() → cycles`, `interrupt(n)`.
  ⚠️ This is code that runs on your machine: only install core mods from people you trust.

### Software and tools
- [ ] **Assembler**: write `MOV`, `ADD`, `JMP` instead of hex
- [ ] Run C programs compiled with GCC/Clang (if RISC-V)
- [ ] aPE-BASIC keeps running as built-in "ROM BASIC"

---

## 💡 Later

### OS
- [ ] Our own **file system** on a disk image file (superblock, FAT or inodes, blocks) instead of host folders
- [ ] Shell: pipes `|`, redirection `>` `<`, batch scripts, environment variables, quoted arguments
- [ ] **Users and permissions**: login, file ownership, using the `level` column in `sys_cmd.csv`
- [ ] Real logging to a file (`logtime`, `logdate`)

### Software
- [ ] Full-screen BananaEditor (`curses`)
- [ ] A GUI (`gui.py` is still empty)

### Engineering
- [ ] Package layout, run with `python -m apeosi`
- [ ] `pytest` tests that drive the shell from a script
- [ ] GitHub Actions CI
- [ ] **Benchmarks**: measure context-switch, system-call and memory costs, to prove the README's "Python is too heavy" claim

---

## 🐞 Known issues

- [ ] The shell's `sleep` command freezes everything while it runs (it should be a process or a system call)
- [ ] `cd` to another drive (`cd B:/foo`) works out the path against the current drive
- [ ] `force_dlt` can delete the OS's own files, because drive `A:` is the OS folder
- [ ] Untested on Windows: Ctrl+C handling, the keyboard thread, the shared RAM file
- [ ] On Windows, close the Watchdog before booting with a different RAM size

---

## Making your own module

| Module type | What you write | Where | Guide |
|---|---|---|---|
| RAM | a JSON spec | `motherboard/ram/` | [modding guide](motherboard/README.md) |
| CPU | a JSON spec | `motherboard/cpu/` | [modding guide](motherboard/README.md) |
| App | a Python class with `run()` that yields system calls | `sysApp/` + a line in `sys_cmd.csv` | [how it works](docs/how-aPEOSI-1.2-works.md) |
| BASIC program | a `.bas` file | anywhere on a drive | [aPE-BASIC](docs/aPE-BASIC.md) |
| New hardware class | a class code and header after the common header | `apedev.py` | [formats](docs/aPE-hardware.md) |
