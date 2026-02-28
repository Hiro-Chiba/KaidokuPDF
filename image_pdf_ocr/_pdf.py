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

from ._engine import _PDF_RENDER_DPI, _POINTS_PER_INCH
from ._environment import _find_japanese_font_path, find_and_set_tesseract_path
from ._exceptions import OCRCancelledError, OCRConversionError, PDFPasswordRemovalError
from ._parallel import _get_max_workers, run_parallel_ocr, run_parallel_ocr_with_text
from ._utils import _build_progress_message, _extract_coordinates, _prepare_output_path

# Decompression Bomb 対策: 200メガピクセルまで許可（デフォルト約178MP）
Image.MAX_IMAGE_PIXELS = 200_000_000


def _extract_page_images(
    doc: fitz.Document,
    start: int,
    end: int,
    cancel_event: Event | None,
) -> list[Image.Image]:
    """ドキュメントから指定範囲のページをPIL画像として抽出する。"""
    images: list[Image.Image] = []
    for page_idx in range(start, end):
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=_PDF_RENDER_DPI)
        with io.BytesIO(pix.tobytes("ppm")) as image_bytes:
            pil_image = Image.open(image_bytes)
            images.append(pil_image.copy())
            pil_image.close()
    return images


def _extract_page_images_with_meta(
    doc: fitz.Document,
    start: int,
    end: int,
    cancel_event: Event | None,
) -> tuple[list[Image.Image], list[fitz.Pixmap], list[fitz.Rect]]:
    """ドキュメントからページ画像+Pixmap+Rectを抽出する（PDF組み立て用）。"""
    images: list[Image.Image] = []
    pixmaps: list[fitz.Pixmap] = []
    page_rects: list[fitz.Rect] = []
    for page_idx in range(start, end):
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=_PDF_RENDER_DPI)
        pixmaps.append(pix)
        page_rects.append(page.rect)
        with io.BytesIO(pix.tobytes("ppm")) as image_bytes:
            pil_image = Image.open(image_bytes)
            images.append(pil_image.copy())
            pil_image.close()
    return images, pixmaps, page_rects


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

    def _dispatch_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)
        else:
            print(message, flush=True)

    def _check_cancellation() -> None:
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")

    try:
        with input_doc, fitz.open() as output_doc:
            total_pages = input_doc.page_count
            start_time = time.perf_counter()

            if total_pages == 0:
                _dispatch_progress("ページが存在しないPDFです。処理を終了します。")

            chunk_size = max(1, _get_max_workers())
            completed_pages = 0

            for chunk_start in range(0, total_pages, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_pages)

                # Phase A: チャンク分のページ画像抽出
                pil_images, pixmaps, page_rects = _extract_page_images_with_meta(
                    input_doc, chunk_start, chunk_end, cancel_event
                )

                # Phase B: チャンク分の並列OCR
                def _ocr_progress(completed: int, total: int, _base: int = completed_pages) -> None:
                    message = _build_progress_message(_base + completed, total_pages, start_time)
                    _dispatch_progress(message)

                ocr_results = run_parallel_ocr(
                    pil_images, cancel_event=cancel_event, progress_callback=_ocr_progress
                )
                completed_pages += len(pil_images)

                # Phase C: チャンク結果をPDF組み立て
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
                        x, y, h = _extract_coordinates(row)
                        if x is None or y is None or h is None:
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

                # チャンク処理完了後にメモリ解放
                del pil_images, pixmaps, page_rects, ocr_results

            _check_cancellation()

            try:
                output_doc.save(output_path, garbage=4, deflate=True, clean=True)
            except PermissionError as exc:
                raise OCRConversionError(
                    f"PDFを書き込めませんでした。権限を確認してください: {exc}"
                ) from exc
            except Exception as exc:  # pragma: no cover - save時のPyMuPDF例外
                raise OCRConversionError(f"PDFを保存できませんでした: {exc}") from exc
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
        resized = processed.resize(new_size, Image.LANCZOS)  # type: ignore[attr-defined]
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
        with fitz.open() as output_doc:
            width_pt = target_width * _POINTS_PER_INCH / _PDF_RENDER_DPI
            height_pt = target_height * _POINTS_PER_INCH / _PDF_RENDER_DPI
            page_rect = fitz.Rect(0, 0, width_pt, height_pt)
            coordinate_scale = _POINTS_PER_INCH / _PDF_RENDER_DPI

            chunk_size = max(1, _get_max_workers())
            completed_images = 0

            for chunk_start in range(0, total, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total)
                chunk_paths = normalized_paths[chunk_start:chunk_end]

                # Phase A: チャンク分の画像読み込み + 正規化
                prepared_images: list[Image.Image] = []
                for index, path in enumerate(chunk_paths, start=chunk_start + 1):
                    _check_cancellation()
                    with Image.open(path) as raw_image:
                        prepared_image = _normalize_image_for_canvas(
                            raw_image, target_width, target_height
                        )
                    _dispatch_preview(index, prepared_image.copy())
                    prepared_images.append(prepared_image)

                # Phase B: チャンク分の並列OCR
                def _ocr_progress(
                    completed: int, total_count: int, _base: int = completed_images
                ) -> None:
                    message = _build_progress_message(_base + completed, total, start_time)
                    _dispatch_progress(_base + completed, message)

                ocr_results = run_parallel_ocr(
                    prepared_images, cancel_event=cancel_event, progress_callback=_ocr_progress
                )
                completed_images += len(prepared_images)

                # Phase C: チャンク結果をPDF組み立て
                for (_ocr_result, filtered_rows), prepared_image in zip(
                    ocr_results, prepared_images, strict=True
                ):
                    _check_cancellation()
                    page = output_doc.new_page(width=width_pt, height=height_pt)

                    with io.BytesIO() as image_buffer:
                        prepared_image.save(image_buffer, format="PPM")
                        page.insert_image(page_rect, stream=image_buffer.getvalue())

                    for row in filtered_rows:
                        text_val = str(row.get("text", "")).strip()
                        if not text_val:
                            continue
                        x, y, h = _extract_coordinates(row)
                        if x is None or y is None or h is None:
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

                # チャンク処理完了後にメモリ解放
                del prepared_images, ocr_results

            _check_cancellation()
            output_doc.save(output_path, garbage=4, deflate=True, clean=True)
    except OCRCancelledError:
        raise
    except PermissionError as exc:
        raise OCRConversionError(
            f"PDFを書き込めませんでした。権限を確認してください: {exc}"
        ) from exc
    except pytesseract.TesseractError as exc:
        raise OCRConversionError(
            f"OCR処理に失敗しました: {exc}\n"
            "対処法: Tesseractのインストールと日本語データ(jpn)を確認してください。"
        ) from exc
    except Exception as exc:
        raise OCRConversionError(f"画像からPDFを生成中に問題が発生しました: {exc}") from exc


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

    def _dispatch_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)
        else:
            print(message, flush=True)

    def _check_cancellation() -> None:
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")

    try:
        with document:
            texts: list[str] = []
            total_pages = document.page_count
            start_time = time.perf_counter()

            if total_pages == 0:
                _dispatch_progress("ページが存在しないPDFです。処理を終了します。")
                return "\n"

            chunk_size = max(1, _get_max_workers())
            completed_pages = 0
            page_index = 0

            for chunk_start in range(0, total_pages, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_pages)

                # Phase A: チャンク分のページ画像抽出
                pil_images = _extract_page_images(document, chunk_start, chunk_end, cancel_event)

                # Phase B: チャンク分の並列OCR + テキスト抽出
                def _ocr_progress(completed: int, total: int, _base: int = completed_pages) -> None:
                    message = _build_progress_message(_base + completed, total_pages, start_time)
                    _dispatch_progress(message)

                ocr_results = run_parallel_ocr_with_text(
                    pil_images, cancel_event=cancel_event, progress_callback=_ocr_progress
                )
                completed_pages += len(pil_images)

                # Phase C: ページ順にテキスト結合
                for _ocr_result, page_text in ocr_results:
                    page_index += 1
                    texts.append(f"--- ページ {page_index} ---\n{page_text.strip()}\n")

                del pil_images, ocr_results

        _check_cancellation()

        return "\n".join(texts).strip() + "\n"
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
