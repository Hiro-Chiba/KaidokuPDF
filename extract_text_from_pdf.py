"""画像PDFからテキストだけを抽出するCLI。"""

from __future__ import annotations

import argparse
from pathlib import Path

from image_pdf_ocr import OCRConversionError, extract_text_to_file


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="画像ベースのPDFをOCRしてテキストファイルに保存します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--pdf_path",
        type=Path,
        required=True,
        help="テキストを抽出したいPDF。例: C:/Users/YourUser/Documents/scan.pdf",
    )
    parser.add_argument(
        "--output_path",
        type=Path,
        required=True,
        help="抽出結果を保存するテキストファイル。例: C:/Users/YourUser/Documents/output.txt",
    )
    return parser


def _run_extraction(pdf_path: Path, output_path: Path) -> None:
    extract_text_to_file(pdf_path, output_path)


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    try:
        _run_extraction(args.pdf_path, args.output_path)
    except FileNotFoundError as exc:
        parser.error(f"ファイルが見つかりません: {exc}")
    except OCRConversionError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
