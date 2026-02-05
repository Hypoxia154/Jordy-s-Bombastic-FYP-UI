import streamlit as st
from ui.flash import set_flash, render_flash
from ui.components import role_badge, render_user_metrics
from mvvm.services.api_client import ApiClient
from mvvm.viewmodels.users_vm import UsersViewModel

# -----------------------------
# Auth Guard
# -----------------------------
# We check this first to prevent rendering unauthorized content
if not st.session_state.get("is_authenticated", False):
    st.warning("Please log in first.")
    st.switch_page("pages/0_Login.py")

user = st.session_state.get("user") or {}
role = (user.get("role") or "").lower()

if role not in ("admin", "master"):
    st.error("Forbidden: Admin/Master only.")
    st.switch_page("pages/1_Chat.py")
    st.stop()

# -----------------------------
# MVVM setup
# -----------------------------
token = st.session_state.get("token")
base_url = st.session_state.get("api_base_url", "http://127.0.0.1:8000")
api = ApiClient(base_url=base_url, token=token)
vm = UsersViewModel(api)


# -----------------------------
# Handlers
# -----------------------------
def onLoad_manage_users():
    try:
        users = vm.list_users()
        st.session_state["manage_users_all"] = users
        # Filter out myself
        candidates = [u for u in users if u.get("username") != user.get("username")]
        st.session_state["manage_users_candidates"] = candidates

        # Default selection logic
        current = st.session_state.get("selected_username")
        valid_usernames = [u["username"] for u in candidates]
        if candidates and (not current or current not in valid_usernames):
            st.session_state["selected_username"] = candidates[0]["username"]

        set_flash("success", f"Loaded {len(users)} users.")
    except Exception as e:
        set_flash("error", f"Failed to load users: {e}")
        st.session_state["manage_users_candidates"] = []


def onSelect_user():
    label = st.session_state.get("selected_label")
    label_map = st.session_state.get("label_map", {})
    u = label_map.get(label)
    if u:
        st.session_state["selected_username"] = u["username"]
        st.session_state["edit_name"] = u.get("name", "")
        st.session_state["edit_email"] = u.get("email", "")


def onPress_update_user():
    username = st.session_state.get("selected_username")
    name = st.session_state.get("edit_name", "").strip()
    email = st.session_state.get("edit_email", "").strip()
    pwd = st.session_state.get("edit_password") or None
    try:
        vm.update_user(username, name=name, email=email, password=pwd)
        set_flash("success", "User details updated.")
        onLoad_manage_users()
        st.rerun()
    except Exception as e:
        set_flash("error", f"Update failed: {e}")


def onPress_update_role():
    username = st.session_state.get("selected_username")
    new_role = st.session_state.get("edit_role")
    try:
        vm.update_role(username, new_role)
        set_flash("success", "Role updated.")
        onLoad_manage_users()
        st.rerun()
    except Exception as e:
        set_flash("error", f"Role update failed: {e}")


def onPress_delete_user():
    username = st.session_state.get("selected_username")
    if not st.session_state.get("confirm_delete", False):
        set_flash("error", "Please confirm deletion.")
        return
    try:
        vm.delete_user(username)
        set_flash("success", "User deleted.")
        st.session_state["selected_username"] = None  # Reset selection
        onLoad_manage_users()
        st.rerun()
    except Exception as e:
        set_flash("error", f"Delete failed: {e}")


# -----------------------------
# Init
# -----------------------------
if "manage_users_loaded" not in st.session_state:
    onLoad_manage_users()
    st.session_state["manage_users_loaded"] = True

# -----------------------------
# UI
# -----------------------------
st.title("Manage Users")
render_flash()

if st.button("Refresh"):
    onLoad_manage_users()
    st.rerun()

candidates = st.session_state.get("manage_users_candidates", [])
if not candidates:
    st.info("No users found.")
    st.stop()

# Selection Logic
label_map = {f"{u['username']} • {u.get('name', '')}": u for u in candidates}
st.session_state["label_map"] = label_map
labels = list(label_map.keys())

# Find current index
current_username = st.session_state.get("selected_username")
idx = 0
for i, lbl in enumerate(labels):
    if label_map[lbl]["username"] == current_username:
        idx = i
        break

st.selectbox("Select user", labels, index=idx, key="selected_label", on_change=onSelect_user)

# Active User
u = label_map.get(labels[idx])
if not u: st.stop()

# Display Card
st.markdown(f"""
<div style="background:#262730; padding:15px; border-radius:10px; margin-bottom:20px;">
    <b>{u['username']}</b> | {u.get('name', '')} | {u.get('email', '')} <br>
    Role: {role_badge(u.get('role', ''))}
</div>
""", unsafe_allow_html=True)

# Forms
st.subheader("Edit Details")
with st.form("edit_form"):
    st.text_input("Name", value=st.session_state.get("edit_name", u.get("name")), key="edit_name")
    st.text_input("Email", value=st.session_state.get("edit_email", u.get("email")), key="edit_email")
    st.text_input("New Password", type="password", key="edit_password")
    if st.form_submit_button("Save"):
        onPress_update_user()

st.divider()

# Master Zone
st.subheader("Master Admin Actions")
if role != "master":
    st.info("Restricted to Master Admins.")
else:
    c1, c2 = st.columns(2)
    with c1:
        roles = ["staff", "admin", "master"]
        curr_role = u.get("role", "staff")
        ridx = roles.index(curr_role) if curr_role in roles else 0
        st.selectbox("Change Role", roles, index=ridx, key="edit_role")
        st.button("Update Role", on_click=onPress_update_role)
    with c2:
        st.warning("Delete user?")
        st.checkbox("Confirm delete", key="confirm_delete")
        st.button("Delete User", type="primary", on_click=onPress_delete_user)

# Display metrics
all_users = st.session_state.get("manage_users_all")
if not all_users:
    try:
        all_users = vm.list_users()
    except:
        all_users = []
render_user_metrics(all_users)