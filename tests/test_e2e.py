"""E2Eテスト — CLIスクリプトをサブプロセスで実行。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .conftest import requires_tesseract

_REPO_ROOT = Path(__file__).resolve().parent.parent


@requires_tesseract
class TestConvertToSearchablePdfCli:
    def test_successful_conversion(self, tmp_path, sample_image_pdf):
        output = tmp_path / "cli_output.pdf"
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "convert_to_searchable_pdf.py"),
                "--input",
                str(sample_image_pdf),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert output.exists()


@requires_tesseract
class TestExtractTextFromPdfCli:
    def test_successful_extraction(self, tmp_path, sample_image_pdf):
        output = tmp_path / "cli_extracted.txt"
        result = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "extract_text_from_pdf.py"),
                "--input",
                str(sample_image_pdf),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert len(content) > 0


def test_convert_missing_input_file(tmp_path):
    """Tesseract不要 — 存在しないファイル指定時のエラーテスト。"""
    output = tmp_path / "cli_output.pdf"
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "convert_to_searchable_pdf.py"),
            "--input",
            str(tmp_path / "nonexistent.pdf"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0


def test_extract_missing_input_file(tmp_path):
    """Tesseract不要 — 存在しないファイル指定時のエラーテスト。"""
    output = tmp_path / "cli_extracted.txt"
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "extract_text_from_pdf.py"),
            "--input",
            str(tmp_path / "nonexistent.pdf"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
