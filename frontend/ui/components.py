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
    User = Right aligned, Blue Gradient
    Assistant = Left aligned, Glass Dark
    """
    if role == "user":
        # User Bubble (Right)
        st.markdown(
            f"""<div style="display:flex; justify-content:flex-end; margin-bottom:1rem;">
<div style="max-width: 80%; background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%); color: white; padding: 0.8rem 1.2rem; border-radius: 16px 16px 2px 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); font-size: 0.95rem; line-height: 1.5;">{content}</div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        # Assistant Bubble (Left)
        # Sources formatting
        sources_html = ""
        if sources:
            sources_html = "<div style='margin-top:0.8rem;padding-top:0.5rem;border-top:1px solid rgba(255,255,255,0.1);font-size:0.8rem;color:#9ca3af;'><strong>Sources:</strong><ul style='margin:0.2rem 0;padding-left:1.2rem;'>"
            for s in sources:
                sources_html += f"<li>{s}</li>"
            sources_html += "</ul></div>"

        # Confidence Badge
        conf_html = ""
        if confidence is not None:
             conf_html = f"<div style='font-size:0.75rem;color:#10b981;margin-top:0.3rem;'>Confidence: {confidence:.2f}</div>"

        st.markdown(
            f"""<div style="display:flex; justify-content:flex-start; margin-bottom:1rem;">
<!-- Avatar (Optional) -->
<div style="min-width:32px; height:32px; border-radius:50%; background: linear-gradient(135deg, #6366f1, #8b5cf6); display:flex;align-items:center;justify-content:center; margin-right: 0.75rem; margin-top: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>
</svg>
</div>
<div style="max-width: 85%; background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(8px); color: #e2e8f0; padding: 1rem 1.25rem; border-radius: 2px 16px 16px 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
<div style="font-size:0.95rem; line-height:1.6;">{content}</div>
{sources_html}
{conf_html}
</div>
</div>""",
            unsafe_allow_html=True,
        )


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
