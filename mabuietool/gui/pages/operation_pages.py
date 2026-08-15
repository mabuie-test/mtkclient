from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from mabuietool.core.branding import APP_COPYRIGHT, APP_DESCRIPTION, APP_DISPLAY_VERSION, APP_NAME


def _button(text: str, enabled: bool = True) -> QPushButton:
    b = QPushButton(text)
    b.setEnabled(enabled)
    return b


class OperationPage(QWidget):
    def __init__(self, title: str, subtitle: str, actions: list[str]) -> None:
        super().__init__()
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
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            label = QLabel(action)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(label)
            card_layout.addWidget(_button("Open legacy workflow" if "Legacy" in action else "Run / Open", True))
            grid.addWidget(card, i // 3, i % 3)
        layout.addLayout(grid)
        layout.addStretch(1)


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
