from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DICOM_AI_ENABLED", "0")

from PySide6 import QtWidgets

from app.ui.main_window import MainWindow


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_loader_thread_cleanup_does_not_leave_busy_state() -> None:
    _ = _get_app()
    window = MainWindow()

    window._validation_queue_active = True
    window._pending_validation_path = None
    window._loader = object()
    window._loader_thread = object()

    calls: list[str] = []
    original = window._advance_validation_queue
    window._advance_validation_queue = lambda: calls.append("advanced")  # type: ignore[method-assign]

    try:
        window._on_loader_thread_finished()
        QtWidgets.QApplication.processEvents()
    finally:
        window._advance_validation_queue = original  # type: ignore[method-assign]

    assert window._loader is None
    assert window._loader_thread is None


def test_ai_thread_cleanup_resumes_queue_when_not_waiting_review() -> None:
    _ = _get_app()
    window = MainWindow()

    window._validation_queue_active = True
    window._validation_waiting_review = False
    window._ai_run_mode = "export"
    window._ai_worker = object()
    window._ai_thread = object()

    calls: list[str] = []
    original = window._advance_validation_queue
    window._advance_validation_queue = lambda: calls.append("advanced")  # type: ignore[method-assign]

    try:
        window._on_ai_thread_finished()
        QtWidgets.QApplication.processEvents()
    finally:
        window._advance_validation_queue = original  # type: ignore[method-assign]

    assert window._ai_worker is None
    assert window._ai_thread is None


def test_ai_thread_cleanup_does_not_resume_while_waiting_review() -> None:
    _ = _get_app()
    window = MainWindow()

    window._validation_queue_active = True
    window._validation_waiting_review = True
    window._ai_run_mode = "validation"
    window._ai_worker = object()
    window._ai_thread = object()

    calls: list[str] = []
    original = window._advance_validation_queue
    window._advance_validation_queue = lambda: calls.append("advanced")  # type: ignore[method-assign]

    try:
        window._on_ai_thread_finished()
        QtWidgets.QApplication.processEvents()
    finally:
        window._advance_validation_queue = original  # type: ignore[method-assign]

    assert calls == []


def test_setting_selected_ocr_engines_resets_cached_validation_manager() -> None:
    _ = _get_app()
    window = MainWindow()
    original_manager = object()
    window._validation_pipeline_manager = original_manager  # type: ignore[assignment]
    window._validation_manager_selection = ("surya",)

    window._set_selected_ocr_engines(("easyocr",))

    assert window._validation_pipeline_manager is None
    assert window._validation_manager_selection == ()
