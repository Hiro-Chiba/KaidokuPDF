# KaidokuPDF

画像ベースのPDFをOCRし、検索可能なPDF生成やテキスト抽出を行うツールです。

**[Webアプリを試す →](https://kaidokupdf.streamlit.app/)**

## できること
- 画像PDFを検索可能なPDFに変換
- 画像PDFからテキストを抽出
- 画像ファイルから検索可能PDFを作成
- パスワード付きPDFのロック解除

## 使い方

### Webアプリ（おすすめ）

インストール不要。ブラウザからすぐに使えます → **https://kaidokupdf.streamlit.app/**

### デスクトップアプリ
```bash
python ocr_desktop_app.py
```

### CLI
```bash
kaidoku-convert --input 入力.pdf --output 出力.pdf   # 検索可能PDFを作成
kaidoku-extract --input 入力.pdf --output 出力.txt    # テキストを抽出
```

> デスクトップアプリ・CLIの利用には環境構築が必要です → [セットアップガイド](docs/setup.md)

## ドキュメント

| ドキュメント | 内容 |
|------------|------|
| [セットアップガイド](docs/setup.md) | Tesseractのインストール・環境構築・環境変数・トラブルシューティング |
| [開発ガイド](docs/development.md) | 開発環境セットアップ・Lint/Format・テスト・Pre-commit |

## スクリーンショット
![Screenshot 1](./images/screenshot-1.png)
![Screenshot 2](./images/screenshot-2.png)
![Screenshot 3](./images/screenshot-3.png)

## ライセンス
[MIT License](LICENSE)
