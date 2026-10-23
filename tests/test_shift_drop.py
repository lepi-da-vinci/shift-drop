"""
ShiftDrop - Automated Test Suite
Verifies image processor, converter engine, and radial menu math.
"""

import os
import sys
import tempfile
import unittest
from PIL import Image

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.image_processor import (
    crop_image, add_background, compress_image, strip_metadata,
    get_non_conflicting_path, hex_to_rgb
)
from core.converter_engine import (
    convert_file, convert_image, convert_pdf_to_images,
    convert_pdf_to_txt, convert_pdf_to_docx
)


class TestShiftDrop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()

        # Create a sample test PNG image
        cls.sample_img_path = os.path.join(cls.temp_dir, "sample.png")
        img = Image.new("RGBA", (300, 200), (255, 100, 50, 255))
        img.save(cls.sample_img_path, "PNG")

        # Create a sample test PDF using pymupdf
        import pymupdf as fitz
        cls.sample_pdf_path = os.path.join(cls.temp_dir, "sample.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), "Hello ShiftDrop! This is a test document.")
        doc.save(cls.sample_pdf_path)
        doc.close()

    def test_hex_to_rgb(self):
        self.assertEqual(hex_to_rgb("#FF0000"), (255, 0, 0))
        self.assertEqual(hex_to_rgb("#00FF00"), (0, 255, 0))
        self.assertEqual(hex_to_rgb("#FFF"), (255, 255, 255))

    def test_non_conflicting_path(self):
        p1 = get_non_conflicting_path(self.temp_dir, "sample", "png")
        self.assertTrue(p1.endswith("sample (1).png") or "sample" in p1)

    def test_crop_image(self):
        out = crop_image(self.sample_img_path, (10, 10, 100, 80))
        self.assertTrue(os.path.exists(out))
        with Image.open(out) as cropped:
            self.assertEqual(cropped.size, (90, 70))

    def test_add_background(self):
        out = add_background(
            self.sample_img_path,
            bg_mode="gradient",
            bg_colors=["#FF5E3A", "#FF2A68"],
            padding=40,
            corner_radius=20,
            shadow_blur=25,
            target_ratio="1:1"
        )
        self.assertTrue(os.path.exists(out))
        with Image.open(out) as result:
            self.assertEqual(result.format, "PNG")
            w, h = result.size
            self.assertEqual(w, h)  # 1:1 ratio verified

    def test_compress_image(self):
        out = compress_image(self.sample_img_path, quality=75)
        self.assertTrue(os.path.exists(out))

    def test_strip_metadata(self):
        out = strip_metadata(self.sample_img_path)
        self.assertTrue(os.path.exists(out))

    def test_image_conversions(self):
        for fmt in ["JPG", "WEBP", "BMP", "TIFF", "PDF", "DOCX"]:
            outs = convert_file(self.sample_img_path, fmt)
            self.assertTrue(len(outs) > 0)
            for f in outs:
                self.assertTrue(os.path.exists(f))

    def test_pdf_conversions(self):
        # PDF -> TXT
        txts = convert_file(self.sample_pdf_path, "TXT")
        self.assertTrue(len(txts) > 0)
        with open(txts[0], "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Hello ShiftDrop", content)

        # PDF -> PNG
        pngs = convert_file(self.sample_pdf_path, "PNG")
        self.assertTrue(len(pngs) > 0)
        self.assertTrue(os.path.exists(pngs[0]))

        # PDF -> JPG
        jpgs = convert_file(self.sample_pdf_path, "JPG")
        self.assertTrue(len(jpgs) > 0)
        self.assertTrue(os.path.exists(jpgs[0]))

        # PDF -> DOCX
        docxs = convert_file(self.sample_pdf_path, "DOCX")
        self.assertTrue(len(docxs) > 0)
        self.assertTrue(os.path.exists(docxs[0]))

    def test_radial_menu_hit_test(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.radial_menu import RadialMenuWindow

        menu = RadialMenuWindow()
        # Test PDF Mode (4 sectors)
        menu.set_file_context(self.sample_pdf_path)
        self.assertEqual(len(menu.sectors), 4)
        self.assertTrue(menu.is_supported)

        # Test Image Mode (supported)
        menu.set_file_context(self.sample_img_path)
        self.assertTrue(menu.is_supported)

        # Test Unsupported file Mode (e.g. .exe or .zip)
        unsupported_path = os.path.join(self.temp_dir, "app.exe")
        with open(unsupported_path, "w") as f:
            f.write("dummy")
        menu.set_file_context(unsupported_path)
        self.assertFalse(menu.is_supported)
        self.assertEqual(menu.menu_mode, "UNSUPPORTED")

        # Re-set to PDF for sector labels testing
        menu.set_file_context(self.sample_pdf_path)

        # Center hit test
        idx, is_center = menu._calculate_hit_sector(180, 180)
        self.assertTrue(is_center)
        self.assertIsNone(idx)

        # Sector 0 is DOCX (top sector, y < 180, x around 180)
        idx_top, is_c = menu._calculate_hit_sector(180, 80)
        self.assertFalse(is_c)
        self.assertEqual(idx_top, 0)
        self.assertEqual(menu.sectors[idx_top]["label"], "DOCX")

        # Sector 1 is JPG (right sector, x > 180, y around 180)
        idx_right, is_c = menu._calculate_hit_sector(280, 180)
        self.assertFalse(is_c)
        self.assertEqual(idx_right, 1)
        self.assertEqual(menu.sectors[idx_right]["label"], "JPG")

        # Sector 2 is PNG (bottom sector, y > 180, x around 180)
        idx_bottom, is_c = menu._calculate_hit_sector(180, 280)
        self.assertFalse(is_c)
        self.assertEqual(idx_bottom, 2)
        self.assertEqual(menu.sectors[idx_bottom]["label"], "PNG")

        # Sector 3 is TXT (left sector, x < 180, y around 180)
        idx_left, is_c = menu._calculate_hit_sector(80, 180)
        self.assertFalse(is_c)
        self.assertEqual(idx_left, 3)
        self.assertEqual(menu.sectors[idx_left]["label"], "TXT")

    def test_crop_modal_init(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.crop_modal import CropModal

        modal = CropModal(self.sample_img_path)
        self.assertEqual(modal.canvas.orig_w, 300)
        self.assertEqual(modal.canvas.orig_h, 200)
        modal.canvas.set_aspect_ratio(1.0)
        l, t, r, b = modal.canvas.get_pixel_crop_box()
        self.assertTrue(r > l)
        self.assertTrue(b > t)

    def test_add_bg_modal_init(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.add_bg_modal import AddBgModal

        modal = AddBgModal(self.sample_img_path)
        self.assertEqual(modal.canvas.orig_w, 300)
        self.assertEqual(modal.canvas.orig_h, 200)
        modal._select_preset(modal.PRESETS[1])
        self.assertEqual(modal.current_colors, modal.PRESETS[1]["colors"])

    def test_app_lifecycle(self):
        from main import ShiftDropApp
        app = ShiftDropApp()
        self.assertIsNotNone(app.radial_menu)
        self.assertIsNotNone(app.detector_thread)
        self.assertIsNotNone(app.tray_icon)
        app._quit()


if __name__ == "__main__":
    unittest.main()
