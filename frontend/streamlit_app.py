import streamlit as st
import importlib.util
from ui.css import apply_custom_css
from ui.components import sidebar_user_card

# -----------------------------
# Init Global State
# -----------------------------
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False

# -----------------------------
# Auth Check
# -----------------------------
is_logged_in = st.session_state.get("is_authenticated", False)
user = st.session_state.get("user") or {}
role = (user.get("role") or "").lower()

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="CRAG",
    layout="wide",
    initial_sidebar_state="expanded" if is_logged_in else "collapsed"
)

apply_custom_css()

# -----------------------------
# Not Logged In - Show Login
# -----------------------------
if not is_logged_in:
    # Force sidebar to be hidden on login page
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Import and run login page
    try:
        spec = importlib.util.spec_from_file_location("login", "pages/0_Login.py")
        login_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(login_module)
    except Exception as e:
        st.error(f"Error loading login page: {e}")
    st.stop()

# -----------------------------
# Logged In - Sidebar Navigation
# -----------------------------

# Define Pages
chat_page = st.Page("pages/1_Chat.py", title="Chat", icon=":material/chat:")
view_users_page = st.Page("pages/2_View_Users.py", title="View Users", icon=":material/group:")
register_page = st.Page("pages/3_Register_User.py", title="Register User", icon=":material/person_add:")
manage_page = st.Page("pages/4_Manage_Users.py", title="Manage Users", icon=":material/manage_accounts:")
admin_docs_page = st.Page("pages/5_Admin_Docs.py", title="Admin Docs", icon=":material/folder_managed:")

# Build navigation based on role
pages = {}

if role == "staff":
    # Staff: Chat only
    pages["Chat"] = [chat_page]

elif role == "admin":
    # Admin: Chat + User Management + Docs
    pages["Chat"] = [chat_page]
    pages["User Management"] = [view_users_page, register_page]
    pages["Knowledge Base"] = [admin_docs_page]

elif role == "master":
    # Master: User Management + Docs (No Chat per original logic)
    pages["User Management"] = [view_users_page, register_page, manage_page]
    pages["Knowledge Base"] = [admin_docs_page]

else:
    # Unknown role - default to chat
    pages["Chat"] = [chat_page]

# Run Navigation (Hidden, we build our own sidebar)
pg = st.navigation(pages, position="hidden")

# -----------------------------
# Custom Sidebar
# -----------------------------
with st.sidebar:
    # 1. User Profile Card
    sidebar_user_card(user)
    st.divider()
    
    # 2. Navigation Menu
    st.markdown("#### Menu")
    
    for section_name, page_list in pages.items():
        # Optional: Add section headers if needed, or just list links
        if len(pages) > 1 and section_name != "Chat":
             st.caption(section_name)
             
        for page_obj in page_list:
            is_active = (page_obj == pg)
            st.page_link(page_obj, label=page_obj.title, icon=page_obj.icon)
    
    st.divider()

    # 3. Logout
    if st.button("Logout", icon=":material/logout:", width="stretch"):
        import time
        with st.spinner("Logging out..."):
            time.sleep(1.0)
        st.session_state.clear()
        st.rerun()

# Run the selected page
pg.run()
