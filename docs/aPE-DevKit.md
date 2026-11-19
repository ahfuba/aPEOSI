# aPE-DevKit

aPE-DevKit lets you **design aPEOSI hardware**. You describe a device's
parameters, memory regions and registers in Python (or JSON), and the kit
checks the design and compiles it into a `.ape<class>` **module file**:

```
my_device.py ──► aPE-DevKit ──► ape-g9.apegpu ──► aPEOSI and the tools read it
 (or .json)      (validates)     (pure data)
```

Real hardware works the same way: Linux describes hardware in device-tree
source files that a compiler turns into binary blobs the kernel reads at boot.

- Library: the `apedk` package
- Command-line tool: `ape_devkit.py`
- Format: [`aPE-hardware.md`](aPE-hardware.md#device-descriptors)
- Example device: [`examples/ape-l1-panel.py`](examples/ape-l1-panel.py) (and the same device in [JSON](examples/ape-l1-panel.json))

## Quick start

```bash
python ape_devkit.py new GPU "aPE-G9"
```

That writes `ape-g9.py`, a template to edit. Then:

```bash
python ape_devkit.py check ape-g9.py
```

```bash
python ape_devkit.py build ape-g9.py
```

```bash
python ape_devkit.py info ape-g9.apegpu
```

`check` validates without writing anything, `build` writes the module, and
`info` shows what any aPE device file contains.

## Describing a device

```python
from apedk import Device, Field

DEVICE = Device("BUS", "aPE-L1 Panel", version=1, description="8 LEDs and a push button")

DEVICE.param("leds", 8)

DEVICE.region("io", size=16, kind="registers")
DEVICE.region("pattern", size=32, kind="buffer")

DEVICE.register("LEDS", "io", offset=0x0, width=8, description="one bit per LED")
DEVICE.register("CTRL", "io", offset=0x1, width=8, reset=0x01, fields=[
    Field("ENABLE", lsb=0, description="1 = panel on"),
    Field("BLINK", lsb=1, width=2, description="0 steady, 1 slow, 2 fast"),
])

DEVICE.init("pattern", bytes([1, 2, 4, 8]))
```

A source file must store its device in a variable called **`DEVICE`**.

| Call | Describes |
|---|---|
| `Device(class, model, version, description)` | the device. Class is `RAM`, `MB`, `BUS`, `GPU`, `CPU`, `DISK` or `NET` |
| `.param(name, value)` | a fixed property: int, float, string or bool |
| `.region(name, size, kind, access, offset, align, description)` | a block of the device's memory |
| `.register(name, region, offset, width, access, reset, description, fields)` | a register inside a region |
| `Field(name, lsb, width, description)` | a named group of bits in a register |
| `.init(region, data, offset)` | initial contents, e.g. a font in ROM |

**Regions** are placed one after another unless you give an `offset`. `align`
(default 16) sets the boundary an automatically placed region starts on.
Kinds: `data`, `registers`, `vram`, `buffer`, `rom`, `state`. Access is any
combination of `r`, `w` and `x`.

**Registers** are 8, 16 or 32 bits wide, sit inside a region at a byte offset,
and start at their `reset` value when the device powers on. Fields name the
bits: `lsb` is the lowest bit, and `width` is how many bits the field uses.

## What gets checked

`check` and `build` report every problem at once.

**Errors** stop a build:
- overlapping regions, or registers that overlap or don't fit in their region
- register widths other than 8/16/32, or registers off their natural boundary
  (a 16-bit register needs an even offset, as on real buses)
- reset values too big for the register, fields outside their register or overlapping each other
- unknown classes, kinds or access letters, duplicate names, model names longer than 14 characters

**Warnings** point out things that break the [naming scheme](../NAMING.md): a GPU
called `aPE-X1` instead of `aPE-G…`, a model name not shaped like `aPE-<letter><model>`,
or a register placed in a region that isn't a `registers` region.

## JSON instead of Python

The same device, without programming:

```json
{
  "type": "bus",
  "name": "aPE-L1 Panel",
  "params": { "leds": 8 },
  "regions": [ { "name": "io", "size": 16, "kind": "registers" } ],
  "registers": [
    { "name": "CTRL", "region": "io", "offset": 1, "reset": 1,
      "fields": [ { "name": "ENABLE", "lsb": 0 } ] }
  ],
  "init": [ { "region": "io", "offset": 8, "bytes": [1, 2, 4, 8] } ]
}
```

Any other top-level key becomes a parameter. That's why the simple RAM and
CPU specs in `/motherboard` compile as they are:

```bash
python ape_devkit.py build motherboard/cpu/ape-p1.json
```

## Modules and instances

- A **module** (`ape-l1-panel.apebus`) is the compiled description. It's
  pure data, so sharing one is safe: loading it never runs anyone's code.
- An **instance** (`bus0.apebus`) is a powered-on device: the same header and
  descriptor, followed by the device's memory with every register at its reset value.

```bash
python ape_devkit.py instance ape-l1-panel.apebus bus0.apebus
```

```bash
python ape_devkit.py info bus0.apebus
```

On an instance, `info` also shows every register's **current** value.

Disks are the exception to "safe to recreate": a `.apedisk` instance holds data,
so the kit refuses to overwrite an existing one (`--overwrite` forces it).

## Using compiled modules in aPEOSI

`board.json` accepts compiled modules wherever it accepts JSON specs:

```json
{
  "name": "aPE-B1 Classic",
  "cpu": "cpu/ape-p1.apecpu",
  "ram": "ram/ape-r16k.aperam"
}
```

aPEOSI checks that each module's class matches its slot, so a CPU module
can't be plugged in as RAM.

## Safety

- **Building a `.py` source runs it**, because it's a Python program. Only
  build Python sources you trust, just as you would only run programs you trust.
- **JSON specs and compiled modules are plain data.** They are safe to
  share and to load.

## Tests

```bash
python -m unittest discover tests
```
