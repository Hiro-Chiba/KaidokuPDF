"""画像PDFを検索可能なPDFに変換するシンプルなCLI。"""

from __future__ import annotations

import argparse
from pathlib import Path

from image_pdf_ocr import OCRConversionError, create_searchable_pdf


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="画像ベースのPDFをOCRして検索可能なPDFを作成します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--input_path",
        type=Path,
        required=True,
        help="OCR対象のPDFファイル。例: C:/scans/document.pdf",
    )
    parser.add_argument(
        "--output_path",
        type=Path,
        required=True,
        help="生成する検索可能PDFの保存先。例: C:/scans/document_searchable.pdf",
    )
    return parser


def _run_conversion(input_path: Path, output_path: Path) -> None:
    create_searchable_pdf(input_path, output_path)


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    try:
        _run_conversion(args.input_path, args.output_path)
    except FileNotFoundError as exc:
        parser.error(f"ファイルが見つかりません: {exc}")
    except OCRConversionError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
