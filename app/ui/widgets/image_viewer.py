from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from PySide6 import QtCore, QtGui, QtWidgets, QtOpenGLWidgets

from app.models.types import OverlayBox
from app.utils.image import qimage_from_array


@dataclass(frozen=True)
class OverlayStyle:
    box_color: QtGui.QColor = field(default_factory=lambda: QtGui.QColor("#00A2FF"))
    text_color: QtGui.QColor = field(default_factory=lambda: QtGui.QColor("#FFFFFF"))
    text_bg: QtGui.QColor = field(default_factory=lambda: QtGui.QColor(0, 0, 0, 160))
    line_width: int = 2
    font: QtGui.QFont = field(default_factory=lambda: QtGui.QFont("Segoe UI", 9))


class ImageViewer(QtWidgets.QGraphicsView):
    """
    Advanced image viewer with:
    - zoom (wheel)
    - pan (drag with left mouse)
    - overlays (boxes + labels)
    - hover HUD (frame index + zoom)
    """

    viewChanged = QtCore.Signal(float)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, use_opengl: bool = False) -> None:
        super().__init__(parent)
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self._overlay_items: List[QtWidgets.QGraphicsItem] = []
        self._hover_text = QtWidgets.QGraphicsSimpleTextItem("")
        self._hover_text.setZValue(10)
        self._scene.addItem(self._hover_text)

        self._overlay_style = OverlayStyle()
        self._frame_index: Optional[int] = None
        self._frame_count: Optional[int] = None

        self._empty_text = QtWidgets.QGraphicsSimpleTextItem(
            "No DICOM loaded\nOpen a folder or select a DICOM file"
        )
        self._empty_text.setBrush(QtGui.QBrush(QtGui.QColor("#8A9199")))
        self._empty_text.setZValue(5)
        font = QtGui.QFont("Segoe UI", 12)
        self._empty_text.setFont(font)
        self._scene.addItem(self._empty_text)
        self._center_empty_text()

        self.setBackgroundBrush(QtGui.QColor("#FAFAFA"))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setRenderHints(
            QtGui.QPainter.Antialiasing
            | QtGui.QPainter.SmoothPixmapTransform
            | QtGui.QPainter.TextAntialiasing
        )

        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self._panning = False
        self._last_mouse_pos: Optional[QtCore.QPoint] = None

        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 8.0

        self.setMouseTracking(True)
        self._use_opengl = False
        self.set_opengl_enabled(use_opengl)
        self._update_hover_hud()

    def set_image(self, image: QtGui.QImage) -> None:
        pixmap = QtGui.QPixmap.fromImage(image)
        self._pixmap_item.setPixmap(pixmap)
        self._empty_text.setVisible(False)
        self._fit_image()
        self._update_hover_hud()

    def set_image_from_array(self, array) -> None:
        image = qimage_from_array(array)
        self.set_image(image)

    def set_empty(self, text: Optional[str] = None) -> None:
        self._pixmap_item.setPixmap(QtGui.QPixmap())
        self._empty_text.setVisible(True)
        if text:
            self._empty_text.setText(text)
        self._center_empty_text()
        self._update_hover_hud()

    def set_overlay_boxes(self, boxes: Sequence[OverlayBox]) -> None:
        self._clear_overlays()
        for box in boxes:
            self._add_box(box)
        self._scene.update()

    def clear_overlays(self) -> None:
        self._clear_overlays()

    def set_frame_info(self, index: Optional[int], total: Optional[int]) -> None:
        self._frame_index = index
        self._frame_count = total
        self._update_hover_hud()

    def set_overlay_style(self, style: OverlayStyle) -> None:
        self._overlay_style = style

    def set_zoom_limits(self, min_zoom: float, max_zoom: float) -> None:
        self._min_zoom = min_zoom
        self._max_zoom = max_zoom

    def zoom_to_fit(self) -> None:
        self._fit_image()

    def zoom(self, factor: float) -> None:
        target = self._zoom * factor
        self._set_zoom(target)

    def set_zoom(self, value: float) -> None:
        self._set_zoom(value)

    def set_opengl_enabled(self, enabled: bool) -> None:
        if enabled == self._use_opengl:
            return
        self._use_opengl = enabled
        if enabled:
            self.setViewport(QtOpenGLWidgets.QOpenGLWidget())
        else:
            self.setViewport(QtWidgets.QWidget())
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._center_empty_text()
        self._update_hover_hud()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._set_zoom(self._zoom * factor, anchor=event.position().toPoint())

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._panning and self._last_mouse_pos is not None:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._panning = False
            self._last_mouse_pos = None
            self.setCursor(QtCore.Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def _fit_image(self) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        self.fitInView(self._pixmap_item.boundingRect(), QtCore.Qt.KeepAspectRatio)
        self._zoom = 1.0
        self.viewChanged.emit(self._zoom)
        self._update_hover_hud()

    def _set_zoom(self, value: float, anchor: Optional[QtCore.QPoint] = None) -> None:
        value = max(self._min_zoom, min(self._max_zoom, value))
        if value == self._zoom:
            return
        if anchor is not None:
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        else:
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)

        factor = value / self._zoom
        self._zoom = value
        self.scale(factor, factor)

        self.viewChanged.emit(self._zoom)
        self._update_hover_hud()

    def _add_box(self, box: OverlayBox) -> None:
        rect_item = QtWidgets.QGraphicsRectItem(
            box.x, box.y, box.width, box.height
        )
        pen = QtGui.QPen(QtGui.QColor(box.color))
        pen.setWidth(self._overlay_style.line_width)
        rect_item.setPen(pen)
        rect_item.setZValue(5)
        self._scene.addItem(rect_item)
        self._overlay_items.append(rect_item)

        label = box.label or ""
        if box.confidence is not None:
            label = f"{label} ({box.confidence:.2f})" if label else f"{box.confidence:.2f}"
        if label:
            text_item = QtWidgets.QGraphicsSimpleTextItem(label)
            text_item.setBrush(QtGui.QBrush(self._overlay_style.text_color))
            text_item.setFont(self._overlay_style.font)
            text_item.setZValue(6)
            text_item.setPos(box.x, box.y - 18)
            bg = QtWidgets.QGraphicsRectItem(text_item.boundingRect())
            bg.setBrush(QtGui.QBrush(self._overlay_style.text_bg))
            bg.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            bg.setZValue(5.5)
            bg.setPos(text_item.pos())
            self._scene.addItem(bg)
            self._scene.addItem(text_item)
            self._overlay_items.extend([bg, text_item])

    def _clear_overlays(self) -> None:
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

    def _center_empty_text(self) -> None:
        rect = self._empty_text.boundingRect()
        center = self.viewport().rect().center()
        self._empty_text.setPos(
            center.x() - rect.width() / 2,
            center.y() - rect.height() / 2,
        )

    def _update_hover_hud(self) -> None:
        frame_text = ""
        if self._frame_index is not None and self._frame_count is not None:
            frame_text = f"Frame {self._frame_index + 1}/{self._frame_count}"
        zoom_text = f"Zoom {self._zoom:.2f}x"
        text = " | ".join([t for t in (frame_text, zoom_text) if t])

        self._hover_text.setText(text)
        self._hover_text.setBrush(QtGui.QBrush(QtGui.QColor("#5C6773")))
        self._hover_text.setFont(QtGui.QFont("Segoe UI", 9))

        margin = 8
        self._hover_text.setPos(margin, margin)
