import streamlit as st

from ui.theme import COLOR_THEME


def role_badge(role: str) -> str:
    """Display a role badge with the given role."""
    if not role:
        return '<span class="badge">UNKNOWN</span>'
    role_lower = role.lower()
    cls = f"badge-{role_lower}"
    return f'<span class="badge {cls}">{role.upper()}</span>'


def sidebar_user_card(user: dict) -> None:
    role = user.get('role', '')
    initials = "".join([w[0].upper() for w in user.get("name", "U").split()[:2]])
    
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.6rem;padding:0.6rem 0.75rem;margin-bottom:0.5rem;">
            <div style="
                width:38px;height:38px;border-radius:999px;
                background:linear-gradient(135deg,#3B82F6,#10B981);
                display:flex;align-items:center;justify-content:center;
                color:white;font-weight:700;">
                {initials}
            </div>
            <div>
                <div style="font-size:0.95rem;font-weight:600;color:{COLOR_THEME['text']}">
                    {user.get('name','User')}
                </div>
                <div>
                   {role_badge(role)}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chat_bubble(role: str, content: str, sources=None, confidence=None) -> None:
    if role == "user":
        st.markdown(
            "<div style='text-align:right;margin:0.15rem 0;'><div style='display:inline-block;max-width:72%;"
            "background:#2563EB;color:#f9fafb;border-radius:12px;padding:0.65rem 1rem;'>"
            + content
            + "</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='text-align:left;margin:0.15rem 0;'><div style='display:inline-block;max-width:72%;"
            f"background:{COLOR_THEME['panel_alt']};border:1px solid rgba(55,65,81,0.9);"
            "border-radius:12px;padding:0.65rem 1rem;'>"
            + content
            + "</div></div>",
            unsafe_allow_html=True,
        )
        if confidence is not None:
            st.caption(f"Confidence: {confidence:.2f}")


def render_user_metrics(users: list) -> None:
    """Render metrics for user counts by role."""
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
