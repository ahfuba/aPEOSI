import argparse
import os
import platform
import sys

from devices.internal.A.apeos.system2.sys.time_mgr import *
from devices.internal.A.apeos.system2.sys import hardware
from devices.internal.A.apeos.system2.sys.aperam import PhysicalRAM
from devices.internal.A.apeos.system2.sys.mem_mgr import MemoryManager
from devices.internal.A.apeos.system2.sys.process_mgr import ProcessManager
from devices.internal.A.apeos.system2.sys.kernel import Kernel

APEOS_VERSION = "alpha-1.2"
ROOT = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(description="Boot aPEOS-I.")
parser.add_argument("--board", default="board.json",
                    help="motherboard file inside /motherboard (default: board.json)")
parser.add_argument("--fast", action="store_true", help="skip boot delays and the memory test")
options = parser.parse_args()
delay = (lambda ms: None) if options.fast else DELAY

print("Booting aPEOS-I System...")
delay(1000)

# --- Hardware detection (the "BIOS") --------------------------------------
try:
    board = hardware.load_board(os.path.join(ROOT, "motherboard"), options.board)
except hardware.HardwareError as e:
    print(f"BIOS: hardware error: {e}")
    sys.exit(1)

print(f"Motherboard: {board.name}")
print(f"CPU:         {board.cpu.name} @ {board.cpu.clock_hz} Hz")
print(f"RAM:         {board.ram.name}, {board.ram.size:,} bytes "
      f"({board.ram.num_pages} x {board.ram.page_size}-byte frames)")
delay(300)

try:
    ram = PhysicalRAM(board.ram_file, board.ram.size)
except RuntimeError as e:
    print(f"BIOS: {e}")
    sys.exit(1)
print(f"RAM file:    {board.ram_file}")

MEMMGR = MemoryManager(ram, board.ram.page_size, board.ram.num_pages)
MEMMGR.write_header(APEOS_VERSION, board.ram.name)
if not options.fast:
    print("Memory test... ", end="", flush=True)
    tested = MEMMGR.power_on_self_test()
    print(f"{tested:,} bytes OK")
MEMMGR.format()

PROCMGR = ProcessManager(MEMMGR)
print("Process Manager initialized.")
delay(300)

print("Getting system credentials...")

OS_NAME = platform.system()
OS_VERSION = platform.version()

print(f"Operating System: {OS_NAME} Version: {OS_VERSION}")
delay(500)

EXEC_TIME = str(f"[{TIME_FULL_DMY()}]")
print(f"Execution Time according to the base system: {EXEC_TIME}")

print("System boot complete. Welcome to aPEOS-I!")
print(f"aPEOSI {APEOS_VERSION}, expect bugs. Use at your own risk.")
print("Tip: run 'python aperam_watchdog.py' in another window to watch the RAM.")
print("\nHanding over to kernel...")
delay(500)

# Initialize and start the kernel
try:
    kernel = Kernel(PROCMGR, MEMMGR, board, APEOS_VERSION, OS_NAME, OS_VERSION)
    kernel.start()
except RuntimeError as e:
    print(f"FATAL: {e}")
finally:
    ram.close()
print("aPEOS-I halted.")
