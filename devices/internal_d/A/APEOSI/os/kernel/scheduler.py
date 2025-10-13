
# scheduler.py
# aPEOSI System Scheduler
# generates ticks at fixed intervals, updating global simulation time.

import threading
import time
from core import global_vars as g

# core system ticker
# emits ticks at fixed intervals, updating global simulation time

class Ticker(threading.Thread):
    def __init__(self, io_manager):
        super().__init__()
        self.daemon = True             # thread ends with main program exit
        self.io = io_manager           # IOManager reference
        self.tick = 0                  # internal tick counter
        self.running = False           # is the thread active?

# main loop of the ticker thread
    def run(self):
        
        self.running = True
        self.io.output("[TICKER] Ticker started.")

        while self.running and not g.terminate:
            # calculate and update global tick
            g.current_tick = self.tick + g.current_tick

            # increment tick
            self.tick += 1

            # wait to avoid CPU hogging
            time.sleep(g.tick_precision)

        self.io.output("[TICKER] Ticker stopped.")

# stops the ticker safely.
    def stop(self):
        self.running = False
