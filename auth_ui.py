
import streamlit as st

from auth import (
    exchange_oauth_code,
    get_google_oauth_url,
    restore_authenticated_client,
    sign_in_with_email,
    sign_up_with_email,
    store_session,
)


def _handle_oauth_callback() -> None:
    """Exchange a Supabase OAuth callback code for a logged-in session."""
    code = st.query_params.get("code")

    if not code:
        return

    try:
        response = exchange_oauth_code(code)
        session = getattr(response, "session", None)
        user = getattr(response, "user", None)

        if session:
            store_session(session, user)
            st.query_params.clear()
            st.rerun()
        else:
            st.error(
                "Google sign-in returned no session. Please try signing in again."
            )
    except Exception as exc:
        st.query_params.clear()
        st.error(f"Google sign-in error: {exc}")


def render_auth_screen() -> bool:
    """
    Display the authentication screen.
    Return True if an authenticated session exists.
    """
    _handle_oauth_callback()

    client = restore_authenticated_client()
    if client is not None:
        return True

    st.title("ResearchPilot")
    st.subheader("Sign in to save and access your research")

    
    google_col, _ = st.columns([1, 1])

    with google_col:
        if st.button("Continue with Google", use_container_width=True):
            try:
                oauth_url = get_google_oauth_url()
                st.markdown(
                    f'<a href="{oauth_url}" target="_self">'
                    'Continue to Google</a>',
                    unsafe_allow_html=True,
                )
                st.info(
                    "Click the link above to continue in this same tab."
                )
            except Exception:
                st.error(
                    "Unable to start Google sign-in. Check your Supabase "
                    "Google provider configuration and redirect URLs."
                )


    st.divider()

    tab_login, tab_signup = st.tabs(["Log in", "Create account"])

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email address", key="login_email")
            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )
            login_submit = st.form_submit_button(
                "Log in",
                use_container_width=True,
            )

        if login_submit:
            if not login_email.strip() or not login_password:
                st.warning("Enter your email address and password.")
            else:
                try:
                    response = sign_in_with_email(login_email, login_password)
                    session = getattr(response, "session", None)
                    user = getattr(response, "user", None)

                    if session:
                        store_session(session, user)
                        st.rerun()
                    else:
                        st.error("No session was returned. Please try again.")
                except Exception:
                    st.error(
                        "Login failed. Check your credentials and confirm "
                        "your email address if required."
                    )

    with tab_signup:
        with st.form("signup_form"):
            signup_email = st.text_input("Email address", key="signup_email")
            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )
            signup_confirm = st.text_input(
                "Confirm password",
                type="password",
                key="signup_confirm",
            )
            signup_submit = st.form_submit_button(
                "Create account",
                use_container_width=True,
            )

        if signup_submit:
            if not signup_email.strip() or not signup_password:
                st.warning("Enter an email address and password.")
            elif signup_password != signup_confirm:
                st.warning("The passwords do not match.")
            elif len(signup_password) < 8:
                st.warning("Use a password with at least 8 characters.")
            else:
                try:
                    response = sign_up_with_email(
                        signup_email,
                        signup_password,
                    )
                    session = getattr(response, "session", None)
                    user = getattr(response, "user", None)

                    if session:
                        store_session(session, user)
                        st.success("Account created successfully.")
                        st.rerun()
                    else:
                        st.success(
                            "Account created. Check your email for the "
                            "confirmation link, then return here to log in."
                        )
                except Exception as exc:
                    st.error(f"Account creation failed: {exc}")

    return False
