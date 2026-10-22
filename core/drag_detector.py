"""
ShiftDrop - Drag & Shift Low-Level Win32 Detector
Polls GetAsyncKeyState for VK_LBUTTON (0x01) + VK_SHIFT (0x10).
When both are held, emits cursor coordinates to trigger the Radial Menu overlay.
"""

import time
import ctypes
from ctypes import wintypes
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal

# Win32 Virtual Key Codes
VK_LBUTTON = 0x01
VK_SHIFT = 0x10


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_current_cursor_pos() -> tuple[int, int]:
    """Retrieve absolute screen coordinates of the cursor."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def is_key_down(vk_code: int) -> bool:
    """Check if a virtual key is currently pressed using GetAsyncKeyState."""
    # Most significant bit indicates key state (down if set)
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


class DragDetectorThread(QThread):
    """
    Background worker thread polling at ~60 Hz (16 ms) for Drag + Shift events.
    """
    # Signals
    drag_triggered = pyqtSignal(int, int)  # (cursor_x, cursor_y)
    drag_released = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._enabled = True
        self._has_triggered = False

    def set_enabled(self, enabled: bool):
        """Toggle active monitoring status."""
        self._enabled = enabled
        if not enabled:
            self._has_triggered = False

    def is_enabled(self) -> bool:
        return self._enabled

    def stop(self):
        """Stop thread execution cleanly."""
        self._running = False
        self.wait(1000)

    def run(self):
        """Continuous polling loop."""
        while self._running:
            if not self._enabled:
                time.sleep(0.050)
                continue

            lbutton_down = is_key_down(VK_LBUTTON)
            shift_down = is_key_down(VK_SHIFT)

            if lbutton_down and shift_down:
                if not self._has_triggered:
                    self._has_triggered = True
                    x, y = get_current_cursor_pos()
                    self.drag_triggered.emit(x, y)
            elif not lbutton_down:
                if self._has_triggered:
                    self._has_triggered = False
                    self.drag_released.emit()

            # ~60 FPS polling interval (16 ms)
            time.sleep(0.016)
