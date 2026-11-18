"""
Process manager: creates, tracks and destroys processes.

A process is an application's generator (its code and saved position, i.e.
its "registers") plus a Process Control Block (PCB). In aPEOSI 1.2 the PCB
lives in aPE-RAM, so ``state`` below is read from and written to RAM.

System calls
------------
An application talks to the kernel by *yielding a request object*, much like
a real program executes a trap instruction:

    yield                       # "I'm done for now, run someone else"
    yield Sleep(0.5)            # don't schedule me for 0.5 seconds
    line = yield ReadLine("> ") # block until the user types a line
"""

import enum
import inspect

from .mem_mgr import AddressSpace, MemoryManager


class ProcessState(enum.IntEnum):
    """Represents the state of a process. The number is what is stored in RAM."""
    RUNNING = 1            # ready to run (or running right now)
    WAITING_FOR_INPUT = 2  # blocked in ReadLine
    TERMINATED = 3         # finished
    SLEEPING = 4           # blocked in Sleep


class Sleep:
    """System call: pause this process for ``seconds``."""
    def __init__(self, seconds):
        self.seconds = max(0.0, float(seconds))


class ReadLine:
    """System call: wait for one line of keyboard input."""
    def __init__(self, prompt=""):
        self.prompt = prompt


def _as_generator(result):
    """Lets an app's run() be a plain function too (it then runs in one step)."""
    if inspect.isgenerator(result):
        return result

    def done():
        return
        yield  # makes this a generator
    return done()


class Process:
    """Python-side handle of a process. Its PCB lives in aPE-RAM."""

    def __init__(self, manager, slot, pid, name, app_instance):
        self._manager = manager
        self.slot = slot
        self.pid = pid
        self.name = name
        self.app_instance = app_instance
        self.task = None        # the generator, created after the app gets its memory
        self.inbox = None       # value sent into the generator on its next step
        self.wake_at = 0.0      # for SLEEPING
        self.prompt = ""        # for WAITING_FOR_INPUT
        self.kill_pending = None  # (reason, quiet) if killed while it was running
        self._terminated = False

    @property
    def state(self):
        if self._terminated:
            return ProcessState.TERMINATED
        return ProcessState(self._manager.mm.read_pcb(self.slot)["state"])

    @state.setter
    def state(self, value):
        if self._terminated:
            return
        self._manager.mm.update_pcb(self.slot, state=int(value))


class ProcessManager:
    """Manages all processes in the system for cooperative multitasking."""

    def __init__(self, mm: MemoryManager):
        self.mm = mm
        self.processes = {}
        self.next_pid = 1
        self.foreground_pid = None  # PID of the process that owns the keyboard
        self.running_pid = None     # PID on the CPU right now (set by the kernel)

    def create_process(self, app_instance, command_name, is_foreground=True):
        """Creates a PCB + address space in RAM and starts the app."""
        pid = self.next_pid
        slot = self.mm.create_process_entry(pid, command_name, int(ProcessState.RUNNING))
        self.next_pid = (self.next_pid % 0xFFFE) + 1

        process = Process(self, slot, pid, command_name, app_instance)
        app_instance.pid = pid
        app_instance.mem = AddressSpace(self.mm, slot)
        try:
            process.task = _as_generator(app_instance.run())
        except Exception:
            self.mm.destroy_process_entry(slot)
            raise
        self.processes[pid] = process

        if is_foreground:
            self.foreground_pid = pid

        print(f"[{pid}] Process '{command_name}' started.")
        return process

    def record_run(self, process, tick):
        """Bookkeeping in the PCB each time the scheduler runs a process."""
        pcb = self.mm.read_pcb(process.slot)
        self.mm.update_pcb(process.slot, sched_count=(pcb["sched_count"] + 1) & 0xFFFFFFFF,
                           last_tick=tick)

    def terminate(self, pid, reason=None, quiet=False):
        """Ends a process and gives all its memory back."""
        process = self.processes.get(pid)
        if process is None:
            return False
        if pid == self.running_pid:
            # The process is killing itself mid-step. Freeing its memory now
            # would pull the floor out from under it, so the kernel finishes
            # the job when its time slice ends.
            process.kill_pending = (reason, quiet)
            return True
        del self.processes[pid]
        try:
            process.task.close()
        except Exception:
            pass
        process._terminated = True
        self.mm.destroy_process_entry(process.slot)
        if self.foreground_pid == pid:
            self.foreground_pid = None
        if not quiet:
            msg = f"[{pid}] Process '{process.name}' terminated."
            print(f"\n{msg}" + (f" ({reason})" if reason else ""))
        return True

    def get(self, pid):
        return self.processes.get(pid)

    def get_running_processes(self):
        """Returns a list of all live (non-terminated) processes."""
        return list(self.processes.values())

    def get_foreground_process(self):
        """Gets the process currently in the foreground."""
        if self.foreground_pid is not None:
            return self.processes.get(self.foreground_pid)
        return None

    def set_foreground_process(self, pid):
        """Gives the keyboard to a process."""
        if pid in self.processes:
            self.foreground_pid = pid
            return True
        return False
