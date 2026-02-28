# Phase 4 実装チェックリスト

## Step 1: DevOps基盤（A-2, A-1）
- [x] `pyproject.toml`: pytest-cov追加、addopts設定
- [x] `ci.yml`: Python 3.11/3.12マトリクス追加、coverage

## Step 2: パフォーマンス改善（B-2, B-1, B-3, B-4）
- [x] `_parallel.py`: DataFrameからテキスト再構築（二重OCR排除）
- [x] `_pdf.py`: チャンク処理でメモリO(chunk)化
- [x] `_engine.py`: `_TESSERACT_CONFIGS`定数化
- [x] `_pdf.py`: PNG→PPM変換

## Step 3: アーキテクチャ/コード品質（D-1, D-2, D-3, D-4）
- [x] `ocr.py`: `__all__`を公開APIのみに絞る（50+→10シンボル）
- [x] `_pdf.py`: `_extract_coordinates`呼び出しでDRY化
- [x] `_environment.py`: `_FONT_PATH_CACHE_LOCK`追加
- [x] `_engine.py`: `_BINARIZE_THRESHOLD`, `_PDF_RENDER_DPI`, `_POINTS_PER_INCH`定数化

## Step 4: セキュリティ強化（F-1, F-2, F-3）
- [x] `_pdf.py`: `Image.MAX_IMAGE_PIXELS = 200_000_000`
- [x] `_environment.py`: `_ALLOWED_FONT_EXTENSIONS`フォント拡張子検証
- [x] `_environment.py`: `_MAX_FONT_SEARCH_FILES = 10_000`rglob上限

## Step 5: テスト品質改善（C-1〜C-4）
- [x] `test_integration.py`: OCR精度検証追加（`test_ocr_accuracy_minimum`, `test_output_contains_text`）
- [x] `test_e2e.py`: `_REPO_ROOT`で絶対パス化
- [x] `test_e2e.py`: `--input`/`--output`統一引数使用
- [x] 新テスト `test_pdf_utils.py`: `_determine_canvas_size`(4件), `_normalize_image_for_canvas`(4件), `_reconstruct_text_from_frame`(7件)

## Step 6: UX改善（E-1, E-2, E-3）
- [x] CLI引数統一: `--input`（`--input_path`/`--pdf_path`はaliasとして残す）
- [x] 進捗表示: `progress_callback`をCLI内で`print(msg, flush=True)`
- [x] `--version`オプション追加

## Step 7: wheel構造修正（A-3）
- [x] `image_pdf_ocr/_cli_convert.py`新規作成
- [x] `image_pdf_ocr/_cli_extract.py`新規作成
- [x] `pyproject.toml`の`[project.scripts]`を`image_pdf_ocr._cli_*:main`に更新
- [x] 元ファイル（`convert_to_searchable_pdf.py`, `extract_text_from_pdf.py`）をラッパー化

## Step 8: 残りDevOps（A-4, A-5）
- [x] `.pre-commit-config.yaml`: check-merge-conflict, detect-private-key, check-case-conflict追加
- [x] `.github/dependabot.yml`新規作成

## Step 9: 仕上げ
- [x] `ruff check .` — エラー0
- [x] `pytest -v` — 100テストpass（14 skipped: Tesseract未インストール）
- [x] `pre-commit run --all-files` — 全10hookパス
- [x] API互換確認: `from image_pdf_ocr import create_searchable_pdf` OK

## Review
- 全9ステップ完了
- テスト数: 既存97件 → 114件（+17件）
  - `test_pdf_utils.py` 新規15件（_determine_canvas_size, _normalize_image_for_canvas, _reconstruct_text_from_frame）
  - `test_integration.py` +2件（OCR精度検証）
- カバレッジ: 53%（Tesseract依存コードがskipのため）
- ruff check: エラー0
- pre-commit: 全10hookパス
