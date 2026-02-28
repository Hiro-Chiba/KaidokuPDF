"""画像PDFからテキストだけを抽出するCLI。"""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path

from ._exceptions import OCRConversionError
from ._pdf import extract_text_to_file


def _get_version() -> str:
    try:
        return importlib.metadata.version("kaidoku-pdf")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "dev"


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="画像ベースのPDFをOCRしてテキストファイルに保存します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "--input_path",
        "--pdf_path",
        dest="input_path",
        type=Path,
        required=True,
        help="テキストを抽出したいPDF。例: C:/Users/YourUser/Documents/scan.pdf",
    )
    parser.add_argument(
        "--output",
        "--output_path",
        dest="output_path",
        type=Path,
        required=True,
        help="抽出結果を保存するテキストファイル。例: C:/Users/YourUser/Documents/output.txt",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    def _progress(message: str) -> None:
        print(message, flush=True)

    try:
        extract_text_to_file(args.input_path, args.output_path, progress_callback=_progress)
    except FileNotFoundError as exc:
        parser.error(f"ファイルが見つかりません: {exc}")
    except OCRConversionError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
