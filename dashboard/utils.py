from __future__ import annotations

from io import BytesIO
from pathlib import Path
from textwrap import dedent

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent


def load_css(relative_path: str) -> None:
    css_path = BASE_DIR / relative_path

    if not css_path.is_file():
        st.error(f"CSS file not found: {css_path}")
        return

    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def compact_html(markup: str) -> str:
    cleaned = dedent(markup).strip()

    return "\n".join(
        line.strip()
        for line in cleaned.splitlines()
        if line.strip()
    )


def render_html(markup: str) -> None:
    st.markdown(
        compact_html(markup),
        unsafe_allow_html=True,
    )



