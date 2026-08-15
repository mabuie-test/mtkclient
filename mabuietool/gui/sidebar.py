from PySide6.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout


NAV_ITEMS = [
    ("dashboard", "DASHBOARD"),
    ("mtk", "MTK / MEDIA TEK\nDetect · BROM · Flash"),
    ("unisoc", "SPD / UNISOC\nDetect · BSL · FDL · PAC"),
    ("qualcomm", "QUALCOMM\nDetect · EDL · Diagnostics"),
    ("android", "ANDROID\nDetect · ADB · Fastboot"),
    ("diagnostics", "GLOBAL DETECTION\nUSB · COM · ADB · Fastboot"),
    ("frp", "FRP\nStatus · Security · Recovery"),
    ("backup", "BACKUP"),
    ("tools", "TOOLS"),
    ("settings", "SETTINGS"),
    ("about", "ABOUT"),
]

class Sidebar(QFrame):
    def __init__(self, on_change) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        layout = QVBoxLayout(self)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for key, label in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=key: on_change(page))
            self.group.addButton(button)
            layout.addWidget(button)
            if key == "dashboard":
                button.setChecked(True)
        layout.addStretch(1)
