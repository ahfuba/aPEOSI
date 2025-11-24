import time

SYS_TIME = time.time()

def get_system_time():
    """Retrieve the current system time in seconds since the epoch."""
    return SYS_TIME

local_time_struct = time.localtime(SYS_TIME)

def HH_MM():
    """Return the current time formatted as hh:mm."""
    return time.strftime("%H:%M", local_time_struct)
# Format 1: hh:mm
TIME_HH_MM = time.strftime("%H:%M", local_time_struct)

def TIME_FULL_DMY():
    """Return the current time formatted as hh:mm:ss dd/mm/yyyy."""
    return time.strftime("%H:%M:%S %d/%m/%Y", local_time_struct)


# Format 3: yyyy/mm/dd/hh/mm/ss
def TIME_FULL_YMD():
    """Return the current time formatted as yyyy/mm/dd/hh/mm/ss."""
    return time.strftime("%Y/%m/%d/%H/%M/%S", local_time_struct)


def TIME_DATE_DMY():
    """Return the current date formatted as dd/mm/yyyy."""
    return time.strftime("%d/%m/%Y", local_time_struct)

# Format 4: Seconds since epoch
# This is the raw value from time.time()
def TIME_SECONDS_EPOCH():
    """Return the current time as seconds since the epoch."""
    return int(SYS_TIME)