from devices.internal.A.apeos.system2.sys.process_mgr import ProcessManager
from devices.internal.A.apeos.system2.sys.time_mgr import *
from devices.internal.A.apeos.system2.sys.kernel import Kernel
import platform

print("Booting aPEOS-I System...")
DELAY(3000)

PROCMGR = ProcessManager()
print("Process Manager initialized.")

DELAY(300)

print("Getting system credentials...")

OS_NAME = platform.system()
OS_VERSION = platform.version()
APEOS_VERSION = "alpha-1"

print(f"Operating System: {OS_NAME} Version: {OS_VERSION}")

DELAY(1500)

EXEC_TIME = str(f"[{TIME_FULL_DMY()}]")
print(f"Execution Time according to the base system: {EXEC_TIME}")

print("System boot complete. Welcome to aPEOS-I!")
print(f"aPEOSI {APEOS_VERSION}, expect bugs. Use at your own risk.")
print("\nHanding over to kernel...")
DELAY(500)

# Initialize and start the kernel
kernel = Kernel(PROCMGR, APEOS_VERSION, OS_NAME, OS_VERSION)
kernel.start()