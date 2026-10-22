"""
ShiftDrop - Interactive Crop Image Modal
Allows visual cropping with 8 draggable handles, aspect ratio presets,
rule-of-thirds grid, and manual pixel dimension inputs.
"""

import os
from typing import Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QSpinBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QImage, QCursor, QFont
)

from core.image_processor import crop_image


class CropCanvas(QWidget):
    """
    Interactive image view with draggable crop overlay and 8 resize handles.
    """
    crop_changed = pyqtSignal(int, int)  # Emits (crop_pixel_w, crop_pixel_h)

    HANDLE_SIZE = 10
    HANDLE_HIT_RADIUS = 14

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.pixmap = QPixmap(image_path)
        self.orig_w = self.pixmap.width()
        self.orig_h = self.pixmap.height()

        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)

        # Normalized crop rect in [0, 1] relative to the image
        self.norm_crop = QRectF(0.1, 0.1, 0.8, 0.8)
        self.active_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None
        self.aspect_ratio: Optional[float] = None  # None for 'Free'

    def set_aspect_ratio(self, ratio: Optional[float]):
        """Set enforced aspect ratio (width / height) or None for Free."""
        self.aspect_ratio = ratio
        if ratio is not None:
            # Adjust current crop to fit ratio
            cx = self.norm_crop.center().x()
            cy = self.norm_crop.center().y()
            current_pixel_w = self.norm_crop.width() * self.orig_w
            target_pixel_h = current_pixel_w / ratio
            target_norm_h = target_pixel_h / self.orig_h

            if target_norm_h > 1.0:
                target_norm_h = 0.9
                target_pixel_w = (target_norm_h * self.orig_h) * ratio
                target_norm_w = target_pixel_w / self.orig_w
            else:
                target_norm_w = self.norm_crop.width()

            # Center adjusted rect
            new_left = max(0.0, min(1.0 - target_norm_w, cx - target_norm_w / 2))
            new_top = max(0.0, min(1.0 - target_norm_h, cy - target_norm_h / 2))
            self.norm_crop = QRectF(new_left, new_top, target_norm_w, target_norm_h)

        self.update()
        self._emit_crop_dimensions()

    def set_crop_dimensions(self, width: int, height: int):
        """Set crop rect from manual pixel input."""
        norm_w = max(0.02, min(1.0, width / self.orig_w))
        norm_h = max(0.02, min(1.0, height / self.orig_h))
        cx = self.norm_crop.center().x()
        cy = self.norm_crop.center().y()

        new_l = max(0.0, min(1.0 - norm_w, cx - norm_w / 2))
        new_t = max(0.0, min(1.0 - norm_h, cy - norm_h / 2))
        self.norm_crop = QRectF(new_l, new_t, norm_w, norm_h)
        self.update()

    def get_image_display_rect(self) -> QRectF:
        """Calculate rect where the pixmap is displayed maintaining aspect ratio."""
        avail_w = self.width() - 20
        avail_h = self.height() - 20
        if avail_w <= 0 or avail_h <= 0 or self.orig_w == 0 or self.orig_h == 0:
            return QRectF(0, 0, 0, 0)

        scale = min(avail_w / self.orig_w, avail_h / self.orig_h)
        disp_w = self.orig_w * scale
        disp_h = self.orig_h * scale
        disp_x = (self.width() - disp_w) / 2
        disp_y = (self.height() - disp_h) / 2
        return QRectF(disp_x, disp_y, disp_w, disp_h)

    def crop_screen_rect(self) -> QRectF:
        """Get the screen coordinates QRectF of the crop box."""
        img_rect = self.get_image_display_rect()
        return QRectF(
            img_rect.x() + self.norm_crop.x() * img_rect.width(),
            img_rect.y() + self.norm_crop.y() * img_rect.height(),
            self.norm_crop.width() * img_rect.width(),
            self.norm_crop.height() * img_rect.height()
        )

    def get_pixel_crop_box(self) -> Tuple[int, int, int, int]:
        """Convert normalized crop to source image pixel coordinates (L, T, R, B)."""
        left = int(self.norm_crop.x() * self.orig_w)
        top = int(self.norm_crop.y() * self.orig_h)
        right = int((self.norm_crop.x() + self.norm_crop.width()) * self.orig_w)
        bottom = int((self.norm_crop.y() + self.norm_crop.height()) * self.orig_h)
        return left, top, right, bottom

    def _emit_crop_dimensions(self):
        l, t, r, b = self.get_pixel_crop_box()
        self.crop_changed.emit(max(1, r - l), max(1, b - t))

    def get_handles(self, rect: QRectF) -> dict:
        """Return coordinates of the 8 resize handles."""
        return {
            "tl": QPointF(rect.left(), rect.top()),
            "t": QPointF(rect.center().x(), rect.top()),
            "tr": QPointF(rect.right(), rect.top()),
            "r": QPointF(rect.right(), rect.center().y()),
            "br": QPointF(rect.right(), rect.bottom()),
            "b": QPointF(rect.center().x(), rect.bottom()),
            "bl": QPointF(rect.left(), rect.bottom()),
            "l": QPointF(rect.left(), rect.center().y()),
        }

    def hit_test_handle(self, pos: QPointF) -> Optional[str]:
        rect = self.crop_screen_rect()
        handles = self.get_handles(rect)
        for name, pt in handles.items():
            if (pos - pt).manhattanLength() <= self.HANDLE_HIT_RADIUS:
                return name
        if rect.contains(pos):
            return "inside"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.active_handle = self.hit_test_handle(pos)
            self.drag_start_pos = pos
            self.drag_start_rect = QRectF(self.norm_crop)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if not event.buttons() & Qt.MouseButton.LeftButton:
            # Update cursor based on hovered handle
            handle = self.hit_test_handle(pos)
            cursors = {
                "tl": Qt.CursorShape.SizeFDiagCursor,
                "br": Qt.CursorShape.SizeFDiagCursor,
                "tr": Qt.CursorShape.SizeBDiagCursor,
                "bl": Qt.CursorShape.SizeBDiagCursor,
                "t": Qt.CursorShape.SizeVerCursor,
                "b": Qt.CursorShape.SizeVerCursor,
                "l": Qt.CursorShape.SizeHorCursor,
                "r": Qt.CursorShape.SizeHorCursor,
                "inside": Qt.CursorShape.SizeAllCursor,
            }
            self.setCursor(cursors.get(handle, Qt.CursorShape.ArrowCursor))
            return

        if not self.active_handle or not self.drag_start_pos or not self.drag_start_rect:
            return

        img_rect = self.get_image_display_rect()
        if img_rect.width() <= 0 or img_rect.height() <= 0:
            return

        dx_norm = (pos.x() - self.drag_start_pos.x()) / img_rect.width()
        dy_norm = (pos.y() - self.drag_start_pos.y()) / img_rect.height()

        sr = self.drag_start_rect
        nl, nt, nr, nb = sr.left(), sr.top(), sr.right(), sr.bottom()

        if self.active_handle == "inside":
            # Translate crop rect
            w = sr.width()
            h = sr.height()
            nl = max(0.0, min(1.0 - w, sr.left() + dx_norm))
            nt = max(0.0, min(1.0 - h, sr.top() + dy_norm))
            nr = nl + w
            nb = nt + h
        else:
            # Handle resizing
            if "l" in self.active_handle:
                nl = max(0.0, min(nr - 0.05, sr.left() + dx_norm))
            if "r" in self.active_handle:
                nr = min(1.0, max(nl + 0.05, sr.right() + dx_norm))
            if "t" in self.active_handle:
                nt = max(0.0, min(nb - 0.05, sr.top() + dy_norm))
            if "b" in self.active_handle:
                nb = min(1.0, max(nt + 0.05, sr.bottom() + dy_norm))

            # Maintain aspect ratio if set
            if self.aspect_ratio:
                new_pw = (nr - nl) * self.orig_w
                new_ph = (nb - nt) * self.orig_h
                if self.active_handle in ("l", "r"):
                    target_ph = new_pw / self.aspect_ratio
                    nb = min(1.0, nt + target_ph / self.orig_h)
                else:
                    target_pw = new_ph * self.aspect_ratio
                    nr = min(1.0, nl + target_pw / self.orig_w)

        self.norm_crop = QRectF(nl, nt, nr - nl, nb - nt)
        self.update()
        self._emit_crop_dimensions()

    def mouseReleaseEvent(self, event):
        self.active_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        img_rect = self.get_image_display_rect()
        if img_rect.width() <= 0:
            return

        # 1. Draw base image
        painter.drawPixmap(img_rect.toRect(), self.pixmap)

        # 2. Dim background outside crop rect
        crop_rect = self.crop_screen_rect()
        dim_color = QColor(0, 0, 0, 140)

        # Top
        painter.fillRect(QRectF(img_rect.left(), img_rect.top(), img_rect.width(), crop_rect.top() - img_rect.top()).toRect(), dim_color)
        # Bottom
        painter.fillRect(QRectF(img_rect.left(), crop_rect.bottom(), img_rect.width(), img_rect.bottom() - crop_rect.bottom()).toRect(), dim_color)
        # Left
        painter.fillRect(QRectF(img_rect.left(), crop_rect.top(), crop_rect.left() - img_rect.left(), crop_rect.height()).toRect(), dim_color)
        # Right
        painter.fillRect(QRectF(crop_rect.right(), crop_rect.top(), img_rect.right() - crop_rect.right(), crop_rect.height()).toRect(), dim_color)

        # 3. Rule of Thirds grid lines
        grid_pen = QPen(QColor(255, 255, 255, 90), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        third_w = crop_rect.width() / 3.0
        third_h = crop_rect.height() / 3.0
        painter.drawLine(QPointF(crop_rect.left() + third_w, crop_rect.top()), QPointF(crop_rect.left() + third_w, crop_rect.bottom()))
        painter.drawLine(QPointF(crop_rect.left() + third_w * 2, crop_rect.top()), QPointF(crop_rect.left() + third_w * 2, crop_rect.bottom()))
        painter.drawLine(QPointF(crop_rect.left(), crop_rect.top() + third_h), QPointF(crop_rect.right(), crop_rect.top() + third_h))
        painter.drawLine(QPointF(crop_rect.left(), crop_rect.top() + third_h * 2), QPointF(crop_rect.right(), crop_rect.top() + third_h * 2))

        # 4. Orange Crop Border
        orange_pen = QPen(QColor(255, 120, 0), 2)
        painter.setPen(orange_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(crop_rect)

        # 5. Draw 8 Handles
        handles = self.get_handles(crop_rect)
        handle_half = self.HANDLE_SIZE / 2.0
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.setBrush(QBrush(QColor(255, 120, 0)))

        for pt in handles.values():
            painter.drawRoundedRect(
                QRectF(pt.x() - handle_half, pt.y() - handle_half, self.HANDLE_SIZE, self.HANDLE_SIZE),
                2, 2
            )


class CropModal(QDialog):
    """
    Sleek modern Crop modal with aspect ratio pills and manual dimension controls.
    """
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.result_path = None

        self.setWindowTitle("ShiftDrop - Crop Image")
        self.setMinimumSize(780, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E24;
                color: #FFFFFF;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #DDD;
                font-size: 13px;
            }
            QPushButton {
                background-color: #2D2D36;
                color: #EEE;
                border: 1px solid #444;
                border-radius: 14px;
                padding: 6px 14px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3C3C48;
                border-color: #FF7800;
            }
            QPushButton.active-pill {
                background-color: #FF7800;
                color: #FFFFFF;
                border-color: #FF9433;
                font-weight: bold;
            }
            QPushButton#primaryBtn {
                background-color: #FF7800;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#primaryBtn:hover {
                background-color: #FF9020;
            }
            QPushButton#cancelBtn {
                background-color: transparent;
                border: 1px solid #555;
                color: #BBB;
                border-radius: 8px;
                padding: 8px 18px;
            }
            QPushButton#cancelBtn:hover {
                background-color: #2D2D36;
                color: #FFF;
            }
            QSpinBox {
                background-color: #2A2A33;
                color: #FFF;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title Header
        header = QHBoxLayout()
        title = QLabel("Crop Image")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Interactive Canvas
        self.canvas = CropCanvas(self.image_path, self)
        layout.addWidget(self.canvas, 1)

        # Controls Bar
        controls = QVBoxLayout()
        controls.setSpacing(12)

        # Row 1: Aspect Ratio Presets
        ratio_row = QHBoxLayout()
        ratio_lbl = QLabel("Aspect ratio:")
        ratio_lbl.setStyleSheet("font-weight: bold; color: #AAA;")
        ratio_row.addWidget(ratio_lbl)

        self.ratio_buttons = {}
        ratios = [
            ("Free", None),
            ("1:1", 1.0),
            ("16:9", 16.0 / 9.0),
            ("9:16", 9.0 / 16.0),
            ("4:3", 4.0 / 3.0),
            ("3:4", 3.0 / 4.0),
        ]
        for label, val in ratios:
            btn = QPushButton(label)
            btn.setCheckable(True)
            if label == "Free":
                btn.setChecked(True)
                btn.setProperty("class", "active-pill")
            btn.clicked.connect(lambda checked, v=val, b=btn: self._on_ratio_clicked(v, b))
            self.ratio_buttons[label] = btn
            ratio_row.addWidget(btn)

        ratio_row.addStretch()

        # Dimension Inputs
        ratio_row.addWidget(QLabel("W:"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(10, 10000)
        self.spin_w.setValue(int(self.canvas.orig_w * 0.8))
        self.spin_w.valueChanged.connect(self._on_manual_dimension_changed)
        ratio_row.addWidget(self.spin_w)

        ratio_row.addWidget(QLabel("H:"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(10, 10000)
        self.spin_h.setValue(int(self.canvas.orig_h * 0.8))
        self.spin_h.valueChanged.connect(self._on_manual_dimension_changed)
        ratio_row.addWidget(self.spin_h)
        ratio_row.addWidget(QLabel("px"))

        controls.addLayout(ratio_row)

        # Row 2: Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("primaryBtn")
        apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(apply_btn)

        controls.addLayout(btn_row)
        layout.addLayout(controls)

        # Connect canvas dimension changes to spinboxes
        self.canvas.crop_changed.connect(self._update_spinboxes)
        self.canvas._emit_crop_dimensions()

    def _on_ratio_clicked(self, ratio_val: Optional[float], clicked_btn: QPushButton):
        for btn in self.ratio_buttons.values():
            btn.setChecked(False)
            btn.setStyleSheet("")
        clicked_btn.setChecked(True)
        clicked_btn.setStyleSheet("background-color: #FF7800; color: white; font-weight: bold;")
        self.canvas.set_aspect_ratio(ratio_val)

    def _update_spinboxes(self, w: int, h: int):
        self.spin_w.blockSignals(True)
        self.spin_h.blockSignals(True)
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)
        self.spin_w.blockSignals(False)
        self.spin_h.blockSignals(False)

    def _on_manual_dimension_changed(self):
        w = self.spin_w.value()
        h = self.spin_h.value()
        self.canvas.set_crop_dimensions(w, h)

    def _on_apply(self):
        crop_box = self.canvas.get_pixel_crop_box()
        self.result_path = crop_image(self.image_path, crop_box)
        self.accept()

