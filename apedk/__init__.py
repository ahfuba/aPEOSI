"""
aPE-DevKit: describe aPEOSI hardware in Python (or JSON) and compile it
into .ape<class> module files.

    from apedk import Device, Field

    gpu = Device("GPU", "aPE-G9", description="my GPU")
    gpu.param("width", 160)
    gpu.region("regs", size=16, kind="registers")
    gpu.register("MODE", "regs", offset=0, fields=[Field("ON", lsb=0)])
    gpu.region("vram", size=160 * 120 // 2, kind="vram", align=256)
    gpu.build()          # -> ape-g9.apegpu

Command line: python ape_devkit.py --help
Guide: docs/aPE-DevKit.md
"""

from devices.internal.A.apeos.system2.sys.apedesc import (DescriptorError, create_instance,
                                                          decode_descriptor, load_module,
                                                          read_device_header)

from .device import DevKitError, Device, Field, model_file_name
from .jsonspec import device_from_spec, from_json

__all__ = [
    "Device", "Field", "DevKitError", "DescriptorError",
    "from_json", "device_from_spec", "load", "model_file_name",
    "create_instance", "decode_descriptor", "read_device_header",
]

__version__ = "1.0"


def load(path):
    """Reads a compiled module file back into a Device."""
    return Device.from_descriptor(load_module(path))
