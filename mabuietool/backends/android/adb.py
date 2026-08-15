"""ADB command helpers."""
from __future__ import annotations
import subprocess


def adb_available() -> bool:
    try:
        return subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
