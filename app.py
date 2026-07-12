"""
app.py
======
PaperBrain — Streamlit frontend entry point.

Run with:
    streamlit run app.py

For remote/ngrok sharing, set API_BASE_URL in .env to the ngrok API tunnel URL.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import requests
import streamlit as st

import config
from frontend.components import (
    render_app_header,
    render_assistant_message,
    render_document_card,
    render_llm_status,
    render_processing_card,
    render_sidebar_header,
    render_stat_chips,
    render_typing_indicator,
    render_upload_duplicate,
    render_upload_success,
    render_user_message,
    render_welcome_screen,
)
from frontend.styles import CUSTOM_CSS

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PaperBrain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Inject CSS ───────────────────────────────────────────────────────────────
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ─── Logo (sidebar top-left) ─────────────────────────────────────────────────
_logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
if os.path.exists(_logo_path):
    st.logo(_logo_path, link="http://localhost:8501", icon_image=_logo_path)

# ─── Session State Init ───────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []          # list of {"role","content","sources","confidence","ms"}
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{int(time.time())}"
if "documents" not in st.session_state:
    st.session_state.documents = []         # list of document dicts from API
if "llm_available" not in st.session_state:
    st.session_state.llm_available = False
if "llm_model" not in st.session_state:
    st.session_state.llm_model = config.OLLAMA_MODEL
if "top_k" not in st.session_state:
    st.session_state.top_k = config.TOP_K
if "api_reachable" not in st.session_state:
    st.session_state.api_reachable = False

BASE = config.API_BASE_URL

from local_api import (
    api_health,
    api_list_documents,
    api_upload,
    api_chat,
    api_delete_document,
    api_delete_all,
    api_clear_history,
)



def refresh_state() -> None:
    """Refresh documents list and LLM status from the API."""
    health = api_health()
    if health:
        st.session_state.api_reachable = True
        llm_info = health.get("llm", {})
        st.session_state.llm_available = llm_info.get("available", False)
        st.session_state.llm_model = llm_info.get("model", config.OLLAMA_MODEL)
    else:
        st.session_state.api_reachable = False
        st.session_state.llm_available = False

    st.session_state.documents = api_list_documents()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    render_sidebar_header()

    # ── LLM Status ────────────────────────────────────────────────────────────
    if st.button("🔄 Refresh Status", use_container_width=True):
        refresh_state()
        st.rerun()

    if not st.session_state.api_reachable:
        # Try once on first load
        refresh_state()

    render_llm_status(
        available=st.session_state.llm_available,
        model_name=st.session_state.llm_model,
        provider=config.LLM_PROVIDER,
    )

    if not st.session_state.api_reachable:
        st.error(
            "⚠️ Cannot reach the API server.\n\n"
            "Make sure the FastAPI backend is running:\n"
            "```\npython api.py\n```",
            icon="🔌",
        )

    st.markdown("---")

    # ── Upload PDF ────────────────────────────────────────────────────────────
    st.markdown("#### 📤 Upload PDFs")
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        for uf in uploaded_files:
            # Check if already in current session documents
            already_in_list = any(
                d.get("filename") == uf.name or uf.name in d.get("filename", "")
                for d in st.session_state.documents
            )
            if already_in_list:
                continue

            with st.spinner(f"Processing {uf.name}…"):
                result = api_upload(uf.read(), uf.name)

            if result is None or "error" in result:
                st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
            elif result.get("already_exists"):
                render_upload_duplicate(result.get("filename", uf.name))
                refresh_state()
            else:
                render_upload_success(
                    result.get("filename", uf.name),
                    result.get("page_count", 0),
                    result.get("chunk_count", 0),
                    result.get("processing_time_ms", 0),
                )
                refresh_state()

    st.markdown("---")

    # ── Document List ─────────────────────────────────────────────────────────
    docs = st.session_state.documents
    if docs:
        st.markdown(f"#### 📚 Documents ({len(docs)})")
        for doc in docs:
            render_document_card(doc)
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🗑️", key=f"del_{doc['filename']}", help="Delete this document"):
                    with st.spinner("Deleting…"):
                        ok = api_delete_document(doc["filename"])
                    if ok:
                        st.success(f"Deleted {doc['filename']}")
                        refresh_state()
                        st.rerun()
                    else:
                        st.error("Delete failed.")

        st.markdown("---")

        # ── Danger zone ───────────────────────────────────────────────────────
        with st.expander("⚠️ Danger Zone"):
            st.warning("This will permanently delete all documents and embeddings.")
            if st.button("🗑️ Delete ALL Documents", use_container_width=True, type="primary"):
                with st.spinner("Deleting all…"):
                    ok = api_delete_all()
                if ok:
                    st.success("All documents deleted.")
                    refresh_state()
                    st.rerun()
    else:
        st.markdown(
            "<div style='text-align:center;color:var(--text-muted);font-size:0.82rem;padding:1rem 0'>"
            "No documents yet.<br>Upload a PDF to get started."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Settings ──────────────────────────────────────────────────────────────
    with st.expander("⚙️ Settings"):
        st.session_state.top_k = st.slider(
            "Top-K Chunks",
            min_value=1,
            max_value=15,
            value=st.session_state.top_k,
            help="Number of document chunks retrieved per query.",
        )
        st.markdown(
            f"<div style='font-size:0.72rem;color:var(--text-muted)'>"
            f"Session: <code>{st.session_state.session_id[-12:]}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Clear Chat ────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        api_clear_history(st.session_state.session_id)
        st.session_state.session_id = f"session_{int(time.time())}"
        st.rerun()

    # ── Footer stats ──────────────────────────────────────────────────────────
    if docs:
        total_chunks = sum(d.get("chunk_count", 0) for d in docs)
        render_stat_chips(len(docs), total_chunks, 0)


# ─── Main Chat Window ─────────────────────────────────────────────────────────

render_app_header(
    doc_count=len(st.session_state.documents),
    llm_online=st.session_state.llm_available,
)

# ── Chat history display ───────────────────────────────────────────────────────
chat_area = st.container()

with chat_area:
    if not st.session_state.messages:
        render_welcome_screen()
    else:
        for msg in st.session_state.messages:
            ts = msg.get("timestamp", "")
            if msg["role"] == "user":
                render_user_message(msg["content"], timestamp=ts)
            else:
                render_assistant_message(
                    content=msg["content"],
                    sources=msg.get("sources", []),
                    confidence=msg.get("confidence", 0.0),
                    processing_ms=msg.get("processing_ms", 0),
                    timestamp=ts,
                )

# ── Chat input ─────────────────────────────────────────────────────────────────
question = st.chat_input(
    "Ask a question about your documents…",
    disabled=not st.session_state.api_reachable,
)

if question:
    if not st.session_state.documents:
        st.warning(
            "⚠️ Please upload at least one PDF document before asking questions.",
            icon="📄",
        )
        st.stop()

    # Save user message
    ts_now = datetime.now().strftime("%H:%M")
    st.session_state.messages.append({
        "role": "user",
        "content": question,
        "timestamp": ts_now,
    })

    # Show typing indicator
    typing_placeholder = st.empty()
    with typing_placeholder:
        render_typing_indicator()

    # Call RAG API
    with st.spinner(""):
        response = api_chat(
            question=question,
            session_id=st.session_state.session_id,
            top_k=st.session_state.top_k,
        )

    typing_placeholder.empty()

    if response is None or "error" in response:
        error_msg = response.get("error", "Unknown error") if response else "API unreachable"
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"❌ Error: {error_msg}",
            "sources": [],
            "confidence": 0.0,
            "processing_ms": 0,
            "timestamp": datetime.now().strftime("%H:%M"),
        })
    else:
        st.session_state.messages.append({
            "role": "assistant",
            "content": response.get("answer", "No answer returned."),
            "sources": [s for s in response.get("sources", [])],
            "confidence": response.get("confidence", 0.0),
            "processing_ms": response.get("processing_time_ms", 0),
            "timestamp": datetime.now().strftime("%H:%M"),
        })

    st.rerun()

# Force reload

# Force reload 2
