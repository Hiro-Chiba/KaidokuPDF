"""OCRエンジン設定・前処理・実行を担うモジュール。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import pandas as pd
import pytesseract
from PIL import Image, ImageOps

try:
    _AVERAGE_CONFIDENCE_THRESHOLD = max(
        0.0, min(100.0, float(os.environ.get("OCR_CONFIDENCE_THRESHOLD", "65")))
    )
except (ValueError, TypeError):
    _AVERAGE_CONFIDENCE_THRESHOLD = 65.0
_TEXT_RENDER_CONFIDENCE_THRESHOLD = 50.0
_UPSCALE_FACTOR = 1.5
_OCR_PSM_CANDIDATES = tuple(
    int(psm.strip())
    for psm in os.environ.get("OCR_PSM_CANDIDATES", "6,11").split(",")
    if psm.strip().isdigit()
)
_SHELL_META_CHARS = re.compile(r"[;&|`$(){}<>!\\\"'\n\r]")
_ALLOWED_TESSERACT_FLAGS = frozenset({"--oem", "--psm", "--dpi", "-l", "--tessdata-dir"})


def _sanitize_tesseract_config(raw: str) -> str:
    """Tesseract設定文字列をホワイトリストで検証し、安全なトークンのみ残す。"""

    if not raw:
        return ""

    tokens = raw.split()
    sanitized: list[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if _SHELL_META_CHARS.search(token):
            i += 1
            continue
        if token in _ALLOWED_TESSERACT_FLAGS:
            sanitized.append(token)
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                value = tokens[i + 1]
                if not _SHELL_META_CHARS.search(value):
                    sanitized.append(value)
                i += 2
                continue
        i += 1

    return " ".join(sanitized)


_EARLY_STOP_CONFIDENCE = 90.0
_BINARIZE_THRESHOLD = 180
_PDF_RENDER_DPI = 300
_POINTS_PER_INCH = 72
_OCR_BASE_CONFIG = _sanitize_tesseract_config(os.environ.get("OCR_TESSERACT_CONFIG", "--oem 1"))


@dataclass
class AdaptiveOCRResult:
    """OCR結果と判定情報を保持するデータクラス。"""

    frame: pd.DataFrame
    average_confidence: float
    image_for_string: Image.Image
    used_preprocessing: bool


def _build_tesseract_configs() -> tuple[str, ...]:
    """OCR時に試すTesseractの設定文字列を構築する。"""

    psm_candidates = _OCR_PSM_CANDIDATES or (6,)
    base_config = _OCR_BASE_CONFIG.strip()
    configs = []

    for psm in psm_candidates:
        psm_config = f"--psm {psm}"
        configs.append(f"{base_config} {psm_config}".strip())

    return tuple(dict.fromkeys(configs))


_TESSERACT_CONFIGS = _build_tesseract_configs()


def _run_ocr_with_best_config(image: Image.Image) -> tuple[pd.DataFrame, float]:
    """複数設定でOCRを実行し、平均信頼度が最も高い結果を返す。"""

    best_frame: pd.DataFrame | None = None
    best_average = -1.0

    for config in _TESSERACT_CONFIGS:
        frame = _image_to_data(image, config=config)
        average = _compute_average_confidence(frame)
        if average > best_average:
            best_average = average
            best_frame = frame
        if best_average >= _EARLY_STOP_CONFIDENCE:
            break

    if best_frame is None:
        return pd.DataFrame(), 0.0

    return best_frame, best_average


def _perform_adaptive_ocr(image: Image.Image) -> AdaptiveOCRResult:
    """平均信頼度に応じて前処理を適用し、最適なOCR結果を返す。"""

    base_image = image.convert("RGB")
    base_frame_raw, base_average = _run_ocr_with_best_config(base_image)
    base_frame = _prepare_frame(base_frame_raw, scale=1.0)

    best_result = AdaptiveOCRResult(
        frame=base_frame,
        average_confidence=base_average,
        image_for_string=base_image,
        used_preprocessing=False,
    )

    if base_average >= _AVERAGE_CONFIDENCE_THRESHOLD:
        return best_result

    preprocessed_image, scale = _preprocess_for_ocr(base_image)
    processed_frame_raw, processed_average = _run_ocr_with_best_config(preprocessed_image)
    processed_frame = _prepare_frame(processed_frame_raw, scale=scale)

    if processed_average > best_result.average_confidence:
        return AdaptiveOCRResult(
            frame=processed_frame,
            average_confidence=processed_average,
            image_for_string=preprocessed_image,
            used_preprocessing=True,
        )

    return best_result


def _image_to_data(image: Image.Image, config: str = "") -> pd.DataFrame:
    """pytesseractを用いてOCR結果をDataFrameで取得する。"""

    return pytesseract.image_to_data(
        image,
        lang="jpn",
        config=config,
        output_type=pytesseract.Output.DATAFRAME,
    )


def _compute_average_confidence(frame: pd.DataFrame) -> float:
    """OCR結果の平均信頼度を算出する。"""

    if "conf" not in frame.columns:
        return 0.0

    confidences = pd.to_numeric(frame["conf"], errors="coerce")
    valid = confidences[(confidences.notna()) & (confidences >= 0)]

    if valid.empty:
        return 0.0

    return float(valid.mean())


def _prepare_frame(frame: pd.DataFrame, scale: float) -> pd.DataFrame:
    """数値列をfloat化し、必要に応じて座標をスケールダウンする。"""

    prepared = frame.copy()

    for column in ("left", "top", "width", "height", "conf"):
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    if scale != 1.0:
        for column in ("left", "top", "width", "height"):
            if column in prepared.columns:
                prepared[column] = prepared[column] / scale

    return prepared


def _filter_frame_by_confidence(frame: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """指定した信頼度以上の行だけを残したDataFrameを返す。"""

    if "conf" not in frame.columns:
        return frame.iloc[0:0]

    confidences = pd.to_numeric(frame["conf"], errors="coerce")
    mask = confidences >= threshold
    filtered = frame.loc[mask].copy()
    filtered["text"] = filtered["text"].fillna("") if "text" in filtered.columns else ""
    return filtered


def _preprocess_for_ocr(image: Image.Image) -> tuple[Image.Image, float]:
    """OCR精度向上のための前処理（拡大＋二値化）を適用する。"""

    grayscale = image.convert("L")
    scale = _UPSCALE_FACTOR
    if scale != 1.0:
        new_size = (int(grayscale.width * scale), int(grayscale.height * scale))
        resized = grayscale.resize(new_size, Image.LANCZOS)  # type: ignore[attr-defined]
    else:
        resized = grayscale

    enhanced = ImageOps.autocontrast(resized)
    binary = enhanced.point(lambda x: 255 if x > _BINARIZE_THRESHOLD else 0, mode="L")
    return binary, scale
