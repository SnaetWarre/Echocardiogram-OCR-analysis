from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from PySide6 import QtWidgets

from app.ui.main_window import MainWindow


def _log_unhandled_exception(
    exc_type: type[BaseException],
    exc: BaseException,
    tb,
) -> Path:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "dicom_viewer.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stack = "".join(traceback.format_exception(exc_type, exc, tb))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] Unhandled exception:\n{stack}\n")
    return log_path


def _excepthook(
    exc_type: type[BaseException],
    exc: BaseException,
    tb,
) -> None:
    log_path = _log_unhandled_exception(exc_type, exc, tb)
    message = (
        "Something went wrong and the application hit an unexpected error.\n\n"
        f"{exc_type.__name__}: {exc}\n\n"
        f"Log file: {log_path}"
    )
    if QtWidgets.QApplication.instance() is None:
        _ = QtWidgets.QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(None, "Unhandled Error", message)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    _excepthook(args.exc_type, args.exc_value, args.exc_traceback)


def main() -> None:
    sys.excepthook = _excepthook
    try:
        threading.excepthook = _thread_excepthook
    except AttributeError:
        pass
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
