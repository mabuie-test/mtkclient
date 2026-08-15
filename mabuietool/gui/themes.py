"""Centralized MabuiETool colors and styles."""

class ThemeManager:
    DARK = {
        "bg": "#0f121a", "panel": "#171c29", "panel2": "#202638", "border": "#30384f",
        "text": "#eef2ff", "muted": "#99a4c2", "accent": "#26d6bf", "progress": "#ff8c1a", "warn": "#f0b84b", "error": "#ff667a",
    }
    LIGHT = {
        "bg": "#f4f7fb", "panel": "#ffffff", "panel2": "#e9eef7", "border": "#cad3e3",
        "text": "#182033", "muted": "#526079", "accent": "#087e70", "progress": "#ff8c1a", "warn": "#9a6500", "error": "#b42335",
    }

    @classmethod
    def stylesheet(cls, theme: str = "dark") -> str:
        c = cls.LIGHT if theme.lower() == "light" else cls.DARK
        return f"""
        QMainWindow, QWidget#root {{ background: {c['bg']}; color: {c['text']}; }}
        QWidget {{ color: {c['text']}; font-family: "Segoe UI", "Cantarell", "Ubuntu", sans-serif; font-size: 10pt; }}
        QLabel#brand {{ color: {c['accent']}; font-size: 18pt; font-weight: 900; }}
        QLabel#subtitle, QLabel#muted {{ color: {c['muted']}; }}
        QLabel#sectionTitle {{ font-size: 15pt; font-weight: 800; color: {c['text']}; }}
        QLabel#statusConnected {{ color: {c['accent']}; font-weight: 800; }}
        QLabel#statusDisconnected {{ color: {c['warn']}; font-weight: 800; }}
        QFrame#topbar, QFrame#sidebar, QFrame#console, QFrame#card, QFrame#actionCard, QFrame#progressPanel {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 10px; }}
        QPushButton {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 8px 12px; font-weight: 650; }}
        QPushButton:hover {{ border-color: {c['accent']}; }}
        QPushButton#navButton {{ text-align: left; border-radius: 8px; padding: 9px 12px; }}
        QPushButton#navButton:checked {{ color: {c['accent']}; border-color: {c['accent']}; background: {c['panel2']}; }}
        QPushButton#primary {{ background: {c['accent']}; color: {c['bg']}; }}
        QPlainTextEdit, QTableWidget, QComboBox {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 6px; }}
        QHeaderView::section {{ background: {c['panel2']}; border: 1px solid {c['border']}; padding: 6px; }}
        QProgressBar {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 7px; height: 16px; text-align: center; }}
        QProgressBar::chunk {{ background: {c['progress']}; border-radius: 6px; }}
        QStatusBar {{ background: {c['panel']}; color: {c['muted']}; }}
        """
