"""ADB command helpers."""
from __future__ import annotations
import subprocess


def adb_available() -> bool:
    try:
        return subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def adb_devices() -> list[dict[str, str]]:
    """Return connected ADB devices with their transport state."""
    try:
        result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    devices: list[dict[str, str]] = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        details = {"serial": serial, "state": state}
        for item in parts[2:]:
            if ":" in item:
                key, value = item.split(":", 1)
                details[key] = value
        devices.append(details)
    return devices
