from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget

from mabuietool.core.branding import APP_DESCRIPTION, APP_DISPLAY_VERSION, APP_NAME
from mabuietool.core.logger import LogCategory, app_logger
from mabuietool.device.manager import DeviceManager
from mabuietool.device.models import DeviceInfo
from mabuietool.gui.console import LogConsole
from mabuietool.gui.dashboard import DashboardPage
from mabuietool.gui.pages.operation_pages import AboutPage, OperationPage, SettingsPage
from mabuietool.gui.pages.spd_page import SpdUnifiedPage
from mabuietool.gui.sidebar import Sidebar
from mabuietool.gui.themes import ThemeManager


class MainWindow(QMainWindow):
    def __init__(self, device_manager: DeviceManager | None = None) -> None:
        super().__init__()
        self.device_manager = device_manager or DeviceManager()
        self.setWindowTitle(f"{APP_DISPLAY_VERSION} - {APP_DESCRIPTION}")
        self.resize(1280, 820)
        self._theme = "dark"
        self._pages: dict[str, QWidget] = {}
        self._build_ui()
        self._setup_timer()
        app_logger.log(LogCategory.SUCCESS, f"{APP_NAME} initialized")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(self._topbar())
        body = QHBoxLayout()
        self.sidebar = Sidebar(self.set_page)
        self.stack = QStackedWidget()
        body.addWidget(self.sidebar, 0)
        body.addWidget(self.stack, 1)
        layout.addLayout(body, 1)
        self.console = LogConsole()
        self.console.setMinimumHeight(180)
        layout.addWidget(self.console)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("USB | COM | Device | Protocol | Status | Log")
        self._build_pages()

    def _topbar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("topbar")
        layout = QHBoxLayout(frame)
        self.brand = QLabel(APP_NAME)
        self.brand.setObjectName("brand")
        subtitle = QLabel(f"{APP_DISPLAY_VERSION} · {APP_DESCRIPTION}")
        subtitle.setObjectName("subtitle")
        self.device_state = QLabel("Device: Disconnected")
        self.usb_state = QLabel("USB: Waiting")
        self.com_state = QLabel("COM: Waiting")
        self.mode_state = QLabel("Mode: Ready")
        refresh = QPushButton("Refresh")
        refresh.setObjectName("primary")
        refresh.clicked.connect(self.refresh_device)
        layout.addWidget(self.brand)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        layout.addWidget(self.device_state)
        layout.addWidget(self.usb_state)
        layout.addWidget(self.com_state)
        layout.addWidget(self.mode_state)
        layout.addWidget(refresh)
        return frame

    def _build_pages(self) -> None:
        self._add_page("dashboard", DashboardPage())
        self._add_page("mtk", OperationPage("MediaTek", "BootROM, Preloader, Device Info, Read, Backup, Flash, Partition Tools and Diagnostics through the preserved MTK backend.", ["Device Info", "Read Partitions", "Backup", "Flash", "Partition Tools", "Diagnostics", "Legacy MTK GUI"]))
        self._add_page("unisoc", SpdUnifiedPage())
        self._add_page("qualcomm", OperationPage("Qualcomm", "EDL device information and diagnostics. Destructive operations remain capability-gated.", ["Device Info", "EDL", "Diagnostics"]))
        self._add_page("android", OperationPage("Android", "ADB, Fastboot, device information, reboot and logs.", ["ADB", "Fastboot", "Device Info", "Reboot", "Logs"]))
        self._add_page("frp", OperationPage("FRP Diagnostics", "Authorized diagnostics only. This module does not implement unauthorized bypass or removal.", ["FRP Status", "Device Security", "Recovery Assistant", "Diagnostic Report"]))
        self._add_page("diagnostics", OperationPage("Diagnostics", "USB, serial, protocol and device health diagnostics.", ["USB Report", "COM Report", "Protocol Report", "Device Report"]))
        self._add_page("backup", OperationPage("Backup", "Create, verify and restore authorized backups with JSON manifests and SHA256 hashes.", ["Create Backup", "Verify Backup", "Restore Authorized Backup"]))
        self._add_page("tools", OperationPage("Tools", "Utility tools for service workflows.", ["USB Monitor", "COM Monitor", "Hex Viewer", "File Analyzer", "Hash Calculator", "Log Viewer"]))
        self._add_page("settings", SettingsPage(self.apply_theme))
        self._add_page("about", AboutPage())

    def _add_page(self, key: str, page: QWidget) -> None:
        self._pages[key] = page
        self.stack.addWidget(page)

    def set_page(self, key: str) -> None:
        page = self._pages[key]
        self.stack.setCurrentWidget(page)
        app_logger.log(LogCategory.INFO, f"Opened {key} page")

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.window().setStyleSheet(ThemeManager.stylesheet(theme))
        app_logger.log(LogCategory.INFO, f"Theme changed to {theme}")

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_device)
        self.timer.start(5000)
        QTimer.singleShot(100, self.refresh_device)

    def refresh_device(self) -> None:
        info = self.device_manager.get_device_info()
        self.update_device(info)

    def update_device(self, info: DeviceInfo) -> None:
        connected = info.connection_state not in {"Disconnected", "Unknown"}
        self.device_state.setText(f"Device: {info.connection_state}")
        self.usb_state.setText(f"USB: {info.usb_label}")
        self.com_state.setText(f"COM: {info.port or 'Waiting'}")
        self.mode_state.setText(f"Mode: {info.mode}")
        self.statusBar().showMessage(f"USB {info.usb_label} | COM {info.port or 'Waiting'} | Device {info.connection_state} | Protocol {info.protocol} | Status Ready")
        self.device_state.setObjectName("statusConnected" if connected else "statusDisconnected")
        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.update_device(info)

