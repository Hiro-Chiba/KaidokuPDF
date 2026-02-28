# Image PDF OCR Suite

画像ベースのPDFをOCRし、検索可能なPDF生成やテキスト抽出を行うシンプルなツールセットです。GUI（Tkinter）とCLIのどちらでも使えます。

## できること
- 画像PDFを検索可能なPDFに変換
- 画像PDFからテキストを抽出
- 画像ファイルから検索可能PDFを作成
- パスワード付きPDFのロック解除

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

## セットアップ

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

## 使い方

### デスクトップアプリ（おすすめ）
```bash
python ocr_desktop_app.py
```
- 「OCR処理」タブでPDFを指定し、検索可能PDF生成またはテキスト抽出を実行
- 「画像からPDF」タブで複数画像から1つの検索可能PDFを作成
- 「PDFパスワード解除」タブでパスワード付きPDFのロック解除

### CLI
検索可能PDFを作成:
```bash
kaidoku-convert --input_path 入力.pdf --output_path 出力.pdf
```

テキストを抽出:
```bash
kaidoku-extract --pdf_path 入力.pdf --output_path 出力.txt
```

## 開発

### セットアップ
```bash
uv sync --group dev
uv run pre-commit install
```

### Lint / Format
```bash
uv run ruff check .        # lint
uv run ruff check . --fix  # lint + 自動修正
uv run ruff format .       # フォーマット
```

### テスト
```bash
uv run pytest
```

### Pre-commit
```bash
uv run pre-commit run --all-files
```

## よくある問題
- 「Tesseract-OCRが見つかりません」: TesseractのインストールとPATH設定を確認し、必要なら環境変数でパスを指定
- 「need font file or buffer」: 日本語フォントをインストールし、`OCR_JPN_FONT` でフォントファイルを指す

## ライセンス
[MIT License](LICENSE)

## スクリーンショット
![Screenshot 1](./images/screenshot-1.png)
![Screenshot 2](./images/screenshot-2.png)
![Screenshot 3](./images/screenshot-3.png)
