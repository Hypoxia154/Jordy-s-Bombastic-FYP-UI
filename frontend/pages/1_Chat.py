import streamlit as st

from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.chat_vm import ChatViewModel
from ui.components import chat_bubble

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


    # Hybrid Approach: "Visualize This" Button
    # Only show for assistant messages that DON'T already have a chart
    # if m.role == "assistant" and not m.chart_data:
    #     # Use a unique key based on message index or ID to prevent conflicts
    #     if st.button("📊 Visualize this data", key=f"viz_{i}"):
    #         # Trigger a new query asking to visualize exactly this text
    #         with st.spinner("Generating chart..."):
    #              viz_query = f"Create a chart visualizing this data: {m.content}"
    #              try:
    #                  resp = vm.query(viz_query, active_session_id)
    #                  # Force reload to show new message
    #                  st.session_state["active_session_id"] = resp.session_id or active_session_id
    #                  st.rerun()
    #              except Exception as e:
    #                  st.error(f"Failed to generate chart: {e}")

# -----------------------------
# Chat input (onPress)
# -----------------------------
question = st.chat_input("Ask about tenancy agreements, policies, real estate procedures...")
if question:
    # Optimistic UI: Render user message immediately
    chat_bubble("user", question)

    with st.spinner("CRAG is retrieving relevant knowledge..."):
        try:
            resp = vm.query(question, active_session_id)
            st.session_state["active_session_id"] = resp.session_id or active_session_id
        except Exception as e:
            st.error(f"Query failed: {e}")
    st.rerun()
