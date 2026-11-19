"""
aPE-DevKit command-line tool: build, check and inspect aPE device files.

    python ape_devkit.py new GPU "aPE-G9"          start a new device source file
    python ape_devkit.py check my_device.py        validate without writing anything
    python ape_devkit.py build my_device.py        compile to a .ape<class> module
    python ape_devkit.py build motherboard/cpu/ape-p1.json
    python ape_devkit.py info ape-g9.apegpu        show what a device file contains
    python ape_devkit.py instance ape-g9.apegpu gpu0.apegpu   power one on

A Python device source is a normal Python file that creates a Device and
stores it in a variable called DEVICE. Building it runs that file, so only
build Python sources you trust. JSON sources and compiled modules are plain
data and safe to share.

Guide: docs/aPE-DevKit.md
"""

import argparse
import os
import runpy
import struct
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from apedk import DescriptorError, DevKitError, Device, create_instance, from_json, load  # noqa: E402
from apedk.device import model_file_name  # noqa: E402
from devices.internal.A.apeos.system2.sys import aperam  # noqa: E402
from devices.internal.A.apeos.system2.sys.apedesc import read_device_header  # noqa: E402
from devices.internal.A.apeos.system2.sys.apedev import (EXTENSIONS, class_code,  # noqa: E402
                                                         class_name)


def load_source(path):
    """A Device from a .py source, a .json spec, or an already compiled module."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        if not os.path.exists(path):
            raise DevKitError([f"{path}: file not found"])
        namespace = runpy.run_path(path, run_name="__apedk__")
        device = namespace.get("DEVICE")
        if not isinstance(device, Device):
            raise DevKitError([f"{path}: must create a Device and store it in a variable called DEVICE"])
        return device
    if ext == ".json":
        return from_json(path)
    if ext in EXTENSIONS.values():
        return load(path)
    raise DevKitError([f"{path}: expected a .py source, a .json spec or a compiled .ape* module"])


def report(device, errors, warnings):
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  error:   {e}")


def cmd_check(args):
    device = load_source(args.source)
    errors, warnings = device.validate()
    report(device, errors, warnings)
    d = device.desc
    if errors:
        print(f"{args.source}: {len(errors)} error(s)")
        return 1
    print(f"{args.source}: OK. {d.model} ({class_name(d.device_class)}), {len(d.params)} params, "
          f"{len(d.regions)} regions, {len(d.registers)} registers, {d.data_size:,}-byte data area")
    return 0


def cmd_build(args):
    device = load_source(args.source)
    errors, warnings = device.validate()
    report(device, errors, warnings)
    if errors:
        print(f"{args.source}: {len(errors)} error(s); nothing was written")
        return 1
    directory = args.directory or os.path.dirname(os.path.abspath(args.source))
    path = device.build(args.output, directory)
    d = device.desc
    print(f"built {path}")
    print(f"  {d.model} ({class_name(d.device_class)}), {len(d.params)} params, {len(d.regions)} regions, "
          f"{len(d.registers)} registers")
    print(f"  module {os.path.getsize(path):,} bytes; an instance will be {d.instance_size:,} bytes")
    return 0


def _flags(common):
    names = [n for n, on in (("module", common["is_module"]), ("persistent", common["persistent"])) if on]
    return ", ".join(names) or "instance"


def cmd_info(args):
    common, desc = read_device_header(args.file)
    print(f"{args.file}")
    print(f"  class    {class_name(common['device_class'])} ({EXTENSIONS.get(common['device_class'], '?')})")
    print(f"  name     {common['name']}")
    print(f"  kind     {_flags(common)}")
    print(f"  format   v{common['format_version']}, header {common['header_size']:,} bytes, "
          f"device {common['device_size']:,} bytes")

    if desc is None:
        if common["device_class"] == aperam.CLASS_RAM:
            with open(args.file, "rb") as f:
                header = aperam.parse_header(f.read(aperam.HEADER_SIZE))
            if header:
                print(f"  RAM      {header['num_pages']} frames x {header['page_size']} bytes, "
                      f"tick {header['tick']:,}, writes {header['write_seq']:,}, OS {header['os_version']}")
        print("  (no descriptor in this file)")
        return 0

    live = None
    if not common["is_module"]:
        with open(args.file, "rb") as f:
            live = f.read()
    if desc.description:
        print(f"  about    {desc.description}")
    print(f"  version  {desc.version}")
    if desc.params:
        print("\n  PARAMETERS")
        for name, value in desc.params.items():
            print(f"    {name:<18} {value!r}")
    if desc.regions:
        print("\n  REGIONS                 file offset   size       kind       access")
        for r in desc.regions:
            print(f"    {r.name:<20} 0x{desc.header_size + r.offset:08X}  {r.size:>9,}  {r.kind:<10} {r.access}"
                  + (f"   {r.description}" if r.description else ""))
    if desc.registers:
        print("\n  REGISTERS               region       offset  bits  access  reset"
              + ("       now" if live else ""))
        for reg in desc.registers:
            line = (f"    {reg.name:<20} {reg.region:<12} 0x{reg.offset:04X}  {reg.width:>4}  {reg.access:<6}  "
                    f"0x{reg.reset:0{reg.width // 4}X}")
            if live:
                addr = desc.address(reg.region, reg.offset)
                now = int.from_bytes(live[addr:addr + reg.width // 8], "little")
                line += f"  0x{now:0{reg.width // 4}X}"
            print(line + (f"   {reg.description}" if reg.description else ""))
            for f in reg.fields:
                bits = f"{f.lsb}" if f.width == 1 else f"{f.lsb + f.width - 1}:{f.lsb}"
                print(f"      .{f.name:<17} bit {bits:<6}" + (f" {f.description}" if f.description else ""))
    if desc.inits:
        print("\n  INITIAL DATA")
        for init in desc.inits:
            print(f"    {init.region} + 0x{init.offset:X}: {len(init.data):,} bytes")
    return 0


def cmd_instance(args):
    device = load_source(args.module)
    path = create_instance(device.desc, args.output, overwrite=args.overwrite)
    print(f"created {path} ({os.path.getsize(path):,} bytes), registers at their reset values")
    return 0


TEMPLATE = '''"""
{model}: describe your device here.
Build it with:  python ape_devkit.py build {source}
"""

from apedk import Device, Field

DEVICE = Device("{cls}", "{model}", version=1, description="what this device does")

# Fixed properties of the device
DEVICE.param("example_hz", 60)

# Memory regions, placed one after another
DEVICE.region("regs", size=16, kind="registers", description="control registers")
DEVICE.region("buffer", size=256, kind="buffer", description="data buffer")

# Registers inside a region, with named bit fields
DEVICE.register("CTRL", "regs", offset=0x0, width=8, reset=0x00, description="control", fields=[
    Field("ENABLE", lsb=0, description="1 = device on"),
    Field("MODE", lsb=1, width=2, description="operating mode"),
])
DEVICE.register("STATUS", "regs", offset=0x1, width=8, access="r", description="status flags")
'''


def cmd_new(args):
    code = class_code(args.device_class)
    if code is None:
        print(f"unknown device class '{args.device_class}' (known: "
              + ", ".join(class_name(c) for c in EXTENSIONS) + ")")
        return 1
    path = args.output or model_file_name(args.model, ".py")
    if os.path.exists(path):
        print(f"{path} already exists; not overwriting it")
        return 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(model=args.model, cls=class_name(code), source=os.path.basename(path)))
    print(f"created {path}; edit it, then: python ape_devkit.py build {path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ape_devkit.py", description="aPE-DevKit: build aPE device files.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="create a new Python device source from a template")
    p.add_argument("device_class", help="RAM, MB, BUS, GPU, CPU, DISK or NET")
    p.add_argument("model", help='model name, e.g. "aPE-G9"')
    p.add_argument("-o", "--output", help="source file to create")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("check", help="validate a device source without writing anything")
    p.add_argument("source")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", help="compile a .py or .json source into a .ape<class> module")
    p.add_argument("source")
    p.add_argument("-o", "--output", help="output file (default: model name, next to the source)")
    p.add_argument("-d", "--directory", help="output directory")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("info", help="show what an aPE device file contains")
    p.add_argument("file")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("instance", help="create a powered-on instance from a module or source")
    p.add_argument("module")
    p.add_argument("output", help="e.g. gpu0.apegpu")
    p.add_argument("--overwrite", action="store_true", help="allow replacing an existing disk")
    p.set_defaults(func=cmd_instance)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except DevKitError as e:
        for line in e.errors:
            print(f"  error:   {line}")
        return 1
    except (DescriptorError, FileExistsError, OSError, struct.error) as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
