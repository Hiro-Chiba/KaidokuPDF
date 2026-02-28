"""OCR処理で使用する例外クラス。"""

from __future__ import annotations


class OCRConversionError(Exception):
    """OCR変換処理で発生した例外。"""


class OCRCancelledError(Exception):
    """ユーザーによって処理がキャンセルされたことを示す例外。"""


class PDFPasswordRemovalError(Exception):
    """PDFのパスワード解除に失敗したことを示す例外。"""
