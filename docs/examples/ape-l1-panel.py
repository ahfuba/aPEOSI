"""
aPE-L1 Panel: an example bus device for aPE-DevKit.

A front panel with 8 LEDs and a push button, the kind of thing you'd wire to a
microcontroller. It shows every DevKit feature: parameters, regions,
registers with bit fields, read-only registers and initial data.

Build it:     python ape_devkit.py build docs/examples/ape-l1-panel.py
Inspect it:   python ape_devkit.py info docs/examples/ape-l1-panel.apebus
"""

from apedk import Device, Field

DEVICE = Device("BUS", "aPE-L1 Panel", version=1, description="8 LEDs and a push button")

DEVICE.param("leds", 8)
DEVICE.param("blink_hz", 2)

# 16 bytes of registers, then a 32-byte pattern buffer
DEVICE.region("io", size=16, kind="registers", description="panel registers")
DEVICE.region("pattern", size=32, kind="buffer", description="LED patterns to play")

DEVICE.register("LEDS", "io", offset=0x0, width=8, description="one bit per LED, 1 = lit")
DEVICE.register("CTRL", "io", offset=0x1, width=8, reset=0x01, description="panel control", fields=[
    Field("ENABLE", lsb=0, description="1 = panel on"),
    Field("BLINK", lsb=1, width=2, description="0 steady, 1 slow, 2 fast"),
    Field("PLAY", lsb=3, description="1 = play the pattern buffer"),
])
DEVICE.register("BUTTON", "io", offset=0x2, width=8, access="r", description="button state", fields=[
    Field("DOWN", lsb=0, description="1 while pressed"),
    Field("CLICKED", lsb=1, description="set by a press; cleared when read"),
])
DEVICE.register("PRESSES", "io", offset=0x4, width=32, access="r", description="total button presses")

# A built-in "knight rider" pattern: one lit LED walking left
DEVICE.init("pattern", bytes(1 << i for i in range(8)))
