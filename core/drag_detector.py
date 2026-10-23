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
VK_ESCAPE = 0x1B


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
    Background worker thread polling at ~60 Hz (16 ms) for Drag + Shift events and Esc cancel.
    """
    # Signals
    drag_triggered = pyqtSignal(int, int)  # (cursor_x, cursor_y)
    drag_released = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._enabled = True
        self._has_triggered = False
        self._prev_shift = False
        self._prev_escape = False

    def set_enabled(self, enabled: bool):
        """Toggle active monitoring status."""
        self._enabled = enabled
        if not enabled:
            self._has_triggered = False

    def is_enabled(self) -> bool:
        return self._enabled

    def reset_trigger(self):
        """Allow triggering again immediately."""
        self._has_triggered = False

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
            escape_down = is_key_down(VK_ESCAPE)

            # Global Esc detection -> cancel radial menu instantly
            if escape_down and not self._prev_escape:
                self.cancel_requested.emit()
            self._prev_escape = escape_down

            # Detect Shift key press edge (rising edge)
            shift_pressed_edge = shift_down and not self._prev_shift
            self._prev_shift = shift_down

            if lbutton_down:
                # Trigger when Shift is pressed once while dragging
                if shift_down:
                    if not self._has_triggered or shift_pressed_edge:
                        self._has_triggered = True
                        x, y = get_current_cursor_pos()
                        self.drag_triggered.emit(x, y)
            else:
                # Left mouse released -> drag ended
                if self._has_triggered:
                    self._has_triggered = False
                    self.drag_released.emit()

            # ~60 FPS polling interval (16 ms)
            time.sleep(0.016)

