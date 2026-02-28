"""CLIモジュールのユニットテスト。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from image_pdf_ocr._cli_convert import _create_parser as create_convert_parser
from image_pdf_ocr._cli_convert import main as convert_main
from image_pdf_ocr._cli_extract import _create_parser as create_extract_parser
from image_pdf_ocr._cli_extract import main as extract_main
from image_pdf_ocr._version import _get_version


class TestGetVersion:
    def test_returns_string(self):
        version = _get_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_returns_dev_when_not_installed(self):
        import importlib.metadata

        with patch(
            "image_pdf_ocr._version.importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("kaidoku-pdf"),
        ):
            version = _get_version()
            assert version == "dev"


class TestConvertParser:
    def test_parses_input_output(self, tmp_path):
        parser = create_convert_parser()
        args = parser.parse_args(["--input", "in.pdf", "--output", "out.pdf"])
        assert str(args.input_path) == "in.pdf"
        assert str(args.output_path) == "out.pdf"

    def test_parses_legacy_input_path(self):
        parser = create_convert_parser()
        args = parser.parse_args(["--input_path", "in.pdf", "--output_path", "out.pdf"])
        assert str(args.input_path) == "in.pdf"
        assert str(args.output_path) == "out.pdf"

    def test_version_flag(self, capsys):
        parser = create_convert_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_missing_required_args(self):
        parser = create_convert_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        assert exc_info.value.code != 0


class TestExtractParser:
    def test_parses_input_output(self):
        parser = create_extract_parser()
        args = parser.parse_args(["--input", "in.pdf", "--output", "out.txt"])
        assert str(args.input_path) == "in.pdf"
        assert str(args.output_path) == "out.txt"

    def test_parses_legacy_pdf_path(self):
        parser = create_extract_parser()
        args = parser.parse_args(["--pdf_path", "in.pdf", "--output_path", "out.txt"])
        assert str(args.input_path) == "in.pdf"
        assert str(args.output_path) == "out.txt"

    def test_version_flag(self, capsys):
        parser = create_extract_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0


class TestConvertMainOverwrite:
    def test_overwrite_prompt_decline(self, tmp_path):
        existing = tmp_path / "output.pdf"
        existing.write_text("dummy")
        with (
            patch("sys.argv", ["prog", "--input", "in.pdf", "--output", str(existing)]),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input", return_value="n"),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_stdin.isatty.return_value = True
            convert_main()
        assert exc_info.value.code == 1

    def test_overwrite_prompt_accept(self, tmp_path):
        existing = tmp_path / "output.pdf"
        existing.write_text("dummy")
        with (
            patch(
                "sys.argv", ["prog", "--input", str(tmp_path / "in.pdf"), "--output", str(existing)]
            ),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input", return_value="y"),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_stdin.isatty.return_value = True
            convert_main()
        # FileNotFoundError → sys.exit(1)
        assert exc_info.value.code == 1


class TestExtractMainOverwrite:
    def test_overwrite_prompt_decline(self, tmp_path):
        existing = tmp_path / "output.txt"
        existing.write_text("dummy")
        with (
            patch("sys.argv", ["prog", "--input", "in.pdf", "--output", str(existing)]),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input", return_value="n"),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_stdin.isatty.return_value = True
            extract_main()
        assert exc_info.value.code == 1

    def test_overwrite_prompt_accept(self, tmp_path):
        existing = tmp_path / "output.txt"
        existing.write_text("dummy")
        with (
            patch(
                "sys.argv",
                ["prog", "--input", str(tmp_path / "in.pdf"), "--output", str(existing)],
            ),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input", return_value="y"),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_stdin.isatty.return_value = True
            extract_main()
        # FileNotFoundError → sys.exit(1)
        assert exc_info.value.code == 1


class TestConvertMainNonTTY:
    def test_no_prompt_when_not_tty(self, tmp_path):
        """非TTY時は上書き確認をスキップしてそのまま処理に進む。"""
        existing = tmp_path / "output.pdf"
        existing.write_text("dummy")
        with (
            patch(
                "sys.argv",
                ["prog", "--input", str(tmp_path / "in.pdf"), "--output", str(existing)],
            ),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input") as mock_input,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_stdin.isatty.return_value = False
            convert_main()
        # 上書き確認なしで処理に進む（FileNotFoundError → exit(1)）
        mock_input.assert_not_called()
        assert exc_info.value.code == 1


class TestExtractMainNonTTY:
    def test_no_prompt_when_not_tty(self, tmp_path):
        """非TTY時は上書き確認をスキップしてそのまま処理に進む。"""
        existing = tmp_path / "output.txt"
        existing.write_text("dummy")
        with (
            patch(
                "sys.argv",
                ["prog", "--input", str(tmp_path / "in.pdf"), "--output", str(existing)],
            ),
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input") as mock_input,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_stdin.isatty.return_value = False
            extract_main()
        mock_input.assert_not_called()
        assert exc_info.value.code == 1


class TestConvertMainErrors:
    def test_file_not_found_error(self, tmp_path, capsys):
        """FileNotFoundError時にstderrにメッセージが出力される。"""
        with (
            patch(
                "sys.argv",
                [
                    "prog",
                    "--input",
                    str(tmp_path / "missing.pdf"),
                    "--output",
                    str(tmp_path / "out.pdf"),
                ],
            ),
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(SystemExit) as exc_info,
        ):
            convert_main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "ファイルが見つかりません" in captured.err


class TestExtractMainErrors:
    def test_file_not_found_error(self, tmp_path, capsys):
        """FileNotFoundError時にstderrにメッセージが出力される。"""
        with (
            patch(
                "sys.argv",
                [
                    "prog",
                    "--input",
                    str(tmp_path / "missing.pdf"),
                    "--output",
                    str(tmp_path / "out.txt"),
                ],
            ),
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(SystemExit) as exc_info,
        ):
            extract_main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "ファイルが見つかりません" in captured.err
