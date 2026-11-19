"""
aPE-T1 Timer: a programmable interval timer on the on-board system bus.

The simplest device with real logic, and the one that makes preemptive
multitasking possible on real computers (the PC's version is the 8253/8254).

How it works:
    a 32-bit down-counter, clocked at clock_hz (1000 = one tick per millisecond).
    Every tick, if CTRL.ENABLE is set, COUNT goes down by one. When it reaches
    zero, STATUS.FIRED is set and, if CTRL.IRQ_EN is set, the IRQ line goes high.
    In periodic mode COUNT reloads from LOAD and keeps going; otherwise the
    timer stops (one-shot).

    STATUS is "write 1 to clear": the OS writes 1 to STATUS.FIRED to acknowledge
    the interrupt, which also lowers the IRQ line.

State machine:
    STOPPED --CTRL.ENABLE=1--> COUNTING --COUNT hits 0--> FIRED
       ^                          ^                        |
       |                          +---- periodic: reload --+
       +------------------------- one-shot: stop ----------+
"""

from apedk import Device, DeviceLogic, Field

DEVICE = Device("BUS", "aPE-T1 Timer", function="TIMER", version=1,
                description="32-bit programmable interval timer")
DEVICE.param("clock_hz", 1000)

DEVICE.region("regs", size=16, kind="registers")
DEVICE.register("CTRL", "regs", offset=0x0, width=8, description="control", fields=[
    Field("ENABLE", lsb=0, description="1 = counting"),
    Field("PERIODIC", lsb=1, description="1 = reload and repeat, 0 = one-shot"),
    Field("IRQ_EN", lsb=2, description="1 = raise the IRQ when the count reaches 0"),
])
DEVICE.register("STATUS", "regs", offset=0x1, width=8, description="write 1 to clear", fields=[
    Field("FIRED", lsb=0, description="the count reached 0"),
])
DEVICE.register("LOAD", "regs", offset=0x4, width=32, reset=1000, description="ticks per period")
DEVICE.register("COUNT", "regs", offset=0x8, width=32, access="r", description="ticks left")
DEVICE.register("FIRES", "regs", offset=0xC, width=32, access="r", description="times the count reached 0")


class LOGIC(DeviceLogic):
    def reset(self):
        self.set("COUNT", 0)

    def write(self, name, value):
        if name == "STATUS":                      # write-1-to-clear
            self.set("STATUS", self.reg("STATUS") & ~value)
            if not self.field("STATUS.FIRED"):
                self.irq(False)
            return
        was_on = self.field("CTRL.ENABLE")
        super().write(name, value)
        if name == "CTRL" and self.field("CTRL.ENABLE") and not was_on:
            self.set("COUNT", self.reg("LOAD"))   # starting: load the counter

    def tick(self):
        if not self.field("CTRL.ENABLE"):
            return
        count = self.reg("COUNT") - 1
        if count > 0:
            self.set("COUNT", count)
            return
        # reached zero
        self.set_field("STATUS.FIRED", 1)
        self.set("FIRES", self.reg("FIRES") + 1)
        if self.field("CTRL.IRQ_EN"):
            self.irq(True)
        if self.field("CTRL.PERIODIC"):
            self.set("COUNT", max(1, self.reg("LOAD")))
        else:
            self.set("COUNT", 0)
            self.set_field("CTRL.ENABLE", 0)
