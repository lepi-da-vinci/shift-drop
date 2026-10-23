"""
ShiftDrop - Main Application Entry Point
Initializes the PyQt6 Application, System Tray, Global Drag+Shift Detector,
and Radial Menu Overlay.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

from core.drag_detector import DragDetectorThread, get_current_cursor_pos
from ui.radial_menu import RadialMenuWindow


def create_tray_icon() -> QIcon:
    """Generate a sleek programmatic tray icon (amber orange rounded circle)."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Orange circular badge
    painter.setBrush(QColor(255, 120, 0))
    painter.setPen(QColor(255, 255, 255, 200))
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)

    # Letter 'S'
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()

    return QIcon(pixmap)


class ShiftDropApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # High DPI scaling
        if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough"):
            self.app.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )

        # 1. Initialize UI Radial Window
        self.radial_menu = RadialMenuWindow()
        self.radial_menu.action_completed.connect(self._on_action_completed)
        self.radial_menu.menu_hidden.connect(self._on_menu_hidden)

        # 2. Initialize Background Drag Detector Thread
        self.detector_thread = DragDetectorThread()
        self.detector_thread.drag_triggered.connect(self._on_drag_triggered)
        self.detector_thread.drag_released.connect(self._on_drag_released)
        self.detector_thread.cancel_requested.connect(self._on_cancel_requested)

        # 3. Initialize System Tray Icon
        self._init_tray()

        # Start detection
        self.detector_thread.start()

    def _init_tray(self):
        self.tray_icon = QSystemTrayIcon(create_tray_icon(), self.app)
        self.tray_icon.setToolTip("ShiftDrop - Drag + Shift File Utility")

        tray_menu = QMenu()

        # Status toggle
        self.status_action = tray_menu.addAction("Status: Active")
        self.status_action.setCheckable(True)
        self.status_action.setChecked(True)
        self.status_action.triggered.connect(self._toggle_active)

        tray_menu.addSeparator()

        # Default image mode
        mode_menu = tray_menu.addMenu("Default Image Mode")
        self.mode_convert_action = mode_menu.addAction("Format Conversion")
        self.mode_convert_action.setCheckable(True)
        self.mode_convert_action.setChecked(True)

        self.mode_tools_action = mode_menu.addAction("Quick Actions / Tools")
        self.mode_tools_action.setCheckable(True)
        self.mode_tools_action.setChecked(False)

        self.mode_convert_action.triggered.connect(lambda: self._set_default_mode("IMAGE_CONVERT"))
        self.mode_tools_action.triggered.connect(lambda: self._set_default_mode("IMAGE_TOOLS"))

        tray_menu.addSeparator()

        # Manual Test Trigger
        test_action = tray_menu.addAction("Test Radial Menu (Under Cursor)")
        test_action.triggered.connect(self._test_trigger)

        # About
        about_action = tray_menu.addAction("About ShiftDrop...")
        about_action.triggered.connect(self._show_about)

        tray_menu.addSeparator()

        # Quit
        quit_action = tray_menu.addAction("Quit ShiftDrop")
        quit_action.triggered.connect(self._quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _toggle_active(self, checked: bool):
        self.detector_thread.set_enabled(checked)
        self.status_action.setText("Status: Active" if checked else "Status: Paused")

    def _set_default_mode(self, mode: str):
        self.radial_menu.menu_mode = mode
        self.mode_convert_action.setChecked(mode == "IMAGE_CONVERT")
        self.mode_tools_action.setChecked(mode == "IMAGE_TOOLS")

    def _on_menu_hidden(self):
        """Called whenever radial menu closes."""
        self.detector_thread.reset_trigger()

    def _on_drag_triggered(self, x: int, y: int):
        """Called when user drags with left mouse and presses Shift."""
        if not self.radial_menu.isVisible():
            self.radial_menu.spawn_at(x, y)

    def _on_drag_released(self):
        """Called when user releases left mouse button."""
        if self.radial_menu.isVisible():
            x, y = get_current_cursor_pos()
            dx = x - (self.radial_menu.x() + self.radial_menu.CENTER_X)
            dy = y - (self.radial_menu.y() + self.radial_menu.CENTER_Y)
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > self.radial_menu.R_OUTER:
                self.radial_menu.hide()
            else:
                # If released inside, OLE dropEvent usually handles it immediately.
                # Safety fallback timer in case OLE drop was cancelled:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(250, self._ensure_hidden_on_release)
        self.detector_thread.reset_trigger()

    def _ensure_hidden_on_release(self):
        if self.radial_menu.isVisible():
            self.radial_menu.hide()

    def _test_trigger(self):
        """Manually trigger radial menu under cursor for easy testing."""
        x, y = get_current_cursor_pos()
        self.radial_menu.spawn_at(x, y)

    def _on_cancel_requested(self):
        """Called when Esc is pressed anywhere to navigate back to main view or close."""
        if self.radial_menu.isVisible():
            navigated_back = self.radial_menu.handle_escape_press()
            if not navigated_back:
                self.radial_menu.hide()
                self.detector_thread.reset_trigger()

    def _on_action_completed(self, action_name: str, output_path: str):
        if action_name == "Tidak Didukung":
            self.tray_icon.showMessage(
                "ShiftDrop",
                output_path,
                QSystemTrayIcon.MessageIcon.Warning,
                3000
            )
            return

        filename = os.path.basename(output_path)
        self.tray_icon.showMessage(
            "ShiftDrop Complete",
            f"Successfully processed {action_name}:\n{filename}",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

    def _show_about(self):
        QMessageBox.information(
            None,
            "About ShiftDrop",
            "ShiftDrop v1.0.0\n\n"
            "A fast Windows Radial Drag-and-Drop File Converter & Quick Editor.\n"
            "Drag any file and press Shift to reveal the radial action wheel.\n\n"
            "Created with PyQt6 & Pillow."
        )

    def _quit(self):
        self.detector_thread.stop()
        self.tray_icon.hide()
        self.app.quit()

    def run(self) -> int:
        return self.app.exec()


def check_single_instance():
    """Ensure only one instance of ShiftDrop is active to prevent hook collisions."""
    try:
        import win32event, winerror, win32api
        mutex = win32event.CreateMutex(None, False, "ShiftDrop_SingleInstance_App_Mutex")
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            return None
        return mutex
    except Exception:
        return True


if __name__ == "__main__":
    _app_mutex = check_single_instance()
    if not _app_mutex:
        # Already running in background
        app = QApplication(sys.argv)
        QMessageBox.information(
            None,
            "ShiftDrop",
            "ShiftDrop is already running in the background!\nCheck the orange 'S' icon in your Windows System Tray (near the clock)."
        )
        sys.exit(0)

    app = ShiftDropApp()
    sys.exit(app.run())

