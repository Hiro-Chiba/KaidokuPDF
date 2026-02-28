"""OCR処理で使用する例外クラス。"""

from __future__ import annotations


class OCRConversionError(RuntimeError):
    """OCR変換処理で発生した例外。"""


class OCRCancelledError(RuntimeError):
    """ユーザーによって処理がキャンセルされたことを示す例外。"""


class PDFPasswordRemovalError(RuntimeError):
    """PDFのパスワード解除に失敗したことを示す例外。"""
