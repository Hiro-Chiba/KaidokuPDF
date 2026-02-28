"""座標抽出・進捗表示・出力パス準備のユーティリティ。"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import TYPE_CHECKING

from ._exceptions import OCRConversionError

if TYPE_CHECKING:
    import pandas as pd


def _extract_coordinates(
    row: pd.Series | dict,
) -> tuple[float | None, float | None, float | None]:
    """DataFrameの1行またはdictから座標情報を抽出する。"""

    try:
        x = float(row.get("left"))  # type: ignore[arg-type]
        y = float(row.get("top"))  # type: ignore[arg-type]
        h = float(row.get("height"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, None, None

    if any(math.isnan(value) for value in (x, y, h)):
        return None, None, None

    return x, y, h


def _format_duration(seconds: float) -> str:
    """秒数から可読な時間文字列を生成する。"""

    if not math.isfinite(seconds):
        return "不明"

    total_seconds = max(0, round(seconds))
    minutes, sec = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def _build_progress_message(current: int, total: int, start_time: float) -> str:
    """進捗状況と推定残り時間のメッセージを生成する。"""

    if total <= 0:
        return "進捗: ページ数が不明です"

    elapsed = time.perf_counter() - start_time
    average_per_page = elapsed / current if current else float("inf")
    remaining_pages = max(total - current, 0)
    remaining_estimate = average_per_page * remaining_pages
    remaining_text = _format_duration(remaining_estimate)

    return f"{current}/{total}ページ完了　残り推定時間: {remaining_text}"


def _prepare_output_path(path: Path) -> None:
    """出力パスの親ディレクトリを作成し、書き込み可能か確認する。"""

    try:
        parent = path.parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - filesystem permissions vary
        raise OCRConversionError(f"出力先ディレクトリを作成できませんでした: {exc}") from exc

    if path.exists() and path.is_dir():
        raise OCRConversionError(f"出力パスがディレクトリを指しています: {path}")
