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


def chat_bubble(role: str, content: str, sources=None, confidence=None, timestamp: str = "") -> None:
    """
    Renders a modern chat bubble.
    User  = Right-aligned custom HTML bubble.
    Assistant = st.chat_message() for proper markdown rendering.
    """
    if role == "user":
        ts_html = f"<div style='font-size:0.7rem;color:rgba(255,255,255,0.5);text-align:right;margin-top:0.3rem;'>{timestamp}</div>" if timestamp else ""
        st.markdown(
            f"""<div style="display:flex; justify-content:flex-end; margin-bottom:1rem;">
<div style="max-width: 80%;">
<div style="background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%); color: white; padding: 0.8rem 1.2rem; border-radius: 16px 16px 2px 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); font-size: 0.95rem; line-height: 1.5;">{content}</div>
{ts_html}
</div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("""
        <style>
        [data-testid="stChatMessage"] {
            background: rgba(30, 41, 59, 0.7) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            backdrop-filter: blur(8px) !important;
            border-radius: 2px 16px 16px 16px !important;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.15) !important;
            padding: 0.75rem 1rem !important;
            margin-bottom: 0.75rem !important;
        }
        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] li {
            color: #e2e8f0 !important;
            text-align: justify !important;
            line-height: 1.65 !important;
        }
        [data-testid="stChatMessage"] h1,
        [data-testid="stChatMessage"] h2,
        [data-testid="stChatMessage"] h3 { color: #f1f5f9 !important; }
        [data-testid="stChatMessage"] strong { color: #93c5fd !important; }
        [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
            background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
            border-radius: 50% !important;
        }
        </style>
        """, unsafe_allow_html=True)

        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)

            # ── Confidence badge ──────────────────────────────────────────
            if confidence is not None:
                pct = int(confidence * 100)
                if pct >= 70:
                    color, label, emoji = "#10b981", "High", "🟢"
                elif pct >= 40:
                    color, label, emoji = "#f59e0b", "Medium", "🟡"
                else:
                    color, label, emoji = "#ef4444", "Low", "🔴"
                st.markdown(
                    f"""<div style="margin-top:0.6rem;display:flex;align-items:center;gap:0.5rem;">
<span style="font-size:0.78rem;color:#9ca3af;">Confidence</span>
<span style="font-size:0.78rem;font-weight:600;color:{color};">{emoji} {label} ({pct}%)</span>
<div style="flex:1;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;max-width:100px;">
  <div style="width:{pct}%;height:4px;background:{color};border-radius:2px;"></div>
</div></div>""",
                    unsafe_allow_html=True,
                )

            # ── Source chips ──────────────────────────────────────────────
            if sources:
                chips = "".join(
                    f'<span style="display:inline-block;margin:0.2rem 0.2rem 0 0;padding:0.2rem 0.6rem;'
                    f'background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);'
                    f'border-radius:999px;font-size:0.75rem;color:#93c5fd;">📄 {s}</span>'
                    for s in sources
                )
                st.markdown(
                    f"<div style='margin-top:0.5rem;padding-top:0.4rem;border-top:1px solid rgba(255,255,255,0.08);'>"
                    f"<span style='font-size:0.75rem;color:#6b7280;'>Sources: </span>{chips}</div>",
                    unsafe_allow_html=True,
                )

            # ── Timestamp ─────────────────────────────────────────────────
            if timestamp:
                st.markdown(
                    f"<div style='font-size:0.7rem;color:#4b5563;margin-top:0.3rem;'>{timestamp}</div>",
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
