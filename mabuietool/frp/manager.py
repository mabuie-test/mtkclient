"""Authorized FRP diagnostics only; no bypass operations are implemented."""
from mabuietool.device.models import DeviceInfo


class FRPManager:
    def diagnostic_report(self, device: DeviceInfo) -> dict[str, str]:
        return {
            "FRP Status": "Unknown",
            "ADB Status": "Available" if device.protocol == "ADB/Fastboot" else "Unknown",
            "Fastboot Status": "Unknown",
            "Bootloader State": device.bootloader,
            "Security Information": device.security,
            "Device Information": f"{device.manufacturer} {device.model}".strip(),
            "Note": "Diagnostics only. Unauthorized FRP bypass/removal is not provided.",
        }
