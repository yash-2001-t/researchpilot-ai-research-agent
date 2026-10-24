
import os

import streamlit as st
from supabase import Client

from database import get_supabase_client


def _get_redirect_url() -> str:
    """Return the configured app URL for the OAuth callback."""
    redirect_url = os.getenv("APP_URL", "http://localhost:8501")
    return redirect_url.rstrip("/")


def sign_up_with_email(email: str, password: str):
    """Register a new user. Email confirmation may be required."""
    client = get_supabase_client()
    return client.auth.sign_up(
        {
            "email": email.strip(),
            "password": password,
        }
    )


def sign_in_with_email(email: str, password: str):
    """Sign in an existing user."""
    client = get_supabase_client()
    return client.auth.sign_in_with_password(
        {
            "email": email.strip(),
            "password": password,
        }
    )


def get_google_oauth_url() -> str:
    """Start Google OAuth and return the URL to open."""
    client = get_supabase_client()
    response = client.auth.sign_in_with_oauth(
        {
            "provider": "google",
            "options": {"redirect_to": _get_redirect_url()},
        }
    )

    url = getattr(response, "url", None)
    if not url:
        raise RuntimeError("Supabase did not return a Google sign-in URL.")

    return url


def exchange_oauth_code(code: str):
    """Exchange the callback authorization code for a Supabase session."""
    client = get_supabase_client()
    return client.auth.exchange_code_for_session({"auth_code": code})


def restore_authenticated_client() -> Client | None:
    """Restore the current session into a Supabase client."""
    access_token = st.session_state.get("supabase_access_token")
    refresh_token = st.session_state.get("supabase_refresh_token")

    if not access_token or not refresh_token:
        return None

    client = get_supabase_client()
    try:
        client.auth.set_session(access_token, refresh_token)
        return client
    except Exception:
        st.session_state.pop("supabase_access_token", None)
        st.session_state.pop("supabase_refresh_token", None)
        st.session_state.pop("supabase_user", None)
        return None


def store_session(session, user=None) -> None:
    """Store session tokens and basic user details in Streamlit session state."""
    if session is None:
        return

    st.session_state["supabase_access_token"] = session.access_token
    st.session_state["supabase_refresh_token"] = session.refresh_token

    if user is not None:
        st.session_state["supabase_user"] = {
            "id": user.id,
            "email": user.email,
        }


def sign_out_current_user() -> None:
    """Clear local session state and sign out from Supabase."""
    client = restore_authenticated_client()
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass

    for key in (
        "supabase_access_token",
        "supabase_refresh_token",
        "supabase_user",
    ):
        st.session_state.pop(key, None)
