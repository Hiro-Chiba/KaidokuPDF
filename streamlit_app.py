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
_BYTES_PER_MB = 1024 * 1024
_PDF_SUFFIX = ".pdf"
_PDF_MIME = "application/pdf"
_TEXT_MIME = "text/plain; charset=utf-8"
_TEXT_ENCODING = "utf-8"
_TEXT_AREA_HEIGHT = 400
_ACCEPTED_FILE_TYPES = ["pdf"]
_OUTPUT_SUFFIX_SEARCHABLE = "_searchable.pdf"
_OUTPUT_SUFFIX_UNLOCKED = "_unlocked.pdf"
_OUTPUT_SUFFIX_TEXT = ".txt"

st.set_page_config(
    page_title="KaidokuPDF",
    page_icon="📄",
    layout="centered",
)

st.markdown(
    """
    <style>
    .gradient-title {
        background: linear-gradient(135deg, #4ECDC4 0%, #44B3CB 50%, #3A99D2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0;
    }
    .subtitle {
        text-align: center;
        color: #8892A0;
        font-size: 1rem;
        margin-top: 0.2rem;
        margin-bottom: 1.5rem;
    }
    .feature-card {
        background: #1A1F2E;
        border: 1px solid #2A3040;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        transition: border-color 0.2s;
    }
    .feature-card:hover {
        border-color: #4ECDC4;
    }
    .feature-card .icon {
        font-size: 1.8rem;
        margin-bottom: 0.4rem;
    }
    .feature-card .label {
        font-weight: 600;
        font-size: 0.95rem;
        color: #E8ECF1;
    }
    .feature-card .desc {
        font-size: 0.8rem;
        color: #8892A0;
        margin-top: 0.3rem;
    }
    .custom-footer {
        text-align: center;
        color: #8892A0;
        font-size: 0.8rem;
        padding: 1.5rem 0 0.5rem 0;
        border-top: 1px solid #2A3040;
        margin-top: 2rem;
    }
    [data-testid="stDownloadButton"] button {
        width: 100%;
    }
    [data-testid="stFileUploader"] {
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<h1 class="gradient-title">KaidokuPDF</h1>'
    '<p class="subtitle">画像ベースの PDF を OCR して検索可能にするツール</p>',
    unsafe_allow_html=True,
)


def _validate_upload(uploaded_file: object) -> bool:
    """アップロードファイルのサイズを検証する。"""
    if uploaded_file is None:
        return False
    size_mb = uploaded_file.size / _BYTES_PER_MB  # type: ignore[union-attr]
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


# --- 機能概要カード ---
_card_cols = st.columns(3)
_cards = [
    ("🔍", "検索可能PDF", "画像PDFにOCRを適用"),
    ("📝", "テキスト抽出", "画像PDFからテキストを抽出"),
    ("🔓", "パスワード解除", "PDFのロックを解除"),
]
for col, (icon, label, desc) in zip(_card_cols, _cards, strict=True):
    col.markdown(
        f'<div class="feature-card">'
        f'<div class="icon">{icon}</div>'
        f'<div class="label">{label}</div>'
        f'<div class="desc">{desc}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("")  # spacer

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
    with st.container(border=True):
        st.markdown("##### PDFファイルをアップロード")
        convert_file = st.file_uploader(
            "PDF ファイルをアップロード",
            type=_ACCEPTED_FILE_TYPES,
            key="convert_upload",
            label_visibility="collapsed",
        )
        if convert_file is not None:
            st.caption(f"📎 {convert_file.name} ({convert_file.size / _BYTES_PER_MB:.1f}MB)")

    if st.button(
        "🔄 変換開始",
        key="convert_btn",
        disabled=convert_file is None,
        use_container_width=True,
    ) and _validate_upload(convert_file):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def convert_progress(message: str) -> None:
            status_text.text(message)
            pct = _parse_progress(message)
            if pct is not None:
                progress_bar.progress(pct)

        with (
            tempfile.NamedTemporaryFile(suffix=_PDF_SUFFIX, delete=False) as tmp_in,
            tempfile.NamedTemporaryFile(suffix=_PDF_SUFFIX, delete=False) as tmp_out,
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
            with st.container(border=True):
                st.success("変換が完了しました。")
                result_data = Path(tmp_out_path).read_bytes()
                original_name = convert_file.name  # type: ignore[union-attr]
                output_name = Path(original_name).stem + _OUTPUT_SUFFIX_SEARCHABLE
                st.download_button(
                    label="📥 変換済み PDF をダウンロード",
                    data=result_data,
                    file_name=output_name,
                    mime=_PDF_MIME,
                    key="convert_download",
                    use_container_width=True,
                )
        except OCRConversionError as e:
            st.error(f"変換エラー: {e}")
        finally:
            Path(tmp_in_path).unlink(missing_ok=True)
            Path(tmp_out_path).unlink(missing_ok=True)

# === タブ2: PDF → テキスト抽出 ===
with tab_extract:
    st.subheader("画像 PDF からテキストを抽出")
    with st.container(border=True):
        st.markdown("##### PDFファイルをアップロード")
        extract_file = st.file_uploader(
            "PDF ファイルをアップロード",
            type=_ACCEPTED_FILE_TYPES,
            key="extract_upload",
            label_visibility="collapsed",
        )
        if extract_file is not None:
            st.caption(f"📎 {extract_file.name} ({extract_file.size / _BYTES_PER_MB:.1f}MB)")

    if st.button(
        "📝 抽出開始",
        key="extract_btn",
        disabled=extract_file is None,
        use_container_width=True,
    ) and _validate_upload(extract_file):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def extract_progress(message: str) -> None:
            status_text.text(message)
            pct = _parse_progress(message)
            if pct is not None:
                progress_bar.progress(pct)

        with tempfile.NamedTemporaryFile(suffix=_PDF_SUFFIX, delete=False) as tmp_in:
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
            with st.container(border=True):
                st.success("テキスト抽出が完了しました。")
                st.text_area("抽出されたテキスト", extracted_text, height=_TEXT_AREA_HEIGHT)
                original_name = extract_file.name  # type: ignore[union-attr]
                output_name = Path(original_name).stem + _OUTPUT_SUFFIX_TEXT
                st.download_button(
                    label="📥 テキストファイルをダウンロード",
                    data=extracted_text.encode(_TEXT_ENCODING),
                    file_name=output_name,
                    mime=_TEXT_MIME,
                    key="extract_download",
                    use_container_width=True,
                )
        except OCRConversionError as e:
            st.error(f"抽出エラー: {e}")
        finally:
            Path(tmp_in_path).unlink(missing_ok=True)

# === タブ3: PDFパスワード解除 ===
with tab_password:
    st.subheader("PDF のパスワードを解除")
    with st.container(border=True):
        st.markdown("##### パスワード付きPDFをアップロード")
        password_file = st.file_uploader(
            "パスワード付き PDF をアップロード",
            type=_ACCEPTED_FILE_TYPES,
            key="password_upload",
            label_visibility="collapsed",
        )
        if password_file is not None:
            st.caption(f"📎 {password_file.name} ({password_file.size / _BYTES_PER_MB:.1f}MB)")
        password_input = st.text_input(
            "パスワード",
            type="password",
            key="password_input",
        )

    if st.button(
        "🔓 パスワード解除",
        key="password_btn",
        disabled=password_file is None,
        use_container_width=True,
    ):
        if not password_input:
            st.warning("パスワードを入力してください。")
        elif _validate_upload(password_file):
            with (
                tempfile.NamedTemporaryFile(suffix=_PDF_SUFFIX, delete=False) as tmp_in,
                tempfile.NamedTemporaryFile(suffix=_PDF_SUFFIX, delete=False) as tmp_out,
            ):
                tmp_in.write(password_file.getvalue())  # type: ignore[union-attr]
                tmp_in_path = tmp_in.name
                tmp_out_path = tmp_out.name

            try:
                remove_pdf_password(tmp_in_path, tmp_out_path, password_input)
                with st.container(border=True):
                    st.success("パスワード解除が完了しました。")
                    result_data = Path(tmp_out_path).read_bytes()
                    original_name = password_file.name  # type: ignore[union-attr]
                    output_name = Path(original_name).stem + _OUTPUT_SUFFIX_UNLOCKED
                    st.download_button(
                        label="📥 解除済み PDF をダウンロード",
                        data=result_data,
                        file_name=output_name,
                        mime=_PDF_MIME,
                        key="password_download",
                        use_container_width=True,
                    )
            except PDFPasswordRemovalError as e:
                st.error(f"パスワード解除エラー: {e}")
            finally:
                Path(tmp_in_path).unlink(missing_ok=True)
                Path(tmp_out_path).unlink(missing_ok=True)

# --- フッター ---
st.markdown(
    f'<div class="custom-footer">'
    f"KaidokuPDF — 画像ベースの PDF を OCR で検索可能にするオープンソースツール。"
    f" ファイルサイズ上限: {MAX_FILE_SIZE_MB}MB"
    f"</div>",
    unsafe_allow_html=True,
)
