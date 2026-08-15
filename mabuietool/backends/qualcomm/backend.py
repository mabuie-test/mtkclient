"""Qualcomm EDL detection backend."""
from mabuietool.backends.base import DeviceBackend
from mabuietool.core.capabilities import QUALCOMM_CAPABILITIES
from mabuietool.device.models import DeviceInfo

QUALCOMM_EDL_IDS = {(0x05C6, 0x9008), (0x05C6, 0x900E)}


class QualcommAdapter(DeviceBackend):
    name = "Qualcomm Backend"
    platform = "Qualcomm"
    capabilities = QUALCOMM_CAPABILITIES

    def detect(self) -> DeviceInfo | None:
        try:
            import usb.core
        except Exception:
            return None
        dev = usb.core.find(find_all=False, custom_match=lambda d: (d.idVendor, d.idProduct) in QUALCOMM_EDL_IDS)
        if dev is None:
            return None
        return DeviceInfo(
            manufacturer="Qualcomm",
            platform=self.platform,
            chipset="Unknown",
            usb_vid=f"{dev.idVendor:04x}",
            usb_pid=f"{dev.idProduct:04x}",
            mode="EDL",
            connection_state="Connected",
            protocol="USB",
            capabilities=self.capabilities,
        )
