"""
Motherboard loader.

aPEOSI's "hardware" is described by files in the /motherboard folder at the
project root. ``board.json`` picks which CPU and RAM module are plugged in;
anyone can add their own modules (see motherboard/README.md).

A module can be a JSON spec or a module compiled by aPE-DevKit
(``ape-p1.apecpu``, ``ape-r16k.aperam``). Both give the same fields.

Keep this file free of aPEOSI imports so the Watchdog can use it on its own.
"""

import json
import os
import re
from dataclasses import dataclass, field

from . import apedesc
from .apedev import CLASS_CPU, CLASS_RAM, class_name
from .aperam import Layout


class HardwareError(Exception):
    """Raised when a motherboard/hardware file is missing or invalid."""


@dataclass
class CPUSpec:
    name: str
    clock_hz: int        # scheduler steps per second (how fast processes advance)
    description: str
    source: str


@dataclass
class RAMSpec:
    name: str
    page_size: int       # bytes per page/frame
    num_pages: int       # number of physical frames
    description: str
    source: str

    @property
    def size(self):
        return self.page_size * self.num_pages


@dataclass
class Board:
    name: str
    cpu: CPUSpec
    ram: RAMSpec
    ram_file: str        # absolute path of the .aperam file
    path: str
    sockets: list = field(default_factory=list)   # [{id, type, device, controller}]


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HardwareError(f"Hardware file not found: {path}")
    except json.JSONDecodeError as e:
        raise HardwareError(f"Invalid JSON in {path}: {e}")
    if not isinstance(data, dict):
        raise HardwareError(f"{path} must contain a JSON object")
    return data


def _require(data, key, kind, path):
    if key not in data:
        raise HardwareError(f"{path}: missing required field '{key}'")
    value = data[key]
    if kind is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise HardwareError(f"{path}: field '{key}' must be an integer")
    if kind is str and not isinstance(value, str):
        raise HardwareError(f"{path}: field '{key}' must be a string")
    return value


def _read_spec(path, device_class):
    """
    Reads a module's fields from a JSON spec or a compiled module file.
    Compiled modules store them as parameters; the result looks the same.
    """
    if not path.lower().endswith(".json"):
        try:
            desc = apedesc.load_module(path)
        except FileNotFoundError:
            raise HardwareError(f"Hardware file not found: {path}")
        except apedesc.DescriptorError as e:
            raise HardwareError(f"{path}: {e}")
        if desc.device_class != device_class:
            raise HardwareError(f"{path}: this is a {class_name(desc.device_class)} module, "
                                f"not a {class_name(device_class)} module")
        data = dict(desc.params)
        data.update(type=class_name(device_class).lower(), name=desc.model, description=desc.description)
        return data
    return _read_json(path)


def load_cpu(path):
    data = _read_spec(path, CLASS_CPU)
    if data.get("type") != "cpu":
        raise HardwareError(f"{path}: not a CPU module (expected \"type\": \"cpu\")")
    clock = _require(data, "clock_hz", int, path)
    if not 1 <= clock <= 100000:
        raise HardwareError(f"{path}: clock_hz must be between 1 and 100000")
    return CPUSpec(_require(data, "name", str, path), clock, data.get("description", ""), path)


def load_ram(path):
    data = _read_spec(path, CLASS_RAM)
    if data.get("type") != "ram":
        raise HardwareError(f"{path}: not a RAM module (expected \"type\": \"ram\")")
    spec = RAMSpec(
        _require(data, "name", str, path)[:14],
        _require(data, "page_size", int, path),
        _require(data, "num_pages", int, path),
        data.get("description", ""),
        path,
    )
    try:
        Layout(spec.page_size, spec.num_pages)  # validates the geometry
    except ValueError as e:
        raise HardwareError(f"{path}: {e}")
    return spec


def load_board(motherboard_dir, board_file="board.json"):
    """Loads a board description and the CPU/RAM modules it points to."""
    board_path = board_file if os.path.isabs(board_file) else os.path.join(motherboard_dir, board_file)
    data = _read_json(board_path)
    base = os.path.dirname(os.path.abspath(board_path))

    def resolve(rel):
        return rel if os.path.isabs(rel) else os.path.join(base, rel)

    cpu = load_cpu(resolve(_require(data, "cpu", str, board_path)))
    ram = load_ram(resolve(_require(data, "ram", str, board_path)))
    ram_file = resolve(data.get("ram_file", "ram0.aperam"))
    sockets = _load_sockets(data.get("sockets", []), resolve, board_path)
    return Board(data.get("name", "Unnamed board"), cpu, ram, os.path.abspath(ram_file), board_path, sockets)


SOCKET_ID = re.compile(r"^[a-z]{2,5}[0-9]{1,2}$")
SOCKET_TYPES = ("bus", "pci", "ser", "usb")


def _load_sockets(entries, resolve, board_path):
    """Checks the board's socket list. Each socket: id, type, optional device and controller."""
    if not isinstance(entries, list):
        raise HardwareError(f"{board_path}: 'sockets' must be a list")
    sockets, ids = [], set()
    for i, e in enumerate(entries):
        where = f"{board_path}: sockets[{i}]"
        if not isinstance(e, dict):
            raise HardwareError(f"{where} must be an object")
        sid = _require(e, "id", str, where)
        stype = _require(e, "type", str, where).lower()
        if not SOCKET_ID.match(sid):
            raise HardwareError(f"{where}: socket id '{sid}' must look like bus0, pci1, com1")
        if sid in ids:
            raise HardwareError(f"{where}: socket id '{sid}' is used twice")
        if stype not in SOCKET_TYPES:
            raise HardwareError(f"{where}: unknown socket type '{stype}' (use {', '.join(SOCKET_TYPES)})")
        device = e.get("device")
        if device is not None and stype == "usb":
            raise HardwareError(f"{where}: USB sockets are specified but not built yet; leave this one empty")
        if device is not None and not isinstance(device, str):
            raise HardwareError(f"{where}: 'device' must be a file path or null")
        controller = e.get("controller")
        if stype == "ser" and device is not None and not controller:
            raise HardwareError(f"{where}: a serial port needs a 'controller' (the UART socket that drives it)")
        ids.add(sid)
        sockets.append({"id": sid, "type": stype, "device": resolve(device) if device else None,
                        "controller": controller})
    return sockets
