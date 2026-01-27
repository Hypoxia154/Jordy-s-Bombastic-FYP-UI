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
with st.sidebar:
    st.markdown("### Chat Sessions")

    # OnLoad() - fetch sessions
    try:
        sessions = vm.list_sessions()
    except Exception as e:
        sessions = []
        st.error(f"Failed to load sessions: {e}")

    if st.button("New chat", use_container_width=True):
        st.session_state["active_session_id"] = None
        st.rerun()

    if st.button("Clear my history", use_container_width=True):
        try:
            vm.clear_sessions()
            st.session_state["active_session_id"] = None
            st.success("History cleared.")
        except Exception as e:
            st.error(f"Failed to clear history: {e}")
        st.rerun()

    st.divider()

    if not sessions:
        st.caption("No sessions yet.")
    else:
        for s in sessions:
            label = f"{s.title or '(untitled)'} • {s.created_at or ''}"
            if st.button(label, use_container_width=True, key=f"sess_{s.id}"):
                st.session_state["active_session_id"] = s.id
                st.rerun()

    # Upload section (UI-ready; backend wiring later)
    st.divider()
    st.markdown("### Upload Knowledge")

    uploaded = st.file_uploader("Upload PDF/TXT", type=["pdf", "txt"])
    if uploaded is not None:
        if st.button("Ingest", use_container_width=True):
            with st.spinner("Ingesting document..."):
                try:
                    msg = vm.ingest_document(uploaded)
                    st.success(f"Done! {msg}")
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

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

# Render messages
for m in messages:
    chat_bubble(
        m.role,
        m.content,
        m.sources,
        m.confidence,
    )

# -----------------------------
# Chat input (onPress)
# -----------------------------
question = st.chat_input("Ask about tenancy agreements, policies, real estate procedures...")
if question:
    with st.spinner("CRAG is retrieving relevant knowledge..."):
        try:
            resp = vm.query(question, active_session_id)
            st.session_state["active_session_id"] = resp.session_id or active_session_id
        except Exception as e:
            st.error(f"Query failed: {e}")
    st.rerun()
