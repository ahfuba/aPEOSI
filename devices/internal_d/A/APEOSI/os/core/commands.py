# commands.py

commands = {
    "tick": {
        "aliases": ["step", "chktick"],
        "description": "Used to check which tick the system is during runtime.",
        "category": "Core",
        "scope": "Kernel I/O"
    },
    "terminate": {
        "aliases": ["$t", "trmnt"],
        "description": "Stops the system immediately, regardless of input type.",
        "category": "Core",
        "scope": "Kernel I/O"
    },
    "panic": {
        "aliases": ["$p", "alarm"],
        "description": "Activates panic mode; halts all processes and only keeps OS base running.",
        "category": "Core",
        "scope": "Kernel I/O"
    },
    "reboot": {
        "aliases": ["restart"],
        "description": "Reboots the system.",
        "category": "Core",
        "scope": "Kernel I/O"
    },
    "pause": {
        "aliases": [],
        "description": "Pauses the system.",
        "category": "Core",
        "scope": "Kernel I/O"
    },
    "go": {
        "aliases": ["cd"],
        "description": "Change directory within the mounted disk.",
        "category": "System",
        "scope": "OS I/O"
    },
    "mount": {
        "aliases": ["mnt", "mntdisk"],
        "description": "Mounts a disk from /devices/external.",
        "category": "System",
        "scope": "OS I/O"
    },
    "run": {
        "aliases": ["start"],
        "description": "Runs a .yrt application.",
        "category": "System",
        "scope": "OS I/O"
    },
    "find": {
        "aliases": ["search"],
        "description": "Searches for a keyword in the current path.",
        "category": "System",
        "scope": "OS I/O"
    },
    "create": {
        "aliases": ["crt", "make"],
        "description": "Creates a new file (e.g. create file.abc).",
        "category": "System",
        "scope": "OS I/O"
    },
    "connect": {
        "aliases": ["cnct"],
        "description": "Connects to a MAC address or local adapter (simulated).",
        "category": "System",
        "scope": "OS I/O"
    },
    "embrc": {
        "aliases": ["embrace"],
        "description": "Embrace a disk (mount and mark as trusted).",
        "category": "System",
        "scope": "OS I/O"
    },
    "disown": {
        "aliases": [],
        "description": "Unembrace or unmount a disk.",
        "category": "System",
        "scope": "OS I/O"
    },
    "ipinfo": {
        "aliases": [],
        "description": "Displays simulated IP configuration info.",
        "category": "System",
        "scope": "OS I/O"
    },
    "edit": {
        "aliases": [],
        "description": "Opens apeditor for file editing.",
        "category": "System",
        "scope": "OS I/O"
    },
    "login": {
        "aliases": [],
        "description": "Locks CLI and returns to login prompt.",
        "category": "User",
        "scope": "OS I/O"
    },
    "diskm": {
        "aliases": ["dskm", "diskmanager"],
        "description": "Opens Disk Manager (CLI system app).",
        "category": "SystemApp",
        "scope": "OS I/O"
    },
    "see": {
        "aliases": ["dir", "directory"],
        "description": "Lists files and folders in current or given directory.",
        "category": "System",
        "scope": "OS I/O"
    }
}
