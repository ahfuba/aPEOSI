import os
import sys
import runpy

def boot_os():
    # Diskteki OS dizinini belirle
    os_root = os.path.join("devices", "internal_d", "A", "APEOSI", "os")
    boot_file = os.path.join(os_root, "boot.py")

    if not os.path.exists(boot_file):
        print("BOOT ERROR: OS core not found!")
        return

    # OS dizinini import path’e ekle
    sys.path.insert(0, os_root)

    print("Booting aPEOSI kernel environment...")
    runpy.run_path(boot_file, run_name="__main__")

if __name__ == "__main__":
    boot_os()
