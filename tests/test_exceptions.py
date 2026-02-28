"""例外クラス階層のテスト。"""

from __future__ import annotations

import pytest

from image_pdf_ocr._exceptions import OCRCancelledError, OCRConversionError, PDFPasswordRemovalError

_EXCEPTION_CLASSES = [OCRConversionError, OCRCancelledError, PDFPasswordRemovalError]


class TestExceptionHierarchy:
    @pytest.mark.parametrize("exc_cls", _EXCEPTION_CLASSES)
    def test_is_exception_subclass(self, exc_cls):
        assert issubclass(exc_cls, Exception)

    @pytest.mark.parametrize("exc_cls", _EXCEPTION_CLASSES)
    def test_is_not_runtime_error(self, exc_cls):
        assert not issubclass(exc_cls, RuntimeError)

    @pytest.mark.parametrize("exc_cls", _EXCEPTION_CLASSES)
    def test_can_be_raised_with_message(self, exc_cls):
        msg = "テストメッセージ"
        with pytest.raises(exc_cls, match=msg):
            raise exc_cls(msg)
