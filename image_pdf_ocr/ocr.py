"""OCR機能を提供するモジュール（後方互換 re-export レイヤー）。

注意: このモジュールの公開APIは __all__ に列挙されたシンボルのみです。
プライベート関数・定数（_で始まるもの）はインポート可能ですが、
将来のバージョンで変更・削除される可能性があります。
"""

from ._engine import (  # noqa: F401
    _AVERAGE_CONFIDENCE_THRESHOLD,
    _EARLY_STOP_CONFIDENCE,
    _UPSCALE_FACTOR,
    AdaptiveOCRResult,
    _build_tesseract_configs,
    _compute_average_confidence,
    _filter_frame_by_confidence,
    _image_to_data,
    _perform_adaptive_ocr,
    _prepare_frame,
    _preprocess_for_ocr,
    _run_ocr_with_best_config,
    _sanitize_tesseract_config,
)
from ._environment import (  # noqa: F401
    _candidate_font_directories,
    _find_japanese_font_path,
    find_and_set_tesseract_path,
)
from ._exceptions import (
    OCRCancelledError,
    OCRConversionError,
    PDFPasswordRemovalError,
)
from ._pdf import (
    create_searchable_pdf,
    create_searchable_pdf_from_images,
    extract_text_from_image_pdf,
    extract_text_to_file,
    remove_pdf_password,
)
from ._utils import (  # noqa: F401
    _build_progress_message,
    _extract_coordinates,
    _format_duration,
    _prepare_output_path,
)

__all__ = [
    "AdaptiveOCRResult",
    "OCRCancelledError",
    "OCRConversionError",
    "PDFPasswordRemovalError",
    "create_searchable_pdf",
    "create_searchable_pdf_from_images",
    "extract_text_from_image_pdf",
    "extract_text_to_file",
    "find_and_set_tesseract_path",
    "remove_pdf_password",
]
