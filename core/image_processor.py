"""
ShiftDrop - Core Image Processor
High-performance image manipulation using Pillow:
- Crop Image
- Add Background (Gradients, solid colors, rounded corners, Gaussian drop shadow)
- Compress Image
- Metadata Stripper & Inspector
- Safe non-overwriting file naming
"""

import os
import math
from typing import Tuple, Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass


def get_non_conflicting_path(
    directory: str,
    base_name: str,
    extension: str,
    suffix: str = ""
) -> str:
    """
    Generate an output path that does not overwrite existing files.
    Example: 'Photo Cropped.png', 'Photo Cropped (1).png', etc.
    """
    clean_ext = extension.lstrip(".")
    initial_name = f"{base_name} {suffix}".strip() if suffix else base_name
    candidate = os.path.join(directory, f"{initial_name}.{clean_ext}")
    if not os.path.exists(candidate):
        return candidate

    counter = 1
    while True:
        candidate = os.path.join(directory, f"{initial_name} ({counter}).{clean_ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def create_rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    """
    Generate a high-resolution antialiased rounded corner alpha mask.
    Uses 4x supersampling for ultra-smooth edges.
    """
    width, height = size
    if radius <= 0:
        return Image.new("L", size, 255)

    # 4x supersample for crisp anti-aliasing
    scale = 4
    high_w = width * scale
    high_h = height * scale
    high_r = min(radius * scale, high_w // 2, high_h // 2)

    mask = Image.new("L", (high_w, high_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (high_w - 1, high_h - 1)], radius=high_r, fill=255)
    return mask.resize((width, height), Image.Resampling.LANCZOS)


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex string (#RRGGBB or #RGB) to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16)
    )


def generate_linear_gradient(
    width: int,
    height: int,
    color1: Tuple[int, int, int],
    color2: Tuple[int, int, int],
    angle_deg: float = 45.0
) -> Image.Image:
    """
    Generate a smooth 2D linear gradient between two RGB colors with a given angle.
    """
    base = Image.new("RGBA", (width, height))
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Calculate gradient vector span
    corners = [
        (0, 0),
        (width, 0),
        (0, height),
        (width, height)
    ]
    projections = [x * cos_a + y * sin_a for x, y in corners]
    min_p = min(projections)
    max_p = max(projections)
    span = max_p - min_p if max_p != min_p else 1.0

    # Draw using vertical scanlines if angle is simple, or rasterize row-by-row
    # For performance and smoothness, render a 1D gradient line and project onto canvas
    # Or create a low-res gradient and upscale with bicubic
    small_w = max(1, width // 4)
    small_h = max(1, height // 4)
    small_img = Image.new("RGBA", (small_w, small_h))
    pixels = small_img.load()

    r1, g1, b1 = color1
    r2, g2, b2 = color2

    scale_x = width / small_w
    scale_y = height / small_h

    for y in range(small_h):
        real_y = y * scale_y
        for x in range(small_w):
            real_x = x * scale_x
            proj = real_x * cos_a + real_y * sin_a
            t = (proj - min_p) / span
            t = max(0.0, min(1.0, t))
            r = int(r1 + t * (r2 - r1))
            g = int(g1 + t * (g2 - g1))
            b = int(b1 + t * (b2 - b1))
            pixels[x, y] = (r, g, b, 255)

    return small_img.resize((width, height), Image.Resampling.BICUBIC)


def generate_mesh_gradient(
    width: int,
    height: int,
    colors: List[Tuple[int, int, int]]
) -> Image.Image:
    """
    Generate an aesthetic multi-color macOS-style blurred mesh gradient.
    """
    if len(colors) < 2:
        c = colors[0] if colors else (255, 255, 255)
        return Image.new("RGBA", (width, height), (*c, 255))

    # Create small canvas, place color blobs, and heavy Gaussian blur
    mesh_w = 64
    mesh_h = 64
    mesh_img = Image.new("RGBA", (mesh_w, mesh_h), (*colors[0], 255))
    draw = ImageDraw.Draw(mesh_img)

    points = [
        (0, 0),
        (mesh_w, 0),
        (mesh_w, mesh_h),
        (0, mesh_h),
        (mesh_w // 2, mesh_h // 2)
    ]
    for i, p in enumerate(points):
        col = colors[(i + 1) % len(colors)]
        r = mesh_w // 2
        draw.ellipse([(p[0] - r, p[1] - r), (p[0] + r, p[1] + r)], fill=(*col, 200))

    blurred = mesh_img.filter(ImageFilter.GaussianBlur(radius=12))
    return blurred.resize((width, height), Image.Resampling.BICUBIC)


def crop_image(
    source_path: str,
    crop_box: Tuple[int, int, int, int],
    output_path: Optional[str] = None
) -> str:
    """
    Crop an image using pixel coordinates (left, top, right, bottom).
    Saves to the same directory as '<OriginalName> Cropped.<ext>'.
    """
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        w, h = img.size

        # Clamp crop box within bounds
        left, top, right, bottom = crop_box
        left = max(0, min(w - 1, int(left)))
        top = max(0, min(h - 1, int(top)))
        right = max(left + 1, min(w, int(right)))
        bottom = max(top + 1, min(h, int(bottom)))

        cropped = img.crop((left, top, right, bottom))

        if output_path is None:
            dirname, filename = os.path.split(source_path)
            basename, ext = os.path.splitext(filename)
            output_path = get_non_conflicting_path(dirname, basename, ext, suffix="Cropped")

        # Save with appropriate options
        save_fmt = cropped.format or "PNG"
        if output_path.lower().endswith((".jpg", ".jpeg")):
            if cropped.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", cropped.size, (255, 255, 255))
                rgb_img.paste(cropped, mask=cropped.split()[-1] if cropped.mode == "RGBA" else None)
                cropped = rgb_img
            cropped.save(output_path, "JPEG", quality=95, optimize=True)
        else:
            cropped.save(output_path, quality=95, optimize=True)

        return output_path


def add_background(
    source_path: str,
    bg_mode: str = "gradient",
    bg_colors: Optional[List[str]] = None,
    padding: int = 60,
    corner_radius: int = 24,
    shadow_blur: int = 35,
    shadow_opacity: float = 0.45,
    target_ratio: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Renders the image centered on a beautiful background with rounded corners and drop shadow.
    Saves as '<OriginalName> With Background.png'.
    """
    if bg_colors is None:
        bg_colors = ["#FF5E3A", "#FF2A68"]

    rgb_colors = [hex_to_rgb(c) for c in bg_colors]

    with Image.open(source_path) as orig_img:
        orig_img = ImageOps.exif_transpose(orig_img)
        inner_img = orig_img.convert("RGBA")
        inner_w, inner_h = inner_img.size

        # Calculate canvas size
        content_w = inner_w + padding * 2
        content_h = inner_h + padding * 2

        canvas_w = content_w
        canvas_h = content_h

        # Handle aspect ratio presets if given (e.g., '1:1', '16:9', '4:3', '9:16')
        if target_ratio and target_ratio != "Auto":
            try:
                rw, rh = [float(x) for x in target_ratio.split(":")]
                desired_ratio = rw / rh
                current_ratio = content_w / content_h
                if current_ratio > desired_ratio:
                    # Content is wider, increase height
                    canvas_w = content_w
                    canvas_h = int(content_w / desired_ratio)
                else:
                    # Content is taller, increase width
                    canvas_h = content_h
                    canvas_w = int(content_h * desired_ratio)
            except Exception:
                canvas_w = content_w
                canvas_h = content_h

        # 1. Generate Background Canvas
        if bg_mode == "solid":
            c = rgb_colors[0]
            bg_layer = Image.new("RGBA", (canvas_w, canvas_h), (*c, 255))
        elif bg_mode == "mesh" and len(rgb_colors) >= 3:
            bg_layer = generate_mesh_gradient(canvas_w, canvas_h, rgb_colors)
        else:
            # Linear Gradient
            c1 = rgb_colors[0]
            c2 = rgb_colors[1] if len(rgb_colors) > 1 else rgb_colors[0]
            bg_layer = generate_linear_gradient(canvas_w, canvas_h, c1, c2, angle_deg=45.0)

        # 2. Position of inner image (centered)
        pos_x = (canvas_w - inner_w) // 2
        pos_y = (canvas_h - inner_h) // 2

        # 3. Apply Rounded Corners to inner image
        if corner_radius > 0:
            mask = create_rounded_mask((inner_w, inner_h), corner_radius)
            # Combine existing alpha channel with rounded mask
            existing_alpha = inner_img.split()[-1]
            combined_alpha = ImageChops.multiply(existing_alpha, mask)
            inner_img.putalpha(combined_alpha)
        else:
            mask = inner_img.split()[-1]

        # 4. Generate Gaussian-Blurred Drop Shadow Layer
        if shadow_blur > 0 and shadow_opacity > 0:
            shadow_offset_y = max(4, shadow_blur // 4)
            shadow_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

            # Create a solid black shape matching the inner image mask
            shadow_alpha = mask.point(lambda p: int(p * min(1.0, max(0.0, shadow_opacity))))
            shadow_shape = Image.new("RGBA", (inner_w, inner_h), (0, 0, 0, 255))
            shadow_shape.putalpha(shadow_alpha)

            # Paste shadow shape with vertical offset
            shadow_canvas.paste(
                shadow_shape,
                (pos_x, pos_y + shadow_offset_y),
                mask=shadow_shape.split()[-1]
            )

            # Apply Gaussian Blur to shadow
            shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(radius=shadow_blur))

            # Composite background + shadow
            bg_layer.alpha_composite(shadow_canvas)

        # 5. Composite inner image on top
        bg_layer.paste(inner_img, (pos_x, pos_y), mask=inner_img.split()[-1])

        # 6. Save Output
        if output_path is None:
            dirname, filename = os.path.split(source_path)
            basename, _ = os.path.splitext(filename)
            output_path = get_non_conflicting_path(dirname, basename, "png", suffix="With Background")

        bg_layer.save(output_path, "PNG", optimize=True)
        return output_path


def compress_image(
    source_path: str,
    quality: int = 80,
    output_path: Optional[str] = None
) -> str:
    """
    Compress an image to reduce file size.
    For JPEG/WEBP: adjusts quality factor.
    For PNG: optimizes palette or quantizes cleanly.
    """
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        dirname, filename = os.path.split(source_path)
        basename, ext = os.path.splitext(filename)
        ext_lower = ext.lower().lstrip(".")

        if output_path is None:
            output_path = get_non_conflicting_path(dirname, basename, ext_lower, suffix="Compressed")

        if ext_lower in ("jpg", "jpeg"):
            if img.mode in ("RGBA", "LA", "P"):
                rgb = Image.new("RGB", img.size, (255, 255, 255))
                rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = rgb
            img.save(output_path, "JPEG", quality=quality, optimize=True)
        elif ext_lower == "webp":
            img.save(output_path, "WEBP", quality=quality, method=6)
        elif ext_lower == "png":
            # Lossless compression optimization
            img.save(output_path, "PNG", optimize=True)
        else:
            img.save(output_path, optimize=True)

        return output_path


def strip_metadata(
    source_path: str,
    output_path: Optional[str] = None
) -> str:
    """
    Strip EXIF and other metadata from the image to protect privacy.
    """
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        # Create a fresh image copy without metadata dict
        clean_img = Image.new(img.mode, img.size)
        clean_img.paste(img)

        dirname, filename = os.path.split(source_path)
        basename, ext = os.path.splitext(filename)
        if output_path is None:
            output_path = get_non_conflicting_path(dirname, basename, ext, suffix="Cleaned")

        clean_img.save(output_path)
        return output_path


def get_image_info(source_path: str) -> Dict[str, Any]:
    """
    Retrieve basic inspection data for an image file.
    """
    size_bytes = os.path.getsize(source_path)
    with Image.open(source_path) as img:
        return {
            "format": img.format,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "size_bytes": size_bytes,
            "size_formatted": f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1048576 else f"{size_bytes / 1024:.1f} KB"
        }
