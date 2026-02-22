import streamlit as st
import pandas as pd
import plotly.express as px

from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.chat_vm import ChatViewModel
from ui.components import chat_bubble


VIZ_KEYWORDS = {"visualize", "visualise", "chart", "graph", "plot", "show chart", "make a chart", "make a graph"}


def _is_viz_request(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in VIZ_KEYWORDS)


def _render_chart(chart_data: list, caption: str = "📊 Chart"):
    """Renders a Plotly chart from a list of {label, value, chart_type} dicts."""
    try:
        df = pd.DataFrame(chart_data)
        if df.empty or "label" not in df.columns or "value" not in df.columns:
            return
        chart_type = df["chart_type"].iloc[0] if "chart_type" in df.columns else "bar"
        st.caption(caption)
        if chart_type == "pie":
            fig = px.pie(df, names="label", values="value",
                         color_discrete_sequence=px.colors.sequential.Blues_r)
        elif chart_type == "line":
            fig = px.line(df, x="label", y="value", markers=True,
                          color_discrete_sequence=["#3b82f6"])
        else:
            fig = px.bar(df, x="label", y="value", color="value",
                         color_continuous_scale="Blues", text_auto=True)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0", margin=dict(l=20, r=20, t=30, b=20),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("📋 View Raw Data"):
            st.dataframe(df[["label", "value"]], use_container_width=True)
    except Exception as e:
        st.error(f"Could not render chart: {e}")


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
    # History Section
    with st.expander("History", expanded=False, icon=":material/history:"):
        # Action Buttons Row
        c1, c2 = st.columns(2)
        if c1.button("New", help="Start a fresh chat", width="stretch"):
            import time
            with st.spinner("Starting new session..."):
                time.sleep(0.6)
            st.session_state["active_session_id"] = None
            st.rerun()
        if c2.button("Clear", help="Delete all history", width="stretch"):
            import time
            with st.spinner("Clearing history..."):
                time.sleep(0.8)
                try:
                    vm.clear_sessions()
                    st.session_state["active_session_id"] = None
                    st.success("Cleared")
                except Exception as e:
                    st.error(f"Error: {e}")
            st.rerun()

        # Session List
        try:
            sessions = vm.list_sessions()
        except:
            sessions = []

        if not sessions:
            st.caption("No history yet.")
        else:
            for s in sessions:
                # Truncate title and show clean date
                t = (s.title or "Untitled")[:20] + "..." if len(s.title or "") > 20 else (s.title or "Untitled")
                d = (s.created_at or "").split("T")[0]
                label = f"{t} ({d})"
                
                if st.button(label, key=f"sess_{s.id}", width="stretch", type="secondary"):
                    st.session_state["active_session_id"] = s.id
                    st.rerun()

    # Upload Section
    with st.expander("Knowledge Base", expanded=True, icon=":material/folder_open:"):
        st.caption("Upload documents to context.")
        uploaded = st.file_uploader("Upload PDF/TXT", type=["pdf", "txt"], label_visibility="collapsed")
        if uploaded is not None:
             if st.button("📥 Ingest File", width="stretch"):
                with st.spinner("Ingesting..."):
                    try:
                        msg = vm.ingest_document(uploaded)
                        st.success(f"Success!")
                        # Optional: clear uploader key if we could (hard in standard streamlit without hack)
                    except Exception as e:
                        st.error(f"Failed: {e}")

# -----------------------------
# Load messages for active session
# -----------------------------
active_session_id = st.session_state.get("active_session_id")

messages = []
if active_session_id:
    try:
        messages = vm.get_messages(active_session_id)
    except Exception as e:
        st.error(f"Failed to load messages: {e}")
        messages = []

# Empty State / Welcome Screen
if not messages:
    st.markdown(
        """
        <div style="
            text-align: center;
            padding: 3rem 1rem;
            color: #9ca3af;
        ">
            <h3>👋 Welcome back!</h3>
            <p>I'm ready to help you with tenancy agreements and policies.</p>
            <div style="
                display:flex; gap:1rem; justify-content:center; margin-top:2rem; flex-wrap:wrap;
            ">
                <div style="background:rgba(30,41,59,0.5);padding:1.5rem;border-radius:12px;border:1px solid rgba(255,255,255,0.1);max-width:220px;display:flex;flex-direction:column;align-items:center;gap:0.5rem;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/></svg>
                    <strong style="color:#e2e8f0;">Summarize</strong>
                    <span style="font-size:0.8rem;color:#9ca3af;">Upload a PDF and ask for a summary.</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Render messages
for i, m in enumerate(messages):
    chat_bubble(
        m.role,
        m.content,
        m.sources,
        m.confidence,
    )

    if m.chart_data:
        _render_chart(m.chart_data, "📊 Visualized Data:")

    # Render inline chart triggered by 'visualize this' text prompt
    inline_key = f"viz_inline_{i}"
    if st.session_state.get(inline_key) and not m.chart_data:
        _render_chart(st.session_state[inline_key], "📊 Visualized Data")



# -----------------------------
# Chat input (onPress)
# -----------------------------
question = st.chat_input("Ask a question, or type 'visualize this' to chart the last response...")
if question:
    # Clear any lingering inline charts from previous visualize requests
    for key in list(st.session_state.keys()):
        if key.startswith("viz_inline_"):
            del st.session_state[key]

    # -- Visualization intent: intercept before CRAG --
    if _is_viz_request(question) and messages:
        # Find the last assistant message
        last_assistant = next(
            (m for m in reversed(messages) if m.role == "assistant"), None
        )
        if last_assistant:
            chat_bubble("user", question)
            with st.spinner("Asking Gemini to extract chart data..."):
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
        # -- Normal CRAG flow --
        chat_bubble("user", question)
        with st.spinner("CRAG is retrieving relevant knowledge..."):
            try:
                resp = vm.query(question, active_session_id)
                st.session_state["active_session_id"] = resp.session_id or active_session_id
            except Exception as e:
                st.error(f"Query failed: {e}")
        st.rerun()
