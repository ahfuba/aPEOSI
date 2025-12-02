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
    """Lists all currently scheduled tasks."""
    print(f"Scheduled tasks: {kernel.scheduler.get_scheduled_tasks()}")

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
