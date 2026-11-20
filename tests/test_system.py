"""
System tests: boot the real aPEOSI, type commands into it, check the output.

Each test boots aPEOSI as a separate process with its own temporary board
(RAM and device files go to a temporary folder), so tests never touch the
files in motherboard/. Programs on drive A: are only read; anything a test
saves is deleted again.

Run from the project folder:   python -m unittest discover tests
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MB = os.path.join(ROOT, "motherboard")
DRIVE_A = os.path.join(ROOT, "devices", "internal", "A")


def board_spec(tmp, sockets=None, ram="ape-r16k.json"):
    if sockets is None:
        sockets = [
            {"id": "bus0", "type": "bus", "device": os.path.join(MB, "bus", "ape-t1-timer.py")},
            {"id": "bus1", "type": "bus", "device": os.path.join(MB, "bus", "ape-u1-uart.py")},
            {"id": "pci0", "type": "pci", "device": None},
            {"id": "com1", "type": "ser", "device": os.path.join(MB, "serial", "ape-e1-echo.py"),
             "controller": "bus1"},
        ]
    spec = {"name": "aPE-B9 Test", "cpu": os.path.join(MB, "cpu", "ape-p1.json"),
            "ram": os.path.join(MB, "ram", ram), "ram_file": os.path.join(tmp, "ram0.aperam"),
            "sockets": sockets}
    path = os.path.join(tmp, "board.json")
    with open(path, "w") as f:
        json.dump(spec, f)
    return path


def run_aPEOSI(lines, board=None, timeout=90):
    """Boots aPEOSI, types `lines`, and returns (exit code, everything it printed)."""
    with tempfile.TemporaryDirectory() as tmp:
        board_path = board or board_spec(tmp)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [sys.executable, "main.py", "--fast", "--board", board_path],
            input="\n".join(lines) + "\n", capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=ROOT, env=env, timeout=timeout)
        return proc.returncode, proc.stdout + proc.stderr


class SystemTest(unittest.TestCase):
    def boot(self, *lines, **kw):
        code, out = run_aPEOSI(list(lines) + ["exit"], **kw)
        self.assertNotIn("Traceback", out, out)
        return out


class TestBootAndShell(SystemTest):
    def test_boot_and_shutdown(self):
        out = self.boot("ver")
        self.assertIn("Sockets:", out)
        self.assertIn("aPEOSI 1.2 A:/>", out)
        self.assertIn("aPEOSI Version: 1.2", out)
        self.assertIn("aPEOSI halted.", out)

    def test_end_of_input_shuts_down(self):
        code, out = run_aPEOSI(["ver"])          # no "exit": input simply ends
        self.assertEqual(code, 0)
        self.assertIn("aPEOSI halted.", out)

    def test_shell_commands(self):
        out = self.boot("sysinfo", "help", "cmd_info ps", "nosuchcommand", "echo hi there", "cd basic", "dir")
        self.assertIn("Motherboard:     aPE-B9 Test", out)
        self.assertIn("CPU:             aPE-P1 (200 Hz)", out)
        self.assertIn("Available commands:", out)
        self.assertIn("Info for command 'list_tasks'", out)       # alias resolved
        self.assertIn("Unknown command: 'nosuchcommand'", out)
        self.assertIn("hi there", out)
        self.assertIn("aPEOSI 1.2 A:/basic>", out)
        self.assertIn("primes.bas", out)

    def test_processes_and_memory(self):
        out = self.boot("counter 20 &", "basic basic/hello.bas", "ps", "mem", "peek 1 0 4", "kill 1", "kill 99", "ps")
        self.assertRegex(out, r"0\s+1\s+counter\s+(SLEEPING|RUNNING)")
        self.assertIn("Frame map", out)
        self.assertRegex(out, r"v0x0000 -> p0x[0-9A-F]{5}")
        self.assertIn("terminated. (killed)", out)
        self.assertIn("Error: no process with PID 99.", out)
        self.assertIn("No processes running.", out)

    def test_bad_hardware_stops_the_bios(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = board_spec(tmp, sockets=[{"id": "pci0", "type": "pci",
                                              "device": os.path.join(MB, "bus", "ape-t1-timer.py")}])
            code, out = run_aPEOSI(["exit"], board=board)
        self.assertEqual(code, 1)
        self.assertIn("does not fit socket pci0", out)


class TestExamplePrograms(SystemTest):
    def test_hello_primes_mmu(self):
        out = self.boot("basic basic/hello.bas", "basic basic/primes.bas", "basic basic/mmu.bas")
        self.assertIn("HELLO FROM aPE-BASIC!", out)
        self.assertIn("5 SQUARED IS 25", out)
        self.assertIn("2 3 5 7 11 13", out)
        self.assertIn("197 199", out)
        self.assertIn("&H8000 IS IN FRAME -1", out)
        self.assertRegex(out, r"NOW &H8000 IS IN FRAME \d+, PHYSICAL ADDRESS &H[0-9A-F]+")

    def test_taskman(self):
        out = self.boot("basic basic/taskman.bas")
        self.assertIn("BOARD: aPE-B9 Test", out)
        self.assertRegex(out, r"KILLED \d+ AND \d+\. \d+ BYTES FREE AGAIN\.")

    def test_guess_loads(self):
        out = self.boot("cd basic", "basic", 'LOAD "guess"', "LIST 30", "BYE")
        self.assertIn("LOADED guess.bas", out)
        self.assertIn("30 N = INT(RND(1) * 100) + 1", out)

    def test_timer_program_gets_interrupts(self):
        out = self.boot("basic basic/timer.bas", "lsdev")
        self.assertIn("TIMER STOPPED.", out)
        irqs = [int(n) for n in re.findall(r"IRQS (\d+)", out)]
        self.assertGreater(max(irqs), 0)
        self.assertRegex(out, r"bus0\s+BUS\s+aPE-T1 Timer\s+TIMER\s+0000-000F\s+0\s+[1-9]")

    def test_serial_program_echoes(self):
        out = self.boot("basic basic/serial.bas", "9600", "hello ape", "basic basic/serial.bas", "300", "ok")
        self.assertIn("ECHO: HELLO APE", out)
        self.assertIn("ECHO: OK", out)


class TestBasic(SystemTest):
    def test_interactive_and_errors(self):
        out = self.boot(
            "basic",
            'PRINT 2 + 3 * 4, "X"; LEN("ABC")',
            "10 FOR I = 1 TO 3 : PRINT I; : NEXT I",
            "20 PRINT",
            "RUN",
            "PRINT 1 / 0",
            "GOTO 999",
            'PRINT "A" + 1',
            "PRINT PEEK(&H9000)",
            "PID = 3",
            "BYE")
        self.assertIn("14            X3", out)
        self.assertIn("123", out)
        for err in ("?DIVISION BY ZERO ERROR", "?UNDEF'D STATEMENT 999 ERROR", "?TYPE MISMATCH ERROR",
                    "?PAGE FAULT ERROR", "?PID IS RESERVED ERROR"):
            self.assertIn(err, out)

    def test_save_and_load(self):
        name = "zz_systemtest"
        path = os.path.join(DRIVE_A, name + ".bas")
        try:
            out = self.boot("basic", '10 PRINT "SAVED OK"', f'SAVE "{name}"', "NEW", f'LOAD "{name}"', "RUN", "BYE",
                            f"type {name}.bas")
            self.assertIn(f"SAVED {name}.bas", out)
            self.assertIn("SAVED OK", out)
            self.assertIn('10 PRINT "SAVED OK"', out)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_system_keywords(self):
        out = self.boot("basic", 'P = SPAWN("counter 30") : PRINT "PID"; P; PNAME$(P)', "PRINT NPROC, CPU$, RAMSIZE",
                        "KILL P", 'PRINT INP(&H0FFF), IOBASE("pci0"), IOBASE("bus1")', "KILL PID")
        self.assertIn("PID2counter", out)
        self.assertRegex(out, r"2\s+aPE-P1\s+16384")
        self.assertRegex(out, r"255\s+-1\s+32")
        self.assertIn("killed by BASIC", out)
        self.assertNotIn("READY.\nREADY.\nREADY.\nREADY.\nREADY.\nREADY.\nREADY.", out)  # BASIC really ended


class TestDevices(SystemTest):
    def test_unhandled_irq_is_masked(self):
        out = self.boot("basic", 'U = IOBASE("bus1") : OUT U + 2, 3 : OUT U, 65', "SLEEP 0.2", "BYE", "lsdev")
        self.assertIn("no driver for aPE-U1 UART (UART); IRQ 1 masked.", out)
        self.assertIn("(IRQ masked: no driver)", out)

    def test_banana_editor(self):
        name = "zz_systemtest.txt"
        path = os.path.join(DRIVE_A, name)
        try:
            out = self.boot(f"banana {name}", "first line", "second line", ":p", ":wq", f"type {name}")
            self.assertIn("2| second line", out)
            self.assertIn(f"File '{name}' saved successfully.", out)
            with open(path) as f:
                self.assertEqual(f.read(), "first line\nsecond line\n")
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestWatchdogReader(unittest.TestCase):
    """The Watchdog's window can't be tested here, but how it reads RAM can."""

    def test_reads_a_ram_file(self):
        try:
            import tkinter  # noqa: F401  (the Watchdog module imports it)
        except ImportError:
            self.skipTest("tkinter is not installed")
        sys.path.insert(0, ROOT)
        import ape_watchdog
        from devices.internal.A.apeos.system2.sys import aperam
        with tempfile.TemporaryDirectory() as tmp:
            run_aPEOSI(["exit"], board=board_spec(tmp))
            reader = ape_watchdog.RamFile(os.path.join(tmp, "ram0.aperam"))
            header = aperam.parse_header(reader.snapshot())
            reader._close()
        self.assertEqual((header["ram_name"], header["num_pages"], header["os_version"]),
                         ("aPE-R16K", 64, "1.2 alpha"))


if __name__ == "__main__":
    unittest.main()
