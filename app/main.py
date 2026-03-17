from __future__ import annotations

import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from PySide6 import QtWidgets

from app.runtime.startup_services import ServiceProcessManager, StartupServices
from app.ui.dialogs.startup_dialog import StartupDialog
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


def _run_startup(app: QtWidgets.QApplication) -> StartupServices | None:
    ai_enabled = os.getenv("DICOM_AI_ENABLED", "1") == "1"
    if not ai_enabled:
        return StartupServices()
    manager = ServiceProcessManager(ai_enabled=ai_enabled)
    dialog = StartupDialog(manager)
    if dialog.exec() != int(QtWidgets.QDialog.DialogCode.Accepted):
        return None
    services = dialog.services
    if services is None:
        return None
    if services.managed_ollama_process is not None:
        app.aboutToQuit.connect(
            lambda: manager.shutdown_managed_ollama(services.managed_ollama_process)
        )
    return services


def main() -> None:
    sys.excepthook = _excepthook
    try:
        threading.excepthook = _thread_excepthook
    except AttributeError:
        pass
    app = QtWidgets.QApplication(sys.argv)
    startup_services = _run_startup(app)
    if os.getenv("DICOM_AI_ENABLED", "1") == "1" and startup_services is None:
        sys.exit(1)
    window = MainWindow(startup_services=startup_services)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
