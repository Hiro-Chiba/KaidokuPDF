"""OCR機能を提供するモジュール（後方互換 re-export レイヤー）。

注意: このモジュールの公開APIは __all__ に列挙されたシンボルのみです。
プライベート関数・定数（_で始まるもの）は内部モジュールから直接
インポートしてください。
"""

from ._engine import AdaptiveOCRResult
from ._environment import find_and_set_tesseract_path
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
