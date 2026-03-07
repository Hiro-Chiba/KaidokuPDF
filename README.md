# KaidokuPDF

画像PDFをOCRで検索可能にするツール。検索可能PDF変換・テキスト抽出・パスワード解除に対応。

## できること

- 画像PDFを検索可能なPDFに変換
- 画像PDFからテキストを抽出
- 画像ファイルから検索可能PDFを作成
- パスワード付きPDFのロック解除

## 使い方

- **Web** — インストール不要。**[kaidokupdf.streamlit.app](https://kaidokupdf.streamlit.app/)**
- **デスクトップ** — `python ocr_desktop_app.py`
- **CLI** — `kaidoku-convert` / `kaidoku-extract`

ローカル実行には環境構築が必要です → [セットアップガイド](docs/setup.md)

## ドキュメント

- [セットアップガイド](docs/setup.md) — インストール・環境変数・トラブルシューティング
- [開発ガイド](docs/development.md) — Lint / テスト / Pre-commit

## スクリーンショット（デスクトップ版）

<img src="./images/screenshot-1.png" width="270"> <img src="./images/screenshot-2.png" width="270"> <img src="./images/screenshot-3.png" width="270">

## ライセンス

[MIT License](LICENSE)
