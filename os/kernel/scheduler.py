# Used to manage (simulating) task scheduling and CPU time allocation

import time

tick = 0

tick_length = 1.0

while True:
    tick += 1
    time.sleep(tick_length)  # Simulate a clock tick every second
    print(f"Ticked. Previous Tick: {tick}")