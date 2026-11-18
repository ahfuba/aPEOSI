# How aPEOSI 1.2 works

A guided tour of the code. Each section names an OS concept, says
what real computers do, and points to the file that does it in aPEOSI.
Read it with the Watchdog open, because every step shows up there.

## 0. Try this first

```bash
python main.py
```

In a second window:

```bash
python ape_watchdog.py
```

Then in aPEOSI:

```
counter &          start a binary counter in the background
counter 500 &      a slower one
banana note.txt    type a few lines, watch them appear in RAM
ps                 the process table, read from RAM
mem                the frame map
peek 1 0           hex-dump PID 1's memory from virtual address 0
kill 1             watch its frames get scrubbed and freed
```

## 1. Hardware and BIOS: `motherboard/`, `sys/hardware.py`, `main.py`

Real PC: firmware detects the CPU and RAM, tests the RAM (POST), then
loads the OS.

aPEOSI: `main.py` is the BIOS. It loads `motherboard/board.json`, validates
each part, creates the RAM file, and runs `power_on_self_test()`, which
writes `AA 55 AA 55 …` to each frame, reads it back and clears it. Boot without
`--fast` and you can watch the sweep in the Watchdog.

## 2. RAM: `sys/aperam.py`

Real PC: RAM is an array of bytes, addressed by number.

aPEOSI: `PhysicalRAM` is that array, backed by a memory-mapped file.
`read(addr, n)` and `write(addr, data)` are the only way anything touches
memory. Because the file is memory-mapped, the Watchdog (a separate program)
sees the same bytes. Read the header comment in `aperam.py` for the layout,
or [`aPE-hardware.md`](aPE-hardware.md) for the full table.

## 3. Frames and the frame table: `sys/mem_mgr.py`

Real OS: physical memory is split into fixed-size **frames**. The kernel
keeps a table of which frames are free.

aPEOSI: frame 1 is the frame table, 1 byte per frame (`type << 4 | owner`).
Look at `alloc_frame()`: it scans for a free entry, marks it, and **zeroes
the frame** so a new process can never read an old process's data.
`free_frame()` scrubs it again on the way out.

## 4. Processes and the PCB: `sys/process_mgr.py`

Real OS: each process has a **Process Control Block** (state, ID, where its
memory is, saved registers).

aPEOSI: the PCB is 32 bytes in the process table in RAM. `Process.state`
is a property that reads and writes those bytes. The "saved registers"
are the Python generator: when a process `yield`s, Python freezes its local
variables and its position in the code; `send()` resumes it exactly there.
That is a **context switch**.

## 5. System calls: `process_mgr.py` (`Sleep`, `ReadLine`), `kernel.py`

Real CPU: a program can't do I/O itself. It executes a trap instruction,
the CPU switches to kernel mode, and the kernel does the work.

aPEOSI: a process `yield`s a request object. The kernel receives it in
`_schedule_round()` and acts on it:

```python
line = yield ReadLine("> ")   # blocks until you type; the kernel send()s the line back
yield Sleep(0.1)              # the kernel won't schedule this process for 0.1 s
```

## 6. Scheduling: `sys/kernel.py`

Real OS: a scheduler picks which ready process runs next; a timer interrupt
forces switches (preemptive).

aPEOSI: `_schedule_round()` is **round-robin**: every RUNNING process gets
one step per round. The CPU module's `clock_hz` limits rounds per second.
Before each step the kernel bumps `tick` and writes `current_pid` into the
RAM header, and when the step ends it writes `0xFFFF` (kernel) back. In the
Watchdog, frame 00 (header) and the process table frames flash on every
switch.

aPEOSI is **cooperative**: a process that never yields freezes the system.
Real OSes use a timer interrupt; Python generators can't be interrupted
mid-step. Ctrl+C is the escape: it kills the foreground process.

The keyboard is read by a separate thread (`Console`), so typing never
blocks the scheduler. Background processes keep running while you type.

## 7. Virtual memory: `MemoryManager.translate()`

Real CPU: the MMU translates every address a program uses through the
process's **page table**.

aPEOSI: every process sees addresses starting at 0. `translate()` splits the
virtual address into *page* and *offset*, looks the page up in the process's
page-table frame, and builds the physical address. Two counters both write
to their virtual address `0x0000`, but `ps` shows different page-table frames
and the Watchdog shows different physical frames.

- **Demand paging**: writing to an unmapped page makes the kernel allocate a
  frame right then. Start `banana` and watch a frame appear when the editor
  first writes.
- **Page fault**: reading an unmapped page raises `PageFault`. Try
  `peek 1 0x500`.

## 8. Applications: `sysApp/`

`counter/counter.py` is the simplest program: it stores a number in its
memory, yields, repeats. `banana_editor/editor.py` keeps its whole text
buffer in RAM (line count at `0x0`, byte count at `0x4`, text from `0x8`), so
`peek <pid> 0` shows your typing.

An app gets two things from the process manager: `self.pid` and `self.mem`
(its address space: `load`, `store`, `load_u32`, `store_u32`).
