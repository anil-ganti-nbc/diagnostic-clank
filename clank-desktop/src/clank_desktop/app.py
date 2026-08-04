"""Application entry point for clank-desktop (Stage 0)."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

from clank_desktop import __version__
from clank_desktop.main_window import MainWindow


def main() -> int:
    """Launch the Stage 0 desktop shell.

    Environment variable CLANK_DESKTOP_TEST_SAFE=1 enables a test-safe mode
    that does not show the window (for headless CI).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Clank Desktop")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Unified Clank")

    window = MainWindow()
    if os.environ.get("CLANK_DESKTOP_TEST_SAFE") == "1":
        # Do not show the window; just exercise construction.
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
