# SYSTEM PROMPT & TECHNICAL SPECIFICATION: Windows Radial Drag-and-Drop File Converter & Quick Editor

## 1. Role & Objective
You are an Expert Windows Desktop Application Developer and Systems Architect. Your task is to build a complete, production-ready Windows desktop utility inspired by the macOS radial drag-and-drop file converter/editor. 

When a user drags a file in Windows File Explorer or Desktop and presses the `Shift` key, a sleek, translucent **Radial (Pie) Menu** pops up directly under the cursor. Dropping the file onto a specific slice/sector either **converts the file** immediately in the same directory or **opens a quick-edit modal** (`Crop Image` or `Add BG`).

---

## 2. Recommended Tech Stack (Agent Default)
Build this project using **Python 3.11+ and PyQt6** for rapid, reliable execution, native Windows OLE Drag-and-Drop integration, and hardware-accelerated 2D canvas rendering (`QPainter`).

### Required Libraries (`requirements.txt`)
* **GUI & Overlay:** `PyQt6`
* **Windows API & Global Hooks:** `pywin32`, `ctypes` (built-in), `pynput`
* **Image Processing (`Crop`, `Add BG`, Conversions):** `Pillow` (PIL), `pillow-heif` (for HEIC/AVIF support)
* **PDF & Document Processing:** `PyMuPDF` (`fitz` for PDF to Image/Text), `pdf2docx` (for PDF to DOCX), `docx2pdf` (optional)

*(Note: If instructed by the user to use C# / .NET 8 WPF instead, translate the architecture below to `System.Windows`, `SetWindowsHookEx` via P/Invoke, `SkiaSharp`, and `PDFtoImage`.)*

---

## 3. Core Windows Architecture (Crucial Implementation Details)

### 3.1. Solving the Windows "Drag + Shift" Detection
In Windows, when a user is actively dragging a file from Explorer, Explorer owns the mouse capture via the **OLE Drag-and-Drop loop**. To intercept this smoothly without breaking the native drag operation:

1. **Global Low-Level Hook / Polling Thread:**
   * Run a background thread or `QTimer` (polling every $16\text{ ms}$ via `ctypes.windll.user32.GetAsyncKeyState`) checking two conditions simultaneously:
     * Left Mouse Button is held down (`VK_LBUTTON` $= 0\text{x}01$).
     * Shift Key is pressed (`VK_SHIFT` $= 0\text{x}10$).
2. **Spawning the Drop-Target Overlay:**
   * As soon as `VK_LBUTTON` + `VK_SHIFT` is detected, move the frameless transparent `RadialMenuWindow` center to the current cursor coordinates $(X_c, Y_c)$ and call `.show()`.
   * Set window flags: `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool` and `Qt.WidgetAttribute.WA_TranslucentBackground`.
   * Enable `setAcceptDrops(True)` on the widget.
3. **Reading the Dragged File via OLE (`dragEnterEvent`):**
   * Because the cursor is now physically over the visible pixels of `RadialMenuWindow` while an OLE drag is active, Windows immediately fires `dragEnterEvent(event)` on the widget.
   * Extract the file path(s) from `event.mimeData().urls()[0].toLocalFile()`.
   * Inspect the file extension (e.g., `.pdf`, `.jpg`, `.png`) and file size in MB, then dynamically populate the radial sectors and re-render the menu.
   * If `dragEnterEvent` does not fire within $150\text{ ms}$ (meaning the user is just selecting text or dragging a non-file window), automatically hide the radial menu.

### 3.2. Radial Menu Geometry & Hit-Testing Math
* **Window Size:** $360 \times 360\text{ px}$ (Center at $(180, 180)$).
* **Inner Circle Radius ($R_{\text{inner}}$):** $50\text{ px}$ (Displays the file icon and file size badge, e.g., `1.1 MB` or `1.2 MB`).
* **Outer Ring Radius ($R_{\text{outer}}$):** $155\text{ px}$.
* **Sector Hit-Testing (`dragMoveEvent`):**
  * Given cursor position $(x, y)$ relative to the center $(x_0, y_0)$:
    $$\Delta x = x - x_0, \quad \Delta y = y - y_0$$
    $$r = \sqrt{(\Delta x)^2 + (\Delta y)^2}$$
    $$\theta = \left( \text{atan2}(\Delta y, \Delta x) \times \frac{180}{\pi} + 360 \right) \bmod 360$$
  * If $R_{\text{inner}} \le r \le R_{\text{outer}}$, highlight the active sector $i$ where:
    $$\text{SectorIndex} = \left\lfloor \frac{\theta}{360 / N} \right\rfloor$$
    (where $N$ is the total number of sectors).
* **Mode Switching for Images (Convert vs. Edit Tools):**
  * When dragging an image, pressing `Tab` or `Space` (or hovering over the center ring toggle) switches the radial ring between **Format Conversion Mode** and **Quick Action/Edit Mode**.

---

## 4. Context-Aware Radial Menu Modes

### Mode A: PDF File Dragged (`.pdf`)
* **Sectors ($N = 4$):**
  1. `DOCX` (Top)
  2. `JPG` (Right)
  3. `PNG` (Bottom)
  4. `TXT` (Left)

### Mode B: Image File Dragged — Format Conversion (`.jpg`, `.png`, `.webp`, etc.)
* **Sectors ($N = 8$):**
  1. `PNG`
  2. `WEBP`
  3. `HEIC`
  4. `AVIF`
  5. `BMP`
  6. `PDF`
  7. `DOCX`
  8. `TIFF` (or center option)

### Mode C: Image File Dragged — Quick Actions / Tools
* **Sectors ($N = 7$):**
  1. `COMPRESS` (Reduces file size via quality/quantization optimization)
  2. `METADATA` (Strips EXIF metadata or shows metadata inspector)
  3. `EDIT` (Quick brightness/contrast adjustments)
  4. `ANNOTATE` (Draw arrows/text/rectangles)
  5. `ADD BG` (Opens the **Add BG Modal**)
  6. `CROP` (Opens the **Crop Image Modal**)
  7. `REDACT` (Blur/pixelate selected region)

---

## 5. Interactive Editor Modals (UI & Functional Specs)

### 5.1. Modal 1: `Crop Image` Window
Triggered when an image is dropped onto the **`CROP`** sector:
* **Visual Theme:** Warm translucent frosted-glass / orange-amber accented dark/light theme matching the radial UI.
* **Canvas Area:** Displays the loaded image scaled to fit, with an interactive orange crop rectangle overlay and 8 draggable corner/edge handles + rule-of-thirds grid lines.
* **Controls Bar (Bottom):**
  * **Aspect Ratio Presets:** Pill buttons for `Free`, `1:1`, `16:9`, `9:16`, `4:3`, `3:4`.
  * **Dimension Inputs:** Numeric fields for `W` (Width in px) and `H` (Height in px) that update dynamically as the crop box is dragged, and also resize the crop box when edited manually.
  * **Action Buttons:** `Cancel` (closes modal) and `Apply` (orange primary button).
* **Output Behavior:** Saves the cropped image in the **same folder** as the source file with the naming convention: `<OriginalName> Cropped.<ext>` (e.g., `Page 001 Cropped.jpg`). Automatically increments if the file exists.

### 5.2. Modal 2: `Add BG` (Background Beautifier) Window
Triggered when an image is dropped onto the **`ADD BG`** sector:
* **Visual Preview:** Live interactive canvas rendering the source image centered on top of a customizable background with rounded corners and drop shadow.
* **Controls Panel (Bottom):**
  * **Background Selector:** A row of 12+ preset swatches (vibrant macOS-style mesh/linear gradients and solid colors) + a custom rainbow color picker button.
  * **Sliders (with live pixel readouts on the right):**
    * `Padding`: $0\text{ px}$ to $300\text{ px}$ (controls spacing around the inner image).
    * `Rounded`: $0\text{ px}$ to $100\text{ px}$ (corner radius of the inner image).
    * `Shadow`: $0\text{ px}$ to $100\text{ px}$ (Gaussian blur radius and opacity of the drop shadow behind the inner image).
  * **Ratio Presets:** Pill buttons for `Auto`, `1:1`, `16:9`, `4:3`.
  * **Action Buttons:** `Cancel` and `Save with Background` (orange primary button).
* **Output Behavior:** Renders the full-resolution composite image using `Pillow` (generating a smooth gradient canvas, applying a rounded alpha mask to the source image, rendering a Gaussian-blurred drop shadow layer, and compositing them together) and saves it to the **same directory** as `<OriginalName> With Background.png`.

---

## 6. Project Directory Structure

Generate the project with the following clean, modular structure:

```text
windows-radial-converter/
├── requirements.txt
├── README.md
├── main.py                      # Entry point, System Tray icon, Global Hook listener
├── core/
│   ├── __init__.py
│   ├── drag_detector.py         # Win32 GetAsyncKeyState polling & cursor tracking
│   ├── converter_engine.py      # PDF/Image/Docx conversion logic & file naming
│   └── image_processor.py       # Pillow logic for Crop, Add BG, Compress, Redact
└── ui/
    ├── __init__.py
    ├── radial_menu.py           # Frameless QWidget, QPainter pie sectors, OLE Drag/Drop events
    ├── crop_modal.py            # Interactive Crop Image window
    └── add_bg_modal.py          # Interactive Add Background window with live preview
```

---

## 7. Step-by-Step Implementation Instructions for the Agent

Please execute the build in the following sequence:

1. **Environment Setup:** Create `requirements.txt` and install dependencies (`PyQt6`, `pywin32`, `Pillow`, `pillow-heif`, `PyMuPDF`, `pdf2docx`).
2. **Build `core/converter_engine.py` & `core/image_processor.py`:**
   * Implement lossless/high-quality conversions for PDF $\rightarrow$ JPG/PNG/TXT/DOCX and Image $\rightarrow$ PNG/JPG/WEBP/BMP/TIFF/PDF.
   * Implement the high-resolution `Pillow` rendering pipeline for `crop_image()` and `add_background()` (gradient generation, rounded corners mask, Gaussian shadow layer).
   * Ensure all outputs are saved directly in the source file's directory with clean non-overwriting filenames.
3. **Build `ui/radial_menu.py`:**
   * Implement `QPainter` custom drawing with anti-aliasing (`QPainter.RenderHint.Antialiasing`).
   * Use warm amber/orange/cream translucent colors (`QColor` with alpha) and smooth hover scaling transitions.
   * Implement `dragEnterEvent`, `dragMoveEvent`, `dragLeaveEvent`, and `dropEvent`.
   * Add a key listener or center hover zone so when dragging an image, the user can toggle between **Conversion Sectors** (`PNG`, `WEBP`, `PDF`, etc.) and **Action Sectors** (`CROP`, `ADD BG`, `COMPRESS`, etc.).
4. **Build `ui/crop_modal.py` & `ui/add_bg_modal.py`:**
   * Ensure both modals have modern custom styling (QSS), responsive live previews, and exact controls matching the specification.
5. **Build `core/drag_detector.py` & `main.py`:**
   * Connect the `VK_LBUTTON` + `VK_SHIFT` detector to show/hide the `RadialMenuWindow`.
   * Add a Windows System Tray icon (`QSystemTrayIcon`) with options to Toggle Active Status, Switch Default Image Mode (Convert vs. Tools), and Quit.
6. **Self-Verification & Testing:**
   * Run `python main.py` to verify there are no syntax, import, or DPI-scaling errors on Windows (enable High-DPI scaling properly in PyQt6).