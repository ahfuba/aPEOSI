from devices.internal.A.apeos.system2.sys.process_mgr import ReadLine


class BananaEditor:
    """
    A simple, line-based text editor for aPEOS-I.
    Inspired by classic terminal editors like ed and nano.

    The text buffer is NOT a Python list: it lives in this process's memory
    in aPE-RAM, so you can watch your typing land in RAM with the Watchdog
    (or with 'peek <pid> 0').

    Virtual memory layout of this process:
        0x0000..0x0003  number of lines (u32)
        0x0004..0x0007  number of text bytes (u32)
        0x0008..        the text, UTF-8, one '\\n' after every line
    """

    LINES_ADDR = 0x0
    LENGTH_ADDR = 0x4
    TEXT_ADDR = 0x8

    def __init__(self, kernel, filename=None):
        """
        :param kernel: The kernel instance, providing access to system managers.
        :param filename: The name of the file to edit.
        """
        self.kernel = kernel
        self.filename = filename

    # --- the buffer, stored in aPE-RAM --------------------------------------
    def _line_count(self):
        return self.mem.load_u32(self.LINES_ADDR)

    def _append(self, text):
        """Appends one or more lines (text must end with '\\n') to the buffer."""
        data = text.encode("utf-8")
        length = self.mem.load_u32(self.LENGTH_ADDR)
        self.mem.store(self.TEXT_ADDR + length, data)
        self.mem.store_u32(self.LENGTH_ADDR, length + len(data))
        self.mem.store_u32(self.LINES_ADDR, self._line_count() + text.count("\n"))

    def _text(self):
        length = self.mem.load_u32(self.LENGTH_ADDR)
        return self.mem.load(self.TEXT_ADDR, length).decode("utf-8", "replace") if length else ""

    # --- files ----------------------------------------------------------------
    def _load_file(self):
        """Loads file content into the RAM buffer if the file exists."""
        content = self.kernel.fs_manager.read_file(self.filename)

        if isinstance(content, str) and content.startswith("Error: File"):
            print(f"New file: '{self.filename}'")
        elif isinstance(content, str) and content.startswith("Error:"):
            # Another error occurred (e.g., it's a directory)
            print(content)
            self.filename = None  # Prevent saving
        else:
            lines = content.splitlines()
            if lines:
                self._append("\n".join(lines) + "\n")
            print(f"Loaded {len(lines)} lines from '{self.filename}' into RAM.")

    def _save_file(self):
        """Saves the RAM buffer to the file."""
        if not self.filename:
            print("Error: No filename specified. Cannot save.")
            return
        result = self.kernel.fs_manager.write_file(self.filename, self._text())
        if result:  # An error occurred
            print(result)
        else:
            print(f"File '{self.filename}' saved successfully.")

    # --- main loop --------------------------------------------------------------
    def run(self):
        """A generator that runs the editor's logic step-by-step."""
        if not self.filename:
            print("Usage: banana <filename>")
            return

        self.mem.store_u32(self.LINES_ADDR, 0)  # touch page 0 so the buffer exists
        self._load_file()

        print("\n--- Banana Editor ---")
        print("Type lines of text.  :p print buffer  :w save  :wq save and quit  :q quit")
        print(f"Your text lives in RAM: try 'peek {self.pid} 0' or the aPE-RAM Watchdog.")
        print("---------------------\n")

        while True:
            # System call: block until the user types a line.
            line = yield ReadLine(f"{self._line_count() + 1:>4}| ")

            if line == ':wq':
                self._save_file()
                break
            elif line == ':w':
                self._save_file()
            elif line == ':q':
                break
            elif line == ':p':
                for number, text in enumerate(self._text().splitlines(), 1):
                    print(f"{number:>4}| {text}")
            else:
                self._append(line + "\n")

        print("Exiting Banana Editor.")
