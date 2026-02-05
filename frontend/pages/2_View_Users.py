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

def onLoad_view_users():
    try:
        users = vm.list_users()
        st.session_state["view_users_data"] = users
        set_flash("success", f"Loaded {len(users)} users.")
    except Exception as e:
        st.session_state["view_users_data"] = []
        set_flash("error", f"Failed to load users: {e}")

if "view_users_loaded" not in st.session_state:
    onLoad_view_users()
    st.session_state["view_users_loaded"] = True

st.title("View Users")
st.caption("Read-only list of all users (Admin/Master only).")
render_flash()

if st.button("Refresh"):
    onLoad_view_users()

users = st.session_state.get("view_users_data", [])
df = pd.DataFrame(users)
if not df.empty and "role" in df.columns:
    df["role"] = df["role"].astype(str).str.upper()

st.dataframe(df, use_container_width=True, hide_index=True)

render_user_metrics(users)
