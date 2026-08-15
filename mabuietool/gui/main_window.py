from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QProgressBar, QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget

from mabuietool.core.branding import APP_DESCRIPTION, APP_DISPLAY_VERSION, APP_NAME
from mabuietool.core.logger import LogCategory, app_logger
from mabuietool.device.manager import DeviceManager
from mabuietool.device.models import DeviceInfo
from mabuietool.frp.manager import FRPManager
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
        self.frp_manager = FRPManager()
        self._operation_timer = QTimer(self)
        self._operation_timer.timeout.connect(self._poll_operation_device)
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
        layout.addWidget(self._progress_panel())
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
        self._add_page("mtk", OperationPage("MediaTek", "BootROM, Preloader, Device Info, Read, Backup, Flash, Partition Tools and Diagnostics through the preserved MTK backend.", ["Device Info", "Read Partitions", "Backup", "Flash", "Partition Tools", "Diagnostics", "Legacy MTK GUI"], "mtk"))
        self._add_page("unisoc", SpdUnifiedPage())
        self._add_page("qualcomm", OperationPage("Qualcomm", "EDL device information and diagnostics. Destructive operations remain capability-gated.", ["Device Info", "EDL", "Diagnostics"], "qualcomm"))
        self._add_page("android", OperationPage("Android", "ADB, Fastboot, device information, reboot and logs.", ["ADB", "Fastboot", "Device Info", "Reboot", "Logs"], "android"))
        self._add_page("frp", OperationPage("FRP Diagnostics", "Authorized diagnostics: FRP status, security properties and recovery reporting from the original device data path.", ["FRP Status", "Device Security", "Recovery Assistant", "Diagnostic Report"], "frp"))
        self._add_page("diagnostics", OperationPage("Diagnostics", "Global USB, ADB, Fastboot, serial, protocol and device health diagnostics.", ["USB Report", "COM Report", "ADB Report", "Fastboot Report", "Protocol Report", "Device Report"], "diagnostics"))
        self._add_page("backup", OperationPage("Backup", "Create, verify and restore authorized backups with JSON manifests and SHA256 hashes.", ["Create Backup", "Verify Backup", "Restore Authorized Backup"], "backup"))
        self._add_page("tools", OperationPage("Tools", "Utility tools for service workflows.", ["USB Monitor", "COM Monitor", "Hex Viewer", "File Analyzer", "Hash Calculator", "Log Viewer"], "tools"))
        self._add_page("settings", SettingsPage(self.apply_theme))
        self._add_page("about", AboutPage())

    def _add_page(self, key: str, page: QWidget) -> None:
        self._pages[key] = page
        if hasattr(page, "operation_requested"):
            page.operation_requested.connect(self.start_operation)
        self.stack.addWidget(page)

    def _progress_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("progressPanel")
        layout = QHBoxLayout(frame)
        self.progress_label = QLabel("Progress: idle")
        self.progress_label.setObjectName("muted")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar, 1)
        return frame

    def start_operation(self, page_key: str, action: str) -> None:
        self._operation_page = page_key
        self._operation_action = action
        self._operation_attempts = 0
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText(f"Progress: {page_key.upper()} / {action} - waiting for device")
        app_logger.log(LogCategory.INFO, f"{page_key.upper()} {action}: waiting for USB/ADB/Fastboot/COM device")
        self._operation_timer.start(1000)
        self._poll_operation_device()

    def _poll_operation_device(self) -> None:
        info = self.device_manager.get_device_info()
        self.update_device(info)
        self._operation_attempts = getattr(self, "_operation_attempts", 0) + 1
        if info.connection_state in {"Connected", "Authorized"} or info.protocol in {"ADB", "Fastboot", "USB"}:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_label.setText(f"Progress: {self._operation_page.upper()} / {self._operation_action} - device detected")
            app_logger.log(LogCategory.SUCCESS, f"{self._operation_action} ready on {info.platform} via {info.protocol}")
            if getattr(self, "_operation_page", "") == "frp":
                self._run_frp_action(info)
            self._operation_timer.stop()
        else:
            self.progress_label.setText(f"Progress: {self._operation_page.upper()} / {self._operation_action} - waiting for device ({self._operation_attempts})")

    def _run_frp_action(self, info: DeviceInfo) -> None:
        report = self.frp_manager.run_action(self._operation_action, info)
        app_logger.log(LogCategory.INFO, f"FRP {self._operation_action}: diagnostic report")
        for label, value in report.items():
            app_logger.log(LogCategory.INFO, f"FRP {label}: {value}")

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

