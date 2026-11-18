from devices.internal.A.apeos.system2.sys.process_mgr import Sleep


class Counter:
    """
    A 32-bit binary ripple counter that lives in this process's aPE-RAM.

    Open the aPE-Watchdog, click this process's user page, and watch the
    bits count up exactly like a chain of T flip-flops: the rightmost bit
    toggles every step, the next one every 2 steps, the next every 4, ...

    Virtual memory layout of this process:
        0x00..0x03  the counter, stored big-endian so it reads left-to-right
                    in the Watchdog like a normal binary number
        0x08..0x0F  a "walking LED": a single 1 bit bouncing back and forth
    """

    def __init__(self, kernel, interval_ms="100"):
        self.kernel = kernel
        try:
            self.interval = max(int(interval_ms), 1) / 1000
        except ValueError:
            raise ValueError(f"interval must be whole milliseconds, got '{interval_ms}'")

    def run(self):
        value = 0
        led, direction = 0, 1
        while True:
            value = (value + 1) & 0xFFFFFFFF
            self.mem.store(0x00, value.to_bytes(4, "big"))

            self.mem.store(0x08, (1 << (63 - led)).to_bytes(8, "big"))
            if not 0 <= led + direction <= 63:
                direction = -direction
            led += direction

            yield Sleep(self.interval)  # system call: let others run
