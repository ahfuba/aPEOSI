import time

def get_system_time():
    """Retrieve the current system time in seconds since the epoch."""
    # get the current time on each call
    return time.time()

def TIME_HH_MM():
    """Return the current time formatted as hh:mm."""
    # get the current time structure on each call
    return time.strftime("%H:%M", time.localtime())

def TIME_FULL_DMY():
    """Return the current time formatted as hh:mm:ss dd/mm/yyyy."""
    return time.strftime("%H:%M:%S %d/%m/%Y", time.localtime())

# format 3: yyyy/mm/dd/hh/mm/ss
def TIME_FULL_YMD():
    """Return the current time formatted as yyyy/mm/dd/hh/mm/ss."""
    return time.strftime("%Y/%m/%d/%H/%M/%S", time.localtime())

def TIME_DATE_DMY():
    """Return the current date formatted as dd/mm/yyyy."""
    return time.strftime("%d/%m/%Y", time.localtime())

# format 4: seconds since epoch
# this is the raw value from time.time()
def TIME_SECONDS_EPOCH():
    """Return the current time as seconds since the epoch."""
    return int(time.time())

def DELAY(milliseconds):
    """Pause execution for a given number of milliseconds."""
    time.sleep(milliseconds / 1000)

