# core/io_manager.py
import sys
from core import globals
from kernel.scheduler import Ticker

class IOManager:
    def __init__(self):
        self.prompt = "> "
        self.terminate_word = "terminate"
        self.tick_check_word = "tick"
        self.logs = []

    def input(self, prompt=None):
        prompt = prompt or self.prompt
        user_input = input(prompt)

       # terminates the system if the terminate word is entered in any input given
        if user_input.lower() == self.terminate_word:
            self.output("System terminating...")
            self.output("System terminated at tick: " + str(globals.current_tick))
            globals.terminate = True
            return None
        if user_input.lower() == self.tick_check_word:
            self.tick_check("Tick check requested by user. Current tick: " + str(globals.current_tick))
            return None

        
        self.log(f"INPUT: {user_input}")
        return user_input

    def output(self, message):
        print(message)
        self.log(f"OUTPUT: {message}")

    def error(self, message):
        print(f"[ERROR] {message}")
        self.log(f"ERROR: {message}")

    def log(self, entry):
        self.logs.append(entry)

    def tick_check(self, message):
        print(f"[TICK CHECK] {message}")
        self.log(f"TICK CHECK: {message}")

        