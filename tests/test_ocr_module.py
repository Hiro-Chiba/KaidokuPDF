"""ocr.py（re-exportレイヤー）のテスト。"""

import image_pdf_ocr.ocr as ocr_module

_EXPECTED_EXPORTS = [
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


def test_all_exports_accessible() -> None:
    """__all__ に列挙された全シンボルが実際にインポートできる。"""
    for name in ocr_module.__all__:
        assert hasattr(ocr_module, name), f"{name} is listed in __all__ but not accessible"


def test_all_list_complete() -> None:
    """__all__ が期待するシンボル一覧と完全一致する。"""
    assert sorted(ocr_module.__all__) == sorted(_EXPECTED_EXPORTS)
