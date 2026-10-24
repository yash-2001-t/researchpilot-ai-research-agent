
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


class StreamlitSessionStorage:
    """Store Supabase auth values in the current Streamlit session."""

    def get_item(self, key: str):
        return st.session_state.get(f"supabase_storage_{key}")

    def set_item(self, key: str, value: str):
        st.session_state[f"supabase_storage_{key}"] = value

    def remove_item(self, key: str):
        st.session_state.pop(f"supabase_storage_{key}", None)


def get_supabase_client() -> Client:
    """Create a Supabase client using the shared Streamlit storage."""

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        try:
            url = url or st.secrets["SUPABASE_URL"]
            key = key or st.secrets["SUPABASE_KEY"]
        except Exception:
            pass

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials are missing. Check SUPABASE_URL "
            "and SUPABASE_KEY in your .env file."
        )

    options = SyncClientOptions(
        flow_type="pkce",
        storage=StreamlitSessionStorage(),
        auto_refresh_token=False,
    )

    return create_client(url, key, options=options)
