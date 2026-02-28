"""環境変数による_engine設定のテスト。"""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch

from image_pdf_ocr import _engine


class TestConfidenceThresholdEnvVar:
    def _reload_threshold(self) -> float:
        importlib.reload(_engine)
        return _engine._AVERAGE_CONFIDENCE_THRESHOLD

    def test_invalid_confidence_threshold_uses_default(self):
        with patch.dict(os.environ, {"OCR_CONFIDENCE_THRESHOLD": "invalid"}):
            assert self._reload_threshold() == 65.0

    def test_valid_confidence_threshold_parsed(self):
        with patch.dict(os.environ, {"OCR_CONFIDENCE_THRESHOLD": "80"}):
            assert self._reload_threshold() == 80.0

    def test_empty_confidence_threshold_uses_default(self):
        with patch.dict(os.environ, {"OCR_CONFIDENCE_THRESHOLD": ""}):
            assert self._reload_threshold() == 65.0
