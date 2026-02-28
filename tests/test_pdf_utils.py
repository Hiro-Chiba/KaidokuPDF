"""_pdf.py / _parallel.py のユーティリティ関数テスト。"""

from __future__ import annotations

import pandas as pd
import pytest
from PIL import Image

from image_pdf_ocr._exceptions import OCRConversionError
from image_pdf_ocr._parallel import _reconstruct_text_from_frame
from image_pdf_ocr._pdf import _determine_canvas_size, _normalize_image_for_canvas


# ---------------------------------------------------------------------------
# _determine_canvas_size
# ---------------------------------------------------------------------------
class TestDetermineCanvasSize:
    def test_single_image(self, tmp_path):
        img = Image.new("RGB", (640, 480), "white")
        path = tmp_path / "test.png"
        img.save(str(path))
        w, h = _determine_canvas_size([path])
        assert w == 640
        assert h == 480

    def test_multiple_images_picks_max(self, tmp_path):
        sizes = [(100, 200), (300, 150), (250, 400)]
        paths = []
        for i, (w, h) in enumerate(sizes):
            img = Image.new("RGB", (w, h), "white")
            path = tmp_path / f"img_{i}.png"
            img.save(str(path))
            paths.append(path)
        w, h = _determine_canvas_size(paths)
        assert w == 300
        assert h == 400

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="有効な画像サイズ"):
            _determine_canvas_size([])

    def test_invalid_image_raises(self, tmp_path):
        path = tmp_path / "invalid.png"
        path.write_text("not an image")
        with pytest.raises(OCRConversionError):
            _determine_canvas_size([path])


# ---------------------------------------------------------------------------
# _normalize_image_for_canvas
# ---------------------------------------------------------------------------
class TestNormalizeImageForCanvas:
    def test_same_size(self):
        img = Image.new("RGB", (100, 100), "red")
        result = _normalize_image_for_canvas(img, 100, 100)
        assert result.size == (100, 100)

    def test_upscale_to_canvas(self):
        img = Image.new("RGB", (50, 50), "blue")
        result = _normalize_image_for_canvas(img, 200, 200)
        assert result.size == (200, 200)

    def test_maintains_aspect_ratio(self):
        img = Image.new("RGB", (100, 50), "green")
        result = _normalize_image_for_canvas(img, 200, 200)
        assert result.size == (200, 200)  # canvas size, not image size

    def test_zero_size_image(self):
        img = Image.new("RGB", (0, 0))
        result = _normalize_image_for_canvas(img, 100, 100)
        assert result.size == (100, 100)


# ---------------------------------------------------------------------------
# _reconstruct_text_from_frame
# ---------------------------------------------------------------------------
class TestReconstructTextFromFrame:
    def test_empty_frame(self):
        frame = pd.DataFrame()
        assert _reconstruct_text_from_frame(frame) == ""

    def test_no_text_column(self):
        frame = pd.DataFrame({"conf": [80, 90]})
        assert _reconstruct_text_from_frame(frame) == ""

    def test_single_line(self):
        frame = pd.DataFrame(
            {
                "text": ["Hello", "World"],
                "conf": [90, 85],
                "block_num": [1, 1],
                "par_num": [1, 1],
                "line_num": [1, 1],
            }
        )
        result = _reconstruct_text_from_frame(frame)
        assert result == "Hello World"

    def test_multi_line(self):
        frame = pd.DataFrame(
            {
                "text": ["Hello", "World"],
                "conf": [90, 85],
                "block_num": [1, 1],
                "par_num": [1, 1],
                "line_num": [1, 2],
            }
        )
        result = _reconstruct_text_from_frame(frame)
        assert "Hello" in result
        assert "World" in result
        assert "\n" in result

    def test_multi_block(self):
        frame = pd.DataFrame(
            {
                "text": ["Block1", "Block2"],
                "conf": [90, 85],
                "block_num": [1, 2],
                "par_num": [1, 1],
                "line_num": [1, 1],
            }
        )
        result = _reconstruct_text_from_frame(frame)
        assert "Block1" in result
        assert "Block2" in result

    def test_low_confidence_filtered(self):
        frame = pd.DataFrame(
            {
                "text": ["Good", "Bad"],
                "conf": [80, -1],
                "block_num": [1, 1],
                "par_num": [1, 1],
                "line_num": [1, 1],
            }
        )
        result = _reconstruct_text_from_frame(frame)
        assert "Good" in result
        assert "Bad" not in result

    def test_empty_text_skipped(self):
        frame = pd.DataFrame(
            {
                "text": ["Hello", "", " "],
                "conf": [90, 80, 80],
                "block_num": [1, 1, 1],
                "par_num": [1, 1, 1],
                "line_num": [1, 1, 1],
            }
        )
        result = _reconstruct_text_from_frame(frame)
        assert result == "Hello"
