"""Backup manifest creation and verification helpers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class BackupManifest:
    device: str
    platform: str
    chipset: str
    partition: str
    size: int
    sha256: str
    date: str
    status: str = "created"


class BackupManager:
    def sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def create_manifest(self, file_path: Path, device: str, platform: str, chipset: str, partition: str) -> BackupManifest:
        return BackupManifest(device, platform, chipset, partition, file_path.stat().st_size, self.sha256_file(file_path), datetime.now().isoformat(timespec="seconds"))

    def save_manifest(self, manifest: BackupManifest, destination: Path) -> None:
        destination.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
