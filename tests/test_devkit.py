"""
Tests for aPE-DevKit and the device descriptor format.

Run from the project folder:   python -m unittest discover tests
"""

import glob
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from apedk import DevKitError, Device, Field, create_instance, from_json, load  # noqa: E402
from devices.internal.A.apeos.system2.sys import apedesc, hardware  # noqa: E402
from devices.internal.A.apeos.system2.sys.apedev import (COMMON_SIZE, parse_common)  # noqa: E402


def sample_device():
    dev = Device("BUS", "aPE-L1 Panel", version=3, description="8 LEDs and a button")
    dev.param("leds", 8).param("ratio", 0.5).param("label", "front").param("dimmable", True)
    dev.region("io", size=16, kind="registers", description="control")
    dev.region("pattern", size=64, kind="buffer", align=64)
    dev.register("LEDS", "io", offset=0, width=8, description="one bit per LED")
    dev.register("CTRL", "io", offset=2, width=16, reset=0x0103, fields=[
        Field("ENABLE", lsb=0, description="1 = on"),
        Field("BLINK", lsb=1, width=2),
        Field("BRIGHT", lsb=8, width=4),
    ])
    dev.register("COUNT", "io", offset=4, width=32, access="r", reset=0xDEADBEEF)
    dev.init("pattern", b"\x01\x02\x04\x08", offset=4)
    return dev


class TestBuildAndRead(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        path = sample_device().build(directory=self.dir)
        self.assertEqual(os.path.basename(path), "ape-l1-panel.apebus")  # NAMING.md file name
        d = load(path).desc
        self.assertEqual((d.model, d.version, d.description), ("aPE-L1 Panel", 3, "8 LEDs and a button"))
        self.assertEqual(d.params, {"leds": 8, "ratio": 0.5, "label": "front", "dimmable": True})
        self.assertEqual([(r.name, r.offset, r.size, r.kind) for r in d.regions],
                         [("io", 0, 16, "registers"), ("pattern", 64, 64, "buffer")])
        ctrl = d.registers[1]
        self.assertEqual((ctrl.name, ctrl.region, ctrl.offset, ctrl.width, ctrl.reset), ("CTRL", "io", 2, 16, 0x0103))
        self.assertEqual([(f.name, f.lsb, f.width) for f in ctrl.fields],
                         [("ENABLE", 0, 1), ("BLINK", 1, 2), ("BRIGHT", 8, 4)])
        self.assertEqual(d.registers[2].access, "r")
        self.assertEqual(d.inits[0].data, b"\x01\x02\x04\x08")

    def test_module_header(self):
        data = sample_device().compile()
        common = parse_common(data)
        self.assertTrue(common["is_module"])
        self.assertFalse(common["persistent"])
        self.assertEqual(common["header_size"] % apedesc.DATA_ALIGN, 0)
        self.assertEqual(common["device_size"], common["header_size"] + 128)

    def test_instance_has_reset_values_and_init_data(self):
        dev = sample_device()
        path = dev.instantiate(os.path.join(self.dir, "bus0.apebus"))
        with open(path, "rb") as f:
            image = f.read()
        common = parse_common(image)
        self.assertFalse(common["is_module"])
        d = apedesc.decode_descriptor(image)
        self.assertEqual(len(image), d.instance_size)
        ctrl = d.address("io", 2)
        self.assertEqual(struct.unpack_from("<H", image, ctrl)[0], 0x0103)
        self.assertEqual(struct.unpack_from("<I", image, d.address("io", 4))[0], 0xDEADBEEF)
        self.assertEqual(image[d.address("pattern", 4):d.address("pattern", 8)], b"\x01\x02\x04\x08")

    def test_disks_are_never_overwritten(self):
        disk = Device("DISK", "aPE-D1").region("blocks", size=4096)
        path = os.path.join(self.dir, "disk0.apedisk")
        disk.instantiate(path)
        with open(path, "r+b") as f:  # "save a file" on the disk
            f.seek(-1, 2)
            f.write(b"\x42")
        with self.assertRaises(FileExistsError):
            disk.instantiate(path)
        with open(path, "rb") as f:
            self.assertEqual(f.read()[-1], 0x42)  # data survived
        self.assertTrue(parse_common(disk.compile())["persistent"])

    def test_unknown_chunks_are_skipped(self):
        # A chunk from some future format version, inserted right after INFO:
        # older readers must skip it and still read everything else.
        data = bytearray(sample_device().compile())
        info_len = struct.unpack_from("<I", data, COMMON_SIZE + 4)[0]
        after_info = COMMON_SIZE + 8 + info_len + (-info_len) % 4
        data[after_info:after_info] = b"ZZZZ" + struct.pack("<I", 5) + b"hello" + b"\x00" * 3
        struct.pack_into("<H", data, 10, apedesc.align_up(len(data), apedesc.DATA_ALIGN))  # header_size
        d = apedesc.decode_descriptor(bytes(data))
        self.assertEqual(d.params["leds"], 8)
        self.assertEqual(len(d.registers), 3)

    def test_wrong_extension_is_refused(self):
        with self.assertRaises(DevKitError):
            sample_device().build(os.path.join(self.dir, "panel.apegpu"))


class TestValidation(unittest.TestCase):
    def errors(self, dev):
        return dev.validate()[0]

    def test_good_device_has_no_errors_or_warnings(self):
        self.assertEqual(sample_device().validate(), ([], []))

    def test_overlaps(self):
        dev = Device("GPU", "aPE-G9").region("a", size=8, offset=0).region("b", size=8, offset=4)
        self.assertTrue(any("overlap" in e for e in self.errors(dev)))
        dev = Device("GPU", "aPE-G9").region("r", size=8, kind="registers")
        dev.register("X", "r", 0, width=16).register("Y", "r", 1)
        self.assertTrue(any("overlap" in e for e in self.errors(dev)))

    def test_register_rules(self):
        dev = Device("GPU", "aPE-G9").region("r", size=4, kind="registers")
        dev.register("WIDTH", "r", 0, width=12)
        dev.register("ALIGN", "r", 1, width=16)
        dev.register("RESET", "r", 0, width=8, reset=256)
        dev.register("OUTSIDE", "r", 4)
        dev.register("NOREGION", "nope", 0)
        text = "\n".join(self.errors(dev))
        for word in ("8, 16 or 32", "boundary", "does not fit in 8 bits", "does not fit in region", "no region"):
            self.assertIn(word, text)

    def test_fields(self):
        dev = Device("GPU", "aPE-G9").region("r", size=4, kind="registers")
        dev.register("R", "r", 0, fields=[Field("A", 0, 4), Field("B", 2, 2), Field("C", 7, 2)])
        text = "\n".join(self.errors(dev))
        self.assertIn("overlaps another field", text)
        self.assertIn("outside the 8-bit register", text)

    def test_naming_warnings(self):
        _, warnings = Device("GPU", "aPE-X1").region("v", size=4).validate()
        self.assertTrue(any("letter G" in w for w in warnings))
        _, warnings = Device("CPU", "my cpu").validate()
        self.assertTrue(any("NAMING.md" in w for w in warnings))
        self.assertTrue(self.errors(Device("GPU", "aPE-G1 Much Too Long Name")))
        self.assertTrue(self.errors(Device("TOASTER", "aPE-T1")))

    def test_errors_stop_compile(self):
        dev = Device("GPU", "aPE-G9").region("a", size=0)
        with self.assertRaises(DevKitError) as ctx:
            dev.compile()
        self.assertTrue(ctx.exception.errors)


class TestMotherboardModules(unittest.TestCase):
    """Every JSON module in /motherboard compiles, and aPEOSI boots from the compiled files."""

    def test_all_specs_compile_and_load_the_same(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        specs = glob.glob(os.path.join(ROOT, "motherboard", "*", "*.json"))
        self.assertTrue(specs)
        for spec in specs:
            with self.subTest(spec=os.path.basename(spec)):
                dev = from_json(spec)
                self.assertEqual(dev.validate(), ([], []))
                path = dev.build(directory=tmp.name)
                loader = hardware.load_cpu if "/cpu/" in spec.replace("\\", "/") else hardware.load_ram
                self.assertEqual({**loader(spec).__dict__, "source": None},
                                 {**loader(path).__dict__, "source": None})

    def test_board_with_compiled_modules(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cpu = from_json(os.path.join(ROOT, "motherboard", "cpu", "ape-p1.json")).build(directory=tmp.name)
        ram = from_json(os.path.join(ROOT, "motherboard", "ram", "ape-r64k.json")).build(directory=tmp.name)
        board = os.path.join(tmp.name, "board.json")
        with open(board, "w") as f:
            f.write('{"name": "t", "cpu": "%s", "ram": "%s"}' % (os.path.basename(cpu), os.path.basename(ram)))
        b = hardware.load_board(tmp.name, board)
        self.assertEqual((b.cpu.name, b.cpu.clock_hz, b.ram.size), ("aPE-P1", 200, 65536))

    def test_wrong_class_module_is_refused(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cpu = from_json(os.path.join(ROOT, "motherboard", "cpu", "ape-p1.json")).build(directory=tmp.name)
        with self.assertRaises(hardware.HardwareError):
            hardware.load_ram(cpu)


if __name__ == "__main__":
    unittest.main()
