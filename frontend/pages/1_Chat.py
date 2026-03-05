import streamlit as st
import pandas as pd
import altair as alt

from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.chat_vm import ChatViewModel
from ui.components import chat_bubble


VIZ_KEYWORDS = {"visualize", "visualise", "chart", "graph", "plot", "show chart", "make a chart", "make a graph"}



@st.dialog("Rename Chat")
def rename_chat_dialog(session_id: int, current_title: str, vm: ChatViewModel):
    new_title = st.text_input("New title", value=current_title, key=f"ren_{session_id}")
    if st.button("Save", type="primary", use_container_width=True):
        if new_title.strip() and new_title.strip() != current_title:
            try:
                vm.rename_session(session_id, new_title.strip())
            except Exception as e:
                st.error(f"Failed to rename: {e}")
        st.rerun()

def _is_viz_request(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in VIZ_KEYWORDS)


def _render_chart(chart_data: list, caption: str = "📊 Chart"):
    """Renders an Altair chart from a list of {label, value, chart_type} dicts."""
    try:
        df = pd.DataFrame(chart_data)
        if df.empty or "label" not in df.columns or "value" not in df.columns:
            return
        chart_type = df["chart_type"].iloc[0] if "chart_type" in df.columns else "bar"
        st.caption(caption)
        
        if chart_type == "pie":
            chart = alt.Chart(df).encode(
                theta=alt.Theta("value:Q", stack=True),
                color=alt.Color("label:N", scale=alt.Scale(scheme='blues')),
                tooltip=["label", "value"]
            ).mark_arc(innerRadius=0)
        elif chart_type == "line":
            chart = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X('label:N', title='Label', sort=None),
                y=alt.Y('value:Q', title='Value'),
                tooltip=["label", "value"],
                color=alt.value("#3b82f6")
            )
        else:
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('label:N', title='Label', sort=None),
                y=alt.Y('value:Q', title='Value'),
                color=alt.Color('value:Q', scale=alt.Scale(scheme='blues'), legend=None),
                tooltip=["label", "value"]
            )
            
        # Common layout configurations
        chart = chart.properties(height=350).configure_view(strokeWidth=0)
        st.altair_chart(chart, use_container_width=True)
        with st.expander("📋 View Raw Data"):
            st.dataframe(df[["label", "value"]], use_container_width=True)
    except Exception as e:
        st.error(f"Could not render chart: {e}")

def render_documents_panel(api):
    """Renders the document summarization panel inline in the main content area."""
    try:
        data = api.get("/crag/documents/my")
        files = data.get("files", [])
    except Exception as e:
        st.error(f"Failed to load documents: {e}")
        return

    if not files:
        st.info("No documents available. Ask your admin to upload and assign documents.")
        return

    c1, c2, c3 = st.columns([0.4, 0.35, 0.25])
    selected = c1.selectbox("Document", files, label_visibility="collapsed",
                             key="sum_doc_select", placeholder="Select a document…")
    focus = c2.text_input("Focus (optional)", placeholder="e.g. deposit, termination…",
                           label_visibility="collapsed", key="sum_focus")
    mode = c3.radio("Output", ["Infographic", "Summary"], horizontal=False,
                    label_visibility="collapsed", key="sum_mode")

    if st.button("✨ Generate", type="primary", use_container_width=False, key="sum_generate"):
        payload = {"file_name": selected, "focus": focus or None, "mode": mode}
        with st.spinner(f"Generating {mode} for **{selected}**…"):
            try:
                res = api.post("/crag/document_summary", payload)
                st.session_state["doc_summary_result"] = res
            except Exception as e:
                st.error(f"Summary failed: {e}")


# -----------------------------
# Auth guard
# -----------------------------
token = st.session_state.get("token")
user = st.session_state.get("user")
if not token or not user:
    st.warning("Please log in first.")
    st.switch_page("pages/0_Login.py")
    st.stop()

# Ensure stable state keys
st.session_state.setdefault("active_session_id", None)

# -----------------------------
# MVVM setup
# -----------------------------
base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
api = ApiClient(base_url=base_url, token=token)
vm = ChatViewModel(api)

# -----------------------------
# UI (View)
# -----------------------------
st.title("Chat")
st.caption("Ask about tenancy agreements, policies, and real estate procedures.")

# -----------------------------
# Sidebar: Sessions + Upload
# -----------------------------
# -----------------------------
# Sidebar: Sessions + Upload
# -----------------------------
with st.sidebar:
    # Document Scope Section
    with st.expander("📂 Document Scope", expanded=True):
        st.caption("Scope queries to a single document.")
        try:
            all_doc_files = api.get("/crag/documents/my").get("files", [])
        except Exception:
            all_doc_files = []

        _DOC_ALL = "🌐 All Documents"
        doc_options = [_DOC_ALL] + all_doc_files

        # For admins/master: add a quick search box to narrow options before picking
        _role = (st.session_state.get("user") or {}).get("role", "staff")
        if _role in ("admin", "master") and len(all_doc_files) > 5:
            _search = st.text_input(
                "🔍 Search documents",
                key="doc_scope_search",
                placeholder="Type to filter...",
                label_visibility="collapsed",
            )
            if _search:
                filtered_options = [_DOC_ALL] + [f for f in all_doc_files if _search.lower() in f.lower()]
            else:
                filtered_options = doc_options
        else:
            filtered_options = doc_options

        selected_doc = st.selectbox(
            "Select document",
            filtered_options,
            key="active_doc_filter_select",
            label_visibility="collapsed",
        )
        # Persist choice — None means "all"
        st.session_state["active_doc_filter"] = (
            None if selected_doc == _DOC_ALL else selected_doc
        )
        if st.session_state["active_doc_filter"]:
            st.caption(f"🔒 Scoped to: `{st.session_state['active_doc_filter']}`")

    # History Section
    with st.expander("History", expanded=True, icon=":material/history:"):
        # New chat button
        if st.button("✏️ New Chat", help="Start a fresh chat", use_container_width=True):
            import time
            st.session_state["active_session_id"] = None
            st.rerun()

        st.divider()

        # Session List
        try:
            sessions = vm.list_sessions()
        except Exception:
            sessions = []

        if not sessions:
            st.caption("No history yet.")
        else:
            for s in sessions:
                # Truncate title more aggressively to prevent multi-line wrapping in sidebar
                raw_title = s.title or "Untitled"
                t = raw_title[:20] + "…" if len(raw_title) > 20 else raw_title
                d = (s.created_at or "").split("T")[0]
                is_pinned = bool(s.pinned)
                is_active = s.id == st.session_state.get("active_session_id")

                pin_icon = "📌 " if is_pinned else ""
                label = f"{pin_icon}{t}"

                # Clean 2-column layout with small gap to prevent uneven layouts
                sc1, sc2 = st.columns([0.85, 0.15], vertical_alignment="center", gap="small")

                btn_type = "primary" if is_active else "secondary"
                if sc1.button(label, key=f"sess_{s.id}", use_container_width=True,
                              type=btn_type, help=f"{raw_title} · {d}"):
                    st.session_state["active_session_id"] = s.id
                    st.rerun()

                with sc2.popover("⋮", use_container_width=True):
                    if st.button("✏️ Rename", key=f"renbtn_{s.id}", use_container_width=True):
                        rename_chat_dialog(s.id, raw_title, vm)
                        
                    pin_label = "📌 Unpin" if is_pinned else "📌 Pin"
                    if st.button(pin_label, key=f"pin_{s.id}", use_container_width=True):
                        try:
                            vm.pin_session(s.id, not is_pinned)
                        except Exception:
                            pass
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"del_{s.id}",
                                 use_container_width=True, type="primary"):
                        try:
                            vm.delete_session(s.id)
                            if st.session_state.get("active_session_id") == s.id:
                                st.session_state["active_session_id"] = None
                        except Exception:
                            pass
                        st.rerun()

# -----------------------------
# Load messages for active session
# -----------------------------
active_session_id = st.session_state.get("active_session_id")

# Clear viz charts only when the user switches to a different session
_prev_viz_session = st.session_state.get("_prev_viz_session", -1)
if _prev_viz_session != active_session_id:
    for key in list(st.session_state.keys()):
        if key.startswith("viz_inline_"):
            del st.session_state[key]
    st.session_state["_prev_viz_session"] = active_session_id

messages = []
if active_session_id:
    try:
        messages = vm.get_messages(active_session_id)
    except Exception as e:
        st.error(f"Failed to load messages: {e}")
        messages = []

# ─────────────────────────────
# Document Summary Panel (top of main area)
# ─────────────────────────────
with st.expander("📄 Summarize a Document", expanded=False):
    render_documents_panel(api)

# Show summary result if available
if st.session_state.get("doc_summary_result"):
    res = st.session_state["doc_summary_result"]
    mode_used = res.get("mode", "summary")

    # Inject custom CSS to hide the button border and background for the X button
    st.markdown("""
    <style>
    div[data-testid="stButton"] button[kind="secondary"] {
        border: none !important;
        background: transparent !important;
        color: #9ca3af !important;
        padding: 0 !important;
        box-shadow: none !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        color: #ef4444 !important;
        background: rgba(239, 68, 68, 0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("<br>", unsafe_allow_html=True)
        # Custom header row
        h_col1, h_col2 = st.columns([0.95, 0.05], vertical_alignment="center")
        
        icon = "📋" if mode_used == "summary" else "📊"
        title = "Summary" if mode_used == "summary" else "Infographic"
        
        h_col1.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.75rem;padding-bottom:0.5rem;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:1rem;">
            <span style="font-size:1.4rem;">{icon}</span>
            <span style="font-size:1.3rem;font-weight:600;color:#f3f4f6;">Document {title}</span>
        </div>
        """, unsafe_allow_html=True)
        
        with h_col2:
            st.markdown("<div style='margin-top:-0.5rem;'>", unsafe_allow_html=True)
            if st.button("✕", key="close_summary", help="Close panel"):
                st.session_state["doc_summary_result"] = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if mode_used == "summary":
            # API returns: {"mode": "summary", "text": "..."}
            st.markdown(f'<div style="padding:0.5rem 0;color:#e2e8f0;font-size:1.05rem;line-height:1.7;">\n{res.get("text", "*(No content returned)*")}\n</div>', unsafe_allow_html=True)

        else:
            # Infographic layout
            info = res.get("infographic")
            if info:
                if "title" in info:
                    st.markdown(f"<h2 style='color:#60a5fa;margin-bottom:0;'>{info['title']}</h2>", unsafe_allow_html=True)
                if "one_liner" in info:
                    st.markdown(f"<p style='color:#9ca3af;font-size:0.95rem;margin-top:0.2rem;margin-bottom:1.5rem;'>{info['one_liner']}</p>", unsafe_allow_html=True)

                for card in info.get("cards", []):
                    st.markdown(f"**{card.get('heading', '')}**")
                    for b in card.get("bullets", []):
                        st.markdown(f"- {b}")

                key_terms = info.get("key_terms", [])
                if key_terms:
                    st.markdown("<br>**📖 Key Terms**", unsafe_allow_html=True)
                    for kt in key_terms:
                        st.markdown(f"- **{kt.get('term', '')}**: {kt.get('meaning', '')}")

                faq = info.get("quick_faq", [])
                if faq:
                    st.markdown("<br>**❓ Quick FAQ**", unsafe_allow_html=True)
                    for qa in faq:
                        with st.expander(qa.get("q", "Question")):
                            st.write(qa.get("a", ""))
            else:
                raw_fallback = res.get("infographic_raw", "*(No content returned)*")
                st.markdown(f'<div style="padding:1rem;background:rgba(255,255,255,0.05);border-radius:8px;">\n{raw_fallback}\n</div>', unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)



# Empty State / Welcome Screen with suggested questions
if not messages:
    st.markdown(
        """
        <div style="text-align:center;padding:2rem 1rem 1rem;color:#9ca3af;">
            <h3 style="color:#e2e8f0;">👋 Welcome back!</h3>
            <p>Ask anything about tenancy agreements, policies, and real estate procedures.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    SUGGESTED = [
        "What are the tenant's rights for early termination?",
        "What is the standard notice period for ending a tenancy?",
        "How is the security deposit calculated?",
        "What repairs is the landlord responsible for?",
        "What happens if rent is paid late?",
        "Can the landlord enter the property without notice?",
    ]

    st.markdown("<p style='text-align:center;font-size:0.82rem;color:#6b7280;margin-bottom:0.5rem;'>💡 Try asking:</p>", unsafe_allow_html=True)
    cols = st.columns(2)
    for idx, suggestion in enumerate(SUGGESTED):
        if cols[idx % 2].button(suggestion, key=f"sugg_{idx}", use_container_width=True):
            st.session_state["_prefill_question"] = suggestion
            st.rerun()

# Render messages
for i, m in enumerate(messages):
    # Format timestamp: "2026-03-04T14:30:00" → "14:30"
    ts = ""
    if getattr(m, "timestamp", None):
        try:
            ts_raw = str(m.timestamp)
            ts = ts_raw.split("T")[1][:5] if "T" in ts_raw else ts_raw[:5]
        except Exception:
            ts = ""

    chat_bubble(m.role, m.content, m.sources, m.confidence, timestamp=ts)

    if m.chart_data:
        _render_chart(m.chart_data, "📊 Visualized Data:")

    # Render inline chart triggered by 'visualize this' text prompt
    inline_key = f"viz_inline_{i}"
    if st.session_state.get(inline_key) and not m.chart_data:
        _render_chart(st.session_state[inline_key], "📊 Visualized Data")


# -----------------------------
# Chat input (onPress)
# -----------------------------
# Handle suggested question pre-fill
_prefill = st.session_state.pop("_prefill_question", None)
question = st.chat_input("Ask a question… or say 'visualize this' to chart the last answer") or _prefill
if question:

    # -- Visualization intent: intercept before CRAG --
    if _is_viz_request(question) and messages:
        # Find the last assistant message
        last_assistant = next(
            (m for m in reversed(messages) if m.role == "assistant"), None
        )
        if last_assistant:
            chat_bubble("user", question)
            with st.spinner("Extracting chart data..."):
                try:
                    result = api.post(
                        "/crag/visualize",
                        {"text": last_assistant.content, "hint": question}
                    )
                    chart_data = result.get("chart_data")
                    if chart_data:
                        # Store chart against the last assistant message index
                        last_idx = next(
                            i for i, m in reversed(list(enumerate(messages)))
                            if m.role == "assistant"
                        )
                        st.session_state[f"viz_inline_{last_idx}"] = chart_data
                        chat_bubble("assistant", "Here's the chart based on that response:")
                    else:
                        chat_bubble("assistant", "⚠️ I couldn't find any numerical data to chart in the last response. Try asking a question that returns specific numbers first (e.g. rent amounts, fees, periods).")
                except RuntimeError as e:
                    if "422" in str(e):
                        chat_bubble("assistant", "⚠️ No chartable numerical data found in the last response. Ask a question with specific numbers first.")
                    else:
                        chat_bubble("assistant", f"Chart generation failed: {e}")
            st.rerun()
        else:
            chat_bubble("assistant", "There's no previous response to visualize yet. Ask a question first!")
            st.rerun()


    else:
        chat_bubble("user", question)

        # Live placeholder assistant bubble
        with st.chat_message("assistant", avatar="🤖"):
            status_box = st.empty()
            live_box = st.empty()

            status_box.markdown("🔍 Retrieving relevant documents…")
            running_text = ""
            _file_filter = st.session_state.get("active_doc_filter")

            try:
                final_payload = None

                for ev in vm.query_stream(question, active_session_id, file_filter=_file_filter):
                    etype = ev.get("type")

                    if etype == "status":
                        _status_icons = {"retrieving": "🔍", "grading": "📋", "generating": "✍️", "reranking": "📊"}
                        _msg = ev.get("message", "Working…")
                        _icon = next((v for k, v in _status_icons.items() if k in _msg.lower()), "🟡")
                        status_box.markdown(f"{_icon} {_msg}")

                    elif etype == "delta":
                        running_text += ev.get("text", "")
                        live_box.markdown(running_text)

                    elif etype == "final":
                        final_payload = ev
                        break

                if not final_payload:
                    raise RuntimeError("Stream ended without a final response.")

                status_box.empty()
                live_box.markdown(final_payload.get("answer", ""))

                st.session_state["active_session_id"] = final_payload.get("session_id") or active_session_id

            except Exception as e:
                # Fallback to non-streaming so UI never becomes unusable
                status_box.empty()
                live_box.markdown(f"⚠️ Streaming failed, falling back: {e}")
                try:
                    resp = vm.query(question, active_session_id, file_filter=_file_filter)
                    st.session_state["active_session_id"] = resp.session_id or active_session_id
                except Exception as e2:
                    st.error(f"Query failed: {e2}")

        st.rerun()


