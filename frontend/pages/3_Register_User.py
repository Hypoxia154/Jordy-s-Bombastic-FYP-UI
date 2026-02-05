import streamlit as st

from ui.auth import require_role
from ui.components import render_user_metrics
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.users_vm import UsersViewModel

token, _me = require_role("admin", "master")

base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
api = ApiClient(base_url=base_url, token=token)
vm = UsersViewModel(api)

st.title("Register User")
st.caption("Create a new staff user (Admin & Master).")

with st.form("register_user"):
    c1, c2 = st.columns(2)
    with c1:
        username = st.text_input("Username*")
        name = st.text_input("Full name*")
    with c2:
        email = st.text_input("Email*")
        pwd = st.text_input("Password*", type="password")
    pwd2 = st.text_input("Confirm password*", type="password")
    submit = st.form_submit_button("Create staff user")

if submit:
    if not all([username, name, email, pwd, pwd2]):
        st.error("Fill in all required fields.")
    elif pwd != pwd2:
        st.error("Passwords do not match.")
    else:
        try:
            vm.create_user(username=username, password=pwd, name=name, email=email, role="staff")
            st.success(f"Created user: {username}")
        except Exception as e:
            st.error(f"Failed to create user: {e}")

# Display metrics
try:
    all_users = vm.list_users()
    render_user_metrics(all_users)
except:
    pass
