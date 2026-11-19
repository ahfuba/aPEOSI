"""
JSON device specs, for modders who would rather not write Python.

"type" is the socket the device plugs into (bus, pci, ser, ram, cpu, ...),
"function" says what it does. The simple specs in /motherboard (RAM and CPU
modules) already are valid input: every top-level key that isn't one of the reserved keys below becomes
a parameter. A full spec can also describe regions and registers:

    {
      "type": "bus",
      "function": "panel",
      "name": "aPE-L1 Panel",
      "description": "8 LEDs and a button",
      "params":    { "leds": 8 },
      "regions":   [ { "name": "io", "size": 16, "kind": "registers" } ],
      "registers": [
        { "name": "LEDS", "region": "io", "offset": 0 },
        { "name": "CTRL", "region": "io", "offset": 1, "reset": 1,
          "fields": [ { "name": "ENABLE", "lsb": 0 } ] }
      ]
    }
"""

from __future__ import annotations

import json

from .device import DevKitError, Device, Field

RESERVED = {"type", "function", "name", "description", "version", "params", "regions", "registers", "init"}


def _need(obj, key, kind, where):
    if key not in obj:
        raise DevKitError([f"{where}: missing '{key}'"])
    value = obj[key]
    if kind is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise DevKitError([f"{where}: '{key}' must be an integer"])
    if kind is str and not isinstance(value, str):
        raise DevKitError([f"{where}: '{key}' must be a string"])
    return value


def device_from_spec(spec, source="spec"):
    """Builds a Device from a parsed JSON object."""
    if not isinstance(spec, dict):
        raise DevKitError([f"{source}: the spec must be a JSON object"])
    dev = Device(_need(spec, "type", str, source), _need(spec, "name", str, source),
                 spec.get("function"), spec.get("version", 1), spec.get("description", ""))
    for key, value in spec.items():
        if key not in RESERVED:
            dev.param(key, value)
    for key, value in spec.get("params", {}).items():
        dev.param(key, value)
    for i, r in enumerate(spec.get("regions", [])):
        where = f"{source}: regions[{i}]"
        dev.region(_need(r, "name", str, where), _need(r, "size", int, where), r.get("kind", "data"),
                   r.get("access", "rw"), r.get("offset"), r.get("align", 16), r.get("description", ""))
    for i, g in enumerate(spec.get("registers", [])):
        where = f"{source}: registers[{i}]"
        fields = [Field(_need(f, "name", str, f"{where}.fields"), _need(f, "lsb", int, f"{where}.fields"),
                        f.get("width", 1), f.get("description", "")) for f in g.get("fields", [])]
        dev.register(_need(g, "name", str, where), _need(g, "region", str, where),
                     _need(g, "offset", int, where), g.get("width", 8), g.get("access", "rw"),
                     g.get("reset", 0), g.get("description", ""), fields)
    for i, init in enumerate(spec.get("init", [])):
        where = f"{source}: init[{i}]"
        dev.init(_need(init, "region", str, where), bytes(init.get("bytes", [])), init.get("offset", 0))
    return dev


def from_json(path):
    """Reads a JSON spec file and returns a Device."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except FileNotFoundError:
        raise DevKitError([f"{path}: file not found"])
    except json.JSONDecodeError as e:
        raise DevKitError([f"{path}: invalid JSON: {e}"])
    return device_from_spec(spec, path)
