"""
Tests for the motherboard runtime: sockets, I/O map, interrupts, device logic.

Run from the project folder:   python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from devices.internal.A.apeos.system2.sys import hardware  # noqa: E402
from devices.internal.A.apeos.system2.sys.board import FLOATING_BUS, Motherboard, SocketError  # noqa: E402

MB = os.path.join(ROOT, "motherboard")
TIMER = os.path.join(MB, "bus", "ape-t1-timer.py")
UART = os.path.join(MB, "bus", "ape-u1-uart.py")
ECHO = os.path.join(MB, "serial", "ape-e1-echo.py")


def make_board(tmp, sockets):
    spec = {"name": "aPE-B9 Test", "cpu": os.path.join(MB, "cpu", "ape-p1.json"),
            "ram": os.path.join(MB, "ram", "ape-r16k.json"), "sockets": sockets}
    path = os.path.join(tmp, "board.json")
    with open(path, "w") as f:
        json.dump(spec, f)
    return hardware.load_board(tmp, path)


class SocketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = None

    def tearDown(self):
        if self.board:
            self.board.close()
        self.tmp.cleanup()

    def power_on(self, sockets):
        self.board = Motherboard(make_board(self.tmp.name, sockets), self.tmp.name)
        self.board.power_on()
        return self.board

    def standard(self):
        return self.power_on([
            {"id": "bus0", "type": "bus", "device": TIMER},
            {"id": "bus1", "type": "bus", "device": UART},
            {"id": "pci0", "type": "pci", "device": None},
            {"id": "com1", "type": "ser", "device": ECHO, "controller": "bus1"},
        ])

    def ticks(self, socket_id, n):
        sock = self.board.by_id[socket_id]
        for _ in range(n):
            sock.logic.tick()


class TestEnumeration(SocketTest):
    def test_windows_irqs_and_files(self):
        mb = self.standard()
        timer, uart, com1 = mb.by_id["bus0"], mb.by_id["bus1"], mb.by_id["com1"]
        self.assertEqual((timer.io_base, timer.io_size, timer.irq), (0x0000, 16, 0))
        self.assertEqual((uart.io_base, uart.io_size, uart.irq), (0x0020, 32, 1))  # 32-byte window, aligned
        self.assertIsNone(com1.io_base)  # serial devices have no addresses
        self.assertFalse(mb.by_id["pci0"].present)
        for name in ("bus0.apebus", "bus1.apebus", "com1.apeser", "board0.apemb"):
            self.assertTrue(os.path.exists(os.path.join(self.tmp.name, name)), name)

    def test_device_must_fit_its_socket(self):
        with self.assertRaises(SocketError):
            self.power_on([{"id": "pci0", "type": "pci", "device": TIMER}])

    def test_empty_ports_float(self):
        mb = self.standard()
        self.assertEqual(mb.io_read(0x0FFF), FLOATING_BUS)
        mb.io_write(0x0FFF, 1)  # ignored, no error


class TestTimer(SocketTest):
    def test_periodic_timer_raises_and_clears_irq(self):
        mb = self.standard()
        base = mb.by_id["bus0"].io_base
        mb.io_write(base + 4, 3)        # LOAD = 3
        mb.io_write(base + 0, 0b111)    # ENABLE | PERIODIC | IRQ_EN
        self.assertEqual(mb.io_read(base + 8), 3)  # COUNT loaded
        self.ticks("bus0", 2)
        self.assertEqual(mb.pending(), [])
        self.ticks("bus0", 1)
        self.assertEqual(mb.pending(), [0])
        self.assertEqual(mb.io_read(base + 1) & 1, 1)  # STATUS.FIRED
        mb.io_write(base + 1, 1)        # write 1 to clear
        self.assertEqual(mb.pending(), [])
        self.assertEqual(mb.io_read(base + 8), 3)  # reloaded
        self.ticks("bus0", 6)
        self.assertEqual(mb.io_read(base + 12), 3)  # fired three times in total

    def test_one_shot_stops(self):
        mb = self.standard()
        base = mb.by_id["bus0"].io_base
        mb.io_write(base + 4, 2)
        mb.io_write(base + 0, 0b001)    # ENABLE only: one-shot, no IRQ
        self.ticks("bus0", 5)
        self.assertEqual(mb.io_read(base + 0) & 1, 0)  # disabled itself
        self.assertEqual(mb.io_read(base + 12), 1)
        self.assertEqual(mb.pending(), [])

    def test_read_only_register_ignores_writes(self):
        mb = self.standard()
        base = mb.by_id["bus0"].io_base
        mb.io_write(base + 12, 99)       # FIRES is read-only
        self.assertEqual(mb.io_read(base + 12), 0)

    def test_masked_irq_is_not_pending(self):
        mb = self.standard()
        base = mb.by_id["bus0"].io_base
        mb.io_write(base + 4, 1)
        mb.io_write(base + 0, 0b101)
        self.ticks("bus0", 1)
        mb.mask_irq(0)
        self.assertEqual(mb.pending(), [])


class TestSerial(SocketTest):
    def send(self, mb, text):
        base = mb.by_id["bus1"].io_base
        for ch in text:
            mb.io_write(base, ord(ch))
            for _ in range(10):
                self.ticks("bus1", 1)
                if mb.io_read(base + 1) & 1:  # TX_READY again: byte has left
                    break

    def test_echo_through_uart(self):
        mb = self.standard()
        base = mb.by_id["bus1"].io_base
        self.send(mb, "hi!")
        self.assertEqual(mb.io_read(base + 3), 3)  # RX_COUNT
        received = "".join(chr(mb.io_read(base)) for _ in range(3))
        self.assertEqual(received, "HI!")          # the plug upper-cases letters
        self.assertEqual(mb.io_read(base + 1) & 2, 0)  # RX_READY cleared

    def test_slow_baud_takes_longer(self):
        mb = self.standard()
        base = mb.by_id["bus1"].io_base
        mb.io_write(base + 4, 1000)     # 1000 baud: 10 bits = 10 ms per byte
        mb.io_write(base, ord("x"))
        self.ticks("bus1", 9)
        self.assertEqual(mb.io_read(base + 3), 0)  # still on the wire
        self.ticks("bus1", 1)
        self.assertEqual(mb.io_read(base + 3), 1)

    def test_fifo_overrun(self):
        mb = self.standard()
        base = mb.by_id["bus1"].io_base
        self.send(mb, "x" * 20)          # 20 echoes into a 16-byte FIFO, never read
        self.assertEqual(mb.io_read(base + 3), 16)
        self.assertEqual(mb.io_read(base + 1) & 4, 4)  # STATUS.OVERRUN

    def test_rx_irq(self):
        mb = self.standard()
        base = mb.by_id["bus1"].io_base
        mb.io_write(base + 2, 0b11)      # ENABLE | RX_IRQ
        self.send(mb, "a")
        self.assertEqual(mb.pending(), [1])
        mb.io_read(base)                 # take the byte
        self.assertEqual(mb.pending(), [])


class TestFaults(SocketTest):
    def test_crashing_device_is_isolated(self):
        bad = os.path.join(self.tmp.name, "ape-x1-bad.py")
        with open(bad, "w") as f:
            f.write("from apedk import Device, DeviceLogic\n"
                    "DEVICE = Device('BUS', 'aPE-X1 Bad', function='BAD')\n"
                    "DEVICE.region('r', size=16, kind='registers')\n"
                    "DEVICE.register('R', 'r', 0)\n"
                    "DEVICE.param('clock_hz', 1000)\n"
                    "class LOGIC(DeviceLogic):\n"
                    "    def tick(self):\n"
                    "        raise RuntimeError('smoke')\n")
        mb = self.power_on([{"id": "bus0", "type": "bus", "device": bad}])
        sock = mb.by_id["bus0"]
        mb._call(sock, "tick")
        self.assertIn("smoke", sock.faulted)
        mb.advance()                      # no exception, device stays faulted


class TestBoardValidation(unittest.TestCase):
    def check(self, sockets):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(hardware.HardwareError):
                make_board(tmp, sockets)

    def test_bad_socket_lists(self):
        self.check([{"id": "bus0", "type": "bus"}, {"id": "bus0", "type": "bus"}])   # duplicate id
        self.check([{"id": "isa0", "type": "isa"}])                                  # unknown type
        self.check([{"id": "BUS!", "type": "bus"}])                                  # bad id
        self.check([{"id": "com1", "type": "ser", "device": ECHO}])                  # no controller
        self.check([{"id": "usb0", "type": "usb", "device": ECHO}])                  # USB not built yet


if __name__ == "__main__":
    unittest.main()
