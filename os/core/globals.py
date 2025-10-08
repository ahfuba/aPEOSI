# core/globals.py
# subject to being moved to a json, yaml or cfg config file later (i will write OBSOLETE in that case)

# do NOT change these variables directly, use the provided methods in io_manager.py and main.py during runtime
import time


terminate = False
current_user = ""
system_name = "aPEOSI"

# singleton instances
input_manager = None
kernel = None
io = None

# do NOT change this value directly, use the Ticker class in scheduler.py to manage ticks
current_tick = 0.0

# determines the simulation ticker precision, lower is more precise but more CPU intensive. use at your own risk.
# the float entered will determine the rate of ticks. ie, 0.2 means each tick will equal to 0.2 seconds.
# WARNING: ONLY USE NUMBERS BETWEEN 0 AND 1.
# DO NOT SET THIS TO 0, IT WILL CRASH THE SYSTEM.
# DO NOT SET THIS TO 1 OR HIGHER, IT WILL MAKE THE SYSTEM UNRESPONSIVE.
# p.s: my dumbass wrote "precision" instead of "length" at first for some fucking reason.
# p.s2: turns out i wasnt a dumbass
# p.s3: yeah im a fucking imbecile i don't know how to use time HAISHFIAUHKJAJGA
tick_precision = 0.1

# do NOT assign anything to this value. even if the world ends.
# START OF TIME IS ALWAYS 0 YOU FUCKING IDIOT. WHY WOULD YOU EVEN THINK OF CHANGING IT.
time_raw = time.time()
current_time = int(time_raw) + int((time_raw % 1) * 10) / 10
print(current_time)
# import time;le_bing_bang = time.time()  # the start of time, in seconds since epoch. do NOT change this value. [OBSOLETE]

