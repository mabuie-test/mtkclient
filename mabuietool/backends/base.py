"""Common backend interface used by DeviceManager."""
from __future__ import annotations

from abc import ABC, abstractmethod

from mabuietool.core.capabilities import Capabilities, EMPTY_CAPABILITIES
from mabuietool.device.models import DeviceInfo


class DeviceBackend(ABC):
    name = "Generic"
    platform = "Unknown"
    capabilities: Capabilities = EMPTY_CAPABILITIES

    @abstractmethod
    def detect(self) -> DeviceInfo | None:
        raise NotImplementedError

    def connect(self) -> bool:
        return False

    def disconnect(self) -> None:
        return None

    def get_device_info(self) -> DeviceInfo:
        detected = self.detect()
        return detected or DeviceInfo(platform=self.platform, capabilities=self.capabilities)

    def get_capabilities(self) -> Capabilities:
        return self.capabilities

    def diagnostics(self) -> dict[str, str]:
        return {"backend": self.name, "status": "available"}
