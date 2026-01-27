import streamlit as st
from ui.flash import set_flash, render_flash
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.auth_vm import AuthViewModel

# NOTE: No st.set_page_config here! It's in streamlit_app.py now.

# -----------------------------
# MVVM setup
# -----------------------------
base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
api = ApiClient(base_url=base_url, token=None)
vm = AuthViewModel(api)

# -----------------------------
# View
# -----------------------------
st.title("Login")
render_flash()

with st.form("login_form"):
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")

if submitted:
    # Your ViewModel handles setting session_state['user'] automatically!
    state = vm.login((username or "").strip(), password or "")

    if state.ok:
        set_flash("success", state.message)
        st.rerun()
    else:
        set_flash("error", state.message)