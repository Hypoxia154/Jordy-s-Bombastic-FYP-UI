import streamlit as st

from ui.theme import COLOR_THEME


def apply_custom_css() -> None:
    st.markdown("<style>.stDeployButton{visibility:hidden;}</style>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * {{ font-family: 'Inter', sans-serif; }}
        .stApp {{
            background: radial-gradient(circle at top, #111827 0, {COLOR_THEME['bg']} 40%) !important;
            color: {COLOR_THEME['text']};
        }}
        section[data-testid="stSidebar"] > div {{
            background: {COLOR_THEME['panel']} !important;
            border-right: 1px solid #111827;
            padding: 0.4rem 0.5rem 0.8rem 0.5rem !important;
        }}
        .badge {{
            display:inline-block;padding:0.15rem 0.55rem;font-size:0.7rem;
            border-radius:999px;font-weight:600;
        }}
        .badge-admin {{ background:#1D4ED8; color:#E5E7EB; }}
        .badge-master {{ background:#F59E0B; color:#111827; }}
        .badge-staff {{ background:#374151; color:#E5E7EB; }}
        /* Hide Streamlit multipage nav ("Pages" list) -> REMOVED because we use st.navigation() now */
        /* [data-testid="stSidebarNav"] {{ display: none !important; }} */
        </style>
        """,
        unsafe_allow_html=True,

    )

