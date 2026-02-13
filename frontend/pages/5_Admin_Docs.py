import streamlit as st
import time
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.docs_vm import DocsViewModel

# -----------------------------
# Auth & Admin Guard
# -----------------------------
st.set_page_config(page_title="Admin Docs", page_icon="📂")

token = st.session_state.get("token")
user = st.session_state.get("user")

if not token or not user:
    st.warning("Please log in first.")
    st.switch_page("pages/0_Login.py")
    st.stop()

# Simple Master Password Check
if "admin_unlocked" not in st.session_state:
    st.session_state["admin_unlocked"] = False

if not st.session_state["admin_unlocked"]:
    st.title("🔐 Admin Access Required")
    st.caption("This area is restricted to Master/Admin users.")
    
    with st.form("admin_login"):
        pwd = st.text_input("Enter Master Password", type="password")
        submitted = st.form_submit_button("Unlock")
        
        if submitted:
            if pwd == "Docs123": # TODO: Move to env var or real RBAC
                st.session_state["admin_unlocked"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# -----------------------------
# MVVM Setup
# -----------------------------
base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
try:
    api = ApiClient(base_url=base_url, token=token)
    vm = DocsViewModel(api)
except Exception as e:
    st.error(f"Failed to connect to backend: {e}")
    st.stop()

# -----------------------------
# UI
# -----------------------------
st.title("📂 Document Management")
st.caption("Manage the knowledge base. Deleting a file removes all its chunks from the vector database.")

col1, col2 = st.columns([0.8, 0.2])
if col2.button("🔄 Refresh", use_container_width=True):
    st.rerun()

st.divider()

# List Docs
with st.spinner("Fetching documents..."):
    try:
        files = vm.list_documents()
        # Sort for better UX
        files = sorted(files)
    except Exception as e:
        st.error(f"Failed to fetch documents: {e}")
        files = []

if not files:
    st.info("No documents found in the database. Upload some via the Chat page!")
else:
    st.success(f"Found {len(files)} documents.")
    
    # Header
    h1, h2 = st.columns([0.8, 0.2])
    h1.markdown("**Filename**")
    h2.markdown("**Action**")
    
    for file in files:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(file)
        
        # Unique key is crucial for buttons in loops
        if c2.button("🗑️ Delete", key=f"del_{file}", type="primary", use_container_width=True):
            with st.spinner(f"Deleting {file}..."):
                try:
                    vm.delete_document(file)
                    st.toast(f"Deleted {file}", icon="✅")
                    time.sleep(1) # Give time to toast
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete: {e}")

st.divider()
if st.button("🔒 Lock Admin Mode"):
    st.session_state["admin_unlocked"] = False
    st.rerun()
