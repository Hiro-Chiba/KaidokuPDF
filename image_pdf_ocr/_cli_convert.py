"""画像PDFを検索可能なPDFに変換するCLI。"""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path

from ._exceptions import OCRConversionError
from ._pdf import create_searchable_pdf


def _get_version() -> str:
    try:
        return importlib.metadata.version("kaidoku-pdf")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "dev"


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="画像ベースのPDFをOCRして検索可能なPDFを作成します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "--input_path",
        dest="input_path",
        type=Path,
        required=True,
        help="OCR対象のPDFファイル。例: C:/scans/document.pdf",
    )
    parser.add_argument(
        "--output",
        "--output_path",
        dest="output_path",
        type=Path,
        required=True,
        help="生成する検索可能PDFの保存先。例: C:/scans/document_searchable.pdf",
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
        create_searchable_pdf(args.input_path, args.output_path, progress_callback=_progress)
    except FileNotFoundError as exc:
        parser.error(f"ファイルが見つかりません: {exc}")
    except OCRConversionError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
