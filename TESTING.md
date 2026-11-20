# Testing aPEOSI

Almost everything is tested automatically. The rest is a short manual check.

## Automatic tests

```bash
python -m unittest discover tests
```

About 45 tests, in about 10 seconds:

| File | Checks |
|---|---|
| `tests/test_system.py` | boots the real aPEOSI, types commands into it and checks the output: the shell, processes, every example BASIC program, BASIC errors and keywords, SAVE/LOAD, Banana Editor, the devices, and how aPE-Watchdog reads RAM |
| `tests/test_sockets.py` | the motherboard: I/O windows, interrupts, the timer, the UART and echo plug, faulty devices, board files |
| `tests/test_devkit.py` | aPE-DevKit and the device file formats |

System tests boot aPEOSI on a temporary board, so they never touch your own
files in `motherboard/`.

**GitHub runs all of them on every push**, on Windows, Linux and macOS with
Python 3.10, 3.12 and 3.13. The badge in the README shows the latest result;
a red ❌ links to the log of what failed, and on which system.

### The rule for new features

**No new feature without its tests**, in the same commit:

- a new shell command or BASIC keyword → a case in `tests/test_system.py`
- a new device → its behaviour in `tests/test_sockets.py`, and a BASIC example that uses it
- a new example program → a system test that runs it and checks its output

## Manual check (about 5 minutes)

Automation can't look at a window or press Ctrl+C in a real terminal. Before a
release, or after big changes, check by hand:

- [ ] `python main.py` boots with the slow boot, the memory test and the socket list
- [ ] `python ape_watchdog.py` in a second window shows frames, bits and the process table
- [ ] `counter &`: its page flashes in the Watchdog and its bits count up
- [ ] `basic basic/bits.bas &`: a diagonal stripe moves in its page at `&H8000`
- [ ] `basic basic/guess.bas` plays a full game
- [ ] Ctrl+C stops a running BASIC program (`basic`, then `10 GOTO 10`, `RUN`, Ctrl+C)
- [ ] `python ape_devkit.py info --watch motherboard/bus0.apebus` updates while `basic basic/timer.bas` runs
- [ ] `exit` shuts down cleanly
