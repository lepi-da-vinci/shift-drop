"""
ShiftDrop - Radial (Pie) Menu Overlay
Frameless, translucent, hardware-accelerated 2D radial menu.
Handles OLE Drag & Drop interception, context-aware modes, and sector hit-testing.
"""

import os
import math
from typing import List, Dict, Optional, Tuple

from PyQt6.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QRadialGradient, QLinearGradient
)

from core.converter_engine import convert_file
from core.image_processor import compress_image, strip_metadata
from ui.crop_modal import CropModal
from ui.add_bg_modal import AddBgModal


class RadialMenuWindow(QWidget):
    """
    Frameless, translucent radial menu positioned directly under the cursor.
    Interprets dropped files and executes actions.
    """
    WINDOW_SIZE = 360
    CENTER_X = 180
    CENTER_Y = 180
    R_INNER = 50
    R_OUTER = 155

    # Signals
    action_completed = pyqtSignal(str, str)  # (action_name, output_file)
    menu_hidden = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WINDOW_SIZE, self.WINDOW_SIZE)

        # Frameless, Always on Top, Tool Window (no taskbar item), Translucent, No Focus Steal
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAcceptDrops(True)

        # File & Mode State
        self.current_file: Optional[str] = None
        self.file_size_text: str = ""
        self.file_ext: str = ""
        self.file_basename: str = ""

        # Modes: 'PDF', 'IMAGE_CONVERT', 'IMAGE_TOOLS'
        self.menu_mode = "IMAGE_CONVERT"
        self.active_sector_index: Optional[int] = None
        self.is_center_hovered = False

        # Sectors Configuration
        self.sectors: List[Dict[str, str]] = []

        # Auto-hide timer if dragEnterEvent doesn't fire within 2500 ms (safety fallback)
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self._on_auto_hide_timeout)
        self._drag_entered = False

    def hideEvent(self, event):
        self.auto_hide_timer.stop()
        self._drag_entered = False
        self.menu_hidden.emit()
        super().hideEvent(event)

    def spawn_at(self, cursor_x: int, cursor_y: int):
        """
        Move window center to cursor coordinates and display it without stealing focus.
        """
        self._drag_entered = False
        target_x = cursor_x - self.CENTER_X
        target_y = cursor_y - self.CENTER_Y
        self.move(target_x, target_y)
        self.active_sector_index = None
        self.is_center_hovered = False

        # Reset sectors to default placeholder until dragEnter identifies file
        self._setup_placeholder_sectors()
        self.show()
        self.raise_()
        self.repaint()

        # Generous 2500ms safety timeout (stops as soon as dragEnter fires)
        self.auto_hide_timer.start(2500)

    def _on_auto_hide_timeout(self):
        if not self._drag_entered:
            self.hide()

    def _setup_placeholder_sectors(self):
        self.sectors = [
            {"label": "CONVERT", "icon": "⚡"},
            {"label": "TOOLS", "icon": "🛠"},
            {"label": "CROP", "icon": "✂"},
            {"label": "ADD BG", "icon": "🎨"},
        ]
        self.file_size_text = ""
        self.file_ext = ""

    def set_file_context(self, file_path: str):
        """
        Analyze dragged file and dynamically populate context-aware radial sectors.
        """
        self.current_file = file_path
        if not os.path.exists(file_path):
            return

        dirname, filename = os.path.split(file_path)
        base, ext = os.path.splitext(filename)
        self.file_basename = base
        self.file_ext = ext.lower().lstrip(".")

        size_bytes = os.path.getsize(file_path)
        if size_bytes >= 1048576:
            self.file_size_text = f"{size_bytes / 1048576:.1f} MB"
        else:
            self.file_size_text = f"{size_bytes / 1024:.0f} KB"

        # Determine Context Mode
        if self.file_ext == "pdf":
            self.menu_mode = "PDF"
            self.sectors = [
                {"label": "DOCX", "icon": "📄"},
                {"label": "JPG", "icon": "🖼"},
                {"label": "PNG", "icon": "✨"},
                {"label": "TXT", "icon": "📝"},
            ]
        else:
            # Default to image conversion mode, can toggle to image tools
            if self.menu_mode not in ("IMAGE_CONVERT", "IMAGE_TOOLS"):
                self.menu_mode = "IMAGE_CONVERT"
            self._update_image_sectors()

        self.update()

    def _update_image_sectors(self):
        if self.menu_mode == "IMAGE_CONVERT":
            self.sectors = [
                {"label": "PNG", "icon": ""},
                {"label": "WEBP", "icon": ""},
                {"label": "HEIC", "icon": ""},
                {"label": "AVIF", "icon": ""},
                {"label": "BMP", "icon": ""},
                {"label": "PDF", "icon": ""},
                {"label": "DOCX", "icon": ""},
                {"label": "TIFF", "icon": ""},
            ]
        else:  # IMAGE_TOOLS
            self.sectors = [
                {"label": "COMPRESS", "icon": "📦"},
                {"label": "METADATA", "icon": "🏷"},
                {"label": "EDIT", "icon": "✏"},
                {"label": "ANNOTATE", "icon": "🖊"},
                {"label": "ADD BG", "icon": "🎨"},
                {"label": "CROP", "icon": "✂"},
                {"label": "REDACT", "icon": "👁"},
            ]

    def toggle_image_mode(self):
        """Toggle between Image Conversion and Image Tools."""
        if self.file_ext != "pdf":
            if self.menu_mode == "IMAGE_CONVERT":
                self.menu_mode = "IMAGE_TOOLS"
            else:
                self.menu_mode = "IMAGE_CONVERT"
            self._update_image_sectors()
            self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Space):
            self.toggle_image_mode()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    # =========================================================================
    # Hit-Testing Mathematics
    # =========================================================================

    def _calculate_hit_sector(self, x: float, y: float) -> Tuple[Optional[int], bool]:
        """
        Given coordinates (x, y), calculates:
        - sector_index (0 to N-1 or None)
        - is_center (True if inside center hub radius)
        """
        dx = x - self.CENTER_X
        dy = y - self.CENTER_Y
        r = math.sqrt(dx * dx + dy * dy)

        if r < self.R_INNER:
            return None, True

        if self.R_INNER <= r <= self.R_OUTER:
            n = len(self.sectors)
            if n == 0:
                return None, False

            # Screen coordinates: dy positive is down.
            # Convert angle to degrees [0, 360)
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360.0

            # Sector 0 is centered at top (270 degrees / -90 degrees).
            sector_span = 360.0 / n
            # Offset angle so sector 0 starts at (270 - sector_span / 2)
            start_angle_0 = (270.0 - sector_span / 2.0) % 360.0
            norm_angle = (angle - start_angle_0) % 360.0
            idx = int(norm_angle // sector_span)
            idx = min(n - 1, max(0, idx))
            return idx, False

        return None, False

    # =========================================================================
    # OLE Drag & Drop Events
    # =========================================================================

    def dragEnterEvent(self, event):
        self._drag_entered = True
        self.auto_hide_timer.stop()

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                local_path = urls[0].toLocalFile()
                if local_path and os.path.exists(local_path):
                    self.set_file_context(local_path)
                    event.setDropAction(Qt.DropAction.CopyAction)
                    event.accept()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        pos = event.position()
        idx, is_center = self._calculate_hit_sector(pos.x(), pos.y())

        need_update = (idx != self.active_sector_index) or (is_center != self.is_center_hovered)
        self.active_sector_index = idx
        self.is_center_hovered = is_center

        if need_update:
            self.update()

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self.active_sector_index = None
        self.is_center_hovered = False
        self.update()
        event.accept()

    def dropEvent(self, event):
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        pos = event.position()
        idx, is_center = self._calculate_hit_sector(pos.x(), pos.y())
        self.hide()

        if is_center and self.file_ext != "pdf":
            # Center drop switches mode
            self.toggle_image_mode()
            return

        if idx is not None and 0 <= idx < len(self.sectors) and self.current_file:
            chosen = self.sectors[idx]["label"]
            self._execute_action(self.current_file, chosen)

    # =========================================================================
    # Action Dispatcher
    # =========================================================================

    def _execute_action(self, file_path: str, action: str):
        """Execute selected conversion or open editor modal."""
        action_up = action.upper().strip()

        try:
            if action_up == "CROP":
                modal = CropModal(file_path)
                if modal.exec() and modal.result_path:
                    self.action_completed.emit("Crop Image", modal.result_path)

            elif action_up == "ADD BG":
                modal = AddBgModal(file_path)
                if modal.exec() and modal.result_path:
                    self.action_completed.emit("Add Background", modal.result_path)

            elif action_up == "COMPRESS":
                out = compress_image(file_path)
                self.action_completed.emit("Compress", out)

            elif action_up == "METADATA":
                out = strip_metadata(file_path)
                self.action_completed.emit("Strip Metadata", out)

            elif action_up in ("EDIT", "ANNOTATE", "REDACT"):
                # Default quick edit fallback opens Crop Modal
                modal = CropModal(file_path)
                if modal.exec() and modal.result_path:
                    self.action_completed.emit(action_up, modal.result_path)

            else:
                # Format conversions (DOCX, JPG, PNG, TXT, WEBP, PDF, BMP, etc.)
                outs = convert_file(file_path, action_up)
                if outs:
                    self.action_completed.emit(f"Convert to {action_up}", outs[0])

        except Exception as e:
            QMessageBox.warning(None, "ShiftDrop Error", f"Operation failed:\n{str(e)}")

    # =========================================================================
    # Custom 2D Rendering
    # =========================================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 0. Solid hit-target layer (alpha=1, completely invisible to human eye, but ensures
        # Windows DWM and OLE hit-testing treats the entire radial region as a valid drop target)
        hit_rect = QRectF(
            self.CENTER_X - self.R_OUTER - 10,
            self.CENTER_Y - self.R_OUTER - 10,
            (self.R_OUTER + 10) * 2,
            (self.R_OUTER + 10) * 2
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 1))
        painter.drawEllipse(hit_rect)

        n = len(self.sectors)
        if n == 0:
            return

        sector_span = 360.0 / n
        start_angle_0 = (270.0 - sector_span / 2.0) % 360.0
        gap_deg = 2.5  # Gap between sectors for petal glass look

        # 1. Outer Ring Drop Shadow
        shadow_rect = QRectF(
            self.CENTER_X - self.R_OUTER - 4,
            self.CENTER_Y - self.R_OUTER - 4,
            (self.R_OUTER + 4) * 2,
            (self.R_OUTER + 4) * 2
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 35))
        painter.drawEllipse(shadow_rect)

        # 2. Draw Sectors
        for i, sector in enumerate(self.sectors):
            is_active = (i == self.active_sector_index)
            r_out = self.R_OUTER + (6 if is_active else 0)
            r_in = self.R_INNER

            # Angular span with spacing
            ang_start = start_angle_0 + i * sector_span + (gap_deg / 2.0)
            ang_sweep = sector_span - gap_deg

            path = QPainterPath()
            outer_rect = QRectF(self.CENTER_X - r_out, self.CENTER_Y - r_out, r_out * 2, r_out * 2)
            inner_rect = QRectF(self.CENTER_X - r_in, self.CENTER_Y - r_in, r_in * 2, r_in * 2)

            # Draw donut sector segment: outer arc, line to inner arc, inner arc backwards, close
            path.arcMoveTo(outer_rect, -ang_start)
            path.arcTo(outer_rect, -ang_start, -ang_sweep)
            path.arcTo(inner_rect, -(ang_start + ang_sweep), ang_sweep)
            path.closeSubpath()

            # Styling
            if is_active:
                # Active amber/orange glow
                fill_color = QColor(255, 120, 20, 240)
                border_color = QColor(255, 200, 140, 255)
                text_color = QColor(255, 255, 255)
                border_width = 2.0
            else:
                # Translucent cream/frosted glass
                fill_color = QColor(255, 250, 245, 215)
                border_color = QColor(255, 255, 255, 140)
                text_color = QColor(35, 35, 40)
                border_width = 1.0

            painter.setPen(QPen(border_color, border_width))
            painter.setBrush(QBrush(fill_color))
            painter.drawPath(path)

            # Draw Sector Label & Icon
            mid_angle_deg = ang_start + ang_sweep / 2.0
            mid_rad = math.radians(mid_angle_deg)
            label_r = (r_in + r_out) / 2.0
            label_x = self.CENTER_X + label_r * math.cos(mid_rad)
            label_y = self.CENTER_Y + label_r * math.sin(mid_rad)

            painter.setPen(text_color)
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

            lbl_text = sector["label"]
            icon_text = sector.get("icon", "")
            full_text = f"{icon_text} {lbl_text}".strip() if icon_text else lbl_text

            text_rect = QRectF(label_x - 45, label_y - 12, 90, 24)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, full_text)

        # 3. Center Hub (File Icon, Size Badge, Mode Indicator)
        center_rect = QRectF(
            self.CENTER_X - self.R_INNER + 2,
            self.CENTER_Y - self.R_INNER + 2,
            (self.R_INNER - 2) * 2,
            (self.R_INNER - 2) * 2
        )

        # Center gradient
        center_grad = QRadialGradient(QPointF(self.CENTER_X, self.CENTER_Y), self.R_INNER)
        if self.is_center_hovered:
            center_grad.setColorAt(0.0, QColor(255, 160, 60, 255))
            center_grad.setColorAt(1.0, QColor(255, 100, 10, 255))
            rim_color = QColor(255, 220, 180, 255)
        else:
            center_grad.setColorAt(0.0, QColor(255, 140, 25, 245))
            center_grad.setColorAt(1.0, QColor(230, 90, 10, 245))
            rim_color = QColor(255, 180, 120, 200)

        painter.setPen(QPen(rim_color, 2.5))
        painter.setBrush(QBrush(center_grad))
        painter.drawEllipse(center_rect)

        # File Icon / Extension in Center
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        center_label = self.file_ext.upper() if self.file_ext else "DROP"
        painter.drawText(
            QRectF(self.CENTER_X - 40, self.CENTER_Y - 24, 80, 20),
            Qt.AlignmentFlag.AlignCenter,
            center_label
        )

        # File Size Pill Badge
        if self.file_size_text:
            badge_rect = QRectF(self.CENTER_X - 30, self.CENTER_Y - 2, 60, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 70))
            painter.drawRoundedRect(badge_rect, 8, 8)

            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.file_size_text)

        # Mode hint (Tab / Space toggle)
        if self.file_ext != "pdf":
            hint_text = "CONVERT" if self.menu_mode == "IMAGE_CONVERT" else "TOOLS"
            painter.setPen(QColor(255, 255, 255, 190))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(
                QRectF(self.CENTER_X - 40, self.CENTER_Y + 16, 80, 14),
                Qt.AlignmentFlag.AlignCenter,
                hint_text
            )

