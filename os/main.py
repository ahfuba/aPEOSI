from core import globals
from core.io_manager import IOManager
from kernel import scheduler
globals.io = IOManager()

globals.scheduler = scheduler.Ticker()

while not globals.terminate:
    cmd = globals.io.input()
    if globals.terminate or cmd is None:
        break
    globals.io.output(f"Executing: {cmd}")

globals.io.output("System has been shut down successfully.")
