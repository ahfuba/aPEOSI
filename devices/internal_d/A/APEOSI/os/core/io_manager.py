# core/io_manager.py
import sys
import csv
import importlib
from core import global_vars
from kernel.scheduler import Ticker
from kernel.dispatcher import dispatcher


class IOManager:
    def __init__(self):
        self.prompt = "> "
        self.terminate_word = "terminate"
        self.tick_check_word = "tick"
        self.logs = []

    def input(self, prompt=None, csv_path="command_dict.csv"):
        prompt = prompt or self.prompt
        user_input = input(prompt)


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

    def handle_input(user_input):
        output = dispatcher.execute(user_input)
        if output:
            print(output)


        