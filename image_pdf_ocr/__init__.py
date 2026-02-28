"""画像PDFを扱うためのOCRユーティリティ集。"""

from ._engine import AdaptiveOCRResult
from ._environment import find_and_set_tesseract_path
from ._exceptions import OCRCancelledError, OCRConversionError, PDFPasswordRemovalError
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
