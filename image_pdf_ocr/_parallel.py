"""ProcessPoolExecutor を用いた並列OCR実行モジュール。"""

from __future__ import annotations

import io
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from threading import Event

import pandas as pd
from PIL import Image

from ._engine import (
    _TEXT_RENDER_CONFIDENCE_THRESHOLD,
    AdaptiveOCRResult,
    _filter_frame_by_confidence,
    _perform_adaptive_ocr,
)
from ._environment import find_and_set_tesseract_path
from ._exceptions import OCRCancelledError


def _get_max_workers() -> int:
    """ワーカー数を環境変数またはデフォルト（CPUコア数//2, 最低1）から取得する。"""
    env_value = os.environ.get("KAIDOKU_OCR_WORKERS")
    if env_value is not None:
        try:
            n = int(env_value)
            return max(1, n)
        except ValueError:
            pass
    cpu_count = os.cpu_count() or 2
    return max(1, cpu_count // 2)


def _is_parallel_enabled() -> bool:
    """並列処理が有効かどうかを判定する。"""
    return os.environ.get("KAIDOKU_PARALLEL", "1") != "0"


def _worker_initializer() -> None:
    """各ワーカープロセスでTesseractパスを設定する。"""
    find_and_set_tesseract_path()


def _ocr_worker(image: Image.Image) -> tuple[AdaptiveOCRResult, list[dict]]:
    """単一画像に対してOCR + 信頼度フィルタリングを実行する。

    Returns:
        (ocr_result, filtered_rows) のタプル。
        filtered_rows は DataFrame.to_dict("records") の結果。
    """
    ocr_result = _perform_adaptive_ocr(image)
    filtered = _filter_frame_by_confidence(ocr_result.frame, _TEXT_RENDER_CONFIDENCE_THRESHOLD)
    return ocr_result, filtered.to_dict("records")


def _reconstruct_text_from_frame(frame: pd.DataFrame) -> str:
    """OCR結果のDataFrameからテキストを再構築する。

    block_num/par_num/line_num の変化でブロック・段落・行の区切りを判定し、
    適切な改行を挿入する。
    """
    if frame.empty or "text" not in frame.columns:
        return ""

    lines: list[str] = []
    current_line_words: list[str] = []
    prev_block = -1
    prev_par = -1
    prev_line = -1

    for row in frame.itertuples(index=False):
        text_val = str(getattr(row, "text", "")).strip()
        conf = getattr(row, "conf", -1)
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0 or not text_val:
            continue

        block = getattr(row, "block_num", -1)
        par = getattr(row, "par_num", -1)
        line = getattr(row, "line_num", -1)

        if prev_block != -1 and (block != prev_block or par != prev_par):
            if current_line_words:
                lines.append(" ".join(current_line_words))
                current_line_words = []
            lines.append("")  # blank line between blocks/paragraphs
        elif prev_line != -1 and line != prev_line:
            if current_line_words:
                lines.append(" ".join(current_line_words))
                current_line_words = []

        current_line_words.append(text_val)
        prev_block = block
        prev_par = par
        prev_line = line

    if current_line_words:
        lines.append(" ".join(current_line_words))

    return "\n".join(lines)


def _ocr_worker_bytes(image_data: bytes) -> tuple[AdaptiveOCRResult, list[dict]]:
    """バイト列から画像を復元してOCR + 信頼度フィルタリングを実行する。"""
    with io.BytesIO(image_data) as buf:
        image = Image.open(buf)
        return _ocr_worker(image)


def _ocr_worker_with_text_bytes(image_data: bytes) -> tuple[AdaptiveOCRResult, str]:
    """バイト列から画像を復元してOCR + テキスト抽出を実行する。"""
    with io.BytesIO(image_data) as buf:
        image = Image.open(buf)
        return _ocr_worker_with_text(image)


def _ocr_worker_with_text(image: Image.Image) -> tuple[AdaptiveOCRResult, str]:
    """OCR + テキスト抽出を実行する。

    image_to_data の結果からテキストを再構築することで、
    二重OCR（image_to_data + image_to_string）を排除する。

    Returns:
        (ocr_result, page_text) のタプル。
    """
    ocr_result = _perform_adaptive_ocr(image)
    page_text = _reconstruct_text_from_frame(ocr_result.frame)
    return ocr_result, page_text


def run_parallel_ocr(
    images: list[Image.Image],
    cancel_event: Event | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[tuple[AdaptiveOCRResult, list[dict]]]:
    """複数画像に対して並列OCRを実行する。

    Args:
        images: OCR対象の画像リスト。
        cancel_event: キャンセル用イベント。
        progress_callback: (completed_count, total) を受け取るコールバック。

    Returns:
        ページ順に並んだ (ocr_result, filtered_rows) のリスト。
    """
    total = len(images)
    if total == 0:
        return []

    use_parallel = _is_parallel_enabled() and total > 1

    if not use_parallel:
        return _run_sequential(images, _ocr_worker, cancel_event, progress_callback)

    try:
        return _run_with_pool(images, _ocr_worker, cancel_event, progress_callback)
    except (OSError, RuntimeError):
        return _run_sequential(images, _ocr_worker, cancel_event, progress_callback)


def run_parallel_ocr_with_text(
    images: list[Image.Image],
    cancel_event: Event | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[tuple[AdaptiveOCRResult, str]]:
    """複数画像に対して並列OCR+テキスト抽出を実行する。

    Returns:
        ページ順に並んだ (ocr_result, page_text) のリスト。
    """
    total = len(images)
    if total == 0:
        return []

    use_parallel = _is_parallel_enabled() and total > 1

    if not use_parallel:
        return _run_sequential(images, _ocr_worker_with_text, cancel_event, progress_callback)

    try:
        return _run_with_pool(images, _ocr_worker_with_text, cancel_event, progress_callback)
    except (OSError, RuntimeError):
        return _run_sequential(images, _ocr_worker_with_text, cancel_event, progress_callback)


def _run_sequential(
    images: list[Image.Image],
    worker_fn: Callable,
    cancel_event: Event | None,
    progress_callback: Callable[[int, int], None] | None,
) -> list:
    """シーケンシャルにOCRを実行する（フォールバック用）。"""
    total = len(images)
    results = []
    for i, image in enumerate(images):
        if cancel_event and cancel_event.is_set():
            raise OCRCancelledError("処理がキャンセルされました。")
        result = worker_fn(image)
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, total)
    return results


_BYTES_WORKER_MAP: dict[Callable, Callable] = {
    _ocr_worker: _ocr_worker_bytes,
    _ocr_worker_with_text: _ocr_worker_with_text_bytes,
}


def _image_to_bytes(image: Image.Image) -> bytes:
    """PIL ImageをPPMバイト列に変換する（pickle回避用）。"""
    with io.BytesIO() as buf:
        image.save(buf, format="PPM")
        return buf.getvalue()


def _run_with_pool(
    images: list[Image.Image],
    worker_fn: Callable,
    cancel_event: Event | None,
    progress_callback: Callable[[int, int], None] | None,
) -> list:
    """ProcessPoolExecutor で並列OCRを実行する。"""
    total = len(images)
    max_workers = _get_max_workers()
    results: dict[int, object] = {}
    completed_count = 0

    bytes_worker = _BYTES_WORKER_MAP[worker_fn]

    with ProcessPoolExecutor(max_workers=max_workers, initializer=_worker_initializer) as executor:
        future_to_index = {
            executor.submit(bytes_worker, _image_to_bytes(img)): idx
            for idx, img in enumerate(images)
        }

        for future in as_completed(future_to_index):
            if cancel_event and cancel_event.is_set():
                for f in future_to_index:
                    f.cancel()
                raise OCRCancelledError("処理がキャンセルされました。")

            idx = future_to_index[future]
            results[idx] = future.result()
            completed_count += 1

            if progress_callback:
                progress_callback(completed_count, total)

    return [results[i] for i in range(total)]
