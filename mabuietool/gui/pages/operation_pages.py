from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from mabuietool.core.branding import APP_COPYRIGHT, APP_DESCRIPTION, APP_DISPLAY_VERSION, APP_NAME


def _button(text: str, enabled: bool = True) -> QPushButton:
    b = QPushButton(text)
    b.setEnabled(enabled)
    return b


class ActionCard(QFrame):
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("actionCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class OperationPage(QWidget):
    operation_requested = Signal(str, str)

    def __init__(self, title: str, subtitle: str, actions: list[str], page_key: str = "") -> None:
        super().__init__()
        self.title = title
        self.page_key = page_key or title.lower().replace(" ", "_")
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        desc = QLabel(subtitle)
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(desc)
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, action in enumerate(actions):
            card = ActionCard()
            card_layout = QVBoxLayout(card)
            label = QLabel(action)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            card_layout.addWidget(label)
            button = _button("Open legacy workflow" if "Legacy" in action else "Run / Open", True)
            button.clicked.connect(lambda checked=False, selected=action: self.request_operation(selected))
            card.clicked.connect(lambda selected=action: self.request_operation(selected))
            card_layout.addWidget(button)
            grid.addWidget(card, i // 3, i % 3)
        layout.addLayout(grid)
        layout.addStretch(1)

    def request_operation(self, action: str) -> None:
        self.operation_requested.emit(self.page_key, action)


class SettingsPage(QWidget):
    def __init__(self, on_theme_change) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel("Appearance"))
        dark = QPushButton("Dark Theme")
        light = QPushButton("Light Theme")
        dark.clicked.connect(lambda: on_theme_change("dark"))
        light.clicked.connect(lambda: on_theme_change("light"))
        layout.addWidget(dark)
        layout.addWidget(light)
        layout.addStretch(1)


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel(APP_NAME)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(APP_DISPLAY_VERSION))
        layout.addWidget(QLabel(APP_DESCRIPTION))
        credits = QLabel(APP_COPYRIGHT + "\n\nLegacy MediaTek functionality remains encapsulated for compatibility and licensing continuity.")
        credits.setWordWrap(True)
        credits.setObjectName("muted")
        layout.addWidget(credits)
        layout.addStretch(1)
