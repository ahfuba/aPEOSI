import importlib
from . import time_mgr

# Command Handler Functions
# Each function handles the logic for a specific command.

def _cmd_help(args, kernel, io_manager):
    """Displays a list of available commands."""
    print("Available commands:")
    # sort commands alphabetically for readability
    for cmd_name in sorted(io_manager.commands.keys()):
        cmd_info = io_manager.commands[cmd_name]
        desc = cmd_info.get('desc', 'No description available.')
        alias = cmd_info.get('alias')
        if alias:
            print(f"  {cmd_name:<12} (alias: {alias:<10}) - {desc}")
        else:
            print(f"  {cmd_name:<12} {' ':<19} - {desc}")

def _cmd_list_tasks(args, kernel, io_manager):
    """Lists processes by reading the process table straight out of aPE-RAM."""
    from .aperam import STATE_NAMES
    fg = kernel.proc_manager.foreground_pid
    rows = [(slot, pcb) for slot, pcb in kernel.mem_manager.all_pcbs() if pcb["used"]]
    if not rows:
        print("No processes running.")
        return
    print(f"{'SLOT':>4} {'PID':>5}  {'NAME':<16} {'STATE':<11} {'RUNS':>8} {'PAGES':>5}  PT-FRAME")
    for slot, pcb in rows:
        mark = "*" if pcb["pid"] == fg else " "
        print(f"{slot:>4} {pcb['pid']:>5}{mark} {pcb['name']:<16} {STATE_NAMES.get(pcb['state'], '?'):<11} "
              f"{pcb['sched_count']:>8} {pcb['pages_mapped']:>5}  0x{pcb['pt_frame']:02X}")
    print("(* = foreground)")

def _parse_pid(args, usage):
    if not args:
        print(usage)
        return None
    try:
        return int(args[0], 0)
    except ValueError:
        print(f"Error: '{args[0]}' is not a valid PID.")
        return None

def _cmd_kill(args, kernel, io_manager):
    """Terminates a process."""
    pid = _parse_pid(args, "Usage: kill <pid>")
    if pid is not None and not kernel.proc_manager.terminate(pid, "killed"):
        print(f"Error: no process with PID {pid}.")

def _cmd_fg(args, kernel, io_manager):
    """Brings a background process to the foreground."""
    pid = _parse_pid(args, "Usage: fg <pid>")
    if pid is not None and not kernel.proc_manager.set_foreground_process(pid):
        print(f"Error: no process with PID {pid}.")

def _cmd_mem(args, kernel, io_manager):
    """Shows aPE-RAM usage and a map of every physical frame."""
    from .aperam import FT_FREE, FT_KERNEL, FT_PAGETABLE, FT_USER, ft_decode
    mm = kernel.mem_manager
    lay = mm.layout
    ram = kernel.board.ram
    counts = mm.usage()
    print(f"aPE-RAM: {ram.name}  {lay.size:,} bytes = {lay.num_pages} frames x {lay.page_size} bytes")
    print(f"  kernel {counts[FT_KERNEL]}  page tables {counts[FT_PAGETABLE]}  "
          f"user {counts[FT_USER]}  free {counts[FT_FREE]}")
    print("Frame map  (K kernel, T page table, 0-F user page of PCB slot, . free):")
    symbols = []
    for entry in mm.frame_table():
        ftype, owner = ft_decode(entry)
        symbols.append({FT_FREE: ".", FT_KERNEL: "K", FT_PAGETABLE: "T"}.get(ftype, f"{owner:X}"))
    for start in range(0, len(symbols), 64):
        print(f"  0x{start:02X}  {''.join(symbols[start:start + 64])}")

def _cmd_peek(args, kernel, io_manager):
    """Hex-dumps part of a process's virtual memory."""
    if len(args) < 2:
        print("Usage: peek <pid> <addr> [length]   (numbers may be hex, e.g. 0x100)")
        return
    try:
        pid, addr = int(args[0], 0), int(args[1], 0)
        length = int(args[2], 0) if len(args) > 2 else 64
    except ValueError:
        print("Error: pid, addr and length must be numbers.")
        return
    process = kernel.proc_manager.get(pid)
    if process is None:
        print(f"Error: no process with PID {pid}.")
        return
    mm = kernel.mem_manager
    for row in range(addr, addr + max(length, 0), 16):
        try:
            data = mm.load(process.slot, row, min(16, addr + length - row))
            paddr = mm.translate(process.slot, row)
        except Exception as e:
            print(f"  v0x{row:04X}  {e}")
            break
        hexes = " ".join(f"{b:02X}" for b in data)
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        print(f"  v0x{row:04X} -> p0x{paddr:05X}  {hexes:<47}  {text}")

def _cmd_exit(args, kernel, io_manager):
    """Exits the current session or application."""
    print("Shutting down aPEOS-I...")
    kernel.running = False

def _cmd_time(args, kernel, io_manager):
    """Displays the current system time."""
    print(f"Current time: {time_mgr.TIME_HH_MM()}")

def _cmd_date(args, kernel, io_manager):
    """Displays the current system date."""
    print(f"Current date: {time_mgr.TIME_DATE_DMY()}")

def _cmd_echo(args, kernel, io_manager):
    """Outputs the provided text to the console."""
    if args:
        print(" ".join(args))
    else:
        # To match standard 'echo' behavior, printing a blank line.
        print()

def _cmd_sleep(args, kernel, io_manager):
    """Pauses execution for a specified number of seconds."""
    if not args:
        print("Usage: sleep <seconds>")
        return
    try:
        duration_sec = float(args[0])
        print(f"Sleeping for {duration_sec} seconds...")
        time_mgr.DELAY(duration_sec * 1000)
        print("Awake.")
    except ValueError:
        print(f"Error: '{args[0]}' is not a valid number.")

def _cmd_logtime(args, kernel, io_manager):
    """Logs the current time to the system log."""
    # In a real system, this would write to a file.
    # For now, we'll print to the console.
    print(f"LOG: {time_mgr.TIME_FULL_DMY()}")

def _cmd_logdate(args, kernel, io_manager):
    """Logs the current date to the system log."""
    print(f"LOG: {time_mgr.TIME_DATE_DMY()}")

def _cmd_version(args, kernel, io_manager):
    """Displays the current system version."""
    print(f"aPEOS-I Version: {kernel.apeos_version}")

def _cmd_fetchbanana(args, kernel, io_manager):
    """Fetches system information alongside a banana ASCII art."""
    banana_art = """
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠉⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣻⡳⡐⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⢵⡳⡝⣸⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢕⢯⢺⡡⣳⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣟⣗⣽⣪⣣⢣⢑⡿⣟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢯⢯⡷⣟⡷⣗⢗⠵⡕⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢟⣝⢮⡫⡽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢯⡿⣽⣻⡻⠜⠀⠀⢑⠝⡮⣟⣾⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⡫⡮⡳⣕⢧⣫⡺⡪⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡽⣯⣟⣯⢟⡾⣐⠀⡀⣕⡕⡧⣻⣺⣿⢾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡻⣕⢗⣝⢮⣫⢺⡪⣖⢽⡹⡼⡺⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⣝⢽⣳⣯⢿⡽⣽⡢⣱⢱⢕⡇⣗⢽⣺⣟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡻⣕⣝⢞⡎⡧⡳⣕⢧⢳⢝⡎⣗⢝⡎⡯⣎⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡳⡵⣻⢽⡾⣯⢿⣺⣺⡸⡸⡕⡕⡎⣟⣞⣿⣻⣿⣿⣿⣿⣿⣿⢿⡫⣗⢝⣝⢼⢜⡵⡹⡭⣫⢺⡪⣏⢞⡺⣪⡳⣹⡪⡺⣍⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡯⡯⣺⢽⡽⡽⡽⣝⣞⢜⢞⡜⡎⡎⡪⡷⣽⣻⣿⣿⣿⣿⣟⢯⡳⣳⢹⣪⢳⢕⡽⡱⣝⢵⢝⢮⢳⡹⣜⢵⢝⢮⢎⡧⣫⢞⢎⢯⣪⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢯⡳⣕⣟⢾⢽⡫⣎⢎⢆⠣⡣⡳⢡⢳⢽⣺⣿⣽⡿⢯⡣⣗⡳⡝⣎⢗⡵⣝⢵⢝⠽⣜⢵⢫⡳⡣⡯⣎⢗⢽⢕⢗⣝⢎⡗⣝⢵⢵⢽⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣯⡺⡜⡮⡯⣳⣝⢮⢮⡢⡣⢅⢨⢰⡹⣝⡾⡯⠣⡑⡵⣹⢜⢮⡫⡮⡳⣕⢗⢵⡫⡫⡮⡳⡳⣹⣪⡳⣕⢯⢳⢝⢵⢕⡗⣝⡮⣫⣺⣼⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣳⡳⣝⢕⡯⣳⢯⣳⡳⣝⢵⡱⣸⣪⢺⢪⢃⠪⠨⢐⢕⡗⣝⣕⢗⣝⢞⣎⢯⢺⢜⣝⢮⢏⢾⢕⢮⡺⣪⢮⡳⣝⣕⢗⡝⣎⣾⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡷⣟⡮⢮⣣⢻⡪⣟⣞⢞⢮⡣⡯⡲⡱⡙⠄⡣⡑⢕⢅⢣⢯⢺⡸⡵⡕⣗⢵⢝⢮⢳⢕⢗⡝⡮⣫⡣⡯⡺⣪⡺⡜⣜⣵⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⣿⣪⡳⣕⢝⣞⢵⡳⣝⢵⢝⢎⣷⢱⡑⠄⠢⡱⣕⢕⠈⡮⡳⡵⣹⣚⢎⡧⣫⢮⢳⡹⣕⢝⢮⡺⡜⡮⣫⣚⣮⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣺⢧⡫⣎⢇⢗⡇⣏⢮⣚⣮⡫⡯⣗⡕⡅⠂⠕⣎⢎⠔⢘⢵⢝⡼⡜⡮⡺⡪⡮⣳⢹⢜⣝⣜⢮⢳⣹⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⢿⣽⡺⣸⢪⢕⠝⡜⢜⢺⣺⣽⣺⢽⢷⡕⡡⠈⢎⢎⢎⠠⠱⡳⡵⣹⢪⢏⡮⡳⡵⣹⡪⣖⣵⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⣽⣞⣧⡃⢇⠣⠈⡐⡈⢎⢗⣿⣯⣟⡯⣿⡰⡁⠅⢇⢇⠪⢈⢳⡹⣪⢳⢳⡹⡪⡞⣮⣾⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣻⣿⣿⣷⣻⠞⢮⡀⠀⡀⠐⡐⡈⢎⢗⣟⣮⡫⡯⣗⢥⢑⠨⠪⡪⠢⡐⢝⢼⢕⢗⣝⣮⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⣽⣿⣿⣿⠽⡨⡐⢄⠙⢄⠀⠀⠀⠄⠈⠺⡳⣳⣯⡺⡽⣕⢕⢌⠪⡨⢣⢂⠍⣗⣽⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⣿⣿⢿⢻⢸⢺⢨⠨⡢⢑⠄⠂⡀⠀⠀⠡⠠⠘⢎⣞⢽⡪⡗⡵⡱⡑⢬⠨⡢⡣⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣯⣿⣿⣿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣟⡝⣎⢞⡜⡮⡲⡑⢌⠢⡡⢂⠀⠀⠄⠀⠀⠂⡁⢎⢳⡹⡜⣵⢱⡱⡡⢣⢪⣸⡽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣯⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡷⡻⡹⡜⡺⣸⢱⢕⢇⢗⢕⢥⢑⢜⢀⢂⠀⠀⠀⠀⠀⠀⢂⠱⡘⡝⣞⢷⢕⢕⢕⢕⢮⡺⡽⣞⡿⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⣷⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢟⢧⢳⢱⢕⢝⡜⣎⢧⢳⢹⢜⢕⢇⢇⠆⢕⠠⡁⠂⠁⠀⠀⠀⠀⠀⠂⢑⠸⢘⢅⢗⡽⡸⣸⢜⢮⣫⡫⣍⠓⡫⢿⣻⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣽⣿⣿⣿⣿
⣿⡿⣿⣾⣿⣿⡿⣿⣿⣿⢿⣻⣿⣿⣿⣿⣿⣻⣿⣿⢿⢻⢪⡺⡜⡎⣇⢏⢮⢺⢸⢜⢜⢎⢮⢣⡫⡪⡝⡔⡐⠨⡈⠄⠀⠂⠁⠀⠀⡀⠠⡨⡢⡣⡡⠑⡹⡵⣯⣻⣺⣪⢇⡯⣢⣇⣮⡹⡽⡽⣯⡿⣿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣿⣿⣿⣿⣿⣿
⣻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⢹⢱⢝⢎⢮⢺⡸⡪⣪⢣⢳⡱⡣⡫⣣⢳⢕⢵⢹⡸⡪⡪⡂⡂⠅⠌⠀⠀⢂⢀⠢⠡⡑⢅⢣⠣⡣⡳⡹⣸⢺⡺⡼⡽⣝⢞⣞⡾⡽⣝⣧⣣⢯⣫⢏⠷⣟⣟⡿⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⡿⣿⣿⡿⣿⣿⣿⣿⣿⣿⡿⡻⡸⡸⡸⡸⡜⡎⡇⡧⣣⢫⢪⡪⡣⡣⣫⢪⢎⢮⢪⡣⡇⡧⡳⡹⡸⣐⢈⠨⡰⡢⡀⠐⠨⡈⠌⡢⠡⡑⡑⠕⢍⢎⢎⠮⡳⡝⡮⡳⣳⣝⣞⢗⣕⢗⢟⢾⢽⣝⢮⡲⣱⢩⢩⠙⣿⣿⣿⣿⣿⣿⡿⣿⣟⣿⣿⣿⣿⣿⣿⣿⣻⣷⣿
⣿⣿⣿⣿⣽⣿⣿⣿⣿⣿⣿⣿⢿⣟⢇⢇⢕⢪⢪⡪⣣⢳⢱⡹⡜⡎⣎⢇⢇⢧⢫⢪⠮⡺⡸⡜⣜⢜⢎⢞⢜⢎⡮⣖⣯⡺⣜⢲⡰⣀⠀⠡⠠⡑⠨⠢⡑⢅⠢⢁⠣⠱⡩⢪⠫⡳⡕⡧⡳⡱⣱⢱⢱⠱⡱⢳⢹⢜⢜⢔⠅⢽⡿⣿⣽⣷⣿⣿⣿⣿⣿⣿⣿⣿⣻⣽⣿⣿⣿⣿
⣿⢿⣯⣿⣿⣿⣿⣿⣿⣿⢿⣿⣿⣿⣮⢪⡪⣎⢎⢎⢮⢪⡣⡳⡱⡕⣕⢕⡳⡱⡕⣕⢝⢜⢎⡎⣎⢎⢧⢫⣮⣿⣿⡿⣯⢿⣺⣵⣕⢵⢹⡢⣄⢀⠑⠐⠌⡐⠌⡂⡂⢅⢐⠐⢄⢑⢑⢕⠱⡑⢕⠡⡑⡨⢐⢱⠱⡱⡑⡡⡴⣯⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⣻⣿⣿⣿⣿⣿⣿
⣾⣿⣿⣿⣿⣿⣟⣯⣷⣿⣿⣿⣿⣿⣿⣯⣟⣗⢯⢺⢸⢱⡱⢕⢵⢹⡸⡪⡪⡇⣏⢎⢮⢺⢸⢜⢜⣎⣾⣿⣿⣻⣽⣿⣿⣻⣽⢾⣾⣻⢮⣮⡪⡎⡦⣂⡀⡈⠐⠐⠄⠔⡀⢅⠑⠌⡂⡢⠑⠌⠄⠅⠔⠨⢈⠢⠑⢈⡢⡮⣞⣟⣾⣿⣿⣿⣿⢿⣿⣽⣿⣾⣿⣿⣿⣿⣿⣿⢿⣿
⣿⣿⣿⣿⣿⣻⣿⣿⣿⣿⣿⣿⣿⣷⣿⣿⣿⣶⢕⢯⢪⢣⢎⢗⡕⣇⢇⢏⢎⢎⢎⢎⢇⡇⡧⣳⣿⣻⣿⣯⣿⣿⣿⣿⣻⣯⣿⣽⢾⣽⣻⢾⣽⢾⡮⣮⣪⡲⡢⡄⡄⠀⠄⠀⠁⠁⠀⠂⠈⠂⠂⠂⠁⢁⠠⣐⢴⢕⣯⣻⣞⣯⣷⡿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣯⣿⣯⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣽⣿⣿⣟⣿⣿⣵⠵⣣⡳⡱⣕⢵⢱⢣⢣⢳⢱⡹⣜⣼⣿⣿⣿⢿⣟⣿⣯⣿⣾⣿⡿⣿⣿⣾⣟⣷⣻⣻⢾⡯⣿⡽⣞⣯⣷⣻⣼⣝⣦⣣⢬⣄⢅⣈⣄⣂⣐⢤⣕⣖⣽⣪⣷⣻⣽⣯⣿⣽⢷⣿⣻⣿⣿⣿⣿⣿⡿⣿⣿⡿⣿⣿⣯⣿⣿⣯
⣿⣿⣿⣿⣿⣯⣿⣯⣿⣿⣽⣾⣿⣿⣿⣿⣿⣿⣿⣿⣷⣗⢝⢽⡸⣪⡳⣝⡮⡳⣵⣟⣿⣿⢿⣯⣿⣿⣿⡿⣟⣿⣟⣷⣿⣿⣿⣾⡿⣷⣻⣽⢯⣟⡷⣟⣯⡷⣟⣾⣳⣟⣾⣽⣻⢾⣻⣽⢾⣽⢾⣻⡾⣞⡷⣟⣾⣯⡿⣾⢷⣟⣿⣳⣿⣻⣯⣿⣿⣾⣿⣿⣿⣿⣿⣿⡿⣿⣻⣿
⣿⣻⣿⣽⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣷⣿⣿⣯⣿⣿⣿⣮⢮⣻⢮⡯⣗⣯⣿⣿⣿⣟⣿⣿⡿⣟⣯⣷⣿⣿⣿⣿⡿⣿⣟⣷⣿⣿⣿⣯⣿⡽⡷⣟⣯⡷⣟⣯⡷⣟⣾⣳⣟⣾⣻⣽⢾⣻⡽⣯⡷⣟⣯⡿⣯⣷⢿⣽⣟⣿⣽⣯⣿⣽⣿⣿⣿⣿⣿⣿⣿⡿⣿⣽⣷⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⡿⣿⣾⣿⣯⣿⣿⣽⣿⣿⣿⣿⣿⣿⣿⣽⣿⣯⣟⡽⣽⣽⣿⣿⣿⡿⣿⡿⣷⣿⣿⣿⣿⣿⢿⣯⣷⣿⣿⣿⡿⣿⣽⣾⣿⣷⣿⣟⣯⣷⢿⡯⣷⣟⣯⡷⣟⣾⣳⢿⣞⣿⢽⡯⣷⣟⣯⣷⢿⣻⣾⢿⡷⣟⣷⢿⣾⣻⣾⣿⣿⣻⣿⣽⣷⣿⣿⣿⣿⣿⣿⣿⣿⣟
⣿⣿⣾⣿⣯⣷⣿⣿⣿⣿⣻⣿⣿⢿⣿⣟⣯⣷⣿⣷⣿⣿⣿⡿⣟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⣯⣿⣾⣿⣿⡿⣿⣻⣷⣿⣿⣿⣟⣿⣾⣿⣯⣿⢾⣻⣟⣷⣻⣞⣯⢿⣺⣽⣻⢾⡽⣯⣟⣷⣻⣾⣻⣟⣯⡿⣯⣿⣻⣟⣿⣽⣿⣟⣿⣿⣿⣿⣿⣿⣿⡿⣿⣻⣯⣿⣿⣾⣿
"""
    print(banana_art)
    # Re-use the sysinfo logic
    _cmd_sysinfo(args, kernel, io_manager)

def _cmd_cmd_info(args, kernel, io_manager):
    """Provides detailed information about a specific command."""
    if not args:
        print("Usage: cmd_info <command_name>")
        return
    cmd_to_find = args[0].lower()
    cmd_to_find = io_manager.aliases.get(cmd_to_find, cmd_to_find)
    if cmd_to_find in io_manager.commands:
        info = io_manager.commands[cmd_to_find]
        print(f"Info for command '{cmd_to_find}':")
        print(f"  Description: {info.get('desc', 'N/A')}")
        print(f"  Category:    {info.get('category', 'N/A')}")
        print(f"  Alias:       {info.get('alias', 'N/A')}")
        print(f"  Auth Level:  {info.get('level', 'N/A')}")
    else:
        print(f"Command '{cmd_to_find}' not found.")

def _cmd_sysinfo(args, kernel, io_manager):
    """Displays system information including OS name and version."""
    print("--- System Information ---")
    print(f"aPEOS-I Version: {kernel.apeos_version}")
    print(f"Base OS:         {kernel.os_name}")
    print(f"Base OS Version: {kernel.os_version}")
    board = kernel.board
    print(f"Motherboard:     {board.name}")
    print(f"CPU:             {board.cpu.name} ({board.cpu.clock_hz} Hz)")
    print(f"RAM:             {board.ram.name} ({board.ram.size:,} bytes, {board.ram.page_size}-byte pages)")
    print(f"RAM file:        {board.ram_file}")
    print("--------------------------")

def _cmd_dir(args, kernel, io_manager):
    """Lists the contents of a directory."""
    from datetime import datetime
    path_to_list = args[0] if args else '.'
    contents = kernel.fs_manager.list_directory(path_to_list)
    
    if isinstance(contents, list):
        dir_path = kernel.fs_manager.get_full_current_path()
        print(f" Directory of {dir_path}\n")
        if not contents:
            print("File Not Found")
        else:
            files = 0
            dirs = 0
            total_size = 0
            for item in sorted(contents, key=lambda x: x['name']):
                mod_time = datetime.fromtimestamp(item['modified']).strftime('%m/%d/%Y %I:%M %p')
                size_str = f"{item['size']:,}" if item['type'] != '<DIR>' else ''
                print(f"{mod_time:<18} {item['type']:<8} {size_str:>14} {item['name']}")
                if item['type'] == '<DIR>':
                    dirs += 1
                else:
                    files += 1
                    total_size += item['size']
            print(f"\n{files:16} File(s) {total_size:14,} bytes")
            print(f"{dirs:16} Dir(s)")
    else:
        # An error message was returned
        print(contents)

def _cmd_cd(args, kernel, io_manager):
    """Changes the current working directory."""
    if not args:
        # Print current directory if no path is given
        print(kernel.fs_manager.get_full_current_path())
        return
    target_path = args[0]
    result = kernel.fs_manager.change_directory(target_path)
    if result: # An error message was returned
        print(result)

def _cmd_md(args, kernel, io_manager):
    """Creates a directory."""
    if not args:
        print("Usage: md <directory_name>")
        return
    result = kernel.fs_manager.create_directory(args[0])
    if result:
        print(result)

def _cmd_rd(args, kernel, io_manager):
    """Removes an empty directory."""
    if not args:
        print("Usage: rd <directory_name>")
        return
    result = kernel.fs_manager.remove_directory(args[0])
    if result:
        print(result)

def _cmd_type(args, kernel, io_manager):
    """Displays the contents of a text file."""
    if not args:
        print("Usage: type <filename>")
        return
    
    content = kernel.fs_manager.read_file(args[0])
    
    # read_file returns the content on success and an error string on failure.
    # We can check if the return value starts with "Error:" to distinguish.
    if isinstance(content, str) and content.startswith("Error:"):
        print(content)
    else:
        # To avoid printing a trailing newline if the file doesn't have one,
        # we use end=''.
        print(content, end='')

def _cmd_delete(args, kernel, io_manager):
    """Moves a file or directory to the trashbin."""
    if not args:
        print("Usage: delete <file_or_directory>")
        return
    path = args[0]
    result = kernel.fs_manager.move_to_trash(path)
    if result:
        print(result)

def _cmd_force_dlt(args, kernel, io_manager):
    """Permanently deletes a file or directory."""
    if not args:
        print("Usage: force_dlt <file_or_directory>")
        return
    path = args[0]
    result = kernel.fs_manager.force_delete(path)
    if result:
        print(result)

def _launch_app(app_info, args, kernel, io_manager, is_background):
    """Dynamically imports and runs an application."""
    module_name = app_info.get('app_module')
    class_name = app_info.get('app_class')

    if not module_name or not class_name:
        print(f"Error: Application '{app_info.get('command')}' is not configured correctly.")
        print("Required fields 'app_module' and 'app_class' are missing in sys_cmd.csv.")
        return

    try:
        # Dynamically import the module
        # The 'package' argument makes the import relative to the 'apeos.system2' package.
        # This allows Python to correctly find 'sysApp' from the 'sys' directory.
        app_module = importlib.import_module(f"..{module_name}", package=__package__)
        # Get the application class from the module
        app_class = getattr(app_module, class_name)
        # Instantiate and run the application, passing arguments
        # The application's __init__ must accept the arguments.
        app_instance = app_class(kernel, *args) # __init__
        
        # Create a process instead of running it directly
        is_foreground = not is_background
        kernel.proc_manager.create_process(app_instance, app_info['command'], is_foreground)
    except ImportError as e:
        print(f"Error: Could not find application module: {module_name}")
        print(f"Import Error: {e}")
    except (AttributeError, Exception) as e:
        print(f"Error launching application '{class_name}': {e}")

# --- Command Dispatch Table ---
# Maps command strings to their handler functions.

_COMMAND_HANDLERS = {
    "help": _cmd_help,
    "list_tasks": _cmd_list_tasks,
    "exit": _cmd_exit,
    "time": _cmd_time,
    "date": _cmd_date,
    "echo": _cmd_echo,
    "sleep": _cmd_sleep,
    "logtime": _cmd_logtime,
    "logdate": _cmd_logdate,
    "version": _cmd_version,
    "fetchbanana": _cmd_fetchbanana,
    "cmd_info": _cmd_cmd_info,
    "sysinfo": _cmd_sysinfo,
    "dir": _cmd_dir,
    "cd": _cmd_cd,
    "md": _cmd_md,
    "rd": _cmd_rd,
    "type": _cmd_type,
    "delete": _cmd_delete,
    "force_dlt": _cmd_force_dlt,
    "kill": _cmd_kill,
    "fg": _cmd_fg,
    "mem": _cmd_mem,
    "peek": _cmd_peek,
}

def execute_command(command, args, kernel, io_manager, is_background=False):
    """
    Executes a system command.

    :param command: The command to execute.
    :param args: A list of arguments for the command.
    :param kernel: The kernel instance, for accessing system components.
    :param io_manager: The IOManager, for accessing command data.
    :param is_background: True if the command should run in the background.
    """
    handler = _COMMAND_HANDLERS.get(command)
    if handler:
        # It's a built-in system command
        handler(args, kernel, io_manager)
        return

    # If not a built-in, check if it's an application
    cmd_info = io_manager.commands.get(command)
    if cmd_info and cmd_info.get('category') == 'app':
        if is_background and cmd_info.get('allow_bg', 'false').lower() != 'true':
            print(f"Error: Application '{command}' cannot be run in the background.")
            return
        _launch_app(cmd_info, args, kernel, io_manager, is_background)
    else:
        # If it's neither a built-in nor a known application, then it's an error.
        print(f"Error: Command '{command}' not recognized. Type 'help' for a list of commands.")
