# 開発ガイド

## セットアップ
```bash
uv sync --group dev
uv run pre-commit install
```

## Lint / Format
```bash
uv run ruff check .        # lint
uv run ruff check . --fix  # lint + 自動修正
uv run ruff format .       # フォーマット
```

## テスト
```bash
uv run pytest
```

## Pre-commit
```bash
uv run pre-commit run --all-files
```
