"""Android ADB/Fastboot diagnostic backend."""
from mabuietool.backends.base import DeviceBackend
from mabuietool.core.capabilities import ANDROID_CAPABILITIES
from mabuietool.device.models import DeviceInfo
from .adb import adb_available
from .fastboot import fastboot_available


class AndroidAdapter(DeviceBackend):
    name = "Android Backend"
    platform = "Android"
    capabilities = ANDROID_CAPABILITIES

    def detect(self) -> DeviceInfo | None:
        adb = adb_available()
        fastboot = fastboot_available()
        if not adb and not fastboot:
            return None
        return DeviceInfo(
            manufacturer="Android",
            platform=self.platform,
            mode="ADB available" if adb else "Fastboot available",
            connection_state="Tool available",
            protocol="ADB/Fastboot",
            capabilities=self.capabilities,
        )
