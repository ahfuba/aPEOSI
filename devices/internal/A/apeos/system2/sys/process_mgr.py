import enum

class ProcessState(enum.Enum):
    """Represents the state of a running process."""
    RUNNING = 1         # The process is actively running or ready to run.
    WAITING_FOR_INPUT = 2 # The process is paused, waiting for user input.
    TERMINATED = 3      # The process has finished execution.

class Process:
    """Represents a single running application instance."""
    def __init__(self, pid, name, app_instance):
        self.pid = pid
        self.name = name
        self.app_instance = app_instance
        self.state = ProcessState.RUNNING
        # Use a generator for cooperative multitasking
        self.task = self.app_instance.run()

class ProcessManager:
    """
    Manages all running processes in the system for cooperative multitasking.
    """
    def __init__(self):
        self.processes = {}
        self.next_pid = 0
        self.foreground_pid = None # PID of the process currently getting user input

    def create_process(self, app_instance, command_name, is_foreground=True):
        """Creates and starts a new process."""
        pid = self.next_pid
        self.next_pid += 1
        
        process = Process(pid, command_name, app_instance)
        self.processes[pid] = process
        
        if is_foreground:
            self.foreground_pid = pid
        
        print(f"[{pid}] Process '{command_name}' started.")
        return process

    def get_running_processes(self):
        """Returns a list of all non-terminated processes."""
        return [p for p in self.processes.values() if p.state != ProcessState.TERMINATED]

    def get_foreground_process(self):
        """Gets the process currently in the foreground."""
        if self.foreground_pid is not None and self.foreground_pid in self.processes:
            return self.processes[self.foreground_pid]
        return None

    def set_foreground_process(self, pid):
        """Sets a process to be in the foreground."""
        if pid in self.processes and self.processes[pid].state != ProcessState.TERMINATED:
            self.foreground_pid = pid
            return True
        return False
