"""
Motherboard loader.

aPEOSI's "hardware" is described by JSON files in the /motherboard folder at
the project root. ``board.json`` picks which CPU and RAM module are plugged
in; anyone can add their own modules (see motherboard/README.md).

Keep this file free of aPEOSI imports so the Watchdog can use it on its own.
"""

import json
import os
from dataclasses import dataclass

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


def load_cpu(path):
    data = _read_json(path)
    if data.get("type") != "cpu":
        raise HardwareError(f"{path}: not a CPU module (expected \"type\": \"cpu\")")
    clock = _require(data, "clock_hz", int, path)
    if not 1 <= clock <= 100000:
        raise HardwareError(f"{path}: clock_hz must be between 1 and 100000")
    return CPUSpec(_require(data, "name", str, path), clock, data.get("description", ""), path)


def load_ram(path):
    data = _read_json(path)
    if data.get("type") != "ram":
        raise HardwareError(f"{path}: not a RAM module (expected \"type\": \"ram\")")
    spec = RAMSpec(
        _require(data, "name", str, path)[:16],
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
    return Board(data.get("name", "Unnamed board"), cpu, ram, os.path.abspath(ram_file), board_path)
