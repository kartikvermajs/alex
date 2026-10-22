"""Build script for packaging Alex into standalone Alex.exe."""

import subprocess
import sys
from pathlib import Path


def build():
    print("Building Alex executable with PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "alex.spec",
    ]
    result = subprocess.run(cmd)
    if result.returncode == 0:
        exe_path = Path("dist/Alex/Alex.exe").resolve()
        print(f"\n[SUCCESS] Alex packaged successfully!")
        print(f"Standalone executable located at: {exe_path}\n")
        return 0
    else:
        print("\n[ERROR] PyInstaller build failed.")
        return result.returncode


if __name__ == "__main__":
    sys.exit(build())
