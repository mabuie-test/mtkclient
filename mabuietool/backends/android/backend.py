"""Android ADB/Fastboot diagnostic backend."""
from mabuietool.backends.base import DeviceBackend
from mabuietool.core.capabilities import ANDROID_CAPABILITIES
from mabuietool.device.models import DeviceInfo
from .adb import adb_available, adb_devices
from .fastboot import fastboot_available, fastboot_devices


class AndroidAdapter(DeviceBackend):
    name = "Android Backend"
    platform = "Android"
    capabilities = ANDROID_CAPABILITIES

    def detect(self) -> DeviceInfo | None:
        adb = adb_available()
        fastboot = fastboot_available()
        adb_list = adb_devices() if adb else []
        fastboot_list = fastboot_devices() if fastboot else []
        if adb_list:
            device = adb_list[0]
            state = device.get("state", "device")
            return DeviceInfo(
                manufacturer=device.get("model", "Android").replace("_", " "),
                model=device.get("model", "Unknown").replace("_", " "),
                platform=self.platform,
                serial=device.get("serial", "Unknown"),
                mode=f"ADB {state}",
                connection_state="Connected" if state == "device" else state.title(),
                protocol="ADB",
                capabilities=self.capabilities,
                raw={"adb": device},
            )
        if fastboot_list:
            return DeviceInfo(
                manufacturer="Android",
                platform=self.platform,
                serial=fastboot_list[0],
                mode="Fastboot connected",
                connection_state="Connected",
                protocol="Fastboot",
                capabilities=self.capabilities,
                raw={"fastboot_serials": fastboot_list},
            )
        if not adb and not fastboot:
            return None
        return None
