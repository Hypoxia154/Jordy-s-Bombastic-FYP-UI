from dataclasses import dataclass
import streamlit as st

from mvvm.services.api_client import ApiClient


@dataclass
class AuthState:
    ok: bool
    message: str = ""
    token: str | None = None
    user: dict | None = None


class AuthViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def login(self, username: str, password: str) -> AuthState:
        try:
            data = self.api.post("/auth/login", {"username": username, "password": password})

            # backend might return "access_token" or "token"
            token = data.get("access_token") or data.get("token")
            user = data.get("user")

            if not token or not user:
                return AuthState(ok=False, message="Login response missing token/user.")

            # Persist into Streamlit session
            st.session_state["token"] = token
            st.session_state["user"] = user
            st.session_state["is_authenticated"] = True

            return AuthState(ok=True, message="Login successful.", token=token, user=user)

        except Exception as e:
            # Don’t crash Streamlit — return clean state
            st.session_state["token"] = None
            st.session_state["user"] = None
            st.session_state["is_authenticated"] = False
            return AuthState(ok=False, message=str(e))
