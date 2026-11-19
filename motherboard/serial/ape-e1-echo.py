"""
aPE-E1 Echo: a serial loopback plug.

Real technicians plugged a "loopback plug" into a serial port to test it:
every byte sent comes straight back. This one can also shout: with
"uppercase" set, letters come back in upper case, so you can tell the
echo apart from what you sent.

It plugs into a serial port (SER socket). Serial devices have no addresses:
they only see a stream of bytes, one at a time, through on_serial().
"""

from apedk import Device, DeviceLogic

DEVICE = Device("SER", "aPE-E1 Echo", function="ECHO", version=1,
                description="serial loopback plug: sends back every byte it receives")
DEVICE.param("uppercase", True)

DEVICE.region("stats", size=8, kind="registers")
DEVICE.register("RECEIVED", "stats", offset=0x0, width=32, access="r", description="bytes received")
DEVICE.register("LAST", "stats", offset=0x4, width=8, access="r", description="last byte received")


class LOGIC(DeviceLogic):
    def on_serial(self, byte):
        self.set("RECEIVED", self.reg("RECEIVED") + 1)
        self.set("LAST", byte)
        if self.param("uppercase") and 97 <= byte <= 122:
            byte -= 32
        self.serial_send(byte)
