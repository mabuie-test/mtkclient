"""Fastboot command helpers."""
from __future__ import annotations
import subprocess


def fastboot_available() -> bool:
    try:
        return subprocess.run(["fastboot", "--version"], capture_output=True, text=True, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def fastboot_devices() -> list[str]:
    """Return connected Fastboot device serials."""
    try:
        result = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
