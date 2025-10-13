# kernel/dispatcher.py
# ahfuba's Python Emulated Operating System Interface (aPEOSI)
# Command Dispatcher - routes parsed commands to appropriate handlers

from core import io_manager
from core import commands as kernel_core
from exec import system_commands, user_commands, app_commands

class Dispatcher:
    
    # the Dispatcher acts as a command execution manager.
    # it routes parsed commands from IOManager to the corresponding module.
    

    def __init__(self):
        self.commands = {}
        self.aliases = {}
        self._register_all()

    def _register_all(self):
        """Register all built-in commands"""
        # CORE commands
        self._register("tick", kernel_core.cmd_tick, category="Core", aliases=["step", "chktick"])
        self._register("terminate", kernel_core.cmd_terminate, category="Core", aliases=["$t", "trmnt"])
        self._register("panic", kernel_core.cmd_panic, category="Core", aliases=["$p", "alarm"])
        self._register("reboot", kernel_core.cmd_reboot, category="Core", aliases=["restart"])
        self._register("pause", kernel_core.cmd_pause, category="Core")

        # SYSTEM commands
        self._register("go", system_commands.cmd_go, category="System", aliases=["cd"])
        self._register("mount", system_commands.cmd_mount, category="System", aliases=["mnt", "mntdisk"])
        self._register("run", system_commands.cmd_run, category="System", aliases=["start"])
        self._register("find", system_commands.cmd_find, category="System", aliases=["search"])
        self._register("create", system_commands.cmd_create, category="System", aliases=["crt", "make"])
        self._register("connect", system_commands.cmd_connect, category="System", aliases=["cnct"])
        self._register("embrc", system_commands.cmd_embrc, category="System", aliases=["embrace"])
        self._register("disown", system_commands.cmd_disown, category="System")
        self._register("ipinfo", system_commands.cmd_ipinfo, category="System")
        self._register("edit", system_commands.cmd_edit, category="System")
        self._register("login", system_commands.cmd_login, category="User")
        self._register("see", system_commands.cmd_see, category="System", aliases=["dir", "directory"])

        # SYSTEM APP commands
        self._register("diskm", app_commands.cmd_disk_manager, category="SystemApp", aliases=["dskm", "diskmanager"])

    def _register(self, name, func, category="System", aliases=None):
        """Register a command and its aliases"""
        self.commands[name] = {"function": func, "category": category}
        if aliases:
            for alias in aliases:
                self.aliases[alias] = name

    def execute(self, raw_input: str):
        """Parse and execute a command line string"""
        if not raw_input.strip():
            return " "

        parts = raw_input.split()
        cmd_name = parts[0].lower()
        args = parts[1:]

        # Alias redirect
        if cmd_name in self.aliases:
            cmd_name = self.aliases[cmd_name]

        # Unknown command
        if cmd_name not in self.commands:
            io_manager.error(f"Unknown command: '{cmd_name}'")
            return

        func = self.commands[cmd_name]["function"]
        try:
            result = func(*args)
            return result if result else ""
        except Exception as e:
            io_manager.error(f"Error while executing '{cmd_name}': {e}")
            return

# Singleton instance
dispatcher = Dispatcher()
