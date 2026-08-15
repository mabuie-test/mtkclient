from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFrame, QHBoxLayout, QPushButton, QPlainTextEdit, QVBoxLayout

from mabuietool.core.logger import LogRecord, app_logger


class LogConsole(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("console")
        self.autoscroll = QCheckBox("Auto-scroll")
        self.autoscroll.setChecked(True)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        clear = QPushButton("Clear")
        copy = QPushButton("Copy")
        save = QPushButton("Save Log")
        clear.clicked.connect(self.clear)
        copy.clicked.connect(self.text.copy)
        save.clicked.connect(self.save)
        bar = QHBoxLayout()
        bar.addWidget(clear)
        bar.addWidget(copy)
        bar.addWidget(save)
        bar.addStretch(1)
        bar.addWidget(self.autoscroll)
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.text)
        app_logger.subscribe(self.append)

    def append(self, record: LogRecord) -> None:
        self.text.appendPlainText(record.format())
        if self.autoscroll.isChecked():
            self.text.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self) -> None:
        app_logger.clear()
        self.text.clear()

    def save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save MabuiETool log", "mabuietool.log", "Log files (*.log);;Text files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.text.toPlainText())
