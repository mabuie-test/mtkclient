from pathlib import Path

from mabuietool.backup.manager import BackupManager
from mabuietool.backends.android.backend import AndroidAdapter
from mabuietool.backends.mtk.backend import MTKLegacyAdapter
from mabuietool.backends.qualcomm.backend import QualcommAdapter
from mabuietool.backends.unisoc.backend import UnisocAdapter
from mabuietool.core.branding import APP_DESCRIPTION, APP_DISPLAY_VERSION, APP_NAME
from mabuietool.core.capabilities import MTK_CAPABILITIES
from mabuietool.device.manager import DeviceManager
from mabuietool.device.models import DeviceInfo
from mabuietool.frp.manager import FRPManager


def test_branding_identity():
    assert APP_NAME == "MabuiETool"
    assert APP_DISPLAY_VERSION == "MabuiETool 1.0"
    assert APP_DESCRIPTION == "Professional Mobile Device Service Tool"


def test_device_info_defaults_are_safe_without_device():
    info = DeviceInfo()
    assert info.connection_state == "Disconnected"
    assert info.usb_label == "Not connected"
    assert dict(info.as_rows())["Mode"] == "Waiting for device"


def test_device_manager_uses_backend_capabilities():
    manager = DeviceManager(backends=[MTKLegacyAdapter()])
    manager.current_device = DeviceInfo(platform="MediaTek", capabilities=MTK_CAPABILITIES)
    assert manager.get_capabilities()["flash"] is True


def test_backends_construct():
    assert MTKLegacyAdapter().platform == "MediaTek"
    assert UnisocAdapter().platform == "Unisoc / SPD"
    assert QualcommAdapter().platform == "Qualcomm"
    assert AndroidAdapter().platform == "Android"


def test_frp_diagnostics_is_non_bypass():
    report = FRPManager().diagnostic_report(DeviceInfo(platform="Android"))
    assert "Unauthorized" in report["Note"]
    assert "not provided" in report["Note"]


def test_backup_manifest(tmp_path: Path):
    sample = tmp_path / "boot.bin"
    sample.write_bytes(b"mabuietool")
    manifest = BackupManager().create_manifest(sample, "device", "MediaTek", "Unknown", "boot")
    assert manifest.size == len(b"mabuietool")
    assert len(manifest.sha256) == 64


def test_unisoc_page_is_unified_in_main_window_source():
    source = Path("mabuietool/gui/main_window.py").read_text(encoding="utf-8")
    assert "SpdUnifiedPage" in source
    assert "open_legacy_spd" not in source
    assert "subprocess.Popen" not in source
