from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.widgets.file_browser import FileFilterProxyModel

if TYPE_CHECKING:
    from app.ui.state import ViewerState


class SidebarWidget(QtWidgets.QFrame):
    """Widget managing the file system tree and search."""

    # Emitted when a user double clicks a DICOM file or folder.
    file_selected = QtCore.Signal(Path)
    folder_selected = QtCore.Signal(Path)

    def __init__(self, state: ViewerState) -> None:
        super().__init__()
        self._state = state
        self.setObjectName("leftPanel")
        self.setMinimumWidth(260)

        self._collapsed = False
        self._build_ui()

        self._state.loading_state_changed.connect(self._update_loading_state)

    def _icon(self, name: str) -> QtGui.QIcon:
        base = Path(__file__).resolve().parent.parent / "icons"
        path = base / f"{name}.svg"
        if path.exists():
            return QtGui.QIcon(str(path))
        return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._stack = QtWidgets.QStackedWidget()
        layout.addWidget(self._stack)

        # Full mode
        self._full_widget = QtWidgets.QWidget()
        full_layout = QtWidgets.QVBoxLayout(self._full_widget)
        full_layout.setContentsMargins(0, 0, 0, 0)
        full_layout.setSpacing(8)

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Search DICOM files...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        full_layout.addWidget(self._search)

        self._filter_toggle = QtWidgets.QCheckBox("Show only .dcm")
        self._filter_toggle.setChecked(True)
        self._filter_toggle.stateChanged.connect(self._on_filter_changed)
        full_layout.addWidget(self._filter_toggle)

        self._fs_model = QtWidgets.QFileSystemModel()
        self._fs_model.setFilter(
            QtCore.QDir.Filter.AllEntries
            | QtCore.QDir.Filter.NoDotAndDotDot
            | QtCore.QDir.Filter.AllDirs
        )
        self._fs_model.setRootPath(str(Path.cwd()))

        self._proxy_model = FileFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._fs_model)
        self._proxy_model.set_show_dcm_only(True)

        self._tree = QtWidgets.QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self._tree.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._tree.doubleClicked.connect(self._tree_double_clicked)
        self._tree.setModel(self._proxy_model)
        self._tree.setRootIndex(
            self._proxy_model.mapFromSource(self._fs_model.index(str(Path.cwd())))
        )
        self._tree.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        full_layout.addWidget(self._tree)

        # Slim mode
        self._slim_widget = QtWidgets.QWidget()
        self._slim_widget.setObjectName("sidebarSlim")
        slim_layout = QtWidgets.QVBoxLayout(self._slim_widget)
        slim_layout.setContentsMargins(0, 0, 0, 0)
        slim_layout.setSpacing(8)

        self._btn_slim_expand = QtWidgets.QToolButton()
        self._btn_slim_expand.setIcon(self._icon("sidebar_expand"))
        self._btn_slim_expand.setToolTip("Expand Sidebar")
        self._btn_slim_expand.clicked.connect(lambda: self.set_collapsed(False))
        slim_layout.addWidget(self._btn_slim_expand)

        self._btn_slim_open_file = QtWidgets.QToolButton()
        self._btn_slim_open_file.setIcon(self._icon("open_file"))
        self._btn_slim_open_file.setToolTip("Open File")
        self._btn_slim_open_file.clicked.connect(self._open_file_dialog)
        slim_layout.addWidget(self._btn_slim_open_file)

        self._btn_slim_open_folder = QtWidgets.QToolButton()
        self._btn_slim_open_folder.setIcon(self._icon("open_folder"))
        self._btn_slim_open_folder.setToolTip("Open Folder")
        self._btn_slim_open_folder.clicked.connect(self._open_folder_dialog)
        slim_layout.addWidget(self._btn_slim_open_folder)

        self._btn_slim_filter = QtWidgets.QToolButton()
        self._btn_slim_filter.setIcon(self._icon("filter"))
        self._btn_slim_filter.setToolTip("Toggle .dcm Filter")
        self._btn_slim_filter.setCheckable(True)
        self._btn_slim_filter.setChecked(self._filter_toggle.isChecked())
        self._btn_slim_filter.clicked.connect(self._toggle_filter)
        slim_layout.addWidget(self._btn_slim_filter)
        slim_layout.addStretch(1)

        self._stack.addWidget(self._full_widget)
        self._stack.addWidget(self._slim_widget)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        if collapsed:
            self._stack.setCurrentWidget(self._slim_widget)
            self.setMinimumWidth(56)
            self.setMaximumWidth(56)
        else:
            self._stack.setCurrentWidget(self._full_widget)
            self.setMinimumWidth(260)
            self.setMaximumWidth(16777215)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _on_search_changed(self, text: str) -> None:
        self._proxy_model.set_search_text(text)

    def _on_filter_changed(self) -> None:
        checked = self._filter_toggle.isChecked()
        self._proxy_model.set_show_dcm_only(checked)
        self._btn_slim_filter.blockSignals(True)
        self._btn_slim_filter.setChecked(checked)
        self._btn_slim_filter.blockSignals(False)

    def _toggle_filter(self) -> None:
        self._filter_toggle.setChecked(not self._filter_toggle.isChecked())

    def set_tree_root(self, path: Path) -> None:
        self._fs_model.setRootPath(str(path))
        source_index = self._fs_model.index(str(path))
        self._tree.setRootIndex(self._proxy_model.mapFromSource(source_index))

    def current_root_path(self) -> Path:
        proxy_index = self._tree.rootIndex()
        source_index = self._proxy_model.mapToSource(proxy_index)
        root_text = self._fs_model.filePath(source_index)
        if root_text:
            return Path(root_text)
        return Path.cwd()

    def list_dicom_files(self) -> list[Path]:
        root = self.current_root_path()
        if root.is_file():
            return [root] if root.suffix.lower() == ".dcm" else []
        if not root.is_dir():
            return []
        return sorted(path for path in root.rglob("*.dcm") if path.is_file())

    def _tree_double_clicked(self, index: QtCore.QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(index)
        path = Path(self._fs_model.filePath(source_index))
        if path.is_dir():
            self.set_tree_root(path)
            return
        self.file_selected.emit(path)

    def _tree_path_from_proxy_index(self, proxy_index: QtCore.QModelIndex) -> Path | None:
        if not proxy_index.isValid():
            return None
        source_index = self._proxy_model.mapToSource(proxy_index)
        if not source_index.isValid():
            return None
        raw = self._fs_model.filePath(source_index)
        if not raw:
            return None
        return Path(raw)

    def _on_tree_context_menu(self, pos: QtCore.QPoint) -> None:
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return
        path = self._tree_path_from_proxy_index(index)
        if path is None:
            return

        menu = QtWidgets.QMenu(self)
        action_copy_name = menu.addAction("Copy Filename")
        action_copy_path = menu.addAction("Copy Full Path")

        selected = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if selected is action_copy_name:
            QtWidgets.QApplication.clipboard().setText(path.name)
        elif selected is action_copy_path:
            QtWidgets.QApplication.clipboard().setText(str(path))

    def _open_folder_dialog(self) -> None:
        dialog = QtWidgets.QFileDialog(self, "Select Folder", str(Path.cwd()))
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly, True)
        if dialog.exec() == int(QtWidgets.QDialog.DialogCode.Accepted):
            folder = dialog.selectedFiles()[0]
            self.folder_selected.emit(Path(folder))

    def _open_file_dialog(self) -> None:
        dialog = QtWidgets.QFileDialog(self, "Select DICOM File", str(Path.cwd()))
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("DICOM Files (*.dcm);;All Files (*.*)")
        if dialog.exec() == int(QtWidgets.QDialog.DialogCode.Accepted):
            file_path = dialog.selectedFiles()[0]
            self.file_selected.emit(Path(file_path))

    def _update_loading_state(self, loading: bool, message: str) -> None:
        _ = message
        self._tree.setEnabled(not loading)
        self._filter_toggle.setEnabled(not loading)
        self._search.setEnabled(not loading)
        self._btn_slim_expand.setEnabled(not loading)
        self._btn_slim_open_file.setEnabled(not loading)
        self._btn_slim_open_folder.setEnabled(not loading)
        self._btn_slim_filter.setEnabled(not loading)
