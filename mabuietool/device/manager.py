"""Device detection manager independent from Qt widgets."""
from __future__ import annotations

from mabuietool.backends.android.backend import AndroidAdapter
from mabuietool.backends.base import DeviceBackend
from mabuietool.backends.mtk.backend import MTKLegacyAdapter
from mabuietool.backends.qualcomm.backend import QualcommAdapter
from mabuietool.backends.unisoc.backend import UnisocAdapter
from mabuietool.core.logger import LogCategory, app_logger
from mabuietool.device.models import DeviceInfo


class DeviceManager:
    def __init__(self, backends: list[DeviceBackend] | None = None) -> None:
        self.backends = backends or [MTKLegacyAdapter(), UnisocAdapter(), QualcommAdapter(), AndroidAdapter()]
        self.current_device = DeviceInfo()

    def detect_usb(self) -> list[dict[str, str]]:
        devices: list[dict[str, str]] = []
        try:
            import usb.core
            for dev in usb.core.find(find_all=True) or []:
                devices.append({"vid": f"{dev.idVendor:04x}", "pid": f"{dev.idProduct:04x}"})
        except Exception as exc:
            app_logger.log(LogCategory.WARNING, f"USB detection unavailable: {exc}")
        return devices

    def detect_serial(self) -> list[str]:
        ports: list[str] = []
        try:
            import serial.tools.list_ports
            ports = [port.device for port in serial.tools.list_ports.comports()]
        except Exception as exc:
            app_logger.log(LogCategory.WARNING, f"COM detection unavailable: {exc}")
        return ports

    def identify_platform(self) -> str:
        return self.current_device.platform

    def identify_chipset(self) -> str:
        return self.current_device.chipset

    def identify_mode(self) -> str:
        return self.current_device.mode

    def identify_manufacturer(self) -> str:
        return self.current_device.manufacturer

    def get_device_info(self) -> DeviceInfo:
        serial_ports = self.detect_serial()
        for backend in self.backends:
            info = backend.detect()
            if info:
                if serial_ports and not info.port:
                    info.port = serial_ports[0]
                self.current_device = info
                app_logger.log(LogCategory.DEVICE, f"{info.platform} detected ({info.mode})")
                return info
        self.current_device = DeviceInfo(port=serial_ports[0] if serial_ports else "")
        app_logger.log(LogCategory.INFO, "No supported device detected")
        return self.current_device

    def get_capabilities(self) -> dict[str, bool]:
        return self.current_device.capabilities.to_dict()
