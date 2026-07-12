"""
frontend/components.py
=======================
Reusable Streamlit UI components for PaperBrain.
"""
from __future__ import annotations
import time
from datetime import datetime
import streamlit as st
from utils.file_utils import format_file_size

def render_sidebar_header() -> None:
    st.markdown("""
        <div class="sidebar-title">\U0001f9e0 PaperBrain</div>
        <div class="sidebar-subtitle">Powered by Ollama &middot; ChromaDB &middot; BGE</div>
        """, unsafe_allow_html=True)
    st.divider()

def render_document_card(doc: dict) -> None:
    size_str = format_file_size(doc.get("file_size_bytes", 0))
    pages = doc.get("page_count", "?")
    chunks = doc.get("chunk_count", "?")
    name = doc.get("filename", "unknown.pdf")
    st.markdown(f"""
        <div class="doc-card">
            <div class="doc-icon">\U0001f4c4</div>
            <div class="doc-info">
                <div class="doc-name" title="{name}">{name}</div>
                <div class="doc-meta">
                    {pages} pages &middot; {chunks} chunks &middot; {size_str}
                    &nbsp;<span class="badge badge-success">indexed</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_llm_status(available: bool, model_name: str, provider: str) -> None:
    if available:
        st.markdown(f"""
            <div class="doc-card" style="border-color:rgba(34,197,94,0.3)">
                <div class="doc-icon">\U0001f7e2</div>
                <div class="doc-info">
                    <div class="doc-name">{provider.capitalize()} &middot; {model_name}</div>
                    <div class="doc-meta">LLM connected</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <div class="doc-card" style="border-color:rgba(239,68,68,0.3)">
                <div class="doc-icon">\U0001f534</div>
                <div class="doc-info">
                    <div class="doc-name">{provider.capitalize()} &middot; {model_name}</div>
                    <div class="doc-meta">LLM offline &mdash; start Ollama</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_user_message(content: str, timestamp: str = "") -> None:
    ts = timestamp or datetime.now().strftime("%H:%M")
    st.markdown(f"""
        <div class="message-row user">
            <div class="avatar avatar-user">\U0001f464</div>
            <div style="display:flex;flex-direction:column;align-items:flex-end">
                <div class="bubble bubble-user">{content}</div>
                <div class="msg-meta user">{ts}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_assistant_message(content: str, sources: list = None, confidence: float = 0.0, processing_ms: int = 0, timestamp: str = "") -> None:
    ts = timestamp or datetime.now().strftime("%H:%M")
    st.markdown(f"""
        <div class="message-row">
            <div class="avatar avatar-bot">\U0001f916</div>
            <div style="display:flex;flex-direction:column">
                <div class="bubble bubble-bot">{content}</div>
                <div class="msg-meta">{ts}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    if sources:
        with st.expander("Sources"):
            for s in sources:
                st.markdown(f"**{s.get('filename','?')}** - Page {s.get('page_num','?')}")
                st.markdown(f"> _{s.get('content','')}..._")

def render_upload_success(filename: str, pages: int, chunks: int) -> None:
    st.success(f"Successfully processed {filename} ({pages} pages, {chunks} chunks).", icon="\U0001f4c4")

def render_upload_duplicate(filename: str) -> None:
    st.warning(f"File {filename} is already indexed.", icon="\u26a0\ufe0f")

def render_typing_indicator() -> None:
    from frontend.styles import TYPING_INDICATOR_HTML
    st.markdown(TYPING_INDICATOR_HTML, unsafe_allow_html=True)

def render_welcome_screen() -> None:
    from frontend.styles import WELCOME_PANEL_HTML
    st.markdown(WELCOME_PANEL_HTML, unsafe_allow_html=True)

def render_stat_chips(docs: int, chunks: int, queries: int) -> None:
    st.markdown(f"<div style='text-align:center;color:var(--text-muted);font-size:0.8rem;'>{docs} Documents &middot; {chunks} Chunks indexed</div>", unsafe_allow_html=True)

def render_processing_card(filename: str, bytes: int) -> None:
    size = format_file_size(bytes)
    st.markdown(f"<div class='processing-card'>Processing {filename} ({size})...</div>", unsafe_allow_html=True)

def render_app_header(doc_count: int, llm_online: bool) -> None:
    status = '<span style="color:var(--success)">\U0001f7e2 LLM Online</span>' if llm_online else '<span style="color:var(--danger)">\U0001f534 LLM Offline</span>'
    st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:0.75rem;margin-bottom:1.5rem">
            <h3 style="margin:0;font-weight:700;color:var(--text-primary);font-size:1.2rem">\U0001f9e0 PaperBrain Chat</h3>
            <div style="font-size:0.8rem;color:var(--text-muted);font-weight:600">
                {doc_count} PDF{'s' if doc_count != 1 else ''} &middot; {status}
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_app_header(doc_count: int, llm_online: bool) -> None:
    status = '<span style="color:var(--success)">\U0001f7e2 LLM Online</span>' if llm_online else '<span style="color:var(--danger)">\U0001f534 LLM Offline</span>'
    st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:0.75rem;margin-bottom:1.5rem">
            <h3 style="margin:0;font-weight:700;color:var(--text-primary);font-size:1.2rem">\U0001f9e0 PaperBrain Chat</h3>
            <div style="font-size:0.8rem;color:var(--text-muted);font-weight:600">
                {doc_count} PDF{'s' if doc_count != 1 else ''} &middot; {status}
            </div>
        </div>
    """, unsafe_allow_html=True)
