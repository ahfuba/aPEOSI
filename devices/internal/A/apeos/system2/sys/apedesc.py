"""
aPE device descriptors: aPEOSI's "device tree".

A descriptor says what a device *is*: its parameters, its memory regions and
the registers inside them. aPE-DevKit compiles descriptors into module files;
aPEOSI and the tools read them back here. (Real systems split it the same
way: the Linux kernel reads device-tree blobs that the separate `dtc` compiler
produced.)

File layout, for both a compiled module and a running instance:

    0             common aPE device header (apedev.py), 32 bytes
    32            descriptor: a sequence of chunks (below)
    header_size   the device's data area: its regions, one after another
                  (only in instances; a module stops after the descriptor)

Chunks work like the chunks in PNG or WAV files, so unknown chunks can be
skipped and the format can grow:

    tag (4 bytes)  length (u32)  payload (length bytes)  padding to 4 bytes

    INFO  model, description, device version
    PARM  parameters: name, type, value
    RGNS  regions: name, offset, size, kind, access, description
    REGS  registers: name, region, offset, width, access, reset value, fields
    INIT  initial contents for regions
    END   end of the descriptor

Region and register offsets are relative to the start of the data area, so
a region at offset 0 starts at byte `header_size` of the instance file.
All numbers are little-endian. Strings are u16 length + UTF-8.

Keep this file free of aPEOSI imports (except apedev) so outside tools can use it.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field

from .apedev import (COMMON_SIZE, FLAG_MODULE, FLAG_PERSISTENT, CLASS_DISK, EXTENSIONS,
                     pack_common, parse_common)

DESCRIPTOR_VERSION = 1
DATA_ALIGN = 64          # the data area starts on a 64-byte boundary

KINDS = {"data": 0, "registers": 1, "vram": 2, "buffer": 3, "rom": 4, "state": 5}
KIND_NAMES = {v: k for k, v in KINDS.items()}

ACCESS_BITS = {"r": 1, "w": 2, "x": 4}

T_INT, T_FLOAT, T_STR, T_BOOL = 0, 1, 2, 3


class DescriptorError(Exception):
    """A descriptor or device file is malformed."""


def parse_access(text):
    """'rw' -> 3. Raises ValueError for anything else."""
    bits = 0
    for ch in text.lower():
        if ch not in ACCESS_BITS or bits & ACCESS_BITS[ch]:
            raise ValueError(f"bad access '{text}' (use letters from 'rwx')")
        bits |= ACCESS_BITS[ch]
    if not bits:
        raise ValueError("access must not be empty")
    return bits


def access_str(bits):
    return "".join(ch for ch, b in ACCESS_BITS.items() if bits & b)


def align_up(value, alignment):
    return -(-value // alignment) * alignment


# --------------------------------------------------------------- data model ---
@dataclass
class Field:
    """A named group of bits inside a register, e.g. ENABLE = bit 0."""
    name: str
    lsb: int
    width: int = 1
    description: str = ""

    @property
    def mask(self):
        return ((1 << self.width) - 1) << self.lsb


@dataclass
class Register:
    name: str
    region: str
    offset: int            # bytes from the start of its region
    width: int = 8         # bits: 8, 16 or 32
    access: str = "rw"
    reset: int = 0         # value after power-on
    description: str = ""
    fields: list = field(default_factory=list)


@dataclass
class Region:
    name: str
    size: int
    kind: str = "data"
    access: str = "rw"
    offset: int = 0        # bytes from the start of the data area
    description: str = ""


@dataclass
class Init:
    region: str
    offset: int
    data: bytes


@dataclass
class Descriptor:
    device_class: bytes
    model: str
    version: int = 1
    description: str = ""
    params: dict = field(default_factory=dict)
    regions: list = field(default_factory=list)
    registers: list = field(default_factory=list)
    inits: list = field(default_factory=list)
    header_size: int = 0   # filled in when compiled or read

    def region(self, name):
        for r in self.regions:
            if r.name == name:
                return r
        return None

    @property
    def data_size(self):
        return max((r.offset + r.size for r in self.regions), default=0)

    @property
    def instance_size(self):
        return self.header_size + self.data_size

    @property
    def extension(self):
        return EXTENSIONS.get(self.device_class, ".ape")

    def address(self, region_name, offset=0):
        """File offset of a byte inside a region of an instance."""
        r = self.region(region_name)
        if r is None:
            raise KeyError(region_name)
        return self.header_size + r.offset + offset


# ----------------------------------------------------------------- encoding ---
def _s(text):
    data = text.encode("utf-8")
    if len(data) > 0xFFFF:
        raise DescriptorError("string too long")
    return struct.pack("<H", len(data)) + data


def _chunk(tag, payload):
    pad = (-len(payload)) % 4
    return tag + struct.pack("<I", len(payload)) + payload + b"\x00" * pad


def _encode_value(value):
    if isinstance(value, bool):
        return struct.pack("<BB", T_BOOL, int(value))
    if isinstance(value, int):
        return struct.pack("<Bq", T_INT, value)
    if isinstance(value, float):
        return struct.pack("<Bd", T_FLOAT, value)
    if isinstance(value, str):
        return struct.pack("<B", T_STR) + _s(value)
    raise DescriptorError(f"parameter values must be int, float, str or bool, not {type(value).__name__}")


def encode_descriptor(desc: Descriptor):
    """The descriptor's chunks, without the common header."""
    region_index = {r.name: i for i, r in enumerate(desc.regions)}
    out = [_chunk(b"INFO", _s(desc.model) + _s(desc.description) + struct.pack("<H", desc.version))]

    payload = struct.pack("<H", len(desc.params))
    for name, value in desc.params.items():
        payload += _s(name) + _encode_value(value)
    out.append(_chunk(b"PARM", payload))

    payload = struct.pack("<H", len(desc.regions))
    for r in desc.regions:
        payload += (_s(r.name) + struct.pack("<IIBB", r.offset, r.size, KINDS[r.kind], parse_access(r.access))
                    + _s(r.description))
    out.append(_chunk(b"RGNS", payload))

    payload = struct.pack("<H", len(desc.registers))
    for reg in desc.registers:
        payload += (_s(reg.name) + struct.pack("<HIBBI", region_index[reg.region], reg.offset, reg.width,
                                               parse_access(reg.access), reg.reset)
                    + _s(reg.description) + struct.pack("<B", len(reg.fields)))
        for f in reg.fields:
            payload += _s(f.name) + struct.pack("<BB", f.lsb, f.width) + _s(f.description)
    out.append(_chunk(b"REGS", payload))

    if desc.inits:
        payload = struct.pack("<H", len(desc.inits))
        for init in desc.inits:
            payload += struct.pack("<HII", region_index[init.region], init.offset, len(init.data)) + init.data
        out.append(_chunk(b"INIT", payload))

    out.append(_chunk(b"END\x00", b""))
    return b"".join(out)


def compile_module(desc: Descriptor):
    """Common header + descriptor: the bytes of a compiled module file."""
    chunks = encode_descriptor(desc)
    desc.header_size = align_up(COMMON_SIZE + len(chunks), DATA_ALIGN)
    if desc.header_size > 0xFFFF:
        raise DescriptorError("descriptor too large (over 64 KB)")
    if desc.instance_size > 0xFFFFFFFF:
        raise DescriptorError("device too large (over 4 GB)")
    flags = FLAG_MODULE | (FLAG_PERSISTENT if desc.device_class == CLASS_DISK else 0)
    header = pack_common(desc.device_class, DESCRIPTOR_VERSION, desc.header_size, desc.instance_size,
                         desc.model, flags)
    return header + chunks


# ----------------------------------------------------------------- decoding ---
class _Reader:
    def __init__(self, buf, pos, end):
        self.buf, self.pos, self.end = buf, pos, end

    def take(self, fmt):
        size = struct.calcsize(fmt)
        if self.pos + size > self.end:
            raise DescriptorError("descriptor is truncated")
        values = struct.unpack_from(fmt, self.buf, self.pos)
        self.pos += size
        return values

    def string(self):
        (n,) = self.take("<H")
        if self.pos + n > self.end:
            raise DescriptorError("descriptor is truncated")
        text = bytes(self.buf[self.pos:self.pos + n]).decode("utf-8", "replace")
        self.pos += n
        return text

    def raw(self, n):
        if self.pos + n > self.end:
            raise DescriptorError("descriptor is truncated")
        data = bytes(self.buf[self.pos:self.pos + n])
        self.pos += n
        return data

    def value(self):
        (t,) = self.take("<B")
        if t == T_INT:
            return self.take("<q")[0]
        if t == T_FLOAT:
            return self.take("<d")[0]
        if t == T_BOOL:
            return bool(self.take("<B")[0])
        if t == T_STR:
            return self.string()
        raise DescriptorError(f"unknown parameter type {t}")


def has_descriptor(buf):
    """True if a device file carries a descriptor (it starts with an INFO chunk)."""
    return len(buf) >= COMMON_SIZE + 4 and bytes(buf[COMMON_SIZE:COMMON_SIZE + 4]) == b"INFO"


def decode_descriptor(buf):
    """Reads the descriptor from the bytes of a module or instance file."""
    common = parse_common(buf)
    if common is None:
        raise DescriptorError("not an aPE device file")
    if not has_descriptor(buf):
        raise DescriptorError("this device file has no descriptor")
    desc = Descriptor(common["device_class"], common["name"], header_size=common["header_size"])
    region_names = []
    pos, end = COMMON_SIZE, min(len(buf), common["header_size"] or len(buf))
    while pos + 8 <= end:
        tag = bytes(buf[pos:pos + 4])
        (length,) = struct.unpack_from("<I", buf, pos + 4)
        start = pos + 8
        if start + length > end:
            raise DescriptorError(f"chunk {tag!r} is truncated")
        r = _Reader(buf, start, start + length)
        if tag == b"INFO":
            desc.model, desc.description = r.string(), r.string()
            (desc.version,) = r.take("<H")
        elif tag == b"PARM":
            for _ in range(r.take("<H")[0]):
                name = r.string()
                desc.params[name] = r.value()
        elif tag == b"RGNS":
            for _ in range(r.take("<H")[0]):
                name = r.string()
                offset, size, kind, access = r.take("<IIBB")
                desc.regions.append(Region(name, size, KIND_NAMES.get(kind, "data"), access_str(access),
                                           offset, r.string()))
                region_names.append(name)
        elif tag == b"REGS":
            for _ in range(r.take("<H")[0]):
                name = r.string()
                region, offset, width, access, reset = r.take("<HIBBI")
                reg = Register(name, region_names[region] if region < len(region_names) else "?",
                               offset, width, access_str(access), reset, r.string())
                for _ in range(r.take("<B")[0]):
                    fname = r.string()
                    lsb, fwidth = r.take("<BB")
                    reg.fields.append(Field(fname, lsb, fwidth, r.string()))
                desc.registers.append(reg)
        elif tag == b"INIT":
            for _ in range(r.take("<H")[0]):
                region, offset, n = r.take("<HII")
                desc.inits.append(Init(region_names[region] if region < len(region_names) else "?",
                                       offset, r.raw(n)))
        elif tag == b"END\x00":
            break
        # unknown chunks are skipped: that is what keeps the format extensible
        pos = start + length + ((-length) % 4)
    return desc


def read_device_header(path):
    """Reads just the header and descriptor of a device file. Returns (common, descriptor or None)."""
    with open(path, "rb") as f:
        head = f.read(COMMON_SIZE)
        common = parse_common(head)
        if common is None:
            raise DescriptorError(f"{path} is not an aPE device file")
        head += f.read(max(0, (common["header_size"] or COMMON_SIZE) - COMMON_SIZE))
    return common, (decode_descriptor(head) if has_descriptor(head) else None)


def load_module(path):
    """Reads a compiled module file and returns its Descriptor."""
    common, desc = read_device_header(path)
    if not common["is_module"]:
        raise DescriptorError(f"{path} is a running device instance, not a module")
    if desc is None:
        raise DescriptorError(f"{path} has no descriptor")
    return desc


# ---------------------------------------------------------------- instances ---
def create_instance(desc: Descriptor, path, overwrite=False):
    """
    Creates a powered-on device: header + descriptor + data area, with every
    register at its reset value and INIT data copied in.

    Persistent devices (disks) are never overwritten unless asked explicitly,
    because the file *is* the data.
    """
    persistent = desc.device_class == CLASS_DISK
    if os.path.exists(path) and (persistent and not overwrite):
        raise FileExistsError(f"{path} already exists and holds data; refusing to overwrite it")
    chunks = encode_descriptor(desc)
    desc.header_size = align_up(COMMON_SIZE + len(chunks), DATA_ALIGN)
    flags = FLAG_PERSISTENT if persistent else 0
    header = pack_common(desc.device_class, DESCRIPTOR_VERSION, desc.header_size, desc.instance_size,
                         desc.model, flags) + chunks
    image = bytearray(header.ljust(desc.header_size, b"\x00")) + bytearray(desc.data_size)
    for reg in desc.registers:
        addr = desc.address(reg.region, reg.offset)
        image[addr:addr + reg.width // 8] = reg.reset.to_bytes(reg.width // 8, "little")
    for init in desc.inits:
        addr = desc.address(init.region, init.offset)
        image[addr:addr + len(init.data)] = init.data
    tmp = path + ".new"
    with open(tmp, "wb") as f:
        f.write(image)
    os.replace(tmp, path)
    return path
