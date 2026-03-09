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
# UI Styling
# -----------------------------
st.markdown("""
<style>
    /* Center the login card vertically (approx) and style it */
    .login-container {
        background: rgba(30, 41, 59, 0.7);
        padding: 3rem;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        margin-top: 5vh;
    }
    
    /* Input field styling adjustments for this page */
    .stTextInput > div > div > input {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        padding: 10px 12px;
    }
    
    /* Header Styling */
    h1 {
        text-align: center;
        font-weight: 800 !important;
        background: -webkit-linear-gradient(45deg, #60a5fa, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem !important;
    }
    
    .subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 0.9rem;
        margin-bottom: 2rem;
    }
    
    /* Hide placeholder when input is focused */
    input:focus::placeholder {
        color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# View
# -----------------------------
# Three columns to center the content
col1, col2, col3 = st.columns([1, 1.2, 1])

with col2:
    # Use a container to visually group, although streamlit containers don't allow direct styling easily.
    # We use a markdown div to wrap the visual card if we were doing pure HTML, 
    # but for Streamlit form we rely on the column width and page-specific CSS.
    
    # Header
    st.markdown("<h1>CRAG Intelligence</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Secure access to the Real Estate Knowledge Base</p>", unsafe_allow_html=True)
    
    render_flash()

    with st.form("login_form"):
        st.markdown("### Sign In")
        username = st.text_input("Username", key="login_username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", key="login_password", placeholder="••••••••")
        
        st.markdown("<br>", unsafe_allow_html=True) # Spacer
        
        submitted = st.form_submit_button("Log in", type="primary", width="stretch")

    if submitted:
        # Your ViewModel handles setting session_state['user'] automatically!
        state = vm.login((username or "").strip(), password or "")

        if state.ok:
            username = state.user.get("username", "User") if isinstance(state.user, dict) else "User"
            set_flash("success", f"Welcome back, {username}!")
            # Visual transition
            import time
            with st.spinner("Authenticating..."):
                time.sleep(0.8)
            st.rerun()
        else:
            set_flash("error", state.message)