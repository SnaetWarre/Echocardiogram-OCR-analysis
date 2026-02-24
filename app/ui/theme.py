from __future__ import annotations

from PySide6 import QtWidgets


APP_STYLESHEET = """
QMainWindow {
    background: #F5F7FA;
}
#leftPanel {
    background: #F0F3F7;
    border: 1px solid #C9D1DA;
    border-radius: 3px;
}
#controls {
    background: #F0F3F7;
    border: 1px solid #C9D1DA;
    border-radius: 3px;
}
#metadataTabs {
    background: #FFFFFF;
    border: 1px solid #C9D1DA;
    border-radius: 3px;
}
QToolBar {
    background: #E9EDF2;
    border: none;
    border-bottom: 1px solid #C9D1DA;
    spacing: 6px;
    padding: 4px;
}
QToolBar QToolButton {
    background: transparent;
    color: #2B3A46;
    border: 1px solid transparent;
    border-radius: 2px;
    padding: 4px 6px;
}
QToolBar QToolButton:hover {
    background: #DDE4EC;
    border: 1px solid #C9D1DA;
}
QToolBar QToolButton:pressed {
    background: #CFD8E3;
}
#sidebarSlim QToolButton {
    background: #E7EBF1;
    color: #2B3A46;
    border: 1px solid #C9D1DA;
    border-radius: 2px;
    padding: 6px;
}
#sidebarSlim QToolButton:hover {
    background: #DDE4EC;
}
#sidebarSlim QToolButton:pressed {
    background: #CFD8E3;
}
QPushButton, QToolButton {
    background: #EEF2F6;
    color: #2B3A46;
    border: 1px solid #C9D1DA;
    border-radius: 3px;
    padding: 6px 10px;
}
QPushButton:hover, QToolButton:hover {
    background: #E1E7EF;
}
QPushButton:pressed, QToolButton:pressed {
    background: #D5DEE8;
}
QPushButton:disabled, QToolButton:disabled {
    background: #F4F6F9;
    color: #8A96A3;
    border-color: #D3DAE2;
}
QTabWidget::pane {
    border: 1px solid #C9D1DA;
    border-radius: 3px;
    background: #FFFFFF;
}
QTabBar::tab {
    background: #EEF2F6;
    border: 1px solid #C9D1DA;
    border-bottom: none;
    padding: 6px 12px;
    margin-right: 4px;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    color: #2B3A46;
}
QTabBar::tab:selected {
    background: #FFFFFF;
}
QHeaderView::section {
    background: #EEF2F6;
    color: #2B3A46;
    border: 1px solid #C9D1DA;
    padding: 4px 6px;
}
QTableWidget {
    background: #FFFFFF;
    gridline-color: #E1E6ED;
    border: 1px solid #C9D1DA;
    border-radius: 2px;
}
QStatusBar {
    background: #E9EDF2;
    color: #2B3A46;
    border-top: 1px solid #C9D1DA;
}
QLineEdit {
    background: #FFFFFF;
    border: 1px solid #C9D1DA;
    border-radius: 2px;
    padding: 6px 8px;
}
QCheckBox {
    color: #3A4756;
}
QTreeView {
    background: #FFFFFF;
    alternate-background-color: #F4F6F9;
    color: #2A3642;
    border: 1px solid #C9D1DA;
    border-radius: 2px;
    selection-background-color: #DCE5F0;
    selection-color: #1B2430;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #C9D1DA;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 12px;
    background: #A5B0BE;
    margin: -4px 0;
    border-radius: 2px;
}
QLabel {
    color: #2A3642;
}
QTextEdit {
    background: #FFFFFF;
    color: #2A3642;
    border: 1px solid #C9D1DA;
    border-radius: 2px;
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 11px;
}
"""


def apply_theme(window: QtWidgets.QWidget) -> None:
    window.setStyleSheet(APP_STYLESHEET)
