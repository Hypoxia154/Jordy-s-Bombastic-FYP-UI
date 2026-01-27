import streamlit as st

def set_flash(kind: str, text: str):
    # kind: "success" | "error" | "info"
    st.session_state["flash"] = {"kind": kind, "text": text}

def render_flash():
    msg = st.session_state.pop("flash", None)  # show once
    if not msg:
        return
    if msg["kind"] == "success":
        st.success(msg["text"])
    elif msg["kind"] == "error":
        st.error(msg["text"])
    else:
        st.info(msg["text"])
