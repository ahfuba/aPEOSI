from devices.internal.A.apeos.system2.sys.process_mgr import ProcessState
 
class BananaEditor:
    """
    A simple, line-based text editor for aPEOS-I.
    Inspired by classic terminal editors like ed and nano.
    """
    def __init__(self, kernel, filename=None):
        """
        Initializes the editor. The command-line arguments from the shell
        are passed here by the application launcher.

        :param kernel: The kernel instance, providing access to system managers.
        :param filename: The name of the file to edit.
        """
        self.kernel = kernel
        self.filename = filename
        self.buffer = []  # This will hold the lines of the file as strings.
        self.user_input = None # To receive input from the kernel
        self.is_running = False

    def _load_file(self):
        """Loads file content into the buffer if the file exists."""
        if not self.filename:
            return

        content = self.kernel.fs_manager.read_file(self.filename)

        if isinstance(content, str) and content.startswith("Error: File"):
            # File does not exist, which is fine for a new file.
            print(f"New file: '{self.filename}'")
        elif isinstance(content, str) and content.startswith("Error:"):
            # Another error occurred (e.g., it's a directory)
            print(content)
            self.filename = None # Prevent saving
        else:
            # File loaded successfully
            self.buffer = content.splitlines()
            print(f"Loaded {len(self.buffer)} lines from '{self.filename}'.")

    def _save_file(self):
        """Saves the buffer content to the specified file."""
        if not self.filename:
            print("Error: No filename specified. Cannot save.")
            return
        
        content_to_save = '\n'.join(self.buffer)
        result = self.kernel.fs_manager.write_file(self.filename, content_to_save)
        if result: # An error occurred
            print(result)
        else:
            print(f"File '{self.filename}' saved successfully.")

    def _request_input(self):
        """A system call to the kernel to wait for input."""
        # Find our own process object
        proc = self.kernel.proc_manager.get_foreground_process()
        if proc:
            proc.state = ProcessState.WAITING_FOR_INPUT
        self.user_input = None # Clear previous input
        while self.user_input is None:
            yield # Yield control to the kernel until input is received

    def send_input(self, text):
        """Called by the kernel to deliver user input."""
        self.user_input = text

    def run(self):
        """A generator that runs the editor's logic step-by-step."""
        if not self.filename:
            print("Usage: banana <filename>")
            return # End the generator

        self._load_file()
        self.is_running = True

        print("\n--- Banana Editor ---")
        print("Enter text line by line. Type ':wq' to save and quit, or ':q' to quit without saving.")
        print("---------------------\n")

        while self.is_running:
            # This is a "syscall" to the kernel to get input
            yield from self._request_input()
            line = self.user_input

            if line == ':wq':
                self._save_file()
                self.is_running = False
            elif line == ':q':
                self.is_running = False
            else:
                self.buffer.append(line)

        print("Exiting Banana Editor.")
