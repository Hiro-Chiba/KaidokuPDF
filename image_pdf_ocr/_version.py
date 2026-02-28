"""パッケージバージョンの一元管理。"""

from __future__ import annotations

import importlib.metadata


def _get_version() -> str:
    try:
        return importlib.metadata.version("kaidoku-pdf")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "dev"
