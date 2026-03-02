from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets


class FileFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._search_text = ""
        self._show_dcm_only = True

    def set_search_text(self, text: str) -> None:
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def set_show_dcm_only(self, value: bool) -> None:
        self._show_dcm_only = value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        model = self.sourceModel()
        if not isinstance(model, QtWidgets.QFileSystemModel):
            return True

        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        path = Path(model.filePath(index))
        if path.is_dir():
            return True

        if self._show_dcm_only and path.suffix.lower() != ".dcm":
            return False

        if self._search_text and self._search_text not in path.name.lower():
            return False

        return True
