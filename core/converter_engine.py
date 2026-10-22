"""
ShiftDrop - Converter Engine
Handles lossless and high-quality document and image format conversions:
- PDF -> DOCX, JPG, PNG, TXT
- Image -> PNG, JPG, WEBP, BMP, TIFF, PDF, DOCX, HEIC, AVIF
All outputs are saved in the source directory with non-overwriting filenames.
"""

import os
from typing import List, Optional
from PIL import Image, ImageOps

from core.image_processor import get_non_conflicting_path

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass


def convert_pdf_to_docx(pdf_path: str, output_path: Optional[str] = None) -> List[str]:
    """
    Convert PDF document to Microsoft Word DOCX format using pdf2docx.
    """
    from pdf2docx import Converter

    dirname, filename = os.path.split(pdf_path)
    basename, _ = os.path.splitext(filename)

    if output_path is None:
        output_path = get_non_conflicting_path(dirname, basename, "docx")

    cv = Converter(pdf_path)
    try:
        cv.convert(output_path)
    finally:
        cv.close()

    return [output_path]


def convert_pdf_to_images(
    pdf_path: str,
    target_ext: str = "png",
    dpi: int = 200,
    output_path: Optional[str] = None
) -> List[str]:
    """
    Convert each page of a PDF into high-resolution images (JPG or PNG) using PyMuPDF (fitz).
    If 1 page: '<Name>.<ext>'
    If >1 pages: '<Name>_page_1.<ext>', '<Name>_page_2.<ext>', etc.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    dirname, filename = os.path.split(pdf_path)
    basename, _ = os.path.splitext(filename)
    clean_ext = target_ext.lower().lstrip(".")

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    generated_files = []

    # Calculate zoom matrix for requested DPI (72 is default PDF points)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    if page_count == 1:
        if output_path is None:
            output_path = get_non_conflicting_path(dirname, basename, clean_ext)
        page = doc[0]
        pix = page.get_pixmap(matrix=mat, alpha=(clean_ext == "png"))
        pix.save(output_path)
        generated_files.append(output_path)
    else:
        for page_num in range(page_count):
            page_suffix = f"page_{page_num + 1}"
            out_file = get_non_conflicting_path(dirname, f"{basename}_{page_suffix}", clean_ext)
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat, alpha=(clean_ext == "png"))
            pix.save(out_file)
            generated_files.append(out_file)

    doc.close()
    return generated_files


def convert_pdf_to_txt(pdf_path: str, output_path: Optional[str] = None) -> List[str]:
    """
    Extract text content from all pages of a PDF into a UTF-8 text file.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    dirname, filename = os.path.split(pdf_path)
    basename, _ = os.path.splitext(filename)

    if output_path is None:
        output_path = get_non_conflicting_path(dirname, basename, "txt")

    doc = fitz.open(pdf_path)
    extracted_texts = []
    for page in doc:
        extracted_texts.append(page.get_text("text"))
    doc.close()

    full_text = "\n\n--- Page Break ---\n\n".join(extracted_texts)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    return [output_path]


def convert_image_to_docx(image_path: str, output_path: Optional[str] = None) -> List[str]:
    """
    Embed an image into a new DOCX document.
    """
    try:
        import docx
        from docx.shared import Inches
    except ImportError:
        raise ImportError("python-docx is required for DOCX creation.")

    dirname, filename = os.path.split(image_path)
    basename, _ = os.path.splitext(filename)

    if output_path is None:
        output_path = get_non_conflicting_path(dirname, basename, "docx")

    doc = docx.Document()
    # Add section with reasonable margins
    section = doc.sections[0]
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)

    # Insert image scaled to fit page width (max 6.5 inches)
    doc.add_picture(image_path, width=Inches(6.5))
    doc.save(output_path)
    return [output_path]


def convert_image(
    image_path: str,
    target_format: str,
    output_path: Optional[str] = None
) -> List[str]:
    """
    Convert an image to various formats (PNG, WEBP, JPG, BMP, TIFF, PDF, DOCX, HEIC, AVIF).
    """
    target_fmt = target_format.upper().strip()
    dirname, filename = os.path.split(image_path)
    basename, _ = os.path.splitext(filename)

    if target_fmt == "DOCX":
        return convert_image_to_docx(image_path, output_path)

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)

        ext_map = {
            "PNG": "png",
            "JPG": "jpg",
            "JPEG": "jpg",
            "WEBP": "webp",
            "BMP": "bmp",
            "TIFF": "tiff",
            "TIF": "tiff",
            "PDF": "pdf",
            "HEIC": "heic",
            "AVIF": "avif",
        }
        out_ext = ext_map.get(target_fmt, target_fmt.lower())

        if output_path is None:
            output_path = get_non_conflicting_path(dirname, basename, out_ext)

        # Handle color mode compatibility
        if target_fmt in ("JPG", "JPEG", "BMP"):
            if img.mode in ("RGBA", "LA", "P"):
                # Composite onto white background for formats lacking alpha channel
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                alpha = img.split()[-1] if img.mode == "RGBA" else None
                rgb_img.paste(img, mask=alpha)
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            if target_fmt in ("JPG", "JPEG"):
                img.save(output_path, "JPEG", quality=95, optimize=True)
            else:
                img.save(output_path, "BMP")

        elif target_fmt == "PDF":
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                alpha = img.split()[-1] if img.mode == "RGBA" else None
                rgb_img.paste(img, mask=alpha)
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output_path, "PDF", resolution=100.0)

        elif target_fmt == "WEBP":
            img.save(output_path, "WEBP", quality=95, method=6)

        elif target_fmt == "PNG":
            img.save(output_path, "PNG", optimize=True)

        elif target_fmt in ("TIFF", "TIF"):
            img.save(output_path, "TIFF", compression="tiff_lzw")

        elif target_fmt in ("HEIC", "AVIF"):
            try:
                img.save(output_path, target_fmt, quality=90)
            except Exception:
                # If specific codec writer isn't available, fallback to PNG with message
                fallback_path = get_non_conflicting_path(dirname, basename, "png")
                img.save(fallback_path, "PNG")
                return [fallback_path]
        else:
            img.save(output_path)

        return [output_path]


def convert_file(file_path: str, target_action: str) -> List[str]:
    """
    Universal conversion dispatcher based on source file extension and target action.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower().lstrip(".")
    action_upper = target_action.upper().strip()

    # Case 1: PDF Source
    if ext_lower == "pdf":
        if action_upper == "DOCX":
            return convert_pdf_to_docx(file_path)
        elif action_upper in ("JPG", "JPEG"):
            return convert_pdf_to_images(file_path, target_ext="jpg", dpi=200)
        elif action_upper == "PNG":
            return convert_pdf_to_images(file_path, target_ext="png", dpi=200)
        elif action_upper == "TXT":
            return convert_pdf_to_txt(file_path)
        else:
            raise ValueError(f"Unsupported action '{action_upper}' for PDF files.")

    # Case 2: Image Source
    IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "heic", "avif", "gif"}
    if ext_lower in IMAGE_EXTS:
        return convert_image(file_path, action_upper)

    raise ValueError(f"Unsupported file type '.{ext_lower}' for conversion.")
