from PySide6.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout


NAV_ITEMS = [
    ("dashboard", "DASHBOARD"),
    ("mtk", "MEDIA TEK\nBootROM · Preloader · Flash"),
    ("unisoc", "UNISOC / SPD\nBSL · FDL · PAC · Flash"),
    ("qualcomm", "QUALCOMM\nEDL · Diagnostics"),
    ("android", "ANDROID\nADB · Fastboot · Logs"),
    ("frp", "FRP\nStatus · Security · Recovery"),
    ("diagnostics", "DIAGNOSTICS"),
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
