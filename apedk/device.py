"""
The Device builder: describe a device in Python, check it, compile it.

    from apedk import Device, Field

    leds = Device("BUS", "aPE-L1 Panel", function="PANEL", description="8 LEDs and a button")
    leds.region("io", size=16, kind="registers")
    leds.register("LEDS", "io", offset=0x0, width=8, description="one bit per LED")
    leds.register("CTRL", "io", offset=0x1, width=8, reset=0x01, fields=[
        Field("ENABLE", lsb=0, description="1 = panel on"),
        Field("BLINK", lsb=1, width=2, description="0 off, 1 slow, 2 fast"),
    ])
    leds.build()   # writes ape-l1-panel.apebus
"""

from __future__ import annotations

import os
import re

from devices.internal.A.apeos.system2.sys import apedesc
from devices.internal.A.apeos.system2.sys.apedesc import Descriptor, Field, Init, Region, Register
from devices.internal.A.apeos.system2.sys.apedev import (EXTENSIONS, NAME_MAX, class_code,
                                                         class_name)

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MODEL = re.compile(r"^aPE-([A-Z])[A-Za-z0-9]*( [A-Za-z0-9]+)*$")

FUNCTION = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Model letter of each device function (NAMING.md). New functions pick an unused letter.
FUNCTION_LETTERS = {
    "BOARD": "B", "CPU": "P", "RAM": "R", "GPU": "G", "DISK": "D", "NET": "N",
    "KEYBOARD": "K", "SOUND": "S", "TIMER": "T", "UART": "U", "ECHO": "E", "PANEL": "L",
}
# A socket's implied function, for sockets that only take one kind of device
SOCKET_FUNCTION = {"RAM": "RAM", "CPU": "CPU", "MB": "BOARD"}


class DevKitError(Exception):
    """The device description has errors. ``errors`` lists every one of them."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


def model_file_name(model, extension):
    """'aPE-P0 Turtle', '.apecpu' -> 'ape-p0-turtle.apecpu' (the NAMING.md rule)."""
    return model.lower().replace(" ", "-") + extension


class Device:
    """A device description under construction."""

    def __init__(self, socket, model, function=None, version=1, description=""):
        """
        socket:   which socket the device plugs into: BUS, PCI, SER, USB, RAM, CPU, MB
                  (or a medium: DISK, NET). It decides the file extension.
        function: what the device does: "TIMER", "GPU", "UART", ... (stored in the file)
        """
        code = class_code(socket) if isinstance(socket, str) else socket
        self._class_text = socket if isinstance(socket, str) else class_name(socket)
        function = (function or SOCKET_FUNCTION.get(self._class_text.upper(), "")).upper()
        self.desc = Descriptor(code or b"????", model, version, description, function)
        self._auto = []          # regions placed automatically: (region, alignment)

    # --- building --------------------------------------------------------------
    def param(self, name, value):
        """A fixed property of the device, e.g. width=160 or refresh_hz=30."""
        self.desc.params[name] = value
        return self

    def region(self, name, size, kind="data", access="rw", offset=None, align=16, description=""):
        """
        A block of the device's memory. Without ``offset`` it is placed after
        the previous region, aligned to ``align`` bytes.
        """
        r = Region(name, size, kind, access, 0 if offset is None else offset, description)
        self.desc.regions.append(r)
        if offset is None:
            self._auto.append((r, align))
        return self

    def register(self, name, region, offset, width=8, access="rw", reset=0, description="", fields=None):
        """A register at ``offset`` bytes into ``region``. ``fields`` name groups of its bits."""
        self.desc.registers.append(Register(name, region, offset, width, access, reset, description,
                                            list(fields or [])))
        return self

    def init(self, region, data, offset=0):
        """Initial contents for part of a region (e.g. a font in ROM)."""
        self.desc.inits.append(Init(region, offset, bytes(data)))
        return self

    # --- layout --------------------------------------------------------------------
    def _place(self):
        """Gives automatically placed regions their offsets, in the order they were declared."""
        auto = {id(r): a for r, a in self._auto}
        end = 0
        for r in self.desc.regions:
            if id(r) in auto:
                r.offset = apedesc.align_up(end, auto[id(r)])
            end = max(end, r.offset + max(r.size, 0))

    # --- checking --------------------------------------------------------------------
    def validate(self):
        """Returns (errors, warnings). Errors stop a build; warnings are naming-scheme advice."""
        self._place()
        d = self.desc
        errors, warnings = [], []
        err, warn = errors.append, warnings.append

        cls = self._class_text.upper()
        if class_code(cls) is None:
            err(f"unknown socket type '{self._class_text}' (known: "
                + ", ".join(class_name(c) for c in EXTENSIONS) + ")")
        fn = d.function
        if not fn:
            warn("no function given: say what the device does, e.g. function=\"TIMER\"")
        elif not FUNCTION.match(fn):
            err(f"function '{fn}' must be an upper-case word like TIMER or GPU")
        if not d.model or not d.model.isascii():
            err("model name must be non-empty ASCII")
        elif len(d.model) > NAME_MAX:
            err(f"model name '{d.model}' is longer than {NAME_MAX} characters")
        m = MODEL.match(d.model or "")
        if not m:
            warn(f"model name '{d.model}' does not follow 'aPE-<letter><model>' (NAMING.md)")
        elif fn in FUNCTION_LETTERS and m.group(1) != FUNCTION_LETTERS[fn]:
            warn(f"{fn} devices use the letter {FUNCTION_LETTERS[fn]} (e.g. aPE-{FUNCTION_LETTERS[fn]}1), "
                 f"not {m.group(1)}")
        elif fn and fn not in FUNCTION_LETTERS and m.group(1) in FUNCTION_LETTERS.values():
            warn(f"the letter {m.group(1)} already belongs to another function; pick an unused one")
        if not 1 <= d.version <= 0xFFFF:
            err("version must be between 1 and 65535")

        # parameters
        for name, value in d.params.items():
            if not IDENT.match(name):
                err(f"parameter '{name}': names may only use letters, digits and _")
            if isinstance(value, bool) or isinstance(value, (float, str)):
                continue
            if isinstance(value, int):
                if not -2**63 <= value < 2**63:
                    err(f"parameter '{name}': integer out of range")
            else:
                err(f"parameter '{name}': value must be int, float, str or bool")

        # regions
        seen = set()
        for r in d.regions:
            where = f"region '{r.name}'"
            if not IDENT.match(r.name):
                err(f"{where}: names may only use letters, digits and _")
            if r.name in seen:
                err(f"{where} is defined twice")
            seen.add(r.name)
            if r.size <= 0:
                err(f"{where}: size must be positive")
            if r.offset < 0:
                err(f"{where}: offset must not be negative")
            if r.kind not in apedesc.KINDS:
                err(f"{where}: unknown kind '{r.kind}' (use " + ", ".join(apedesc.KINDS) + ")")
            try:
                apedesc.parse_access(r.access)
            except ValueError as e:
                err(f"{where}: {e}")
        ordered = sorted(d.regions, key=lambda r: r.offset)
        for a, b in zip(ordered, ordered[1:]):
            if a.offset + a.size > b.offset:
                err(f"regions '{a.name}' and '{b.name}' overlap")
        if d.data_size > 0xFFFF0000:
            err("the device's data area is larger than 4 GB")

        # registers
        names = set()
        used = {}  # region -> list of (start, end, register)
        for reg in d.registers:
            where = f"register '{reg.name}'"
            if not IDENT.match(reg.name):
                err(f"{where}: names may only use letters, digits and _")
            if reg.name in names:
                err(f"{where} is defined twice")
            names.add(reg.name)
            r = d.region(reg.region)
            if r is None:
                err(f"{where}: no region called '{reg.region}'")
                continue
            if r.kind != "registers":
                warn(f"{where} is in region '{r.name}', whose kind is '{r.kind}' (usually 'registers')")
            if reg.width not in (8, 16, 32):
                err(f"{where}: width must be 8, 16 or 32 bits")
                continue
            size = reg.width // 8
            if reg.offset < 0 or reg.offset + size > r.size:
                err(f"{where}: does not fit in region '{r.name}' ({r.size} bytes)")
            if reg.offset % size:
                err(f"{where}: a {reg.width}-bit register must sit on a {size}-byte boundary")
            if not 0 <= reg.reset < (1 << reg.width):
                err(f"{where}: reset value 0x{reg.reset:X} does not fit in {reg.width} bits")
            try:
                apedesc.parse_access(reg.access)
            except ValueError as e:
                err(f"{where}: {e}")
            for start, end, other in used.get(reg.region, []):
                if reg.offset < end and start < reg.offset + size:
                    err(f"registers '{other}' and '{reg.name}' overlap")
            used.setdefault(reg.region, []).append((reg.offset, reg.offset + size, reg.name))

            fnames, mask = set(), 0
            for f in reg.fields:
                fwhere = f"{where}, field '{f.name}'"
                if not IDENT.match(f.name):
                    err(f"{fwhere}: names may only use letters, digits and _")
                if f.name in fnames:
                    err(f"{fwhere} is defined twice")
                fnames.add(f.name)
                if f.width < 1 or f.lsb < 0 or f.lsb + f.width > reg.width:
                    err(f"{fwhere}: bits {f.lsb}..{f.lsb + f.width - 1} are outside the {reg.width}-bit register")
                    continue
                if mask & f.mask:
                    err(f"{fwhere}: overlaps another field")
                mask |= f.mask

        # initial contents
        for init in d.inits:
            r = d.region(init.region)
            if r is None:
                err(f"initial data: no region called '{init.region}'")
            elif init.offset < 0 or init.offset + len(init.data) > r.size:
                err(f"initial data for '{init.region}' does not fit in the region")
        return errors, warnings

    # --- output ------------------------------------------------------------------------
    def compile(self):
        """Returns the module file's bytes. Raises DevKitError if the description has errors."""
        errors, _ = self.validate()
        if errors:
            raise DevKitError(errors)
        return apedesc.compile_module(self.desc)

    @property
    def file_name(self):
        return model_file_name(self.desc.model, self.desc.extension)

    def build(self, path=None, directory="."):
        """Compiles and writes the module. Default file name follows NAMING.md."""
        data = self.compile()
        path = path or os.path.join(directory, self.file_name)
        if os.path.splitext(path)[1] != self.desc.extension:
            raise DevKitError([f"a {class_name(self.desc.device_class)}-socket module must end in "
                               f"{self.desc.extension}, not '{os.path.basename(path)}'"])
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def instantiate(self, path, overwrite=False):
        """Creates a powered-on instance file (registers at their reset values)."""
        errors, _ = self.validate()
        if errors:
            raise DevKitError(errors)
        return apedesc.create_instance(self.desc, path, overwrite)

    @classmethod
    def from_descriptor(cls, desc):
        dev = cls(desc.device_class, desc.model, desc.function, desc.version, desc.description)
        dev.desc = desc
        return dev
