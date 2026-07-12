"""
frontend/styles.py
==================
Custom CSS for the PaperBrain Streamlit UI.
Groww-inspired clean aesthetic.
"""

CUSTOM_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── CSS Variables (Groww Aesthetic) ── */
:root {
    --bg-primary:    #ffffff;
    --bg-secondary:  #0f172a;
    --bg-card:       #f8fafc;
    --bg-card-hover: #f1f5f9;
    --border:        #e8ebf0;
    --border-dark:   rgba(255,255,255,0.1);
    --accent:        #1d4ed8;
    --accent-light:  #bfdbfe;
    --accent-dim:    rgba(29,78,216,0.1);
    --success:       #22c55e;
    --warning:       #f59e0b;
    --danger:        #ef4444;
    --text-primary:  #1b2029;
    --text-secondary:#44475b;
    --text-muted:    #64748b;
    --text-sidebar:  #f1f5f9;
    --user-bubble:   #1b2029;
    --bot-bubble:    #f8fafc;
    --font-main:     'Inter', sans-serif;
    --font-mono:     'JetBrains Mono', monospace;
    --radius-sm:     8px;
    --radius-md:     12px;
    --radius-lg:     16px;
    --transition:    0.2s cubic-bezier(0.4,0,0.2,1);
}

/* ── Base ── */
html, body, [class*="css"] {
    font-family: var(--font-main) !important;
}

/* ── Main App Background ── */
.stApp {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* ── Hide Streamlit branding ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Main block container ── */
.block-container {
    padding: 2rem 2rem 140px 2rem !important; /* Extra bottom padding for chat input so it does not overlap */
    max-width: 100% !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border-dark) !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1rem !important;
}
[data-testid="stSidebar"] [class*="css"] {
    color: var(--text-sidebar) !important;
}
[data-testid="stSidebar"] hr {
    border-top: 1px solid var(--border-dark) !important;
}

/* ── Sidebar title ── */
.sidebar-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 0.25rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.sidebar-subtitle {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-bottom: 1.5rem;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(255,255,255,0.15) !important;
    border-radius: var(--radius-md) !important;
    transition: var(--transition) !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
    background: rgba(29,78,216,0.1) !important;
}

/* ── Document card ── */
.doc-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--radius-md);
    padding: 0.65rem 0.85rem;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    transition: var(--transition);
}
.doc-card:hover {
    border-color: rgba(29,78,216,0.45);
}
.doc-icon { font-size: 1.2rem; flex-shrink: 0; }
.doc-info { flex: 1; min-width: 0; }
.doc-name {
    font-size: 0.82rem;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.doc-meta {
    font-size: 0.7rem;
    color: #94a3b8;
    margin-top: 0.15rem;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
}
.badge-success { background: #eff6ff; color: #1e40af; }

/* ── Chat message bubble ── */
.message-row {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1rem;
}
.message-row.user { flex-direction: row-reverse; }

.avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
    font-weight: 700;
}
.avatar-user { background: var(--user-bubble); color: #fff; }
.avatar-bot  {
    background: var(--accent); color: #fff;
}

.bubble {
    max-width: 78%;
    padding: 0.9rem 1.1rem;
    border-radius: var(--radius-lg);
    line-height: 1.65;
    font-size: 0.9rem;
}
.bubble-user {
    background: var(--user-bubble);
    color: #fff;
    border-bottom-right-radius: 4px;
}
.bubble-bot {
    background: var(--bot-bubble);
    border: 1px solid var(--border);
    color: var(--text-primary);
    border-bottom-left-radius: 4px;
}

/* ── Source citations ── */
.citations-wrapper { margin-top: 0.85rem; border-top: 1px solid var(--border); padding-top: 0.75rem; }
.citations-title { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem; }
.citation-item {
    background: #fff;
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.35rem;
    font-size: 0.78rem;
}

/* ── Streamlit chat input ── */
[data-testid="stChatInput"] {
    background: var(--bg-primary) !important;
    padding-bottom: 30px !important;
}
[data-testid="stChatInput"] > div {
    background: var(--bg-card) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 99px !important;
}
[data-testid="stChatInput"] > div:focus-within {
    border-color: var(--accent) !important;
}
[data-testid="stChatInput"] textarea { color: var(--text-primary) !important; }
[data-testid="stChatInput"] button { background: var(--accent) !important; border-radius: 50% !important; }

/* ── Buttons ── */
.stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    transition: var(--transition) !important;
}
.stButton > button:hover { background: #1e40af !important; }
.danger-btn > button { background: transparent !important; color: #ef4444 !important; border: 1px solid rgba(239,68,68,0.3) !important; }
.danger-btn > button:hover { background: rgba(239,68,68,0.1) !important; border-color: #ef4444 !important; }

/* ── Welcome panel ── */
.welcome-panel {
    text-align: center;
    padding: 3rem 2rem 2rem 2rem;
    margin-bottom: 150px;
}
.welcome-icon {
    width: 76px; height: 76px;
    margin: 0 auto 1.5rem auto;
    background: linear-gradient(135deg, var(--accent), #60a5fa);
    border-radius: var(--radius-lg);
    display: flex; align-items: center; justify-content: center;
    font-size: 2.2rem;
    box-shadow: 0 10px 28px rgba(29,78,216,0.25);
    animation: float 3s ease-in-out infinite;
}
.welcome-title {
    font-size: 1.8rem; font-weight: 800; color: var(--text-primary);
    margin-bottom: 0.5rem; letter-spacing: -0.02em;
}
.welcome-title span { color: var(--accent); }
.welcome-text {
    font-size: 0.95rem; color: var(--text-muted); max-width: 450px;
    margin: 0 auto 2.5rem auto; line-height: 1.7;
}
.feature-grid {
    display: flex; justify-content: center; gap: 0.75rem; flex-wrap: wrap; max-width: 700px; margin: 0 auto;
}
.feature-chip {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 0.85rem 1.25rem;
    color: var(--text-primary); font-size: 0.8rem; font-weight: 600;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
}
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
</style>
"""

WELCOME_PANEL_HTML = """
<div class="welcome-panel">
    <div class="welcome-icon">&#x1F9E0;</div>
    <div class="welcome-title">Ask <span>PaperBrain</span></div>
    <div class="welcome-text">
        Upload your PDFs and ask any question.<br/>
        Answers come <strong>only from your documents</strong> &mdash; zero hallucinations.
    </div>
    <div class="feature-grid">
        <div class="feature-chip">&#x1F50D; Semantic Search</div>
        <div class="feature-chip">&#x1F3AF; Exact Citations</div>
        <div class="feature-chip">&#x1F512; 100% Offline</div>
    </div>
</div>
<div style="height: 150px; width: 100%; display: block;"></div>
"""

TYPING_INDICATOR_HTML = """
<div class="message-row" style="margin-bottom:1rem">
    <div class="avatar avatar-bot" style="background:var(--accent);color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;font-weight:700">&#x1F916;</div>
    <div class="bubble bubble-bot" style="display:flex;align-items:center;gap:6px;padding:0.75rem 1.1rem">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--text-muted);animation:bounce 1s infinite 0s"></span>
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--text-muted);animation:bounce 1s infinite 0.2s"></span>
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--text-muted);animation:bounce 1s infinite 0.4s"></span>
        <style>@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}</style>
    </div>
</div>
"""
