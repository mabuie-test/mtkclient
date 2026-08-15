"""Device state models for GUI and backend communication."""
from dataclasses import dataclass, field
from typing import Any

from mabuietool.core.capabilities import EMPTY_CAPABILITIES, Capabilities


@dataclass
class DeviceInfo:
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    chipset: str = "Unknown"
    platform: str = "Unknown"
    serial: str = "Unknown"
    usb_vid: str = ""
    usb_pid: str = ""
    mode: str = "Waiting for device"
    bootloader: str = "Unknown"
    security: str = "Unknown"
    android_version: str = "Unknown"
    battery: str = "Unknown"
    storage: str = "Unknown"
    connection_state: str = "Disconnected"
    protocol: str = "None"
    port: str = ""
    capabilities: Capabilities = field(default_factory=lambda: EMPTY_CAPABILITIES)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def usb_label(self) -> str:
        if self.usb_vid and self.usb_pid:
            return f"{self.usb_vid}:{self.usb_pid}"
        return "Not connected"

    def as_rows(self) -> list[tuple[str, str]]:
        return [
            ("Status", self.connection_state),
            ("Platform", self.platform),
            ("Manufacturer", self.manufacturer),
            ("Model", self.model),
            ("Chipset", self.chipset),
            ("Mode", self.mode),
            ("Security", self.security),
            ("USB", self.usb_label),
            ("COM", self.port or "Not connected"),
            ("Protocol", self.protocol),
            ("Battery", self.battery),
            ("Android", self.android_version),
        ]
