from devices.internal.A.apeos.system2.sys.schedule_mgr import ScheduleManager
from devices.internal.A.apeos.system2.sys.time_mgr import *
import platform

print("Booting aPEOS-I System...")
DELAY(100)

SCHLMGR = ScheduleManager()
print("Schedule Manager initialized.")

DELAY(50)

print("Getting system credentials...")

OS_NAME = platform.system()
OS_VERSION = platform.version()

print(f"Operating System: {OS_NAME} Version: {OS_VERSION}")

DELAY(50)

EXEC_TIME = str(f"[{TIME_FULL_YMD()}]")
print(f"Execution Time according to the base system: {EXEC_TIME}")

