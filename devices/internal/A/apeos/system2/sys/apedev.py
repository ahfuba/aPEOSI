"""
aPE device files: the common header shared by every simulated hardware file.

Every piece of simulated hardware is a file. All of them start with the same
32-byte *device header*, followed by a header specific to that device class:

    offset  size  field
    0       4     magic          b"APE\\x1A"  (same for every device file)
    4       4     device class   b"RAM\\0", b"MB\\0\\0", b"BUS\\0"
    8       2     format version (of the class-specific layout)
    10      2     header size    (common + class header, in bytes)
    12      4     device size    (whole file, in bytes)
    16      16    device name    (ASCII, zero-padded)

    32      ...   class-specific header (see aperam.py for RAM)

So any tool can open any aPE device file, read the first 32 bytes, and know
what it is looking at before parsing the rest.

Device classes and file extensions:

    .aperam   RAM module (SODIMM)              -- implemented in aPEOSI 1.2
    .apemb    motherboard / PCI configuration  -- reserved, see docs/aPE-hardware.md
    .apebus   bus devices (I/O ports, etc.)    -- reserved, see docs/aPE-hardware.md

Keep this file free of aPEOSI imports so outside tools can use it.
"""

import struct

DEVICE_MAGIC = b"APE\x1A"

CLASS_RAM = b"RAM\x00"
CLASS_MOTHERBOARD = b"MB\x00\x00"
CLASS_BUS = b"BUS\x00"

EXTENSIONS = {
    CLASS_RAM: ".aperam",
    CLASS_MOTHERBOARD: ".apemb",
    CLASS_BUS: ".apebus",
}

COMMON_FMT = "<4s4sHHI16s"
COMMON_SIZE = struct.calcsize(COMMON_FMT)  # 32
assert COMMON_SIZE == 32


def pack_common(device_class, format_version, header_size, device_size, name):
    return struct.pack(COMMON_FMT, DEVICE_MAGIC, device_class, format_version, header_size,
                       device_size, name.encode("ascii", "replace")[:16])


def parse_common(buf):
    """Parses the common device header. Returns a dict, or None if not an aPE device."""
    if len(buf) < COMMON_SIZE:
        return None
    magic, dev_class, version, header_size, size, name = struct.unpack_from(COMMON_FMT, buf, 0)
    if magic != DEVICE_MAGIC:
        return None
    return {
        "device_class": dev_class,
        "format_version": version,
        "header_size": header_size,
        "device_size": size,
        "name": name.rstrip(b"\x00").decode("ascii", "replace"),
    }
