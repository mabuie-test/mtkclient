"""Authorized FRP diagnostics backed by ADB/Fastboot device state.

This module intentionally reports FRP/security information only. It does not
perform bypass, erase, unlock, or destructive operations.
"""
from __future__ import annotations

import subprocess

from mabuietool.device.models import DeviceInfo


def _run_command(command: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return "Unavailable"
    if result.returncode != 0:
        return (result.stderr or result.stdout or "Unavailable").strip()
    return result.stdout.strip() or "Unavailable"


class FRPManager:
    """Read-only FRP/security diagnostics for authorized service workflows."""

    ADB_PROPERTIES = {
        "FRP Partition": "ro.frp.pst",
        "Verified Boot": "ro.boot.verifiedbootstate",
        "Device State": "ro.boot.vbmeta.device_state",
        "OEM Unlock Allowed": "sys.oem_unlock_allowed",
        "Brand": "ro.product.brand",
        "Model": "ro.product.model",
        "Android Version": "ro.build.version.release",
        "Security Patch": "ro.build.version.security_patch",
    }

    FASTBOOT_VARS = {
        "Unlocked": "unlocked",
        "Secure": "secure",
        "Product": "product",
        "Current Slot": "current-slot",
        "Variant": "variant",
    }

    def run_action(self, action: str, device: DeviceInfo) -> dict[str, str]:
        """Run the requested FRP workflow through the safest available backend path."""
        normalized = action.strip().lower()
        if normalized in {"frp status", "device security", "diagnostic report"}:
            return self.diagnostic_report(device)
        if normalized == "recovery assistant":
            return self.recovery_assistant(device)
        report = self.diagnostic_report(device)
        report["Requested Action"] = action
        report["Action Result"] = "Unsupported FRP action"
        return report

    def diagnostic_report(self, device: DeviceInfo) -> dict[str, str]:
        report: dict[str, str] = {
            "Connection": device.connection_state,
            "Protocol": device.protocol,
            "Serial": device.serial,
            "Bootloader State": device.bootloader,
            "Security Information": device.security,
            "Device Information": f"{device.manufacturer} {device.model}".strip(),
        }
        if device.protocol == "ADB":
            report.update(self._adb_report(device.serial))
        elif device.protocol == "Fastboot":
            report.update(self._fastboot_report(device.serial))
        else:
            report["FRP Status"] = "Connect an authorized ADB or Fastboot device to read FRP diagnostics"
        report["Note"] = "Diagnostics only. Unauthorized FRP bypass/removal is not provided."
        return report

    def recovery_assistant(self, device: DeviceInfo) -> dict[str, str]:
        report = self.diagnostic_report(device)
        report["Requested Action"] = "Recovery Assistant"
        if device.protocol != "ADB":
            report["Action Result"] = "Recovery assistant needs an authorized ADB session"
            return report
        base = ["adb"]
        if device.serial and device.serial != "Unknown":
            base += ["-s", device.serial]
        security = _run_command(base + ["shell", "am", "start", "-a", "android.settings.SECURITY_SETTINGS"])
        accounts = _run_command(base + ["shell", "am", "start", "-a", "android.settings.SYNC_SETTINGS"])
        report["Security Settings Intent"] = security
        report["Accounts Settings Intent"] = accounts
        report["Action Result"] = "Opened Android security/account settings for authorized owner recovery"
        return report

    def _adb_report(self, serial: str) -> dict[str, str]:
        base = ["adb"]
        if serial and serial != "Unknown":
            base += ["-s", serial]
        report = {label: _run_command(base + ["shell", "getprop", prop]) for label, prop in self.ADB_PROPERTIES.items()}
        accounts = _run_command(base + ["shell", "dumpsys", "account"], timeout=8)
        report["Account Service"] = "Available" if accounts and accounts != "Unavailable" else "Unavailable"
        frp_partition = report.get("FRP Partition", "Unavailable")
        report["FRP Status"] = "FRP partition configured" if frp_partition not in {"", "Unavailable"} else "Unknown"
        return report

    def _fastboot_report(self, serial: str) -> dict[str, str]:
        base = ["fastboot"]
        if serial and serial != "Unknown":
            base += ["-s", serial]
        report = {label: _run_command(base + ["getvar", var]) for label, var in self.FASTBOOT_VARS.items()}
        unlocked = report.get("Unlocked", "").lower()
        report["FRP Status"] = "Bootloader unlocked" if "yes" in unlocked or "true" in unlocked else "Protected / unknown"
        return report
