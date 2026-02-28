"""Tesseractパス検出・日本語フォント探索を担うモジュール。"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path
from shutil import which

import pytesseract

from ._exceptions import OCRConversionError

_FONT_PATH_CACHE: Path | None = None


def _find_japanese_font_path() -> Path:
    """日本語描画可能なフォントファイルを探索して返す。"""

    global _FONT_PATH_CACHE

    if _FONT_PATH_CACHE and _FONT_PATH_CACHE.exists():
        return _FONT_PATH_CACHE

    env_font = os.environ.get("OCR_JPN_FONT")
    if env_font:
        font_path = Path(env_font).expanduser()
        if font_path.exists():
            _FONT_PATH_CACHE = font_path
            return font_path

    candidate_files = [
        "NotoSansCJK-Regular.ttc",
        "NotoSansCJKjp-Regular.otf",
        "NotoSerifCJK-Regular.ttc",
        "SourceHanSansJP-Regular.otf",
        "SourceHanSerifJP-Regular.otf",
        "ipaexg.ttf",
        "ipaexm.ttf",
        "ipag.ttf",
        "ipam.ttf",
        "YuGothR.ttc",
        "YuMincho.ttc",
    ]

    candidate_patterns = [
        "*NotoSansCJK*.ttc",
        "*NotoSansCJK*.otf",
        "*NotoSerifCJK*.ttc",
        "*NotoSerifCJK*.otf",
        "*SourceHanSans*.otf",
        "*SourceHanSerif*.otf",
        "*ipaex*.ttf",
        "*ipaex*.otf",
        "*ipag*.ttf",
        "*ipag*.ttc",
        "*ipam*.ttf",
        "*ipam*.ttc",
        "*YuGoth*.ttc",
        "*YuMincho*.ttc",
    ]

    directories = _candidate_font_directories()

    for directory in directories:
        for name in candidate_files:
            path = directory / name
            if path.exists():
                _FONT_PATH_CACHE = path
                return path

    for directory in directories:
        if not directory.exists():
            continue
        for pattern in candidate_patterns:
            matches = sorted(directory.rglob(pattern))
            for match in matches:
                if match.is_file():
                    _FONT_PATH_CACHE = match
                    return match

    raise OCRConversionError(
        "日本語フォントが見つかりません。Noto Sans CJKなどのフォントをインストールし、"
        "環境変数 OCR_JPN_FONT でフォントファイルへのパスを指定してください。"
    )


def _candidate_font_directories() -> list[Path]:
    """日本語フォント探索対象となるディレクトリ一覧を返す。"""

    dirs: list[Path] = []

    for env_name in ("OCR_JPN_FONT_DIR", "OCR_FONT_DIR"):
        env_value = os.environ.get(env_name)
        if env_value:
            resolved = Path(env_value).expanduser().resolve()
            if resolved.is_dir():
                dirs.append(resolved)

    home = Path.home()
    dirs.extend(
        [
            home / ".fonts",
            home / ".local/share/fonts",
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path("/Library/Application Support/Microsoft/Fonts"),
        ]
    )

    module_dir = Path(__file__).resolve().parent
    dirs.append(module_dir)
    dirs.append(module_dir / "fonts")

    if os.name == "nt":
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        dirs.append(windir / "Fonts")

    seen: dict[Path, None] = {}
    ordered_dirs: list[Path] = []
    for directory in dirs:
        resolved = directory.resolve()
        if resolved not in seen:
            seen[resolved] = None
            ordered_dirs.append(resolved)

    return ordered_dirs


def _validate_tesseract_setting() -> bool:
    """設定済みの`tesseract_cmd`が妥当かを確認する。"""

    try:
        pytesseract.get_tesseract_version()
        return True
    except pytesseract.TesseractNotFoundError:
        return False


def _try_assign_candidates(paths: Iterable[Path]) -> bool:
    """候補パス群から`tesseract_cmd`を設定し、利用可能か検証する。"""

    for candidate in paths:
        if candidate and candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            if _validate_tesseract_setting():
                return True
    return False


def find_and_set_tesseract_path() -> bool:
    """環境に応じてTesseractの実行ファイルを検出して設定する。"""

    def _set_cmd_if_exists(path: Path) -> bool:
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            return True
        return False

    # 環境変数で明示的に指定されている場合を優先する
    for env_name in ("TESSERACT_CMD", "TESSERACT_PATH", "PIL_TESSERACT_CMD"):
        env_value = os.environ.get(env_name)
        if env_value and _set_cmd_if_exists(Path(env_value)):
            break

    # すでに設定済みの場合やPATHで検出できた場合はそのまま利用する
    if pytesseract.pytesseract.tesseract_cmd and _validate_tesseract_setting():
        return True

    cmd_from_path = which("tesseract")
    if cmd_from_path and _set_cmd_if_exists(Path(cmd_from_path)) and _validate_tesseract_setting():
        return True

    # Windows向けの既定インストールパスをチェック
    path_64 = Path(r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
    path_32 = Path(r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe")

    if (
        _set_cmd_if_exists(path_64) or _set_cmd_if_exists(path_32)
    ) and _validate_tesseract_setting():
        return True

    # PyInstaller等で配布する際に同梱した`tesseract.exe`を探索
    candidate_roots: list[Path] = []

    if getattr(sys, "frozen", False):  # PyInstaller実行ファイル
        candidate_roots.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_roots.append(Path(meipass))
    module_dir = Path(__file__).resolve().parent
    candidate_roots.append(module_dir)
    candidate_roots.append(module_dir.parent)

    exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
    bundle_dirs = ("", "Tesseract-OCR", "tesseract", "tesseract-ocr", "bin")

    bundle_candidates = [
        root / sub_dir / exe_name for root in candidate_roots for sub_dir in bundle_dirs
    ]

    if _try_assign_candidates(bundle_candidates):
        return True

    return _validate_tesseract_setting()
