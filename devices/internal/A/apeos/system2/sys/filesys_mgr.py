import os
import json
import shutil
from datetime import datetime

class FileSystemManager:
    """
    Manages the virtual file system of aPEOS-I.

    It treats subdirectories inside a 'disks' folder at the project root
    as mountable drives for the emulated OS.
    """

    def __init__(self, kernel, project_root):
        """
        Initializes the FileSystemManager.

        :param kernel: The main kernel instance.
        :param project_root: The absolute path to the aPEOSI project root.
        """
        self.kernel = kernel
        self.project_root = project_root
        # Use 'devices' folder at project root as the source for drives
        self.disks_path = os.path.join(self.project_root, 'devices')
        self.mounted_drives = {}  # e.g., {'A:': {'path': '...', 'type': '...'}}
        self.current_drive = None
        self.current_path = '/'  # Path relative to the current drive
        self.trashbin_path = None # Will be initialized after mounting

        self._mount_drives()

        if 'A:' in self.mounted_drives:
            self.current_drive = 'A:'
        elif self.mounted_drives:
            # Fallback to the first available drive if A: is not found
            self.current_drive = sorted(self.mounted_drives.keys())[0]
        else:
            print("FSManager Warning: No drives found in 'devices' directory.")
        
        # Initialize trashbin on drive A: if it exists
        if 'A:' in self.mounted_drives:
            self.trashbin_path = self._get_host_path('A:/user/trashbin')

    def _mount_drives(self):
        """
        Scans the 'disks' directory and mounts found drives.
        A drive is a subdirectory in the 'disks' folder.
        """
        if not os.path.isdir(self.disks_path):
            print(f"FSManager Info: 'devices' directory not found at {self.disks_path}. Creating it.")
            try:
                os.makedirs(self.disks_path)
            except OSError as e:
                print(f"FSManager FATAL: Could not create 'devices' directory: {e}")
                return

        # Scan subdirectories within 'devices' (like 'internal', 'external')
        for device_type_folder in os.listdir(self.disks_path):
            device_type_path = os.path.join(self.disks_path, device_type_folder)
            if os.path.isdir(device_type_path):
                # Now scan for actual drives (like 'A', 'B') inside the type folder
                for drive_name in os.listdir(device_type_path):
                    drive_path = os.path.join(device_type_path, drive_name)
                    if os.path.isdir(drive_path):
                        drive_letter = f"{drive_name.upper()}:"
                        drive_info = self._read_drive_config(drive_path)
                        self.mounted_drives[drive_letter] = {
                            'path': drive_path,
                            'type': drive_info.get('type', 'generic'),
                            'label': drive_info.get('label', 'No Label')
                        }
                        print(f"FSManager: Mounted drive {drive_letter} ({drive_info.get('type', 'generic')})")

    def _read_drive_config(self, drive_path):
        """
        Reads a 'disk.json' config file from a drive's root directory.
        Returns a dictionary with config data, or an empty one if not found.
        """
        config_path = os.path.join(drive_path, 'disk.json')
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"FSManager Warning: Could not read or parse {config_path}: {e}")
        return {}

    def get_full_current_path(self):
        """Returns the full virtual path, e.g., 'A:\system'."""
        if not self.current_drive:
            return "[no drive]"
        return self.current_drive + self.current_path

    def _get_host_path(self, virtual_path):
        """
        Converts a virtual path (e.g., 'A:\system') to a real host OS path.
        Returns None if the path is invalid.
        """
        # An absolute path starts with a drive letter, e.g., "A:/..." or "A:"
        # A relative path does not.
        if not (len(virtual_path) > 1 and virtual_path[1] == ':' and virtual_path[0].isalpha()):
            # It's a relative path, combine with current context.
            # Replace backslashes with forward slashes for consistency.
            if not self.current_drive:
                return None
            # Construct an absolute virtual path from the relative one
            current_full_path = self.get_full_current_path()
            # Use string joining with forward slashes to avoid os-specific separators
            if current_full_path.endswith('/'):
                full_virtual_path = current_full_path + virtual_path
            else:
                full_virtual_path = current_full_path + '/' + virtual_path
        else:
            # It's an absolute path
            full_virtual_path = virtual_path

        # Normalize path to use forward slashes and split drive from path
        if ':' in full_virtual_path:
            drive, path_part = full_virtual_path.split(':', 1)
        else:
            drive = self.current_drive.strip(':')
            path_part = full_virtual_path

        drive_letter = f"{drive.upper()}:"

        if drive_letter not in self.mounted_drives:
            return None # Invalid drive

        drive_root_path = self.mounted_drives[drive_letter]['path']

        # Normalize the path and prevent directory traversal attacks (e.g., '..')
        # The path part starts with '\', so we strip it for os.path.join
        relative_path = path_part.strip('/')
        host_path = os.path.join(drive_root_path, relative_path)
        
        # Security check: ensure the resolved path is still within the drive's directory
        if os.path.commonpath([drive_root_path, os.path.abspath(host_path)]) != drive_root_path:
            print("FSManager Security Warning: Path traversal attempt detected and blocked.")
            return None

        return os.path.abspath(host_path)

    def list_directory(self, path='.'):
        """
        Lists contents of a directory, providing details for each item.
        Returns a list of dictionaries, each with 'name', 'type', 'size', 'modified'.
        """
        host_path = self._get_host_path(path)
        if not host_path or not os.path.isdir(host_path):
            if host_path and not os.path.isdir(host_path):
                return f"Error: '{path}' is not a directory."
            return f"Error: Directory '{path}' not found."

        detailed_contents = []
        for item_name in os.listdir(host_path):
            item_path = os.path.join(host_path, item_name)
            try:
                stat = os.stat(item_path)
                item_type = '<DIR>' if os.path.isdir(item_path) else ''
                detailed_contents.append({
                    'name': item_name,
                    'type': item_type,
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except OSError:
                # Could be a broken symlink or permission error, skip it
                continue
        return detailed_contents

    def read_file(self, path):
        """Reads the content of a file in the virtual file system."""
        host_path = self._get_host_path(path)
        if not host_path or not os.path.exists(host_path):
            return f"Error: File '{path}' not found."
        if os.path.isdir(host_path):
            return f"Error: '{path}' is a directory, not a file."
        try:
            with open(host_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except IOError as e:
            return f"Error reading file '{path}': {e}"

    def write_file(self, path, content):
        """Writes content to a file in the virtual file system, overwriting it."""
        host_path = self._get_host_path(path)
        if not host_path:
            return f"Error: Invalid path '{path}'."
        if os.path.isdir(host_path):
            return f"Error: Cannot write to '{path}', it is a directory."
        
        try:
            with open(host_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return None # Success
        except IOError as e:
            return f"Error writing to file '{path}': {e}"

    def create_directory(self, path):
        """Creates a new directory."""
        host_path = self._get_host_path(path)
        if not host_path:
            return f"Error: Invalid path '{path}'."
        if os.path.exists(host_path):
            return f"Error: Directory or file '{path}' already exists."
        try:
            os.makedirs(host_path)
            return None # Success
        except OSError as e:
            return f"Error creating directory '{path}': {e}"

    def remove_directory(self, path):
        """Removes an empty directory."""
        host_path = self._get_host_path(path)
        if not host_path or not os.path.isdir(host_path):
            return f"Error: '{path}' is not a directory."
        try:
            os.rmdir(host_path)
            return None # Success
        except OSError:
            # This can fail if the directory is not empty
            return f"Error: Directory '{path}' is not empty or could not be removed."

    def move_to_trash(self, path):
        """Moves a file or directory to the trashbin."""
        if not self.trashbin_path:
            return "Error: Trashbin is not configured."

        host_path = self._get_host_path(path)
        if not host_path or not os.path.exists(host_path):
            return f"Error: File or directory '{path}' not found."

        # Create trashbin if it doesn't exist
        if not os.path.exists(self.trashbin_path):
            try:
                os.makedirs(self.trashbin_path)
            except OSError as e:
                return f"Error: Could not create trashbin directory: {e}"

        # Create a unique name for the trashed item to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        base_name = os.path.basename(host_path)
        trash_name = f"{base_name}.{timestamp}"
        destination_path = os.path.join(self.trashbin_path, trash_name)

        try:
            shutil.move(host_path, destination_path)
            return None # Success
        except OSError as e:
            return f"Error moving '{path}' to trash: {e}"

    def force_delete(self, path):
        """Permanently deletes a file or directory."""
        host_path = self._get_host_path(path)
        if not host_path or not os.path.exists(host_path):
            return f"Error: File or directory '{path}' not found."

        try:
            if os.path.isfile(host_path) or os.path.islink(host_path):
                os.remove(host_path)
            elif os.path.isdir(host_path):
                shutil.rmtree(host_path)
            else:
                return f"Error: '{path}' is not a file or directory."
            return None # Success
        except OSError as e:
            return f"Error deleting '{path}': {e}"


    def change_directory(self, path):
        """
        Changes the current working directory or drive.
        Returns an error message string on failure, None on success.
        """
        if not self.current_drive:
            return "Error: No drive is currently selected."

        # Handle drive change, e.g., 'cd A:'
        if len(path) == 2 and path.endswith(':'):
            drive_letter = path.upper()
            if drive_letter in self.mounted_drives:
                self.current_drive = drive_letter
                # Optional: could also change current_path to root of new drive
                # self.current_path = '\\'
                return None
            else:
                return f"Error: Drive '{drive_letter}' not found."

        # Get the real host path for the target virtual path
        new_host_path = self._get_host_path(path)

        if new_host_path is None:
            return f"Error: Path '{path}' is invalid or not found."
        
        if not os.path.isdir(new_host_path):
            return f"Error: '{path}' is not a directory."

        # If we got a valid directory, update the current path
        # We need to convert the host path back to a virtual path
        drive_root_path = self.mounted_drives[self.current_drive]['path']
        relative_path = os.path.relpath(new_host_path, drive_root_path)

        # Format for aPEOS: use backslashes and start with one
        self.current_path = '/' + relative_path.replace('\\', '/')
        if self.current_path == '/.': # relpath can return '.' for the root
            self.current_path = '/'
        return None