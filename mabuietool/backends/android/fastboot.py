"""Fastboot command helpers."""
from __future__ import annotations
import subprocess


def fastboot_available() -> bool:
    try:
        return subprocess.run(["fastboot", "--version"], capture_output=True, text=True, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
