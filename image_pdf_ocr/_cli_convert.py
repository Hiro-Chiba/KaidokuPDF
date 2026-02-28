"""画像PDFを検索可能なPDFに変換するCLI。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._exceptions import OCRConversionError
from ._pdf import create_searchable_pdf
from ._version import _get_version


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

    if args.output_path.exists() and sys.stdin.isatty():
        answer = input(f"{args.output_path} は既に存在します。上書きしますか？ [y/N]: ")
        if answer.lower() not in ("y", "yes"):
            print("中止しました。", file=sys.stderr)
            sys.exit(1)

    def _progress(message: str) -> None:
        if sys.stdout.isatty():
            print(f"\r{message}", end="", flush=True)
        else:
            print(message, flush=True)

    try:
        create_searchable_pdf(args.input_path, args.output_path, progress_callback=_progress)
    except FileNotFoundError as exc:
        print(f"\nエラー: ファイルが見つかりません: {exc}", file=sys.stderr)
        sys.exit(1)
    except OCRConversionError as exc:
        print(f"\nエラー: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print(f"完了: {args.output_path}")


if __name__ == "__main__":
    main()
