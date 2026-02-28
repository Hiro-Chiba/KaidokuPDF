"""PDF作成・テキスト抽出・パスワード解除を担うモジュール。"""

from __future__ import annotations

import io
import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import Event

import fitz  # type: ignore
import pytesseract
from PIL import Image, ImageOps

from ._environment import _find_japanese_font_path, find_and_set_tesseract_path
from ._exceptions import OCRCancelledError, OCRConversionError, PDFPasswordRemovalError
from ._parallel import run_parallel_ocr, run_parallel_ocr_with_text
from ._utils import _build_progress_message, _prepare_output_path


def remove_pdf_password(
    input_path: str | Path,
    output_path: str | Path,
    password: str,
) -> None:
    """パスワード保護されたPDFからパスワードを解除して保存する。

    Args:
        input_path: 入力となるパスワード付きPDFファイルのパス。
        output_path: パスワードを解除したPDFを書き出すパス。
        password: PDFを開くためのパスワード。

    Raises:
        FileNotFoundError: 入力ファイルが存在しない場合。
        ValueError: 入力ファイルと出力ファイルのパスが同一の場合。
        PDFPasswordRemovalError: パスワード解除に失敗した場合。
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"入力PDFが見つかりません: {input_path}")

    if input_path.resolve() == output_path.resolve():
        raise ValueError("入力と同じ場所には保存できません。保存先を変更してください。")

    with fitz.open(str(input_path)) as doc:  # type: ignore[arg-type]
        if not doc.is_encrypted:
            raise PDFPasswordRemovalError("指定されたPDFはパスワードで保護されていません。")

        if not password:
            raise PDFPasswordRemovalError("パスワードを入力してください。")

        if not doc.authenticate(password):
            raise PDFPasswordRemovalError("パスワードが正しくありません。")

        if output_path.parent and not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            doc.save(str(output_path), encryption=fitz.PDF_ENCRYPT_NONE)
        except RuntimeError as exc:
            raise PDFPasswordRemovalError(f"PDFの保存に失敗しました: {exc}") from exc


def create_searchable_pdf(
    input_path: str | os.PathLike,
    output_path: str | os.PathLike,
    progress_callback: Callable[[str], None] | None = None,
    cancel_event: Event | None = None,
) -> None:
    """画像PDFをOCRして検索可能なPDFを生成する。"""
    if not find_and_set_tesseract_path():
        raise OCRConversionError(
            "Tesseract-OCRが見つかりません。インストールとPATH設定を確認してください。"
        )

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    _prepare_output_path(output_path)

    font_path = _find_japanese_font_path()

    try:
        input_doc = fitz.open(input_path)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - PyMuPDF例外
        raise OCRConversionError(f"PDFファイルを開けませんでした: {exc}") from exc

    output_doc = fitz.open()

    total_pages = input_doc.page_count
    start_time = time.perf_counter()

    def _dispatch_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)
        else:
            print(message, flush=True)

    if total_pages == 0:
        _dispatch_progress("ページが存在しないPDFです。処理を終了します。")

    def _check_cancellation() -> None:
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")

    try:
        # Phase A: 全ページの画像抽出（メインプロセス）
        pil_images: list[Image.Image] = []
        pixmaps: list[fitz.Pixmap] = []
        page_rects: list[fitz.Rect] = []

        for page in input_doc:
            _check_cancellation()
            pix = page.get_pixmap(dpi=300)
            pixmaps.append(pix)
            page_rects.append(page.rect)
            image_bytes = io.BytesIO(pix.tobytes("ppm"))
            pil_image = Image.open(image_bytes)
            pil_images.append(pil_image.copy())
            pil_image.close()

        input_doc.close()

        # Phase B: 並列OCR
        def _ocr_progress(completed: int, total: int) -> None:
            message = _build_progress_message(completed, total_pages, start_time)
            _dispatch_progress(message)

        ocr_results = run_parallel_ocr(
            pil_images, cancel_event=cancel_event, progress_callback=_ocr_progress
        )

        # Phase C: 結果をページ順にPDF組み立て（メインプロセス）
        for (_ocr_result, filtered_rows), pix, rect in zip(
            ocr_results, pixmaps, page_rects, strict=True
        ):
            _check_cancellation()
            new_page = output_doc.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, pixmap=pix)

            for row in filtered_rows:
                text_val = str(row.get("text", "")).strip()
                if not text_val:
                    continue
                x = row.get("left")
                y = row.get("top")
                h = row.get("height")
                if x is None or y is None or h is None:
                    continue
                try:
                    x, y, h = float(x), float(y), float(h)
                except (TypeError, ValueError):
                    continue
                try:
                    new_page.insert_text(
                        (x, y + h),
                        text_val,
                        fontfile=str(font_path),
                        fontsize=h * 0.8,
                        render_mode=3,
                    )
                except RuntimeError:
                    continue
    except OCRCancelledError:
        raise
    except (fitz.FileDataError, fitz.FileNotFoundError) as exc:
        raise OCRConversionError(
            f"PDFの読み取りに失敗しました: {exc}\n"
            "対処法: PDFファイルが破損していないか確認してください。"
        ) from exc
    except pytesseract.TesseractError as exc:
        raise OCRConversionError(
            f"OCR処理に失敗しました: {exc}\n"
            "対処法: Tesseractのインストールと日本語データ(jpn)を確認してください。"
        ) from exc
    except Exception as exc:
        raise OCRConversionError(f"ページ処理中に予期しない問題が発生しました: {exc}") from exc

    _check_cancellation()

    try:
        output_doc.save(output_path, garbage=4, deflate=True, clean=True)
    except PermissionError as exc:
        raise OCRConversionError(
            f"PDFを書き込めませんでした。権限を確認してください: {exc}"
        ) from exc
    except Exception as exc:  # pragma: no cover - save時のPyMuPDF例外
        raise OCRConversionError(f"PDFを保存できませんでした: {exc}") from exc
    finally:
        output_doc.close()


def _determine_canvas_size(image_paths: Sequence[Path]) -> tuple[int, int]:
    """指定した画像群を収めるキャンバスサイズを決定する。"""

    max_width = 0
    max_height = 0

    for path in image_paths:
        try:
            with Image.open(path) as image:
                normalized = ImageOps.exif_transpose(image)
                width, height = normalized.size
        except UnboundLocalError:  # pragma: no cover - Pillow internal edge case
            continue
        except Image.UnidentifiedImageError as exc:
            raise OCRConversionError(
                f"画像を読み込めませんでした: {path} ({exc})\n"
                "対処法: 対応形式(JPEG/PNG/TIFF/BMP)の画像ファイルか確認してください。"
            ) from exc
        except Exception as exc:
            raise OCRConversionError(f"画像を読み込めませんでした: {path} ({exc})") from exc

        max_width = max(max_width, width)
        max_height = max(max_height, height)

    if max_width <= 0 or max_height <= 0:
        raise ValueError("有効な画像サイズを取得できませんでした。")

    return max_width, max_height


def _normalize_image_for_canvas(
    image: Image.Image, target_width: int, target_height: int
) -> Image.Image:
    """キャンバスに合わせて余白付きで画像を整形する。"""

    processed = ImageOps.exif_transpose(image)
    processed = processed.convert("RGB")

    width, height = processed.size
    if width <= 0 or height <= 0:
        return Image.new("RGB", (target_width, target_height), "white")

    scale = min(target_width / width, target_height / height)
    if scale <= 0:
        scale = 1.0

    new_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )

    if new_size != (width, height):
        resized = processed.resize(new_size, Image.LANCZOS)
    else:
        resized = processed

    canvas = Image.new("RGB", (target_width, target_height), "white")
    offset = (
        max((target_width - resized.width) // 2, 0),
        max((target_height - resized.height) // 2, 0),
    )
    canvas.paste(resized, offset)
    return canvas


def create_searchable_pdf_from_images(
    image_paths: Sequence[str | os.PathLike],
    output_path: str | os.PathLike,
    progress_callback: Callable[[int, int, str], None] | None = None,
    preview_callback: Callable[[int, int, Image.Image], None] | None = None,
    cancel_event: Event | None = None,
) -> None:
    """複数の画像から検索可能なPDFを生成する。"""

    if not find_and_set_tesseract_path():
        raise OCRConversionError(
            "Tesseract-OCRが見つかりません。インストールとPATH設定を確認してください。"
        )

    if not image_paths:
        raise OCRConversionError("入力する画像ファイルを1つ以上選択してください。")

    normalized_paths = [Path(path) for path in image_paths]
    for path in normalized_paths:
        if not path.exists():
            raise FileNotFoundError(f"入力画像が見つかりません: {path}")

    output_path = Path(output_path)
    if output_path.suffix.lower() != ".pdf":
        raise OCRConversionError("出力ファイルには.pdf拡張子を指定してください。")

    _prepare_output_path(output_path)

    font_path = _find_japanese_font_path()

    try:
        target_width, target_height = _determine_canvas_size(normalized_paths)
    except ValueError as exc:
        raise OCRConversionError(str(exc)) from exc

    output_doc = fitz.open()
    total = len(normalized_paths)
    start_time = time.perf_counter()

    def _dispatch_progress(current: int, message: str) -> None:
        if progress_callback:
            progress_callback(current, total, message)
        else:
            print(message, flush=True)

    def _dispatch_preview(current: int, image: Image.Image) -> None:
        if preview_callback:
            preview_callback(current, total, image)

    def _check_cancellation() -> None:
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")

    try:
        # Phase A: 画像読み込み + 正規化（メインプロセス）
        prepared_images: list[Image.Image] = []
        for index, path in enumerate(normalized_paths, start=1):
            _check_cancellation()
            with Image.open(path) as raw_image:
                prepared_image = _normalize_image_for_canvas(raw_image, target_width, target_height)
            _dispatch_preview(index, prepared_image.copy())
            prepared_images.append(prepared_image)

        # Phase B: 並列OCR
        def _ocr_progress(completed: int, total_count: int) -> None:
            message = _build_progress_message(completed, total, start_time)
            _dispatch_progress(completed, message)

        ocr_results = run_parallel_ocr(
            prepared_images, cancel_event=cancel_event, progress_callback=_ocr_progress
        )

        # Phase C: 結果をページ順にPDF組み立て（メインプロセス）
        dpi = 300
        width_pt = target_width * 72 / dpi
        height_pt = target_height * 72 / dpi
        page_rect = fitz.Rect(0, 0, width_pt, height_pt)
        coordinate_scale = 72 / dpi

        for (_ocr_result, filtered_rows), prepared_image in zip(
            ocr_results, prepared_images, strict=True
        ):
            _check_cancellation()
            page = output_doc.new_page(width=width_pt, height=height_pt)

            image_buffer = io.BytesIO()
            prepared_image.save(image_buffer, format="PNG")
            page.insert_image(page_rect, stream=image_buffer.getvalue())

            for row in filtered_rows:
                text_val = str(row.get("text", "")).strip()
                if not text_val:
                    continue
                x = row.get("left")
                y = row.get("top")
                h = row.get("height")
                if x is None or y is None or h is None:
                    continue
                try:
                    x, y, h = float(x), float(y), float(h)
                except (TypeError, ValueError):
                    continue
                try:
                    page.insert_text(
                        (x * coordinate_scale, (y + h) * coordinate_scale),
                        text_val,
                        fontfile=str(font_path),
                        fontsize=h * coordinate_scale * 0.8,
                        render_mode=3,
                    )
                except RuntimeError:
                    continue

        _check_cancellation()
        output_doc.save(output_path, garbage=4, deflate=True, clean=True)
    except OCRCancelledError:
        output_doc.close()
        raise
    except PermissionError as exc:
        output_doc.close()
        raise OCRConversionError(
            f"PDFを書き込めませんでした。権限を確認してください: {exc}"
        ) from exc
    except pytesseract.TesseractError as exc:
        output_doc.close()
        raise OCRConversionError(
            f"OCR処理に失敗しました: {exc}\n"
            "対処法: Tesseractのインストールと日本語データ(jpn)を確認してください。"
        ) from exc
    except Exception as exc:
        output_doc.close()
        raise OCRConversionError(f"画像からPDFを生成中に問題が発生しました: {exc}") from exc
    else:
        output_doc.close()


def extract_text_from_image_pdf(
    input_path: str | os.PathLike,
    progress_callback: Callable[[str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """画像ベースのPDFからOCRでテキストを抽出して返す。"""

    if not find_and_set_tesseract_path():
        raise OCRConversionError(
            "Tesseract-OCRが見つかりません。インストールとPATH設定を確認してください。"
        )

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    try:
        document = fitz.open(input_path)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - PyMuPDF例外
        raise OCRConversionError(f"PDFファイルを開けませんでした: {exc}") from exc

    texts: list[str] = []
    total_pages = document.page_count
    start_time = time.perf_counter()

    def _dispatch_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)
        else:
            print(message, flush=True)

    if total_pages == 0:
        _dispatch_progress("ページが存在しないPDFです。処理を終了します。")
        document.close()
        return "\n"

    def _check_cancellation() -> None:
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")

    try:
        # Phase A: 全ページの画像抽出（メインプロセス）
        pil_images: list[Image.Image] = []
        for page in document:
            _check_cancellation()
            pix = page.get_pixmap(dpi=300)
            image_bytes = io.BytesIO(pix.tobytes("ppm"))
            pil_image = Image.open(image_bytes)
            pil_images.append(pil_image.copy())
            pil_image.close()

        document.close()

        # Phase B: 並列OCR + テキスト抽出
        def _ocr_progress(completed: int, total: int) -> None:
            message = _build_progress_message(completed, total_pages, start_time)
            _dispatch_progress(message)

        ocr_results = run_parallel_ocr_with_text(
            pil_images, cancel_event=cancel_event, progress_callback=_ocr_progress
        )

        # Phase C: ページ順にテキスト結合
        for index, (_ocr_result, page_text) in enumerate(ocr_results, start=1):
            texts.append(f"--- ページ {index} ---\n{page_text.strip()}\n")
    except OCRCancelledError:
        raise
    except (fitz.FileDataError, fitz.FileNotFoundError) as exc:
        raise OCRConversionError(
            f"PDFの読み取りに失敗しました: {exc}\n"
            "対処法: PDFファイルが破損していないか確認してください。"
        ) from exc
    except pytesseract.TesseractError as exc:
        raise OCRConversionError(
            f"OCR処理に失敗しました: {exc}\n"
            "対処法: Tesseractのインストールと日本語データ(jpn)を確認してください。"
        ) from exc
    except Exception as exc:
        raise OCRConversionError(f"テキスト抽出中に予期しない問題が発生しました: {exc}") from exc

    _check_cancellation()

    return "\n".join(texts).strip() + "\n"


def extract_text_to_file(
    input_path: str | os.PathLike,
    output_path: str | os.PathLike,
    progress_callback: Callable[[str], None] | None = None,
    cancel_event: Event | None = None,
) -> None:
    """画像PDFから抽出したテキストをファイルに保存する。"""

    text = extract_text_from_image_pdf(
        input_path,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
    )
    output_path = Path(output_path)
    _prepare_output_path(output_path)

    if cancel_event and cancel_event.is_set():
        raise OCRCancelledError("処理がキャンセルされました。")

    try:
        output_path.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        raise OCRConversionError(
            f"テキストを書き込めませんでした。権限を確認してください: {exc}"
        ) from exc
    except OSError as exc:
        raise OCRConversionError(f"テキストファイルを保存できませんでした: {exc}") from exc
