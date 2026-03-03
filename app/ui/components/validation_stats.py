from __future__ import annotations

from PySide6 import QtWidgets


class ValidationStatsWidget(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("validationStats")
        self.setStyleSheet(
            "QFrame#validationStats {"
            "background-color: rgba(20, 26, 36, 200);"
            "border-radius: 8px;"
            "padding: 6px;"
            "}"
            "QLabel { color: #EAF2FF; }"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._accuracy_label = QtWidgets.QLabel("Session Accuracy: 0.0%")
        self._count_label = QtWidgets.QLabel("0 verified measurements today.")
        layout.addWidget(self._accuracy_label)
        layout.addWidget(self._count_label)

    def set_stats(self, accuracy: float, measurement_count: int) -> None:
        self._accuracy_label.setText(f"Session Accuracy: {accuracy * 100:.1f}%")
        self._count_label.setText(f"{measurement_count} verified measurements today.")
