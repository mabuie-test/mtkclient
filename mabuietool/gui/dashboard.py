from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from mabuietool.device.models import DeviceInfo


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Dashboard")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("Device status and supported operation summary")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        layout.addLayout(self.grid)
        layout.addStretch(1)
        self._cards: dict[str, QLabel] = {}
        self.update_device(DeviceInfo())

    def update_device(self, info: DeviceInfo) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, (label, value) in enumerate(info.as_rows()):
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            name = QLabel(label.upper())
            name.setObjectName("muted")
            val = QLabel(value or "Unknown")
            val.setWordWrap(True)
            val.setObjectName("statusConnected" if value in {"Connected", "Tool available"} else "statusDisconnected" if label == "Status" else "")
            card_layout.addWidget(name)
            card_layout.addWidget(val)
            self.grid.addWidget(card, index // 4, index % 4)
