"""Adapter around the legacy MTK implementation."""
from mabuietool.backends.base import DeviceBackend
from mabuietool.core.capabilities import MTK_CAPABILITIES
from mabuietool.device.models import DeviceInfo

MTK_USB_VIDS = {0x0E8D}


class MTKLegacyAdapter(DeviceBackend):
    name = "MediaTek Backend"
    platform = "MediaTek"
    capabilities = MTK_CAPABILITIES

    def detect(self) -> DeviceInfo | None:
        try:
            import usb.core
        except Exception:
            return None
        dev = usb.core.find(find_all=False, custom_match=lambda d: d.idVendor in MTK_USB_VIDS)
        if dev is None:
            return None
        return DeviceInfo(
            manufacturer="MediaTek",
            platform=self.platform,
            chipset="Unknown",
            usb_vid=f"{dev.idVendor:04x}",
            usb_pid=f"{dev.idProduct:04x}",
            mode="BootROM / Preloader detected",
            connection_state="Connected",
            protocol="USB",
            capabilities=self.capabilities,
        )
