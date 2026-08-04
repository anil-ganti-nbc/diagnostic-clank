"""Desktop shell construction test (Stage 0)."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["CLANK_DESKTOP_TEST_SAFE"] = "1"


def test_main_window_constructs() -> None:
    from PySide6.QtWidgets import QApplication

    from clank_desktop.main_window import MainWindow

    QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    assert "Stage 0" in window.windowTitle()
    assert window.statusBar().currentMessage()
    window.close()
