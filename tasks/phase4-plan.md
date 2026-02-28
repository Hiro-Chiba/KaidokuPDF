# KaidokuPDF Phase 4 実装計画

## 目標
7専門家レビューで指摘されたP0/P1問題を解決し、総合スコア 56→70+ を目指す。

---

## 施策A: DevOps基盤整備（22→60）

### A-1: GitHub Actions CI 確認・修正
- `.github/workflows/ci.yml` が既存なら内容確認・強化
- Python 3.10, 3.11, 3.12, 3.13 マトリクス
- `uv sync --group dev` → `ruff check` → `ruff format --check` → `pytest --cov`

### A-2: pytest-cov 導入
```toml
[dependency-groups]
dev = ["ruff", "pytest", "pytest-cov", "pre-commit"]

[tool.pytest.ini_options]
addopts = "--cov=image_pdf_ocr --cov-report=term-missing"
```

### A-3: wheel パッケージ構造修正
- `convert_to_searchable_pdf.py` → `image_pdf_ocr/_cli_convert.py` に移動
- `extract_text_from_pdf.py` → `image_pdf_ocr/_cli_extract.py` に移動
- `pyproject.toml` の `[project.scripts]` を更新
- 元のファイルはラッパーとして残す（後方互換）

### A-4: pre-commit フック強化
```yaml
- id: check-merge-conflict
- id: detect-private-key
- id: check-case-conflict
```

### A-5: Dependabot 設定追加
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
```

---

## 施策B: パフォーマンス改善（47→65）

### B-1: チャンク処理でメモリO(n)→O(chunk_size)化
現状: 全ページの画像を一括メモリ保持（100ページで11GB超）
改善: ワーカー数と同程度のチャンクサイズで処理

```python
CHUNK_SIZE = max_workers  # ワーカー数と同程度

for chunk_start in range(0, total_pages, CHUNK_SIZE):
    chunk_images = [render_page(p) for p in pages[chunk_start:chunk_start+CHUNK_SIZE]]
    chunk_results = run_parallel_ocr(chunk_images, ...)
    for result, pix, rect in zip(chunk_results, chunk_pixmaps, chunk_rects):
        # PDF組み立て
        ...
    # チャンクスコープ抜けで画像解放
```

### B-2: 二重OCR排除
`_ocr_worker_with_text` で `image_to_data` + `image_to_string` の2回Tesseract起動を廃止。
`image_to_data` の DataFrame からテキストを再構築する。

```python
def _extract_text_from_frame(frame: pd.DataFrame) -> str:
    if frame.empty or "text" not in frame.columns:
        return ""
    valid = frame.loc[frame["conf"].astype(float) >= 0, "text"].dropna().astype(str)
    return " ".join(t for t in valid if t.strip())
```

### B-3: `_build_tesseract_configs` モジュール定数化
```python
_TESSERACT_CONFIGS: tuple[str, ...] = _build_tesseract_configs()
```

### B-4: PNG→PPM変換（`create_searchable_pdf_from_images`）
```python
prepared_image.save(image_buffer, format="PPM")  # PNG圧縮を回避
```

---

## 施策C: テスト品質改善（55→70）

### C-1: OCR精度の最低限検証
```python
@requires_tesseract
def test_extracts_known_text(self, sample_image_pdf):
    text = extract_text_from_image_pdf(sample_image_pdf)
    lower = text.lower()
    assert "hello" in lower or "world" in lower
```

### C-2: E2Eテストの絶対パス修正
```python
_REPO_ROOT = Path(__file__).parent.parent
# subprocess.run([sys.executable, str(_REPO_ROOT / "convert_to_searchable_pdf.py"), ...])
```

### C-3: 未カバー関数のテスト追加
- `_determine_canvas_size`: 空リスト、ゼロサイズ画像
- `_normalize_image_for_canvas`: アスペクト比維持、余白配置
- `find_and_set_tesseract_path`: 環境変数優先順位（モック）

### C-4: `test_e2e.py` の `test_missing_input_file` から `@requires_tesseract` を除去
Tesseract不要なテストがスキップされている問題を修正。

---

## 施策D: アーキテクチャ/コード品質改善（62→72）

### D-1: `ocr.py` の `__all__` からプライベートシンボル除去
公開APIのみに絞る（約12シンボル）。テストは `image_pdf_ocr._engine` 等から直接インポート。

### D-2: `_extract_coordinates` の実際の活用（DRY化）
`_pdf.py` のインライン重複を `_extract_coordinates` 呼び出しに置換。
ただし `_parallel.py` の `_ocr_worker` が dict を返すため、dict→Series変換が必要。

### D-3: `_FONT_PATH_CACHE` に `threading.Lock` 追加
```python
_FONT_PATH_CACHE_LOCK = threading.Lock()

def _find_japanese_font_path() -> Path:
    global _FONT_PATH_CACHE
    with _FONT_PATH_CACHE_LOCK:
        if _FONT_PATH_CACHE and _FONT_PATH_CACHE.exists():
            return _FONT_PATH_CACHE
        # ... 探索
        _FONT_PATH_CACHE = font_path
        return font_path
```

### D-4: マジックナンバー定数化
```python
_PDF_RENDER_DPI = 300
_POINTS_PER_INCH = 72
_BINARIZE_THRESHOLD = 180
```

---

## 施策E: UX改善（62→70）

### E-1: CLI引数名の統一
- `kaidoku-convert`: `--input_path` → `--input`（旧名もaliasとして残す）
- `kaidoku-extract`: `--pdf_path` → `--input`（旧名もaliasとして残す）

### E-2: CLIに進捗表示追加
```python
def main() -> None:
    ...
    _run_conversion(args.input, args.output, progress_callback=lambda msg: print(msg, flush=True))
```

### E-3: `--version` オプション追加
```python
parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
```

---

## 施策F: セキュリティ強化（72→80）

### F-1: PIL Decompression Bomb対策
```python
import PIL.Image
PIL.Image.MAX_IMAGE_PIXELS = 200_000_000
```

### F-2: フォントパス拡張子検証
```python
_ALLOWED_FONT_EXTENSIONS = frozenset({".ttf", ".otf", ".ttc", ".woff", ".woff2"})
```

### F-3: rglob 探索上限
```python
_MAX_FONT_SEARCH_FILES = 10_000
```

---

## 実装順序

1. A-2: pytest-cov 導入
2. A-1: CI確認・修正
3. B-2: 二重OCR排除
4. B-1: チャンク処理
5. B-3: `_build_tesseract_configs` 定数化
6. D-1: `ocr.py` の `__all__` 整理
7. D-2: `_extract_coordinates` DRY化
8. D-3: `_FONT_PATH_CACHE` Lock追加
9. D-4: マジックナンバー定数化
10. F-1〜F-3: セキュリティ強化
11. C-1〜C-4: テスト追加・修正
12. E-1〜E-3: UX改善
13. A-3: wheel構造修正
14. A-4〜A-5: pre-commit/Dependabot
15. `ruff check --fix && ruff format`
16. `pytest -v` 全テスト pass
17. `pre-commit run --all-files` 全hook パス

---

## 期待スコア変化

| 領域 | Phase 3後 | Phase 4後（推定） |
|------|-----------|------------------|
| セキュリティ | 72 | ~80 |
| テスト品質 | 55 | ~70 |
| アーキテクチャ | 62 | ~72 |
| UX/プロダクト | 62 | ~70 |
| パフォーマンス | 47 | ~65 |
| コード品質 | 71 | ~78 |
| DevOps | 22 | ~60 |
| **総合** | **56** | **~71** |
