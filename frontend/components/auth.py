"""
Authentication helpers shared across all pages.
"""

import streamlit as st

from .. import api_client  # relative import: frontend/api_client.py


def require_login() -> str:
    """
    Enforce authentication on any page.

    - On the home page (Home.py): renders the login form inline.
    - On all other pages: redirects to Home.py using st.switch_page().

    Returns the JWT token if already authenticated.

    Usage (add to top of every page):
        token = require_login()
    """
    if "token" not in st.session_state:
        # Detect whether we're on the main app page or a sub-page.
        # __file__ for pages lives in frontend/pages/; Home.py lives in frontend/.
        import inspect

        caller_file = inspect.stack()[1].filename
        is_home = caller_file.endswith("Home.py")

        if is_home:
            # A reset link (emailed by /auth/forgot-password) deep-links
            # here as ?reset_token=... — that takes priority over the
            # normal login form since the user arrived with a specific
            # task (set a new password), not to sign in with an existing one.
            reset_token = st.query_params.get("reset_token")
            if reset_token:
                _render_reset_password_form(reset_token)
            else:
                _render_login_form()
        else:
            # On any other page, redirect to the home/login page.
            st.warning("Please sign in to continue.")
            st.switch_page("Home.py")

        st.stop()

    return st.session_state["token"]


def get_user() -> dict:
    """Return the current user dict from session state."""
    return st.session_state.get("user", {})


def get_role() -> str:
    """Return the current user's role name."""
    return get_user().get("role", "employee")


def logout() -> None:
    """Clear session state and rerun to show login page."""
    st.session_state.clear()
    st.rerun()


def _render_login_form() -> None:
    """Render the login form and handle submission."""
    st.title("🎫 Helpdesk AI")
    st.subheader("Sign in to your account")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@company.com")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign In", use_container_width=True)

    if submit:
        if not email or not password:
            st.error("Please enter both email and password.")
            return

        with st.spinner("Signing in..."):
            try:
                tokens = api_client.login(email, password)
                user = api_client.get_current_user(tokens["access_token"])

                # Store in session
                st.session_state["token"] = tokens["access_token"]
                st.session_state["user"] = user

                st.success(f"Welcome, {user['full_name']}!")
                st.rerun()  # reload page now that token exists

            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error(
                    "⚠️ Cannot connect to the backend. Make sure the FastAPI server is running on port 8000."
                )

    with st.expander("Forgot your password?"):
        _render_forgot_password_form()

    with st.expander("Don't have an account? Register"):
        _render_register_form()


def _render_forgot_password_form() -> None:
    """
    Request a reset link. Always shows the same success message on submit,
    regardless of whether the email is registered — the backend's response
    is deliberately generic for the same reason (see AuthService.request_
    password_reset's docstring), and the frontend shouldn't undo that by
    branching on the result.
    """
    with st.form("forgot_password_form"):
        email = st.text_input("Email", placeholder="you@company.com", key="forgot_email")
        submit = st.form_submit_button("Send reset link", use_container_width=True)

    if submit:
        if not email:
            st.error("Please enter your email.")
            return
        try:
            api_client.forgot_password(email)
        except Exception:
            pass  # network/backend errors shouldn't reveal anything either
        st.info(
            "If that email is registered, a reset link has been sent. "
            "It's valid for a limited time — check your inbox."
        )


def _render_register_form() -> None:
    """
    Self-service registration — always creates an 'employee' account.

    POST /auth/register hardcodes the 'employee' role server-side
    (AuthService.register()) regardless of what this form sends; there is
    no role field here at all, deliberately. Letting anyone who can reach
    this public form choose "engineer" or "admin" would be a privilege-
    escalation bug, not a feature. Creating engineer/admin accounts is a
    separate, admin-only action — see pages/5_Admin_Users.py's "Add User"
    form, which calls the admin-only POST /users endpoint instead.
    """
    with st.form("register_form"):
        full_name = st.text_input("Full name", key="register_full_name")
        email = st.text_input("Email", placeholder="you@company.com", key="register_email")
        username = st.text_input(
            "Username",
            placeholder="lowercase letters, numbers, underscores",
            key="register_username",
        )
        password = st.text_input(
            "Password",
            type="password",
            key="register_password",
            help="At least 8 characters.",
        )
        submit = st.form_submit_button("Create account", use_container_width=True)

    if submit:
        if not all([full_name, email, username, password]):
            st.error("Please fill in every field.")
            return
        try:
            api_client.register(
                full_name=full_name, email=email, username=username, password=password
            )
            st.success("Account created — you can now sign in above with your new password.")
        except ValueError as e:
            st.error(str(e))
        except Exception:
            st.error(
                "⚠️ Cannot connect to the backend. Make sure the FastAPI server is running on port 8000."
            )


def _render_reset_password_form(reset_token: str) -> None:
    """Render the "set a new password" form reached via an emailed reset link."""
    st.title("🎫 Helpdesk AI")
    st.subheader("Choose a new password")

    with st.form("reset_password_form"):
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        submit = st.form_submit_button("Reset password", use_container_width=True)

    if submit:
        if not new_password or not confirm_password:
            st.error("Please fill in both fields.")
            return
        if new_password != confirm_password:
            st.error("Passwords do not match.")
            return

        with st.spinner("Resetting password..."):
            try:
                api_client.reset_password(reset_token, new_password)
                st.query_params.clear()
                st.success("Password reset. Please sign in with your new password.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error(
                    "⚠️ Cannot connect to the backend. Make sure the FastAPI server is running on port 8000."
                )

    if st.button("Back to sign in"):
        st.query_params.clear()
        st.rerun()
