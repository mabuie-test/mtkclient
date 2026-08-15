"""Capability model shared by all device backends."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Capabilities:
    read_info: bool = False
    read_partition: bool = False
    backup: bool = False
    restore_backup: bool = False
    flash: bool = False
    format: bool = False
    frp_diagnostics: bool = False
    adb: bool = False
    fastboot: bool = False
    diagnostics: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


EMPTY_CAPABILITIES = Capabilities()
MTK_CAPABILITIES = Capabilities(read_info=True, read_partition=True, backup=True, restore_backup=True, flash=True, frp_diagnostics=True)
UNISOC_CAPABILITIES = Capabilities(read_info=True, read_partition=True, backup=True, restore_backup=True, flash=True, diagnostics=True)
QUALCOMM_CAPABILITIES = Capabilities(read_info=True, backup=True, restore_backup=True, flash=True, diagnostics=True)
ANDROID_CAPABILITIES = Capabilities(read_info=True, frp_diagnostics=True, adb=True, fastboot=True, diagnostics=True)
