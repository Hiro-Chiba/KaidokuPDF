# KaidokuPDF Phase 3 完了後 — 7専門家レビュー結果

## スコアサマリー

| 専門領域 | スコア | 評価 |
|----------|--------|------|
| セキュリティ | **72/100** | 良好（ローカルツールとして） |
| テスト品質 | **55/100** | 要改善 |
| アーキテクチャ | **62/100** | 要改善 |
| UX/プロダクト | **62/100** | 要改善 |
| パフォーマンス | **47/100** | 危険 |
| Pythonコード品質 | **71/100** | 良好 |
| DevOps/CI-CD | **22/100** | 危機的 |
| **総合（7領域平均）** | **56/100** | **改善余地大** |

---

## 前回レビュー（初期44点）との比較

| 領域 | 初期 | 自己推定 | 専門家評価 | 差分 |
|------|------|---------|-----------|------|
| セキュリティ | 35 | ~55 | **72** | +37 |
| テスト品質 | 25 | ~80 | **55** | +30 |
| アーキテクチャ | 62 | ~75 | **62** | ±0 |
| UX/プロダクト | 62 | ~72 | **62** | ±0 |
| パフォーマンス | 38 | ~70 | **47** | +9 |
| コード品質 | - | - | **71** | (新規) |
| DevOps | - | - | **22** | (新規) |

---

## 複数専門家が一致して指摘した問題（重要度順）

### 1. `ocr.py` のプライベートシンボル全公開（アーキ + コード品質）
30以上の `_xxx` シンボルを `__all__` で公開。API境界を破壊している。

### 2. 全ページ一括メモリ保持（パフォーマンス + アーキ）
100ページPDFで **11GB超** のメモリ消費推定。Pixmap + PIL Image を全ページ分保持したまま ProcessPool に pickle 転送。

### 3. CI/CD パイプライン不在（DevOps）
`.github/workflows/` が存在しない（注: 実際にはci.ymlが存在するが、DevOps専門家はファイルを見つけられなかった可能性あり。要再確認）。

### 4. `_ocr_worker_with_text` の二重OCR（パフォーマンス + アーキ）
`image_to_data` と `image_to_string` で Tesseract を2回起動している。

### 5. `_extract_coordinates` がデッドコード化（コード品質 + アーキ）
ユーティリティ関数を作りながら使わず、インラインで2箇所重複実装。

### 6. `_FONT_PATH_CACHE` のスレッドセーフ欠如（セキュリティ + アーキ）
`threading.Lock` なしの check-then-act パターン。GUIアプリでレースコンディションのリスク。

### 7. CLI引数の不統一・進捗表示なし（UX）
`--input_path` vs `--pdf_path` の不一致。CLIで長時間無表示。

### 8. wheel パッケージの構造不整合（DevOps + コード品質）
`project.scripts` がパッケージ外のトップレベルスクリプトを参照。`pip install` 後にCLIが動かない。

---

## 各専門家の詳細指摘

### セキュリティ（72/100）

#### Critical
- C-1: パストラバーサル — `_prepare_output_path()` が出力パスを検証せず任意パスに書き込み可能
- C-2: 環境変数経由のTesseractバイナリ差し替え — 存在チェックのみで任意バイナリを実行登録可能

#### High
- H-1: フォントパスの拡張子検証なし（`OCR_JPN_FONT` で非フォントファイル指定可能）
- H-2: フォントディレクトリ `rglob()` にDoS上限なし
- H-3: PIL Decompression Bomb対策なし（`MAX_IMAGE_PIXELS` 未設定）

#### Medium
- M-1: `--tessdata-dir` 値のパス検証なし
- M-2: 依存関係バージョン下限が古すぎる（Pillow 10.0.x にCVE-2023-44271）
- M-3: pandas NaN伝播リスク

---

### テスト品質（55/100）

#### Critical
- C1: 統合テストのOCR精度検証が皆無（`len(text) > 0` のみ）
- C2: conftest.py のフォント失敗隠蔽（デフォルトフォント8pxでTesseract認識不可）
- C3: E2Eテストがカレントディレクトリ依存

#### High
- H1: ProcessPoolExecutor の実際の並列実行が完全未テスト
- H2: `_determine_canvas_size` / `_normalize_image_for_canvas` テスト不在
- H3: `find_and_set_tesseract_path` テスト不在
- H4: カバレッジ計測が存在しない（推定行カバレッジ50%未満）
- H5: CLIスクリプトのユニットテストなし

---

### アーキテクチャ（62/100）

#### Critical
- C1: `ocr.py` がプライベートシンボル30+を `__all__` で全公開
- C2: `_FONT_PATH_CACHE` のスレッドセーフ欠如

#### High
- H1: `_pdf.py` の巨大関数（130行、SRP違反）+ PDF組み立てロジック重複
- H2: OCRエンジン差し替え不可（pytesseract直接依存が3ファイルに散在）
- H3: `_image_to_data` の言語 `"jpn"` ハードコード

#### Medium
- M1: fitz.open のコンテキストマネージャ不使用（リソースリークリスク）
- M2: `_ocr_worker_with_text` の二重OCR
- M3: dpi=300 ハードコード

---

### パフォーマンス（47/100）

#### Critical
- C-1: 全ページ画像を一括メモリ保持（100ページで推定11GB超）
- C-2: Pixmapを解放せずに保持（非管理メモリ）
- C-3: ProcessPoolへの画像Pickle転送コスト（1枚26MB、8ページ同時で200MB IPC転送）

#### High
- H-1: `_ocr_worker_with_text` が同じ画像にOCRを2回実行
- H-2: `_prepare_frame` での不要な `frame.copy()`
- H-3: `_build_tesseract_configs()` が毎回再構築
- H-4: `create_searchable_pdf_from_images` での低速PNG圧縮

#### 改善提案
- チャンク処理でメモリO(1)化
- ワーカー内でPDFページをレンダリング（Pickle転送なし）
- `image_to_data` 結果からテキスト再構築（二重OCR排除）
- PNG→PPMでI/Oコスト削減
- `_build_tesseract_configs` をモジュール定数化

---

### UX/プロダクト（62/100）

#### Critical
- C1: CLI引数名に一貫性がない（`--input_path` vs `--pdf_path`）
- C2: CLIに進捗表示が一切ない
- C3: 出力先が既存ファイルの場合の警告なし

#### High
- H1: GUIで出力パス自動提案なし
- H2: 処理完了後に出力ファイルを開く手段なし
- H3: フォント未検出エラーにインストールコマンドなし
- H4: ページ数0 PDFで空ファイルが保存される

---

### Pythonコード品質（71/100）

#### Critical
- C-1: `ocr.py` の `__all__` にプライベートシンボル大量公開
- C-2: `_run_sequential` / `_run_with_pool` の型アノテーション不完全

#### High
- H-1: `_extract_coordinates` 未使用（デッドコード）+ インライン重複
- H-2: fitz.open にコンテキストマネージャ未使用
- H-3: 関数が長すぎる（130行超）
- H-4: `find_and_set_tesseract_path` の副作用が大きい
- H-5: マジックナンバー散在（300, 72, 180, 50.0, 1.5等）

---

### DevOps/CI-CD（22/100）

#### Critical
- C1: GitHub Actions CIが存在しない（要再確認: ci.ymlがあるはず）
- C2: pyproject.toml の wheel ターゲットが壊れている（CLIスクリプトがパッケージ外）
- C3: リリース自動化が皆無

#### High
- H1: pre-commitフックが最小限（mypy/bandit/detect-private-key等なし）
- H2: Dependabot / セキュリティスキャン不在
- H3: Python バージョンマトリクステストなし
