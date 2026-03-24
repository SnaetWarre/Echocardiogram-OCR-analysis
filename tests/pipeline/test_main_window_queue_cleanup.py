from __future__ import annotations

import os
from pathlib import Path

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


def test_run_validation_batch_prefetch_starts_batch_mode(tmp_path: Path, monkeypatch) -> None:
    _ = _get_app()
    window = MainWindow()
    window._state.ai_enabled = True

    queued_paths = [Path("/tmp/a.dcm"), Path("/tmp/b.dcm")]
    prefetch_calls: list[str] = []

    monkeypatch.setattr(window, "_ensure_validation_manager", lambda: object())
    monkeypatch.setattr(window, "_build_validation_queue", lambda: queued_paths.copy())
    monkeypatch.setattr(window, "_select_validation_output_path", lambda: tmp_path / "exact_lines.json")
    monkeypatch.setattr(
        window,
        "_start_validation_batch_prefetch",
        lambda: prefetch_calls.append("started"),
    )

    window._run_validation_batch_prefetch()

    assert prefetch_calls == ["started"]
    assert window._validation_queue_active is True
    assert window._validation_queue_mode == "review-batch"
    assert window._validation_queue == queued_paths
    assert window._validation_writer.output_path == tmp_path / "exact_lines.json"


def test_validation_batch_prefetch_finished_filters_queue_and_advances() -> None:
    _ = _get_app()
    window = MainWindow()
    first = Path("/tmp/first.dcm")
    second = Path("/tmp/second.dcm")
    window._validation_queue_active = True
    window._validation_queue_mode = "review-batch"
    window._validation_queue = [first, second]
    window._prefetched_validation_items = {second: (object(), object())}  # type: ignore[assignment]

    calls: list[str] = []
    original = window._advance_validation_queue
    window._advance_validation_queue = lambda: calls.append("advanced")  # type: ignore[method-assign]

    try:
        window._on_validation_batch_prefetch_finished(1, 1)
        QtWidgets.QApplication.processEvents()
    finally:
        window._advance_validation_queue = original  # type: ignore[method-assign]

    assert window._validation_queue == [second]
    assert calls == ["advanced"]


def test_advance_validation_queue_uses_prefetched_items_in_batch_mode() -> None:
    _ = _get_app()
    window = MainWindow()
    path = Path("/tmp/example.dcm")
    series_obj = object()
    result_obj = object()

    window._validation_queue_active = True
    window._validation_queue_mode = "review-batch"
    window._validation_queue = [path]
    window._prefetched_validation_items = {path: (series_obj, result_obj)}  # type: ignore[assignment]

    captured: list[tuple[str, object]] = []
    original_set_series = window._state.set_series
    original_set_loading = window._state.set_loading
    original_on_ai_finished = window._on_ai_finished
    window._state.set_series = lambda series: captured.append(("series", series))  # type: ignore[method-assign]
    window._state.set_loading = lambda *args, **kwargs: None  # type: ignore[method-assign]
    window._on_ai_finished = lambda result: captured.append(("result", result))  # type: ignore[method-assign]

    try:
        window._advance_validation_queue()
    finally:
        window._state.set_series = original_set_series  # type: ignore[method-assign]
        window._state.set_loading = original_set_loading  # type: ignore[method-assign]
        window._on_ai_finished = original_on_ai_finished  # type: ignore[method-assign]

    assert captured == [("series", series_obj), ("result", result_obj)]
    assert window._ai_run_mode == "validation"
    assert path not in window._prefetched_validation_items
