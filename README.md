# ShiftDrop ⚡

> **Windows Radial Drag-and-Drop File Converter & Quick Editor**  
> Inspired by macOS's viral productivity utility, built natively for Windows 10/11 with Python 3.11+ and PyQt6.

![ShiftDrop Banner](https://img.shields.io/badge/ShiftDrop-v1.0.0-orange?style=for-the-badge)
![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Windows Native](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

---

## 🌟 Key Features

* 🚀 **Instant Gesture Activation (`Drag + Shift`)**:  
  Drag any file from Windows File Explorer or Desktop and press the `Shift` key. A sleek, frosted-glass **Radial (Pie) Menu** appears immediately under your mouse cursor.
* 📄 **Context-Aware Dynamic Slices**:
  * **When dragging a PDF file ($N=4$ sectors)**:
    * `DOCX` (Top) — Converts PDF to Word Document using `pdf2docx`.
    * `JPG` (Right) — Renders high-DPI images of PDF pages using `PyMuPDF`.
    * `PNG` (Bottom) — Renders crisp PNG images of PDF pages with alpha channel.
    * `TXT` (Left) — Extracts document text to a UTF-8 text file.
  * **When dragging an Image file ($N=8$ format conversion sectors)**:
    * `PNG`, `WEBP`, `HEIC`, `AVIF`, `BMP`, `PDF`, `DOCX`, `TIFF`.
  * **Quick Actions / Editing Mode ($N=7$ tool sectors)**:
    * `CROP` — Opens the interactive **Crop Image Modal**.
    * `ADD BG` — Opens the macOS-style **Background Beautifier Modal**.
    * `COMPRESS` — Optimizes image quality and reduces file size.
    * `METADATA` — Strips EXIF metadata for privacy.
    * `EDIT`, `ANNOTATE`, `REDACT` — Quick markup tools.
* 🔄 **Mode Switching on the Fly**:
  * Dragging an image? Press `Tab` or `Space` (or hover/drop on the center hub) to instantly switch between **Format Conversion Mode** and **Quick Actions Mode**.
* 🖼️ **Interactive Visual Modals**:
  1. **Crop Image Modal**:
     * Scaled canvas with interactive orange crop rectangle overlay and rule-of-thirds grid.
     * 8 draggable resize handles + center drag translation.
     * Aspect ratio presets: `Free`, `1:1`, `16:9`, `9:16`, `4:3`, `3:4`.
     * Live two-way synchronized manual pixel inputs (`W` and `H`).
  2. **Add Background (Beautifier) Modal**:
     * Live real-time canvas preview.
     * 12+ vibrant gradient presets (Sunset Fire, Ocean Deep, Spring Mint, Neon Violet, etc.), solid colors, and a custom color picker.
     * Precision sliders with live pixel readouts: `Padding` ($0-300\text{ px}$), `Rounded Corners` ($0-100\text{ px}$), and `Drop Shadow` ($0-100\text{ px}$).
     * Aspect ratio pill buttons: `Auto`, `1:1`, `16:9`, `4:3`.
* 🛡️ **Non-Destructive Output**:
  * All converted files and edited images are automatically saved directly in the original file's directory.
  * Smart non-overwriting naming (`<Name> Cropped.jpg`, `<Name> With Background.png`, `<Name> (1).png`).
* 🔔 **Windows System Tray & Native Toast Notifications**:
  * Runs unobtrusively in the background.
  * Tray icon menu with options to Pause/Resume, select default mode, manual test trigger, and quick exit.
  * Native desktop toasts upon task completion.

---

## 🏗️ Architecture & Technical Implementation

1. **Win32 OLE Drag Interception**:
   * During an Explorer drag-and-drop operation, Windows Explorer retains exclusive mouse capture in an internal modal loop.
   * ShiftDrop runs a dedicated 60 Hz (~16 ms) background listener using `GetAsyncKeyState(VK_LBUTTON)` and `GetAsyncKeyState(VK_SHIFT)`.
   * As soon as both keys are active, ShiftDrop positions the frameless `RadialMenuWindow` directly beneath the cursor.
2. **OLE Handshake (`dragEnterEvent`)**:
   * Because the overlay is now positioned right under the cursor, Windows immediately fires `dragEnterEvent` into the widget.
   * ShiftDrop extracts the file path via `event.mimeData().urls()[0].toLocalFile()`.
   * If `dragEnterEvent` does not fire within $150\text{ ms}$ (e.g. text selection or regular click), the overlay hides itself automatically.
3. **Polar Geometry & Hit-Testing Math**:
   * Radius $r = \sqrt{\Delta x^2 + \Delta y^2}$ and polar angle $\theta = (\text{atan2}(\Delta y, \Delta x) \times \frac{180}{\pi} + 360) \bmod 360$.
   * Sector index: $\lfloor \theta_{\text{norm}} / (360 / N) \rfloor$.

---

## 📁 Project Directory Structure

```text
ShiftDrop/
├── requirements.txt             # Required Python dependencies
├── README.md                    # Documentation & guide
├── main.py                      # Application entry point, System Tray, Detector thread
├── core/
│   ├── __init__.py
│   ├── drag_detector.py         # Win32 GetAsyncKeyState polling & cursor tracking
│   ├── converter_engine.py      # PDF, Image, and Document conversion pipelines
│   └── image_processor.py       # High-res Pillow logic: Crop, Add BG, Shadow, Compress
├── ui/
│   ├── __init__.py
│   ├── radial_menu.py           # Frameless QWidget, QPainter pie sectors, OLE events
│   ├── crop_modal.py            # Interactive Crop Image modal window
│   └── add_bg_modal.py          # Interactive Add Background modal window
└── tests/
    └── test_shift_drop.py       # Automated test suite (conversions, math, modals, lifecycle)
```

---

## 🚀 Getting Started

### Prerequisites
* Windows 10 or 11 (64-bit)
* Python 3.11+ (Python 3.13 tested and verified)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/lepi-da-vinci/shift-drop.git
   cd shift-drop
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running ShiftDrop

Launch ShiftDrop:
```bash
python main.py
```
* Look for the orange **S** icon in the Windows System Tray (near the clock).
* Drag any file in File Explorer, press `Shift`, and drop it onto your desired sector!

### Running Tests

Execute the automated test suite:
```bash
python tests/test_shift_drop.py
```

---

## ⌨️ Shortcuts & Controls

| Action | Shortcut / Gesture |
| :--- | :--- |
| **Open Radial Menu** | Drag any file + Press `Shift` |
| **Switch Image Mode** | Press `Tab` or `Space` while dragging, or hover center hub |
| **Cancel / Close Menu** | Release mouse outside ring or press `Esc` |
| **Test Menu Manually** | Right-click System Tray icon $\rightarrow$ "Test Radial Menu" |

---

## 📜 License

MIT License. Crafted with ❤️ for Windows users seeking a fast, tactile workflow.
