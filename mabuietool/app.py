from __future__ import annotations

import argparse
import os
import sys


from mabuietool.core.branding import APP_DESCRIPTION, APP_DISPLAY_VERSION, APP_NAME, APP_ORGANIZATION
from mabuietool.core.config import resource_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mabuietool", description=f"{APP_NAME} - {APP_DESCRIPTION}")
    parser.add_argument("--theme", choices=["dark", "light"], default="dark", help="Initial interface theme")
    parser.add_argument("--version", action="version", version=APP_DISPLAY_VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from mabuietool.gui.main_window import MainWindow
    from mabuietool.gui.themes import ThemeManager

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_DISPLAY_VERSION)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setStyle("Fusion")
    app.setStyleSheet(ThemeManager.stylesheet(args.theme))
    icon_path = resource_path("mabuietool/resources/icons/app.svg")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.apply_theme(args.theme)
    window.show()
    return app.exec()
