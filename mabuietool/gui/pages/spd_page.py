"""Unified Unisoc/SPD page embedding the existing SPD tool in MabuiETool."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

from mabuietool.core.logger import LogCategory, app_logger
from mabuietool.gui.pages.operation_pages import OperationPage


class SpdUnifiedPage(QWidget):
    operation_requested = Signal(str, str)
    """Host the existing SPD GUI inside MabuiETool instead of launching it separately."""

    def __init__(self) -> None:
        super().__init__()
        self._embedded_window = None
        layout = QVBoxLayout(self)
        title = QLabel("Unisoc / SPD")
        title.setObjectName("sectionTitle")
        intro = QLabel("Unified SPD workspace: native MabuiETool actions and the full existing SPD interface run inside this page.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        native_spd = OperationPage(
            "Unisoc / SPD Operations",
            "BSL, FDL, PAC extraction, read, backup, flash and diagnostics through the bundled SPD backend.",
            ["Device Info", "BSL", "FDL", "PAC", "Read", "Backup", "Flash", "Diagnostics"],
            "unisoc",
        )
        native_spd.operation_requested.connect(self.operation_requested)
        self.tabs.addTab(native_spd, "MabuiETool SPD")
        self.tabs.addTab(self._build_embedded_spd(), "Full SPD Tool")
        layout.addWidget(self.tabs, 1)

    def _build_embedded_spd(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        try:
            spd_root = Path(__file__).resolve().parents[3] / "spd_gui"
            if str(spd_root) not in sys.path:
                sys.path.insert(0, str(spd_root))
            from spd_gui.gui import MainWindow as SpdMainWindow

            self._embedded_window = SpdMainWindow()
            self._embedded_window.setWindowFlags(self._embedded_window.windowFlags())
            self._embedded_window.setWindowTitle("MabuiETool - Unified SPD")
            layout.addWidget(self._embedded_window)
            app_logger.log(LogCategory.SUCCESS, "Embedded SPD interface loaded inside MabuiETool")
        except Exception as exc:  # pragma: no cover - depends on optional GUI/runtime deps
            app_logger.log(LogCategory.ERROR, f"Unable to embed SPD interface: {exc}")
            message = QLabel(
                "Não foi possível carregar a interface SPD integrada. "
                "Verifique dependências PySide6/USB e os módulos spd_gui.\n\n"
                f"Detalhes: {exc}"
            )
            message.setWordWrap(True)
            retry = QPushButton("Retry loading SPD")
            retry.clicked.connect(self._retry_embed)
            layout.addWidget(message)
            layout.addWidget(retry)
            layout.addStretch(1)
        return container

    def _retry_embed(self) -> None:
        index = self.tabs.indexOf(self.sender().parent()) if self.sender() else -1
        replacement = self._build_embedded_spd()
        current = self.tabs.widget(1)
        self.tabs.removeTab(1)
        current.deleteLater()
        self.tabs.insertTab(1, replacement, "Full SPD Tool")
        self.tabs.setCurrentIndex(1 if index < 0 else index)
