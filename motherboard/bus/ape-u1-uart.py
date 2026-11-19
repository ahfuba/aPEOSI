"""
aPE-U1 UART: the chip behind a serial port (the PC's version is the 8250/16550).

A UART turns bytes into a serial bit stream and back. It sits on the on-board
system bus (registers the OS can read and write) and drives a serial port
(a byte-stream socket, e.g. COM1) where serial devices plug in.

How it works:
    Sending: the OS writes a byte to DATA. If the transmitter is free, the
    byte is held while it is "on the wire": at BAUD bits per second, one
    byte (1 start bit + 8 data bits + 1 stop bit = 10 bits) takes 10/BAUD
    seconds. Then it leaves through the serial port and STATUS.TX_READY
    goes back to 1. Writing while TX_READY is 0 loses the byte, as on a
    real UART without a FIFO.

    Receiving: bytes arriving from the serial port go into a 16-byte FIFO.
    STATUS.RX_READY says a byte is waiting; reading DATA takes the oldest one
    out. If the FIFO is full, the new byte is lost and STATUS.OVERRUN is set.
    With CTRL.RX_IRQ set, the IRQ line is high while bytes are waiting.

Bytes on the wire are timed, so a slow BAUD really is slow.
"""

from apedk import Device, DeviceLogic, Field

FIFO = 16

DEVICE = Device("BUS", "aPE-U1 UART", function="UART", version=1,
                description="serial port controller with a 16-byte receive FIFO")
DEVICE.param("clock_hz", 1000)

DEVICE.region("regs", size=16, kind="registers")
DEVICE.register("DATA", "regs", offset=0x0, width=8,
                description="write: send a byte; read: take the oldest received byte")
DEVICE.register("STATUS", "regs", offset=0x1, width=8, access="r", reset=0x01, fields=[
    Field("TX_READY", lsb=0, description="1 = the transmitter can take a byte"),
    Field("RX_READY", lsb=1, description="1 = a received byte is waiting"),
    Field("OVERRUN", lsb=2, description="a byte was lost because the FIFO was full"),
])
DEVICE.register("CTRL", "regs", offset=0x2, width=8, reset=0x01, fields=[
    Field("ENABLE", lsb=0, description="1 = UART on"),
    Field("RX_IRQ", lsb=1, description="1 = IRQ while received bytes are waiting"),
])
DEVICE.register("RX_COUNT", "regs", offset=0x3, width=8, access="r", description="bytes waiting in the FIFO")
DEVICE.register("BAUD", "regs", offset=0x4, width=16, reset=9600, description="bits per second")
DEVICE.register("TX_BYTE", "regs", offset=0x6, width=8, access="r", description="byte on the wire right now")
DEVICE.register("TX_LEFT", "regs", offset=0x8, width=32, access="r",
                description="time left for the byte on the wire, in 1/1000 bit")
DEVICE.region("rx_fifo", size=FIFO, kind="buffer", access="r", description="receive FIFO, oldest byte first")


class LOGIC(DeviceLogic):
    def write(self, name, value):
        if name == "DATA":
            if self.field("CTRL.ENABLE") and self.field("STATUS.TX_READY"):
                self.set("TX_BYTE", value)
                self.set("TX_LEFT", 10 * 1000)              # 10 bits on the wire
                self.set_field("STATUS.TX_READY", 0)
            return
        super().write(name, value)

    def read(self, name):
        if name != "DATA":
            return self.reg(name)
        count = self.reg("RX_COUNT")
        if not count:
            return 0
        fifo = self.region_read("rx_fifo", 0, FIFO)
        byte = fifo[0]
        self.region_write("rx_fifo", 0, fifo[1:] + b"\x00")  # shift the queue
        self._set_count(count - 1)
        return byte

    def tick(self):
        """One millisecond: the byte on the wire moves BAUD bits further."""
        left = self.reg("TX_LEFT")
        if not left:
            return
        left -= self.reg("BAUD")                             # BAUD bits per second = BAUD/1000 per ms
        if left > 0:
            self.set("TX_LEFT", left)
            return
        self.set("TX_LEFT", 0)
        self.set_field("STATUS.TX_READY", 1)
        self.serial_send(self.reg("TX_BYTE"))                # out through the serial port

    def on_serial(self, byte):
        if not self.field("CTRL.ENABLE"):
            return
        count = self.reg("RX_COUNT")
        if count >= FIFO:
            self.set_field("STATUS.OVERRUN", 1)
            return
        self.region_write("rx_fifo", count, bytes([byte]))
        self._set_count(count + 1)

    def _set_count(self, count):
        self.set("RX_COUNT", count)
        self.set_field("STATUS.RX_READY", 1 if count else 0)
        self.irq(bool(count) and bool(self.field("CTRL.RX_IRQ")))
