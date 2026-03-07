"""KaidokuPDF Streamlit Web アプリケーション。

ブラウザから PDF の OCR 変換・テキスト抽出・パスワード解除を行う。
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import streamlit as st

from image_pdf_ocr import (
    OCRConversionError,
    PDFPasswordRemovalError,
    create_searchable_pdf,
    extract_text_from_image_pdf,
    remove_pdf_password,
)

MAX_FILE_SIZE_MB = 50

st.set_page_config(
    page_title="KaidokuPDF",
    page_icon="📄",
    layout="centered",
)

st.title("KaidokuPDF")
st.caption("画像ベースの PDF を OCR して検索可能にするツール")


def _validate_upload(uploaded_file: object) -> bool:
    """アップロードファイルのサイズを検証する。"""
    if uploaded_file is None:
        return False
    size_mb = uploaded_file.size / (1024 * 1024)  # type: ignore[union-attr]
    if size_mb > MAX_FILE_SIZE_MB:
        st.error(f"ファイルサイズが上限 ({MAX_FILE_SIZE_MB}MB) を超えています。({size_mb:.1f}MB)")
        return False
    return True


def _parse_progress(message: str) -> float | None:
    """進捗メッセージからパーセンテージを抽出する。

    例: '3/10ページ完了　残り推定時間: 00:15' → 0.30
    """
    match = re.search(r"(\d+)\s*/\s*(\d+)", message)
    if match:
        current, total = int(match.group(1)), int(match.group(2))
        if total > 0:
            return min(current / total, 1.0)
    return None


# --- タブ構成 ---
tab_convert, tab_extract, tab_password = st.tabs(
    [
        "PDF → 検索可能PDF",
        "PDF → テキスト抽出",
        "PDFパスワード解除",
    ]
)

# === タブ1: PDF → 検索可能PDF ===
with tab_convert:
    st.subheader("画像 PDF を検索可能な PDF に変換")
    convert_file = st.file_uploader(
        "PDF ファイルをアップロード",
        type=["pdf"],
        key="convert_upload",
    )

    if st.button("変換", key="convert_btn", disabled=convert_file is None) and _validate_upload(
        convert_file
    ):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def convert_progress(message: str) -> None:
            status_text.text(message)
            pct = _parse_progress(message)
            if pct is not None:
                progress_bar.progress(pct)

        with (
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in,
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out,
        ):
            tmp_in.write(convert_file.getvalue())  # type: ignore[union-attr]
            tmp_in_path = tmp_in.name
            tmp_out_path = tmp_out.name

        try:
            with st.spinner("OCR 変換中..."):
                create_searchable_pdf(
                    tmp_in_path,
                    tmp_out_path,
                    progress_callback=convert_progress,
                )
            progress_bar.progress(1.0)
            status_text.text("変換完了!")
            st.success("変換が完了しました。")
            result_data = Path(tmp_out_path).read_bytes()
            original_name = convert_file.name  # type: ignore[union-attr]
            output_name = Path(original_name).stem + "_searchable.pdf"
            st.download_button(
                label="変換済み PDF をダウンロード",
                data=result_data,
                file_name=output_name,
                mime="application/pdf",
                key="convert_download",
            )
        except OCRConversionError as e:
            st.error(f"変換エラー: {e}")
        finally:
            Path(tmp_in_path).unlink(missing_ok=True)
            Path(tmp_out_path).unlink(missing_ok=True)

# === タブ2: PDF → テキスト抽出 ===
with tab_extract:
    st.subheader("画像 PDF からテキストを抽出")
    extract_file = st.file_uploader(
        "PDF ファイルをアップロード",
        type=["pdf"],
        key="extract_upload",
    )

    if st.button("抽出", key="extract_btn", disabled=extract_file is None) and _validate_upload(
        extract_file
    ):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def extract_progress(message: str) -> None:
            status_text.text(message)
            pct = _parse_progress(message)
            if pct is not None:
                progress_bar.progress(pct)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
            tmp_in.write(extract_file.getvalue())  # type: ignore[union-attr]
            tmp_in_path = tmp_in.name

        try:
            with st.spinner("テキスト抽出中..."):
                extracted_text = extract_text_from_image_pdf(
                    tmp_in_path,
                    progress_callback=extract_progress,
                )
            progress_bar.progress(1.0)
            status_text.text("抽出完了!")
            st.success("テキスト抽出が完了しました。")
            st.text_area("抽出されたテキスト", extracted_text, height=400)
            original_name = extract_file.name  # type: ignore[union-attr]
            output_name = Path(original_name).stem + ".txt"
            st.download_button(
                label="テキストファイルをダウンロード",
                data=extracted_text.encode("utf-8"),
                file_name=output_name,
                mime="text/plain; charset=utf-8",
                key="extract_download",
            )
        except OCRConversionError as e:
            st.error(f"抽出エラー: {e}")
        finally:
            Path(tmp_in_path).unlink(missing_ok=True)

# === タブ3: PDFパスワード解除 ===
with tab_password:
    st.subheader("PDF のパスワードを解除")
    password_file = st.file_uploader(
        "パスワード付き PDF をアップロード",
        type=["pdf"],
        key="password_upload",
    )
    password_input = st.text_input(
        "パスワード",
        type="password",
        key="password_input",
    )

    if st.button("パスワード解除", key="password_btn", disabled=password_file is None):
        if not password_input:
            st.warning("パスワードを入力してください。")
        elif _validate_upload(password_file):
            with (
                tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in,
                tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out,
            ):
                tmp_in.write(password_file.getvalue())  # type: ignore[union-attr]
                tmp_in_path = tmp_in.name
                tmp_out_path = tmp_out.name

            try:
                remove_pdf_password(tmp_in_path, tmp_out_path, password_input)
                st.success("パスワード解除が完了しました。")
                result_data = Path(tmp_out_path).read_bytes()
                original_name = password_file.name  # type: ignore[union-attr]
                output_name = Path(original_name).stem + "_unlocked.pdf"
                st.download_button(
                    label="解除済み PDF をダウンロード",
                    data=result_data,
                    file_name=output_name,
                    mime="application/pdf",
                    key="password_download",
                )
            except PDFPasswordRemovalError as e:
                st.error(f"パスワード解除エラー: {e}")
            finally:
                Path(tmp_in_path).unlink(missing_ok=True)
                Path(tmp_out_path).unlink(missing_ok=True)

# --- フッター ---
st.divider()
st.caption(
    "KaidokuPDF — 画像ベースの PDF を OCR で検索可能にするオープンソースツール。"
    f" ファイルサイズ上限: {MAX_FILE_SIZE_MB}MB"
)
