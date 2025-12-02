import csv
from . import sys_cmd_exec

class IOManager:
    """Handles user input, command parsing, and delegation."""

    def __init__(self, kernel):
        self.kernel = kernel
        self.commands = {}
        self.aliases = {}
        self._load_commands()

    def _load_commands(self):
        """Loads command definitions from the CSV file."""
        try:
            path = 'c:/Users/ahfuba/Desktop/aPEOSI/devices/internal/A/apeos/system2/sys/sys_cmd.csv'
            with open(path, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # skip empty rows which can cause KeyErrors
                    if not row or not row.get('command'):
                        continue

                    command_name = row.get('command', '').strip()
                    alias_name = row.get('alias', '').strip()
                    self.commands[command_name] = {k.strip(): v.strip() for k, v in row.items()}
                    if alias_name and command_name:
                        self.aliases[alias_name] = command_name
            print("Command Manager: Commands loaded successfully.")
        except FileNotFoundError:
            print(f"FATAL: Command CSV not found at {path}")
            self.kernel.running = False
        except Exception as e:
            print(f"FATAL: Error loading commands: {e}")
            self.kernel.running = False

    def handle_input(self, command_line: str):
        """Parses and executes a command."""
        parts = command_line.strip().split()
        if not parts:
            return

        is_background = False
        if parts[-1] == '&':
            is_background = True
            parts.pop()
            if not parts: return # User just typed '&'

        command_name = parts[0].lower()
        args = parts[1:]

        # resolve alias if used
        actual_command = self.aliases.get(command_name, command_name)
        cmd_info = self.commands.get(actual_command)

        if cmd_info:
            # Delegate execution to the command executor.
            # sys_cmd_exec will determine if it's a built-in or an app.
            sys_cmd_exec.execute_command(actual_command, args, self.kernel, self, is_background)
        else:
            print(f"Unknown command: '{command_name}'. Type 'help' for a list of commands.")
