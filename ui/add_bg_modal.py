"""
ShiftDrop - Interactive Add Background (Beautifier) Modal
Renders source image centered on top of macOS-style vibrant mesh/linear gradients
or solid colors with rounded corners, drop shadows, and aspect ratio presets.
"""

import os
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QSlider, QColorDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QImage,
    QLinearGradient, QFont, QPainterPath
)

from core.image_processor import add_background, hex_to_rgb


class BgPreviewCanvas(QWidget):
    """
    Live canvas rendering preview of background + shadow + rounded inner image.
    """
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.orig_pixmap = QPixmap(image_path)
        self.orig_w = max(1, self.orig_pixmap.width())
        self.orig_h = max(1, self.orig_pixmap.height())

        self.setMinimumSize(450, 320)

        # Style parameters
        self.bg_mode = "gradient"  # "gradient", "mesh", "solid"
        self.bg_colors = ["#FF5E3A", "#FF2A68"]
        self.padding_val = 60
        self.rounded_val = 24
        self.shadow_val = 35
        self.ratio_preset = "Auto"

    def update_params(
        self,
        bg_mode: str,
        bg_colors: List[str],
        padding: int,
        rounded: int,
        shadow: int,
        ratio: str
    ):
        self.bg_mode = bg_mode
        self.bg_colors = bg_colors
        self.padding_val = padding
        self.rounded_val = rounded
        self.shadow_val = shadow
        self.ratio_preset = ratio
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Total canvas virtual size
        content_w = self.orig_w + self.padding_val * 2
        content_h = self.orig_h + self.padding_val * 2

        v_canvas_w = content_w
        v_canvas_h = content_h

        if self.ratio_preset != "Auto":
            try:
                rw, rh = [float(x) for x in self.ratio_preset.split(":")]
                target_ratio = rw / rh
                curr_ratio = content_w / content_h
                if curr_ratio > target_ratio:
                    v_canvas_w = content_w
                    v_canvas_h = int(content_w / target_ratio)
                else:
                    v_canvas_h = content_h
                    v_canvas_w = int(content_h * target_ratio)
            except Exception:
                pass

        # Scale virtual canvas to fit inside widget viewport
        margin = 15
        avail_w = self.width() - margin * 2
        avail_h = self.height() - margin * 2
        if avail_w <= 0 or avail_h <= 0 or v_canvas_w <= 0 or v_canvas_h <= 0:
            return

        scale = min(avail_w / v_canvas_w, avail_h / v_canvas_h)
        disp_w = v_canvas_w * scale
        disp_h = v_canvas_h * scale
        disp_x = (self.width() - disp_w) / 2
        disp_y = (self.height() - disp_h) / 2
        canvas_rect = QRectF(disp_x, disp_y, disp_w, disp_h)

        # 1. Draw Background
        canvas_path = QPainterPath()
        canvas_path.addRoundedRect(canvas_rect, 12, 12)
        painter.save()
        painter.setClipPath(canvas_path)

        if self.bg_mode == "solid":
            painter.fillRect(canvas_rect, QColor(self.bg_colors[0]))
        else:
            grad = QLinearGradient(canvas_rect.topLeft(), canvas_rect.bottomRight())
            if len(self.bg_colors) == 1:
                grad.setColorAt(0.0, QColor(self.bg_colors[0]))
                grad.setColorAt(1.0, QColor(self.bg_colors[0]))
            elif len(self.bg_colors) == 2:
                grad.setColorAt(0.0, QColor(self.bg_colors[0]))
                grad.setColorAt(1.0, QColor(self.bg_colors[1]))
            else:
                for i, c in enumerate(self.bg_colors):
                    pos = i / (len(self.bg_colors) - 1)
                    grad.setColorAt(pos, QColor(c))
            painter.fillRect(canvas_rect, grad)

        # 2. Inner Image Coordinates
        inner_disp_w = self.orig_w * scale
        inner_disp_h = self.orig_h * scale
        inner_disp_x = disp_x + (disp_w - inner_disp_w) / 2
        inner_disp_y = disp_y + (disp_h - inner_disp_h) / 2
        inner_rect = QRectF(inner_disp_x, inner_disp_y, inner_disp_w, inner_disp_h)

        # 3. Draw Shadow behind inner image
        if self.shadow_val > 0:
            shadow_radius = self.shadow_val * scale
            shadow_offset = max(2.0, shadow_radius / 3.0)
            inner_rounded = self.rounded_val * scale

            for i in range(int(shadow_radius)):
                alpha = int(45 * (1.0 - (i / shadow_radius)))
                shadow_rect = inner_rect.adjusted(-i, -i + shadow_offset, i, i + shadow_offset)
                shadow_path = QPainterPath()
                shadow_path.addRoundedRect(shadow_rect, inner_rounded + i, inner_rounded + i)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, alpha))
                painter.drawPath(shadow_path)

        # 4. Draw Inner Rounded Image
        inner_rounded = self.rounded_val * scale
        img_path = QPainterPath()
        img_path.addRoundedRect(inner_rect, inner_rounded, inner_rounded)
        painter.setClipPath(img_path)
        painter.drawPixmap(inner_rect.toRect(), self.orig_pixmap)

        painter.restore()

        # Canvas Border
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(canvas_rect, 12, 12)


class AddBgModal(QDialog):
    """
    Sleek Add Background (Beautifier) Modal matching macOS / ShiftDrop theme.
    """
    PRESETS = [
        {"name": "Sunset Fire", "mode": "gradient", "colors": ["#FF5E3A", "#FF2A68"]},
        {"name": "Neon Violet", "mode": "gradient", "colors": ["#8A2387", "#E94057", "#F27121"]},
        {"name": "Ocean Deep", "mode": "gradient", "colors": ["#2193B0", "#6DD5ED"]},
        {"name": "Spring Mint", "mode": "gradient", "colors": ["#11998E", "#38EF7D"]},
        {"name": "Midnight Dark", "mode": "gradient", "colors": ["#0F2027", "#203A43", "#2C5364"]},
        {"name": "Peach Candy", "mode": "gradient", "colors": ["#FF9A8B", "#FF6A88", "#FF99AC"]},
        {"name": "Cosmic Night", "mode": "gradient", "colors": ["#141E30", "#243B55"]},
        {"name": "Golden Sun", "mode": "gradient", "colors": ["#F7971E", "#FFD200"]},
        {"name": "Lavender Glow", "mode": "gradient", "colors": ["#7F00FF", "#E100FF"]},
        {"name": "Emerald Pure", "mode": "gradient", "colors": ["#0575E6", "#00F260"]},
        {"name": "Slate Steel", "mode": "gradient", "colors": ["#2C3E50", "#4CA1AF"]},
        {"name": "Dark Obsidian", "mode": "solid", "colors": ["#1A1A1A"]},
        {"name": "Clean White", "mode": "solid", "colors": ["#FFFFFF"]},
    ]

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.result_path = None

        self.current_mode = "gradient"
        self.current_colors = self.PRESETS[0]["colors"]
        self.current_ratio = "Auto"

        self.setWindowTitle("ShiftDrop - Add Background")
        self.setMinimumSize(820, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A20;
                color: #FFFFFF;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #CCC;
                font-size: 13px;
            }
            QPushButton {
                background-color: #282832;
                color: #EEE;
                border: 1px solid #444;
                border-radius: 14px;
                padding: 6px 14px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #383846;
                border-color: #FF7800;
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
                background-color: #282832;
                color: #FFF;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #333340;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #FF7800;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #FF7800;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #FFD4AA;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Add Background Beautifier")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Canvas Preview
        self.canvas = BgPreviewCanvas(self.image_path, self)
        layout.addWidget(self.canvas, 1)

        # Controls Container
        controls = QVBoxLayout()
        controls.setSpacing(12)

        # 1. Swatch Selector Row
        swatch_layout = QHBoxLayout()
        swatch_layout.addWidget(QLabel("Background:"))

        for p in self.PRESETS:
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setToolTip(p["name"])
            if p["mode"] == "solid":
                btn.setStyleSheet(f"background-color: {p['colors'][0]}; border-radius: 13px; border: 2px solid #555;")
            else:
                c1, c2 = p["colors"][0], p["colors"][-1]
                btn.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c1}, stop:1 {c2}); border-radius: 13px; border: 2px solid #555;")
            btn.clicked.connect(lambda checked, preset=p: self._select_preset(preset))
            swatch_layout.addWidget(btn)

        # Custom Color Picker button
        custom_btn = QPushButton("🎨")
        custom_btn.setFixedSize(28, 28)
        custom_btn.setToolTip("Custom Color...")
        custom_btn.clicked.connect(self._pick_custom_color)
        swatch_layout.addWidget(custom_btn)
        swatch_layout.addStretch()
        controls.addLayout(swatch_layout)

        # 2. Sliders Row (Padding, Rounded, Shadow)
        slider_grid = QVBoxLayout()
        slider_grid.setSpacing(8)

        # Padding
        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("Padding:"), 1)
        self.pad_slider = QSlider(Qt.Orientation.Horizontal)
        self.pad_slider.setRange(0, 300)
        self.pad_slider.setValue(60)
        self.pad_slider.valueChanged.connect(self._sync_canvas)
        p_row.addWidget(self.pad_slider, 6)
        self.pad_val_lbl = QLabel("60 px")
        self.pad_val_lbl.setFixedWidth(55)
        p_row.addWidget(self.pad_val_lbl)
        slider_grid.addLayout(p_row)

        # Rounded Corners
        r_row = QHBoxLayout()
        r_row.addWidget(QLabel("Rounded:"), 1)
        self.round_slider = QSlider(Qt.Orientation.Horizontal)
        self.round_slider.setRange(0, 100)
        self.round_slider.setValue(24)
        self.round_slider.valueChanged.connect(self._sync_canvas)
        r_row.addWidget(self.round_slider, 6)
        self.round_val_lbl = QLabel("24 px")
        self.round_val_lbl.setFixedWidth(55)
        r_row.addWidget(self.round_val_lbl)
        slider_grid.addLayout(r_row)

        # Shadow
        s_row = QHBoxLayout()
        s_row.addWidget(QLabel("Shadow:"), 1)
        self.shadow_slider = QSlider(Qt.Orientation.Horizontal)
        self.shadow_slider.setRange(0, 100)
        self.shadow_slider.setValue(35)
        self.shadow_slider.valueChanged.connect(self._sync_canvas)
        s_row.addWidget(self.shadow_slider, 6)
        self.shadow_val_lbl = QLabel("35 px")
        self.shadow_val_lbl.setFixedWidth(55)
        s_row.addWidget(self.shadow_val_lbl)
        slider_grid.addLayout(s_row)

        controls.addLayout(slider_grid)

        # 3. Ratio Presets & Action Buttons
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Ratio:"))

        self.ratio_buttons = {}
        ratios = ["Auto", "1:1", "16:9", "4:3"]
        for r in ratios:
            btn = QPushButton(r)
            if r == "Auto":
                btn.setStyleSheet("background-color: #FF7800; color: white; font-weight: bold;")
            btn.clicked.connect(lambda checked, ratio=r, b=btn: self._select_ratio(ratio, b))
            self.ratio_buttons[r] = btn
            bottom_row.addWidget(btn)

        bottom_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save with Background")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        bottom_row.addWidget(save_btn)

        controls.addLayout(bottom_row)
        layout.addLayout(controls)

        self._sync_canvas()

    def _select_preset(self, preset: dict):
        self.current_mode = preset["mode"]
        self.current_colors = preset["colors"]
        self._sync_canvas()

    def _pick_custom_color(self):
        col = QColorDialog.getColor(QColor(self.current_colors[0]), self, "Pick Background Color")
        if col.isValid():
            self.current_mode = "solid"
            self.current_colors = [col.name()]
            self._sync_canvas()

    def _select_ratio(self, ratio: str, clicked_btn: QPushButton):
        for btn in self.ratio_buttons.values():
            btn.setStyleSheet("")
        clicked_btn.setStyleSheet("background-color: #FF7800; color: white; font-weight: bold;")
        self.current_ratio = ratio
        self._sync_canvas()

    def _sync_canvas(self):
        pad = self.pad_slider.value()
        rnd = self.round_slider.value()
        shd = self.shadow_slider.value()

        self.pad_val_lbl.setText(f"{pad} px")
        self.round_val_lbl.setText(f"{rnd} px")
        self.shadow_val_lbl.setText(f"{shd} px")

        self.canvas.update_params(
            self.current_mode,
            self.current_colors,
            pad,
            rnd,
            shd,
            self.current_ratio
        )

    def _on_save(self):
        pad = self.pad_slider.value()
        rnd = self.round_slider.value()
        shd = self.shadow_slider.value()

        self.result_path = add_background(
            source_path=self.image_path,
            bg_mode=self.current_mode,
            bg_colors=self.current_colors,
            padding=pad,
            corner_radius=rnd,
            shadow_blur=shd,
            shadow_opacity=0.45,
            target_ratio=self.current_ratio
        )
        self.accept()
