import os
from .process_mgr import ProcessManager, ProcessState
from .time_mgr import *
from .io_mgr import IOManager
from .filesys_mgr import FileSystemManager

class Kernel:
    """The core of the OS, handling process scheduling and system calls."""

    def __init__(self, proc_manager: ProcessManager, apeos_version: str, os_name: str, os_version: str):
        self.proc_manager = proc_manager
        
        # Determine project root to find the 'disks' directory
        # Assumes kernel.py is at aPEOSI/devices/internal/A/apeos/system2/sys/
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..'))
        
        self.fs_manager = FileSystemManager(self, project_root)
        self.io_manager = IOManager(self) # Handles command parsing
        
        self.running = False
        self.apeos_version = apeos_version
        self.os_name = os_name
        self.os_version = os_version

    def _get_prompt(self):
        """Determines the correct prompt to display."""
        foreground_process = self.proc_manager.get_foreground_process()
        if foreground_process and foreground_process.state == ProcessState.WAITING_FOR_INPUT:
            # If an app is waiting for input, it controls the prompt
            return "" # The app itself will print a prompt if it has one
        
        # Otherwise, show the default shell prompt
        full_path = self.fs_manager.get_full_current_path()
        if full_path.endswith('/') and len(full_path) > 1:
            full_path = full_path[:-1]
        return f"aPEOS_{self.apeos_version} {full_path}> "

    def start(self):
        """Starts the main kernel loop to process commands."""
        self.running = True
        while self.running:
            try:
                # --- INPUT HANDLING ---
                foreground_process = self.proc_manager.get_foreground_process()
                if foreground_process and foreground_process.state == ProcessState.WAITING_FOR_INPUT:
                    # An app is waiting for input, so we block and wait for the user
                    user_input = input(self._get_prompt())
                    foreground_process.app_instance.send_input(user_input)
                    foreground_process.state = ProcessState.RUNNING
                else:
                    # The shell is active. We can run background tasks here.
                    # For now, we just handle the next command.
                    user_input = input(self._get_prompt())
                    self.io_manager.handle_input(user_input)

                # --- SCHEDULER ---
                # Give every running process a chance to run
                # Make a copy of the list as it might be modified during iteration
                for process in list(self.proc_manager.get_running_processes()):
                    if process.state == ProcessState.RUNNING:
                        try:
                            # Execute the next step of the process's generator
                            next(process.task)
                        except StopIteration:
                            # The process's run() method has finished
                            print(f"\n[{process.pid}] Process '{process.name}' terminated.")
                            process.state = ProcessState.TERMINATED
                            if self.proc_manager.foreground_pid == process.pid:
                                self.proc_manager.foreground_pid = None
                        except Exception as e:
                            print(f"\n[{process.pid}] Error in process '{process.name}': {e}")
                            process.state = ProcessState.TERMINATED
                            if self.proc_manager.foreground_pid == process.pid:
                                self.proc_manager.foreground_pid = None

            except KeyboardInterrupt:
                print("\nUse 'exit' to shut down the system.")
            except Exception as e:
                print(f"An error occurred: {e}")
