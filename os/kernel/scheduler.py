# Used to manage (simulating) task scheduling and CPU time allocation
# not efficient, subject to change
import time
from core import globals

tick = 0




class Ticker:
    def __init__(self):
        self.tick = 0

    def start(self):
        while True:
            globals.current_tick = self.tick + globals.current_time
            self.tick = self.tick + globals.tick_precision
            time.sleep(globals.tick_precision)
