import streamlit as st
import pandas as pd

from ui.flash import set_flash, render_flash
from ui.auth import require_role
from ui.components import render_user_metrics
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.users_vm import UsersViewModel

token, _me = require_role("admin", "master")

base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
api = ApiClient(base_url=base_url, token=token)
vm = UsersViewModel(api)

st.title("View Users")
st.caption("Read-only list of all users (Admin/Master only).")

# Always reload fresh on page visit
with st.spinner("Loading users…"):
    try:
        users = vm.list_users()
    except Exception as e:
        users = []
        st.error(f"Failed to load users: {e}")

render_flash()

if st.button("🔄 Refresh", use_container_width=False):
    st.rerun()

df = pd.DataFrame([u if isinstance(u, dict) else u.model_dump() for u in users])
if not df.empty and "role" in df.columns:
    df["role"] = df["role"].astype(str).str.upper()

st.dataframe(df, use_container_width=True, hide_index=True)

render_user_metrics(users)
