"""
The motherboard at runtime: sockets, the I/O address map, the interrupt
controller, device clocks and serial links. Spec: docs/aPE-Socket.md.

    OS  ──io_read/io_write(port)──►  address decoder ──► socket ──► device logic
    OS  ◄──pending IRQs────────────  interrupt controller ◄── device IRQ lines
    board.advance() ──► every device's tick(), at its own clock_hz

The board's own state (socket table, IRQ lines and mask, interrupt counts)
lives in board0.apemb, so tools can watch the interrupt controller too.
"""

import os
import runpy
import struct
import time

from . import apedesc
from .apedesc import Descriptor, Field, Region, Register
from .apedev import (CLASS_BUS, CLASS_MOTHERBOARD, CLASS_PCI, CLASS_SER, CLASS_USB, EXTENSIONS,
                     class_name)
from .devlogic import DeviceInstance, DeviceLogic

IO_BUS_BASE = 0x0000       # on-board devices
IO_PCI_BASE = 0x1000       # expansion cards
IO_MIN_WINDOW = 16
MAX_IRQ = 16
MAX_TICKS = 5000           # per device per advance(); a slow host makes devices fall behind
FLOATING_BUS = 0xFF        # what a read from an empty address returns, as on real buses

SOCKET_TYPES = {"bus": CLASS_BUS, "pci": CLASS_PCI, "ser": CLASS_SER, "usb": CLASS_USB}
SOCKET_ENTRY = struct.Struct("<8s4sHHBB14s")   # id, type, io base, io size, irq, present, model


class SocketError(Exception):
    """A device could not be plugged in."""


def load_device_source(path):
    """
    Loads a device for a socket. Returns (descriptor, logic class or None).
    .py sources may define LOGIC; JSON specs and compiled modules have no logic.
    """
    import apedk  # the toolkit lives at the project root; only needed for sources

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".py":
            namespace = runpy.run_path(path, run_name="__apedevice__")
            device = namespace.get("DEVICE")
            if not isinstance(device, apedk.Device):
                raise SocketError(f"{path}: must define DEVICE = Device(...)")
            logic = namespace.get("LOGIC")
            if logic is not None and not (isinstance(logic, type) and issubclass(logic, DeviceLogic)):
                raise SocketError(f"{path}: LOGIC must be a DeviceLogic subclass")
        elif ext == ".json":
            device, logic = apedk.from_json(path), None
        else:
            device, logic = apedk.load(path), None
        errors, _ = device.validate()
    except FileNotFoundError:
        raise SocketError(f"device file not found: {path}")
    except (apedk.DevKitError, apedesc.DescriptorError) as e:
        raise SocketError(f"{path}: {e}")
    if errors:
        raise SocketError(f"{path}: " + "; ".join(errors))
    return device.desc, logic


class Socket:
    def __init__(self, sid, stype, source, controller=None):
        self.id = sid
        self.type = stype             # class code, e.g. CLASS_BUS
        self.source = source          # device file, or None for an empty socket
        self.controller = controller  # serial ports: the UART socket that drives them
        self.desc = None
        self.instance = None
        self.logic = None
        self.irq = None
        self.io_base = None
        self.io_size = 0
        self.clock_hz = 0
        self._owed = 0.0
        self._last = 0.0
        self.faulted = None

    @property
    def present(self):
        return self.logic is not None

    @property
    def function(self):
        return self.desc.function if self.desc else ""


def _window_size(data_size):
    size = IO_MIN_WINDOW
    while size < data_size:
        size *= 2
    return size


class Motherboard:
    def __init__(self, board_spec, runtime_dir):
        self.spec = board_spec
        self.dir = runtime_dir
        self.sockets = []
        self.by_id = {}
        self.links = {}               # serial line: socket id -> socket id at the other end
        self.irq_lines = 0
        self.irq_mask = 0
        self.irq_counts = [0] * MAX_IRQ
        self.mb = None

    # ================================================================ power on ===
    def power_on(self):
        """Plugs every device in, assigns I/O windows and IRQs. Returns report lines."""
        report = []
        next_io = {CLASS_BUS: IO_BUS_BASE, CLASS_PCI: IO_PCI_BASE}
        next_irq = 0
        for cfg in self.spec.sockets:
            sock = Socket(cfg["id"], SOCKET_TYPES[cfg["type"]], cfg.get("device"), cfg.get("controller"))
            self.sockets.append(sock)
            self.by_id[sock.id] = sock
            if sock.source is None:
                report.append(f"{sock.id:<6} {class_name(sock.type):<4} (empty)")
                continue
            desc, logic_cls = load_device_source(sock.source)
            if desc.device_class != sock.type:
                raise SocketError(f"{desc.model} is a {class_name(desc.device_class)} device; it does not fit "
                                  f"socket {sock.id} ({class_name(sock.type)})")
            sock.desc = desc
            if sock.type in next_io:  # register-based sockets get an I/O window and an IRQ line
                sock.io_size = _window_size(desc.data_size)
                base = apedesc.align_up(next_io[sock.type], sock.io_size)
                sock.io_base, next_io[sock.type] = base, base + sock.io_size
                if next_irq < MAX_IRQ:
                    sock.irq, next_irq = next_irq, next_irq + 1
            sock.clock_hz = int(desc.params.get("clock_hz", 0) or 0)
            path = os.path.join(self.dir, sock.id + EXTENSIONS[sock.type])
            sock.instance = DeviceInstance(desc, path)
            sock.logic = (logic_cls or DeviceLogic)(sock.instance, self, sock.id)
            sock._last = time.monotonic()
            self._call(sock, "reset")
            where = f"io 0x{sock.io_base:04X}-0x{sock.io_base + sock.io_size - 1:04X}" if sock.io_base is not None else ""
            irq = f"irq {sock.irq}" if sock.irq is not None else ""
            report.append(f"{sock.id:<6} {class_name(sock.type):<4} {desc.model:<14} {desc.function:<9} {where:<18} {irq}")

        for sock in self.sockets:  # wire serial ports to their controllers
            if sock.type == CLASS_SER and sock.controller:
                ctrl = self.by_id.get(sock.controller)
                if ctrl is None or ctrl.type not in (CLASS_BUS, CLASS_PCI):
                    raise SocketError(f"serial port {sock.id}: controller '{sock.controller}' is not a bus or PCI socket")
                self.links[sock.id] = ctrl.id
                self.links[ctrl.id] = sock.id
        self._create_board_file()
        return report

    def _create_board_file(self):
        n = max(1, len(self.sockets))
        desc = Descriptor(CLASS_MOTHERBOARD, self.spec.name[:14], function="BOARD",
                          description="sockets, I/O map and interrupt controller")
        desc.regions = [
            Region("ic", 16, "registers", "rw", 0, "interrupt controller"),
            Region("irq_counts", MAX_IRQ * 4, "data", "r", 16, "interrupts delivered, per IRQ (u32)"),
            Region("sockets", n * SOCKET_ENTRY.size, "data", "r", 16 + MAX_IRQ * 4, "socket table"),
        ]
        desc.registers = [
            Register("IRQ_LINES", "ic", 0, 16, "r", 0, "current level of each IRQ line"),
            Register("IRQ_MASK", "ic", 2, 16, "rw", 0, "1 = IRQ disabled"),
        ]
        self.mb = DeviceInstance(desc, os.path.join(self.dir, "board0.apemb"))
        table = b"".join(SOCKET_ENTRY.pack(
            s.id.encode("ascii")[:8], s.type, s.io_base or 0, s.io_size,
            0xFF if s.irq is None else s.irq, int(s.present),
            (s.desc.model if s.desc else "").encode("ascii", "replace")[:14]) for s in self.sockets)
        self.mb.write_bytes(desc.region("sockets").offset, table)

    def close(self):
        for sock in self.sockets:
            if sock.instance:
                sock.instance.close()
        if self.mb:
            self.mb.close()

    # ============================================================ logic calls ===
    def _call(self, sock, hook, *args):
        """Runs a device hook. A device that crashes is marked faulted instead of crashing the OS."""
        if sock.faulted or not sock.present:
            return None
        try:
            return getattr(sock.logic, hook)(*args)
        except Exception as e:
            sock.faulted = f"{hook}: {e}"
            print(f"\n[{sock.id}] device fault in {sock.desc.model}: {sock.faulted}")
            return None

    # ================================================================== clock ===
    def advance(self):
        """Gives every device the ticks its clock owes since the last call."""
        now = time.monotonic()
        for sock in self.sockets:
            if not sock.present or not sock.clock_hz or sock.faulted:
                continue
            sock._owed += (now - sock._last) * sock.clock_hz
            sock._last = now
            ticks = min(int(sock._owed), MAX_TICKS)
            sock._owed = min(sock._owed - ticks, MAX_TICKS)
            for _ in range(ticks):
                self._call(sock, "tick")
                if sock.faulted:
                    break

    # ===================================================== interrupt controller ===
    def set_irq_line(self, socket_id, level):
        sock = self.by_id[socket_id]
        if sock.irq is None:
            return
        bit = 1 << sock.irq
        self.irq_lines = (self.irq_lines | bit) if level else (self.irq_lines & ~bit)
        self.mb.set_reg_value(self.mb.desc.reg("IRQ_LINES"), self.irq_lines)

    def pending(self):
        """IRQ numbers whose line is high and not masked."""
        active = self.irq_lines & ~self.irq_mask
        return [i for i in range(MAX_IRQ) if active & (1 << i)]

    def irq_socket(self, irq):
        return next((s for s in self.sockets if s.irq == irq), None)

    def count_irq(self, irq):
        self.irq_counts[irq] = (self.irq_counts[irq] + 1) & 0xFFFFFFFF
        self.mb.write_bytes(self.mb.desc.region("irq_counts").offset + irq * 4,
                            struct.pack("<I", self.irq_counts[irq]))

    def mask_irq(self, irq, masked=True):
        bit = 1 << irq
        self.irq_mask = (self.irq_mask | bit) if masked else (self.irq_mask & ~bit)
        self.mb.set_reg_value(self.mb.desc.reg("IRQ_MASK"), self.irq_mask)

    # ======================================================= address decoder ===
    def decode(self, port):
        """Which socket answers an I/O port. Returns (socket, offset) or (None, None)."""
        for sock in self.sockets:
            if sock.present and sock.io_base is not None and sock.io_base <= port < sock.io_base + sock.io_size:
                return sock, port - sock.io_base
        return None, None

    def _reg_at(self, sock, offset):
        for reg in sock.desc.registers:
            start = sock.desc.reg_offset(reg)
            if start <= offset < start + reg.width // 8:
                return reg, offset - start
        return None, None

    def io_read(self, port):
        sock, offset = self.decode(port)
        if sock is None or offset >= sock.desc.data_size:
            return FLOATING_BUS
        reg, byte = self._reg_at(sock, offset)
        if reg is None:  # buffer/data regions read as raw memory
            return sock.instance.read_bytes(offset, 1)[0]
        value = self._call(sock, "read", reg.name)
        if value is None:
            value = sock.instance.reg_value(reg)
        value &= (1 << reg.width) - 1
        return value if byte == 0 else (value >> (8 * byte)) & 0xFF

    def io_write(self, port, value):
        sock, offset = self.decode(port)
        if sock is None or offset >= sock.desc.data_size:
            return
        reg, byte = self._reg_at(sock, offset)
        if reg is None:
            region = next((r for r in sock.desc.regions if r.offset <= offset < r.offset + r.size), None)
            if region is not None and "w" in region.access:
                sock.instance.write_bytes(offset, bytes([value & 0xFF]))
            return
        if byte:  # writing one byte of a wider register: merge into the stored value
            old = sock.instance.reg_value(reg)
            shift = 8 * byte
            value = (old & ~(0xFF << shift)) | ((value & 0xFF) << shift)
        self._call(sock, "write", reg.name, value & ((1 << reg.width) - 1))

    def write_reg(self, socket_id, name, value):
        """Kernel helper: write a register by name, through the device's logic."""
        sock = self.by_id[socket_id]
        self._call(sock, "write", name, value)

    def read_reg(self, socket_id, name):
        sock = self.by_id[socket_id]
        value = self._call(sock, "read", name)
        return sock.instance.reg_value(sock.desc.reg(name)) if value is None else value

    # ============================================================ serial lines ===
    def serial_send(self, socket_id, byte):
        peer = self.by_id.get(self.links.get(socket_id))
        if peer is not None and peer.present:
            self._call(peer, "on_serial", byte)
