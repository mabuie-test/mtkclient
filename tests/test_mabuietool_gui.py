import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover - environment dependency
    pytest.skip(f"PySide6 runtime unavailable: {exc}", allow_module_level=True)

from mabuietool.gui.main_window import MainWindow


def test_main_window_builds_without_device():
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    assert win.windowTitle().startswith("MabuiETool 1.0")
    assert win.stack.count() >= 10
    win.close()
