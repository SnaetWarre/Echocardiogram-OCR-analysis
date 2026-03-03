from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.pipeline.startup_services import ServiceProcessManager, StartupServices


class _StartupWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, manager: ServiceProcessManager) -> None:
        super().__init__()
        self._manager = manager

    @QtCore.Slot()
    def run(self) -> None:
        try:
            services = self._manager.initialize(self._emit_progress)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(services)

    def _emit_progress(self, message: str, step: int, total: int) -> None:
        self.progress.emit(message, step, total)


class StartupDialog(QtWidgets.QDialog):
    def __init__(
        self,
        manager: ServiceProcessManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Starting services")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedWidth(540)

        self._manager = manager
        self._services: StartupServices | None = None
        self._thread: QtCore.QThread | None = None
        self._worker: _StartupWorker | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._title = QtWidgets.QLabel("Initializing AI services...")
        self._title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._status = QtWidgets.QLabel("Preparing startup checks...")
        self._bar = QtWidgets.QProgressBar()
        self._bar.setRange(0, 3)
        self._bar.setValue(0)

        self._troubleshooting = QtWidgets.QPlainTextEdit()
        self._troubleshooting.setReadOnly(True)
        self._troubleshooting.hide()

        self._close_button = QtWidgets.QPushButton("Close")
        self._close_button.clicked.connect(self.reject)
        self._close_button.hide()

        layout.addWidget(self._title)
        layout.addWidget(self._status)
        layout.addWidget(self._bar)
        layout.addWidget(self._troubleshooting)
        layout.addWidget(self._close_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        QtCore.QTimer.singleShot(0, self._start_worker)

    @property
    def services(self) -> StartupServices | None:
        return self._services

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _start_worker(self) -> None:
        if self._thread is not None:
            return
        self._thread = QtCore.QThread(self)
        self._worker = _StartupWorker(self._manager)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._on_failed)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    @QtCore.Slot(str, int, int)
    def _on_progress(self, message: str, step: int, total: int) -> None:
        self._status.setText(message)
        self._bar.setRange(0, max(1, total))
        self._bar.setValue(min(step, total))

    @QtCore.Slot(object)
    def _on_finished(self, services: object) -> None:
        if not isinstance(services, StartupServices):
            self._on_failed("Startup returned an invalid service state.")
            return
        self._services = services
        self._status.setText("Ready!")
        self._bar.setValue(self._bar.maximum())
        QtCore.QTimer.singleShot(150, self.accept)

    @QtCore.Slot(str)
    def _on_failed(self, message: str) -> None:
        self._status.setText("Startup failed.")
        self._title.setText("AI service startup failed")
        self._bar.setValue(0)
        self._troubleshooting.setPlainText(
            f"{message}\n\n{self._manager.troubleshooting_text()}"
        )
        self._troubleshooting.show()
        self._close_button.show()

    @QtCore.Slot()
    def _cleanup_thread(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
