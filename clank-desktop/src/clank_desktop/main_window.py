"""Main window shell for Stage 0."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from clank_desktop import __version__


class PlaceholderView(QWidget):
    """Simple view that clearly states Stage 0 status."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        notice = QLabel("Not implemented in Stage 0")
        notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice.setStyleSheet("color: #a00; font-size: 14px;")
        stage = QLabel("Stage 0 skeleton — no data, no API, no operations")
        stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(heading)
        layout.addWidget(notice)
        layout.addWidget(stage)
        layout.addStretch()


class MainWindow(QMainWindow):
    """Primary window with disabled navigation placeholders."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Clank Desktop — Stage 0 ({__version__})")
        self.resize(960, 640)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._views = {
            "Fleet": PlaceholderView("Fleet"),
            "Newsroom Queue": PlaceholderView("Newsroom Queue"),
            "Clanks": PlaceholderView("Clanks"),
            "Search": PlaceholderView("Search"),
            "Operations": PlaceholderView("Operations"),
            "Settings": PlaceholderView("Settings"),
        }
        for view in self._views.values():
            self._stack.addWidget(view)

        self._build_menu()
        self._stack.setCurrentWidget(self._views["Fleet"])

        status = self.statusBar()
        status.showMessage("Stage 0 — not connected to any fleet")

    def _build_menu(self) -> None:
        menu = self.menuBar()
        nav = menu.addMenu("&Navigate")
        for name in self._views:
            action = QAction(name, self)
            action.setEnabled(True)  # navigation between placeholders is allowed
            action.triggered.connect(lambda checked=False, n=name: self._show(n))
            nav.addAction(action)

        ops = menu.addMenu("&Operations")
        for label in ("Run Now", "Pause", "Resume", "Restart", "Deploy", "Backup"):
            action = QAction(label, self)
            action.setEnabled(False)  # operational buttons must remain disabled
            ops.addAction(action)

        help_menu = menu.addMenu("&Help")
        about = QAction("About", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _show(self, name: str) -> None:
        self._stack.setCurrentWidget(self._views[name])

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About Clank Desktop",
            f"Clank Desktop\nVersion {__version__}\n\n"
            "Stage 0 skeleton only.\n"
            "No Fleet API connection, no data, no operations.\n\n"
            "See unified-clank-architecture-v2.1-reviewed.md",
        )
