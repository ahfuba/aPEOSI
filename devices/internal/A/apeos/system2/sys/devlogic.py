"""
Device logic: what a device *does*.

A device's descriptor (apedesc.py) is its datasheet: registers and memory.
Its logic is the circuit inside: the state machine that reacts when the OS
touches a register and keeps running on the device's own clock.

A device source file (.py) may define a LOGIC class, a subclass of
DeviceLogic. The motherboard calls its hooks through the socket:

    reset()                 power-on
    read(name)  -> value    the OS read register `name` (side effects allowed)
    write(name, value)      the OS wrote register `name`
    tick()                  one tick of the device clock (param "clock_hz")
    on_serial(byte)         a byte arrived on the device's serial line

Everything a device remembers between ticks should live in its registers
or regions: they are stored in the device's file, so tools can watch it.

Keep this file free of aPEOSI imports (except apedesc/apedev).
"""

import mmap
import os

from . import apedesc


class DeviceInstance:
    """A powered-on device: its file, mapped into memory, plus helpers."""

    def __init__(self, desc, path):
        self.desc = desc
        self.path = path
        apedesc.create_instance(desc, path)        # power on: reset values, INIT data
        self._file = open(path, "r+b")
        self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_WRITE)
        self.base = desc.header_size               # where the data area starts

    def close(self):
        if self._mm is not None:
            self._mm.close()
            self._file.close()
            self._mm = None

    # --- raw access to the data area (offsets from its start) ---------------------
    def read_bytes(self, offset, n):
        return bytes(self._mm[self.base + offset:self.base + offset + n])

    def write_bytes(self, offset, data):
        self._mm[self.base + offset:self.base + offset + len(data)] = data

    # --- registers ------------------------------------------------------------------
    def reg_value(self, reg):
        return int.from_bytes(self.read_bytes(self.desc.reg_offset(reg), reg.width // 8), "little")

    def set_reg_value(self, reg, value):
        size = reg.width // 8
        self.write_bytes(self.desc.reg_offset(reg), (value & ((1 << reg.width) - 1)).to_bytes(size, "little"))


class DeviceLogic:
    """
    Base class for device behaviour. With no overrides a device is just a
    set of plain registers: reads return what was stored, writes store,
    and writes to read-only registers are ignored.
    """

    def __init__(self, instance: DeviceInstance, board, socket_id):
        self.dev = instance
        self.desc = instance.desc
        self._board = board
        self.socket_id = socket_id

    # --- hooks for subclasses -------------------------------------------------------
    def reset(self):
        pass

    def read(self, name):
        return self.reg(name)

    def write(self, name, value):
        if "w" in self.desc.reg(name).access:
            self.set(name, value)

    def tick(self):
        pass

    def on_serial(self, byte):
        pass

    # --- helpers --------------------------------------------------------------------
    def reg(self, name):
        """Current value of a register."""
        return self.dev.reg_value(self._reg(name))

    def set(self, name, value):
        """Store a register value (from the device's side: access rules don't apply)."""
        self.dev.set_reg_value(self._reg(name), value)

    def field(self, path):
        """Value of a bit field, e.g. field("CTRL.ENABLE")."""
        reg, f = self._field(path)
        return (self.dev.reg_value(reg) & f.mask) >> f.lsb

    def set_field(self, path, value):
        reg, f = self._field(path)
        old = self.dev.reg_value(reg)
        self.dev.set_reg_value(reg, (old & ~f.mask) | ((value << f.lsb) & f.mask))

    def param(self, name, default=None):
        return self.desc.params.get(name, default)

    def region_read(self, name, offset, n):
        return self.dev.read_bytes(self.desc.region(name).offset + offset, n)

    def region_write(self, name, offset, data):
        self.dev.write_bytes(self.desc.region(name).offset + offset, bytes(data))

    def irq(self, level):
        """Raise (True) or lower (False) this device's interrupt line."""
        self._board.set_irq_line(self.socket_id, bool(level))

    def serial_send(self, byte):
        """Send one byte down this device's serial line (to whatever is plugged in)."""
        self._board.serial_send(self.socket_id, byte & 0xFF)

    def _reg(self, name):
        reg = self.desc.reg(name)
        if reg is None:
            raise KeyError(f"{self.desc.model} has no register {name}")
        return reg

    def _field(self, path):
        name, _, fname = path.partition(".")
        reg = self._reg(name)
        for f in reg.fields:
            if f.name == fname:
                return reg, f
        raise KeyError(f"register {name} has no field {fname}")
