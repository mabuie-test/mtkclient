"""Adapter around the bundled Spreadtrum/Unisoc GUI/protocol modules."""
from mabuietool.backends.base import DeviceBackend
from mabuietool.core.capabilities import UNISOC_CAPABILITIES
from mabuietool.device.models import DeviceInfo

UNISOC_USB_VIDS = {0x1782, 0x2020}


class UnisocAdapter(DeviceBackend):
    name = "Unisoc / SPD Backend"
    platform = "Unisoc / SPD"
    capabilities = UNISOC_CAPABILITIES

    def detect(self) -> DeviceInfo | None:
        try:
            import usb.core
        except Exception:
            return None
        dev = usb.core.find(find_all=False, custom_match=lambda d: d.idVendor in UNISOC_USB_VIDS)
        if dev is None:
            return None
        return DeviceInfo(
            manufacturer="Unisoc / Spreadtrum",
            platform=self.platform,
            chipset="Unknown",
            usb_vid=f"{dev.idVendor:04x}",
            usb_pid=f"{dev.idProduct:04x}",
            mode="BSL / FDL capable",
            connection_state="Connected",
            protocol="USB",
            capabilities=self.capabilities,
        )
