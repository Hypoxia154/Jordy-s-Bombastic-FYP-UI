import streamlit as st

from ui.theme import COLOR_THEME


def apply_custom_css() -> None:
    # 1. Hide Deploy Button
    st.markdown("<style>.stDeployButton{visibility:hidden;}</style>", unsafe_allow_html=True)
    
    # 2. Modern Glassmorphism & Colors
    st.markdown(
        f"""
        <style>
        /* Hide 'Press Enter to submit form' hint inside inputs globally */
        div[data-testid="InputInstructions"] {{
            display: none !important;
        }}
        
        /* Import Font: Inter */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        :root {{
            --bg-dark: #0f172a;
            --bg-panel: #1e293b;
            --primary: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }}

        * {{ font-family: 'Inter', sans-serif; }}

        /* KEYFRAME: Fade In */
        @keyframes fadein {{
            from {{ opacity: 0; }}
            to   {{ opacity: 1; }}
        }}

        /* Main App Background */
        .stApp {{
            background: linear-gradient(135deg, #0f172a 0%, #172554 100%) !important;
            color: var(--text-main);
            animation: fadein 0.6s cubic-bezier(0.2, 0.8, 0.2, 1);
        }}

        /* Make header transparent so the gradient shows through */
        header[data-testid="stHeader"] {{
            background-color: transparent !important;
        }}

        /* Make bottom chat input container transparent */
        div[data-testid="stBottom"] {{
            background-color: transparent !important;
        }}
        div[data-testid="stBottom"] > div {{
             background-color: transparent !important;
        }}
        
        /* Disclaimer Footer */
        div[data-testid="stBottom"]::after {{
            content: 'AI-powered analysis. Not legal advice. Verify with original documents.';
            display: block;
            text-align: center;
            color: #9ca3af;
            font-size: 0.75rem;
            padding-top: 0.5rem;
            padding-bottom: 1rem;
            pointer-events: none;
        }}

        /* Sidebar Styling (Glassmorphism) */
        section[data-testid="stSidebar"] > div {{
            background: rgba(15, 23, 42, 0.75) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 2rem;
        }}
        
        /* FIX: Hide sidebar handle/element when collapsed to avoid login artifacts */
        section[data-testid="stSidebar"][aria-expanded="false"] {{
            display: none !important;
        }}
        
        /* Headers */
        h1, h2, h3 {{
            color: #f8fafc !important;
            font-weight: 700 !important;
        }}
        
        /* Buttons (Outline & Primary) */
        div.stButton > button {{
            border-radius: 12px;
            font-weight: 600;
            transition: all 0.2s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(30, 41, 59, 0.6);
            color: #e2e8f0;
        }}
        div.stButton > button:hover {{
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(59, 130, 246, 0.1);
            transform: translateY(-1px);
        }}
        
        /* Inputs */
        .stTextInput > div > div > input {{
            background-color: rgba(30, 41, 59, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border-radius: 10px;
            padding: 0.5rem 0.75rem !important;
        }}
        .stTextInput > div > div > input:focus {{
             border-color: var(--primary) !important;
             box-shadow: 0 0 0 1px var(--primary);
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            font-size: 0.7rem;
            border-radius: 999px;
            font-weight: 600;
            letter-spacing: 0.025em;
            text-transform: uppercase;
        }}
        .badge-admin {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-master {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-staff {{ background: rgba(75, 85, 99, 0.4); color: #d1d5db; border: 1px solid rgba(75, 85, 99, 0.5); }}

        /* Chat Bubbles (User vs AI) are handled inline in components.py, 
           but we can add general card styles here */
        .chat-card {{
            padding: 1rem;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            margin-bottom: 0.75rem;
            line-height: 1.5;
        }}
        
        /* Scrollbars */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent; 
        }}
        ::-webkit-scrollbar-thumb {{
            background: #334155; 
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #475569; 
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
