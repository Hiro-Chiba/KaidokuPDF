"""テスト共通の設定とフィクスチャ。"""

from __future__ import annotations

import io
import shutil

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont


def _has_tesseract() -> bool:
    return shutil.which("tesseract") is not None


requires_tesseract = pytest.mark.skipif(
    not _has_tesseract(),
    reason="Tesseractがインストールされていません",
)


@pytest.fixture()
def sample_image_with_text(tmp_path):
    """PILで 'Hello World 12345' を描画したPNG画像を生成する。"""
    img = Image.new("RGB", (800, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((50, 50), "Hello World 12345", fill="black", font=font)
    path = tmp_path / "sample_text.png"
    img.save(str(path))
    return path


@pytest.fixture()
def sample_image_pdf(tmp_path, sample_image_with_text):
    """テキスト画像を埋め込んだ1ページPDFを生成する。"""
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, filename=str(sample_image_with_text))
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def sample_multi_page_pdf(tmp_path):
    """3ページの画像PDFを生成する。"""
    pdf_path = tmp_path / "multi_page.pdf"
    doc = fitz.open()
    for i in range(3):
        img = Image.new("RGB", (400, 200), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
        draw.text((50, 50), f"Page {i + 1}", fill="black", font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")

        page = doc.new_page(width=400, height=200)
        page.insert_image(page.rect, stream=buf.getvalue())

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def sample_images(tmp_path):
    """複数PNG画像のリストを生成する。"""
    paths = []
    for i in range(3):
        img = Image.new("RGB", (400, 200), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
        draw.text((50, 50), f"Image {i + 1}", fill="black", font=font)
        path = tmp_path / f"image_{i}.png"
        img.save(str(path))
        paths.append(path)
    return paths
