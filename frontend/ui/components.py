import streamlit as st

from ui.theme import COLOR_THEME


def role_badge(role: str) -> str:
    """Display a role badge with the given role."""
    if not role:
        return '<span class="badge">UNKNOWN</span>'
    role_lower = role.lower()
    return f'<span class="badge badge-{role_lower}">{role.upper()}</span>'


def sidebar_user_card(user: dict) -> None:
    role = user.get('role', '')
    initials = "".join([w[0].upper() for w in user.get("name", "U").split()[:2]])
    
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:0.8rem;padding:0.75rem 1rem; margin-bottom:1rem;background: rgba(255,255,255,0.05);border: 1px solid rgba(255,255,255,0.1);border-radius: 12px;backdrop-filter: blur(10px);">
<div style="width:42px;height:42px;border-radius:50%;background: linear-gradient(135deg, #3B82F6, #10B981);display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:1.1rem;box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">{initials}</div>
<div style="display:flex;flex-direction:column;gap:0.1rem;">
<div style="font-size:0.95rem;font-weight:600;color:#f3f4f6;">{user.get('name','User')}</div>
<div>{role_badge(role)}</div>
</div>
</div>""",
        unsafe_allow_html=True,
    )


def chat_bubble(role: str, content: str, sources=None, confidence=None) -> None:
    """
    Renders a modern chat bubble.
    User  = Right-aligned custom HTML bubble.
    Assistant = st.chat_message() for proper markdown rendering.
    """
    if role == "user":
        # User Bubble (Right, custom styled HTML)
        st.markdown(
            f"""<div style="display:flex; justify-content:flex-end; margin-bottom:1rem;">
<div style="max-width: 80%; background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%); color: white; padding: 0.8rem 1.2rem; border-radius: 16px 16px 2px 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); font-size: 0.95rem; line-height: 1.5;">{content}</div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        # Inject CSS once to style the native st.chat_message like the glass bubble
        st.markdown("""
        <style>
        /* Glass bubble for assistant messages */
        [data-testid="stChatMessage"] {
            background: rgba(30, 41, 59, 0.7) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            backdrop-filter: blur(8px) !important;
            border-radius: 2px 16px 16px 16px !important;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.15) !important;
            padding: 0.75rem 1rem !important;
            margin-bottom: 0.75rem !important;
        }
        /* Justify text inside assistant bubble */
        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] li {
            color: #e2e8f0 !important;
            text-align: justify !important;
            line-height: 1.65 !important;
        }
        [data-testid="stChatMessage"] h1,
        [data-testid="stChatMessage"] h2,
        [data-testid="stChatMessage"] h3 {
            color: #f1f5f9 !important;
        }
        [data-testid="stChatMessage"] strong {
            color: #93c5fd !important;
        }
        /* Hide default Streamlit chat avatar background */
        [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
            background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
            border-radius: 50% !important;
        }
        </style>
        """, unsafe_allow_html=True)

        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)  # Full markdown: headers, bullets, bold, tables, code

            if sources:
                st.markdown(
                    "<div style='margin-top:0.6rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.1);font-size:0.8rem;color:#9ca3af;'>"
                    "<strong>Sources:</strong><ul style='margin:0.2rem 0;padding-left:1.2rem;'>"
                    + "".join(f"<li>{s}</li>" for s in sources)
                    + "</ul></div>",
                    unsafe_allow_html=True,
                )

            if confidence is not None:
                st.caption(f"Confidence: {confidence:.2f}")



def render_user_metrics(users: list) -> None:
    """Render metrics for user counts by role with modern styling."""
    if not users:
        return

    total = len(users)
    master_cnt = sum(1 for u in users if u.get("role", "").lower() == "master")
    admin_cnt = sum(1 for u in users if u.get("role", "").lower() == "admin")
    staff_cnt = sum(1 for u in users if u.get("role", "").lower() == "staff")

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Users", total)
    c2.metric("Master Admins", master_cnt)
    c3.metric("Admins", admin_cnt)
    c4.metric("Staff / Agents", staff_cnt)
