"""Authentication helper utilities for Streamlit pages."""
import streamlit as st


def require_role(*allowed_roles: str) -> tuple[str, dict]:
    """
    Require user to be authenticated and have one of the allowed roles.
    
    Args:
        *allowed_roles: One or more role names (e.g., "admin", "master", "staff")
    
    Returns:
        tuple: (token, user_dict)
    
    Redirects to login page if not authenticated or role not allowed.
    """
    # Check if authenticated
    if not st.session_state.get("is_authenticated", False):
        st.warning("Please log in first.")
        st.switch_page("pages/0_Login.py")
        st.stop()
    
    # Get user info
    token = st.session_state.get("token")
    user = st.session_state.get("user") or {}
    role = (user.get("role") or "").lower()
    
    # Check if user has required role
    allowed_roles_lower = [r.lower() for r in allowed_roles]
    if role not in allowed_roles_lower:
        st.error(f"Access denied. Required role: {', '.join(allowed_roles)}")
        st.switch_page("pages/1_Chat.py")
        st.stop()
    
    return token, user
