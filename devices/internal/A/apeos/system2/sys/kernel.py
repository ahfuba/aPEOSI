import os
import queue
import sys
import threading
import time

from .aperam import KERNEL_PID
from .process_mgr import ProcessManager, ProcessState, ReadLine, Sleep
from .mem_mgr import MemoryManager
from .io_mgr import IOManager
from .filesys_mgr import FileSystemManager

_EOF = object()


class Console:
    """
    The keyboard. A background thread reads lines and queues them, so the
    kernel never has to block on input() and background processes keep
    running while you type.
    """

    def __init__(self):
        self.lines = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            line = sys.stdin.readline()
            if line == "":
                if sys.stdin.isatty():
                    # Interactive console: ignore stray EOFs (Ctrl+Z/Ctrl+D);
                    # use 'exit' to shut down.
                    time.sleep(0.1)
                    continue
                self.lines.put(_EOF)  # piped input ran out
                return
            self.lines.put(line.rstrip("\r\n"))

    def get(self, timeout):
        try:
            if timeout <= 0:
                return self.lines.get_nowait()
            return self.lines.get(timeout=timeout)
        except queue.Empty:
            return None


class Kernel:
    """The core of the OS, handling process scheduling and system calls."""

    # Never wait longer than this in one go, so Ctrl+C stays responsive.
    MAX_WAIT = 0.05

    def __init__(self, proc_manager: ProcessManager, mem_manager: MemoryManager, board,
                 apeos_version: str, os_name: str, os_version: str):
        self.proc_manager = proc_manager
        self.mem_manager = mem_manager
        self.board = board

        # Determine project root to find the 'devices' directory
        # kernel.py is at aPEOSI/devices/internal/A/apeos/system2/sys/
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..'))

        self.fs_manager = FileSystemManager(self, project_root)
        self.io_manager = IOManager(self)  # Handles command parsing

        self.running = False
        self.apeos_version = apeos_version
        self.os_name = os_name
        self.os_version = os_version
        self.cycle_time = 1.0 / board.cpu.clock_hz
        self._last_round = 0.0

    def _get_prompt(self):
        """Determines the correct prompt to display."""
        foreground_process = self.proc_manager.get_foreground_process()
        if foreground_process:
            # An app owns the keyboard; it chose its own prompt in ReadLine.
            return foreground_process.prompt

        full_path = self.fs_manager.get_full_current_path()
        if full_path.endswith('/') and not full_path.endswith(':/'):
            full_path = full_path[:-1]  # keep the slash only at a drive's root
        return f"aPEOSI {self.apeos_version} {full_path}> "

    def _wants_input(self):
        fg = self.proc_manager.get_foreground_process()
        return fg is None or fg.state == ProcessState.WAITING_FOR_INPUT

    def _next_wakeup(self):
        """Seconds until a sleeping process must run again (or None)."""
        wakes = [p.wake_at for p in self.proc_manager.get_running_processes()
                 if p.state == ProcessState.SLEEPING]
        return max(0.0, min(wakes) - time.monotonic()) if wakes else None

    def _has_runnable(self):
        return any(p.state == ProcessState.RUNNING for p in self.proc_manager.get_running_processes())

    def start(self):
        """Starts the main kernel loop."""
        self.running = True
        console = Console()
        prompt_shown = False

        while self.running:
            try:
                # --- INPUT ---------------------------------------------------
                if self._wants_input():
                    if not prompt_shown:
                        print(self._get_prompt(), end="", flush=True)
                        prompt_shown = True
                    if self._has_runnable():
                        timeout = 0
                    else:
                        wake = self._next_wakeup()
                        timeout = self.MAX_WAIT if wake is None else min(wake, self.MAX_WAIT)
                    line = console.get(timeout)
                    if line is _EOF:
                        print("\n[end of input]")
                        self.running = False
                        break
                    if line is not None:
                        prompt_shown = False
                        self.mem_manager.keyboard(line)
                        fg = self.proc_manager.get_foreground_process()
                        if fg and fg.state == ProcessState.WAITING_FOR_INPUT:
                            fg.inbox = line          # becomes the result of ReadLine
                            fg.state = ProcessState.RUNNING
                        else:
                            self.io_manager.handle_input(line)
                elif not self._has_runnable():
                    # Foreground app is asleep and nothing else can run.
                    wake = self._next_wakeup()
                    time.sleep(self.MAX_WAIT if wake is None else min(wake, self.MAX_WAIT))

                # --- SCHEDULER -----------------------------------------------
                if self._schedule_round():
                    prompt_shown = False  # something terminated; redraw the prompt

            except KeyboardInterrupt:
                fg = self.proc_manager.get_foreground_process()
                if fg:
                    print("^C")
                    self.proc_manager.terminate(fg.pid, "interrupted")
                else:
                    print("\nUse 'exit' to shut down the system.")
                prompt_shown = False
            except Exception as e:
                print(f"An error occurred: {e}")
                prompt_shown = False

        # Shutdown: end every process while their memory still exists.
        for process in self.proc_manager.get_running_processes():
            self.proc_manager.terminate(process.pid, "shutdown", quiet=True)
        self.mem_manager.set_current_pid(KERNEL_PID)

    def _schedule_round(self):
        """
        Gives every ready process one step (round-robin). The CPU module's
        clock_hz limits how many rounds happen per second.
        Returns True if a process terminated.
        """
        now = time.monotonic()
        for p in self.proc_manager.get_running_processes():
            if p.state == ProcessState.SLEEPING and now >= p.wake_at:
                p.state = ProcessState.RUNNING
        ready = [p for p in self.proc_manager.get_running_processes() if p.state == ProcessState.RUNNING]
        if not ready:
            return False

        # Throttle to the CPU clock.
        wait = self._last_round + self.cycle_time - now
        if wait > 0:
            time.sleep(min(wait, self.MAX_WAIT))
            if wait > self.MAX_WAIT:
                return False
        self._last_round = time.monotonic()

        terminated = False
        for process in ready:
            if process.pid not in self.proc_manager.processes:
                continue  # killed earlier in this round
            # --- context switch in: the RAM header shows who is running ---
            tick = self.mem_manager.tick()
            self.mem_manager.set_current_pid(process.pid)
            self.proc_manager.record_run(process, tick)
            self.proc_manager.running_pid = process.pid
            error = None
            try:
                message, process.inbox = process.inbox, None
                request = process.task.send(message)
            except StopIteration:
                request, error = None, StopIteration
            except Exception as e:
                request, error = None, e
            finally:
                # --- context switch out: back to the kernel ---
                self.proc_manager.running_pid = None
                self.mem_manager.set_current_pid(KERNEL_PID)

            if error is StopIteration:
                self.proc_manager.terminate(process.pid)
                terminated = True
                continue
            if error is not None:
                self.proc_manager.terminate(process.pid, f"error: {error}")
                terminated = True
                continue
            if process.kill_pending is not None:
                reason, quiet = process.kill_pending
                self.proc_manager.terminate(process.pid, reason, quiet)
                terminated = True
                continue

            # --- handle the system call the process made ---
            if isinstance(request, Sleep):
                process.wake_at = time.monotonic() + request.seconds
                process.state = ProcessState.SLEEPING
            elif isinstance(request, ReadLine):
                process.prompt = request.prompt
                process.state = ProcessState.WAITING_FOR_INPUT
        return terminated
