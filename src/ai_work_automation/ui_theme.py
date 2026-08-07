"""Streamlit Apple-inspired theme CSS."""

from __future__ import annotations

import streamlit as st

_APPLE_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

:root {
  --ap-bg: #f5f5f7;
  --ap-surface: #ffffff;
  --ap-text: #1d1d1f;
  --ap-secondary: #6e6e73;
  --ap-border: rgba(0, 0, 0, 0.08);
  --ap-blue: #0071e3;
  --ap-blue-hover: #0077ed;
  --ap-radius: 14px;
  --ap-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.04);
  --ap-font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
    "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", sans-serif;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
  background: var(--ap-bg) !important;
  color: var(--ap-text) !important;
  font-family: var(--ap-font) !important;
  -webkit-font-smoothing: antialiased;
}

[data-testid="stHeader"] {
  background: rgba(245, 245, 247, 0.82) !important;
  backdrop-filter: saturate(180%) blur(16px);
  border-bottom: 1px solid var(--ap-border);
}

[data-testid="stToolbar"] { background: transparent !important; }

/* Main column: use available width (responsive), avoid huge side gutters */
.block-container {
  padding-top: 1.1rem !important;
  padding-bottom: 2rem !important;
  padding-left: 1.25rem !important;
  padding-right: 1.25rem !important;
  max-width: min(1600px, 100%) !important;
}
@media (min-width: 1400px) {
  .block-container {
    padding-left: 1.75rem !important;
    padding-right: 1.75rem !important;
  }
}
@media (max-width: 900px) {
  .block-container {
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
    padding-top: 0.85rem !important;
  }
  .ap-hero {
    padding: 1rem 1.1rem !important;
    border-radius: 16px !important;
  }
  .ap-hero-title {
    font-size: 1.45rem !important;
  }
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: #fafafa !important;
  border-right: 1px solid var(--ap-border) !important;
}
[data-testid="stSidebar"] * {
  font-family: var(--ap-font) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  letter-spacing: -0.02em;
  font-weight: 600 !important;
}

/* Headings */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: var(--ap-font) !important;
  letter-spacing: -0.03em !important;
  font-weight: 650 !important;
  color: var(--ap-text) !important;
}
h1 { font-size: 2rem !important; font-weight: 700 !important; }
h2, h3 { font-size: 1.25rem !important; }

p, label, .stMarkdown, .stCaption, .stText {
  font-family: var(--ap-font) !important;
}
[data-testid="stCaptionContainer"], .stCaption {
  color: var(--ap-secondary) !important;
}

/* Brand hero strip */
.ap-hero {
  margin: 0 0 0.85rem 0;
  padding: 1.05rem 1.35rem 1rem;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f7f7f9 100%);
  border: 1px solid var(--ap-border);
  box-shadow: var(--ap-shadow);
}
.ap-hero-kicker {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ap-secondary);
  margin: 0 0 0.25rem 0;
}
.ap-hero-title {
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.035em;
  margin: 0;
  color: var(--ap-text);
}
.ap-hero-sub {
  margin: 0.3rem 0 0 0;
  font-size: 0.92rem;
  color: var(--ap-secondary);
  letter-spacing: -0.01em;
}

/* Tabs */
button[data-baseweb="tab"] {
  font-family: var(--ap-font) !important;
  font-weight: 550 !important;
  letter-spacing: -0.01em;
  color: var(--ap-secondary) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--ap-text) !important;
  font-weight: 650 !important;
}
[data-baseweb="tab-highlight"] {
  background-color: var(--ap-blue) !important;
}

/* Inputs */
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {
  border-radius: 12px !important;
  border-color: var(--ap-border) !important;
  background: var(--ap-surface) !important;
  box-shadow: none !important;
}
div[data-baseweb="input"]:focus-within > div,
div[data-baseweb="textarea"]:focus-within > div {
  border-color: var(--ap-blue) !important;
  box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.18) !important;
}

/* Buttons */
.stButton > button {
  font-family: var(--ap-font) !important;
  border-radius: 980px !important;
  font-weight: 600 !important;
  letter-spacing: -0.01em;
  padding: 0.45rem 1.15rem !important;
  border: 1px solid var(--ap-border) !important;
  background: #e8e8ed !important;
  color: var(--ap-text) !important;
  transition: background 0.15s ease, transform 0.1s ease;
}
.stButton > button:hover {
  background: #dcdce0 !important;
  border-color: transparent !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--ap-blue) !important;
  color: #ffffff !important;
  border: none !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
  background: var(--ap-blue-hover) !important;
}

/* Dataframes / tables as soft cards */
[data-testid="stDataFrame"],
[data-testid="stTable"] {
  border-radius: var(--ap-radius) !important;
  overflow: hidden;
  border: 1px solid var(--ap-border);
  box-shadow: var(--ap-shadow);
  background: var(--ap-surface);
}

/* Alerts */
div[data-testid="stAlert"] {
  border-radius: var(--ap-radius) !important;
  border: 1px solid var(--ap-border) !important;
  box-shadow: none !important;
}

/* Dividers */
hr { border-color: var(--ap-border) !important; opacity: 1 !important; }

/* Checkbox / radio labels */
[data-testid="stCheckbox"] label, [data-testid="stRadio"] label {
  font-family: var(--ap-font) !important;
  color: var(--ap-text) !important;
}

/* Expander */
[data-testid="stExpander"] {
  border: 1px solid var(--ap-border) !important;
  border-radius: var(--ap-radius) !important;
  background: var(--ap-surface) !important;
  box-shadow: var(--ap-shadow);
}

/* File uploader */
[data-testid="stFileUploader"] {
  border-radius: var(--ap-radius) !important;
}

/* Reduce noisy widget chrome */
.stSlider, .stSelectbox, .stMultiSelect, .stTextInput, .stTextArea {
  margin-bottom: 0.35rem;
}
</style>
"""


def inject_apple_theme() -> None:
    st.markdown(_APPLE_CSS, unsafe_allow_html=True)


def render_app_hero(
    *,
    title: str = "AI 업무 자동화",
    subtitle: str = "Salesforce · 출장 보고 · 메일까지, 한곳에서 이어서",
) -> None:
    st.markdown(
        f"""
<div class="ap-hero">
  <p class="ap-hero-kicker">Park Systems · Field Service</p>
  <p class="ap-hero-title">{title}</p>
  <p class="ap-hero-sub">{subtitle}</p>
</div>
""".strip(),
        unsafe_allow_html=True,
    )
