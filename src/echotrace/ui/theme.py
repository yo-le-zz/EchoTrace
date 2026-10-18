"""Thème Catppuccin Macchiato."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

STYLESHEET = """
QMainWindow, QDialog { background-color: #181926; }
QTabWidget::pane { border: 1px solid #494a64; background-color: #1e1f2e; border-radius: 8px; }
QTabBar::tab { background-color: #313244; color: #cad3f5; padding: 8px 16px; margin-right: 2px;
               border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background-color: #575268; border-bottom: 2px solid #8bd5ca; }
QTabBar::tab:hover { background-color: #45475a; }
QGroupBox { font-weight: 600; color: #cad3f5; border: 2px solid #494a64; border-radius: 10px;
            margin-top: 10px; padding-top: 10px; background-color: #1e1f2e; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; background-color: #1e1f2e; }
QPushButton { background-color: #313244; color: #cad3f5; border: 1px solid #494a64;
              border-radius: 6px; padding: 8px 16px; }
QPushButton:hover { background-color: #45475a; border-color: #575268; }
QPushButton:pressed { background-color: #575268; }
QPushButton:disabled { color: #6e6c7e; }
QPushButton#primary { background-color: #8bd5ca; color: #1e1f2e; border-color: #8bd5ca;
                      font-weight: 600; padding: 10px 20px; }
QPushButton#primary:hover { background-color: #a6da95; }
QPushButton#primary:disabled { background-color: #494a64; color: #6e6c7e; }
QPushButton#danger { background-color: #ed8796; color: #1e1f2e; border-color: #ed8796; font-weight: 600; }
QLineEdit, QTextEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #1e1f2e; color: #cad3f5; border: 1px solid #494a64;
    border-radius: 6px; padding: 6px 10px; }
QLineEdit:focus, QTextEdit:focus { border: 2px solid #8bd5ca; }
QTableWidget { background-color: #1e1f2e; color: #cad3f5; border: 1px solid #494a64;
               border-radius: 6px; gridline-color: #494a64; selection-background-color: #575268; }
QTableWidget::item { padding: 6px; }
QHeaderView::section { background-color: #313244; color: #cad3f5; padding: 8px;
                       border: 1px solid #494a64; font-weight: 600; }
QProgressBar { border: 1px solid #494a64; border-radius: 6px; text-align: center;
               background-color: #1e1f2e; color: #cad3f5; }
QProgressBar::chunk { background-color: #8bd5ca; border-radius: 5px; }
QLabel { color: #cad3f5; }
QCheckBox { color: #cad3f5; }
QStatusBar { background-color: #1e1f2e; color: #cad3f5; border-top: 1px solid #494a64; }
QMenu { background-color: #1e1f2e; color: #cad3f5; border: 1px solid #494a64; }
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background-color: #313244; }
"""


def apply_theme(app: QApplication) -> None:
    """Applique le thème. Le style Fusion rend l'apparence identique sur tous les systèmes."""
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: (24, 25, 38),
        QPalette.ColorRole.WindowText: (202, 211, 245),
        QPalette.ColorRole.Base: (30, 31, 46),
        QPalette.ColorRole.AlternateBase: (24, 25, 38),
        QPalette.ColorRole.ToolTipBase: (24, 25, 38),
        QPalette.ColorRole.ToolTipText: (202, 211, 245),
        QPalette.ColorRole.Text: (202, 211, 245),
        QPalette.ColorRole.Button: (49, 50, 68),
        QPalette.ColorRole.ButtonText: (202, 211, 245),
        QPalette.ColorRole.BrightText: (243, 139, 168),
        QPalette.ColorRole.Link: (137, 180, 250),
        QPalette.ColorRole.Highlight: (137, 180, 250),
        QPalette.ColorRole.HighlightedText: (30, 31, 46),
    }
    for role, rgb in colors.items():
        palette.setColor(role, QColor(*rgb))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
