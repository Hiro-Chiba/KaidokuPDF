# セットアップガイド

## 必要なもの
- Python 3.10 以上
- Tesseract-OCR（日本語データを含む）
  - `tesseract -v` が動かない場合は `TESSERACT_CMD`/`TESSERACT_PATH` でパスを指定
  - 日本語フォント（Noto Sans CJKなど）をインストールするとPDFの文字化けを防げます。特定フォントを使いたい場合は `OCR_JPN_FONT` でファイルパスを指定

### Tesseract-OCR のインストール

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-jpn
```

**Windows:**

[UB Mannheim のインストーラー](https://github.com/UB-Mannheim/tesseract/wiki) からダウンロードし、インストール時に日本語データを選択してください。

## インストール

### uv（推奨）
```bash
uv sync
```

### pip
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|----------|
| `TESSERACT_CMD` | Tesseract実行ファイルのパス | 自動検出 |
| `OCR_JPN_FONT` | 日本語フォントファイルのパス | 自動検出 |
| `OCR_JPN_FONT_DIR` | フォント探索ディレクトリ | 自動検出 |
| `OCR_CONFIDENCE_THRESHOLD` | OCR信頼度の閾値（0〜100） | 65.0 |
| `KAIDOKU_OCR_WORKERS` | 並列OCRワーカー数 | CPU数 // 2 |
| `KAIDOKU_PARALLEL` | 並列処理の有効化（`0`で無効） | 1 |

## よくある問題
- 「Tesseract-OCRが見つかりません」: TesseractのインストールとPATH設定を確認し、必要なら環境変数でパスを指定
- 「need font file or buffer」: 日本語フォントをインストールし、`OCR_JPN_FONT` でフォントファイルを指す
