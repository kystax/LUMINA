"""
LUMINA - Authentication UI
Styled login/sign-up screen matching the lumina_dashboard JSX LoginScreen design.
Call `require_login()` at the top of app.py before rendering the dashboard.
"""

import re
import streamlit as st
from auth import login_user, register_user


# ─────────────────────────────────────────────
# VALIDATION HELPERS
# ─────────────────────────────────────────────

def _valid_email(email: str) -> bool:
    if not email:
        return True  # email optional in schema
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def _valid_password(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "Password must include at least one letter and one number."
    return True, ""


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

def init_auth_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None


def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()


def require_login():
    init_auth_state()
    if not st.session_state.get("authenticated"):
        render_auth_page()
        st.stop()


# ─────────────────────────────────────────────
# SIGN-IN PAGE (matches JSX LoginScreen)
# ─────────────────────────────────────────────

_AUTH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600;700&display=swap');

.lumina-auth-root {
    min-height: 100vh;
    background: #F7F7F4;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Inter', sans-serif;
}

/* Override Streamlit page bg on auth screen */
.stApp { background: #F7F7F4 !important; }
[data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
.block-container { padding: 3rem 1rem !important; max-width: 100% !important; }

/* Center column */
.auth-wrap {
    width: 100%;
    max-width: 440px;
    margin: 0 auto;
    padding: 32px 24px;
}

@media (max-width: 768px) {
    .block-container {
        padding: 1.5rem 0.75rem !important;
    }
    .stApp [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    .auth-wrap {
        padding: 16px 8px !important;
    }
}

.auth-brand {
    text-align: center;
    margin-bottom: 28px;
}

.auth-brand-name {
    font-family: 'DM Serif Display', Georgia, serif;
    font-size: 36px;
    font-weight: 400;
    color: #55446F;
    letter-spacing: 0.02em;
    line-height: 1.1;
}

.auth-brand-sub {
    color: #6F7470;
    font-size: 13px;
    margin-top: 6px;
}

.auth-card {
    background: #FFFFFF;
    border: 1px solid #DDD9DF;
    border-radius: 16px;
    padding: 28px 24px;
    box-shadow: 0 4px 20px rgba(111, 90, 142, 0.05);
}

/* Field labels */
.auth-label {
    color: #292D2B !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    margin-bottom: 6px;
    display: block;
}

/* Clean white input container styling */
.stApp [data-testid="stTextInput"] div[data-baseweb="input"],
.stApp [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    border: 1px solid #DDD9DF !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}

/* Inner input element */
.stApp [data-testid="stTextInput"] div[data-baseweb="base-input"],
.stApp [data-testid="stTextInput"] input,
.stApp input[type="text"],
.stApp input[type="password"] {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    color: #292D2B !important;
    -webkit-text-fill-color: #292D2B !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    caret-color: #6F5A8E !important;
}

/* WebKit autofill override */
.stApp input:-webkit-autofill,
.stApp input:-webkit-autofill:hover, 
.stApp input:-webkit-autofill:focus, 
.stApp input:-webkit-autofill:active {
    -webkit-box-shadow: 0 0 0 30px #FFFFFF inset !important;
    -webkit-text-fill-color: #292D2B !important;
    color: #292D2B !important;
    caret-color: #6F5A8E !important;
}

/* Focus state */
.stApp [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
    border-color: #6F5A8E !important;
    box-shadow: 0 0 0 2px rgba(111, 90, 142, 0.15) !important;
}

.stApp [data-testid="stTextInput"] input::placeholder,
.stApp input::placeholder {
    color: #969A96 !important;
    -webkit-text-fill-color: #969A96 !important;
}

/* Password eye button icon styling */
.stApp [data-testid="stTextInput"] button,
.stApp [data-testid="stTextInput"] svg {
    color: #6F7470 !important;
    fill: #6F7470 !important;
    background: transparent !important;
}

.stApp [data-testid="stTextInput"] label,
.stApp [data-testid="stSelectbox"] label,
.stApp label,
.stApp p {
    color: #292D2B !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

/* Tab & Submit buttons */
.stApp div[data-testid="stButton"] > button[kind="primary"],
.stApp div[data-testid="stFormSubmitButton"] > button {
    background: #6F5A8E !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 0.65rem 1rem !important;
    transition: background 0.15s ease !important;
}

.stApp div[data-testid="stButton"] > button[kind="primary"]:hover,
.stApp div[data-testid="stFormSubmitButton"] > button:hover {
    background: #55446F !important;
}

.stApp div[data-testid="stButton"] > button[kind="secondary"] {
    background: #FFFFFF !important;
    color: #55446F !important;
    border: 1px solid #DDD9DF !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 0.65rem 1rem !important;
}

.stApp div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #F3EFF6 !important;
}

.stApp [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
.stApp [data-testid="stSelectbox"] div[data-baseweb="select"] * {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    color: #292D2B !important;
    -webkit-text-fill-color: #292D2B !important;
    border-radius: 10px !important;
}

.stApp [data-testid="stForm"] {
    background: #FFFFFF !important;
    border: 1px solid #DDD9DF !important;
    border-radius: 16px !important;
    padding: 24px 20px !important;
    box-shadow: 0 4px 16px rgba(111, 90, 142, 0.04) !important;
}

/* Alert overrides */
.stAlert { border-radius: 10px !important; }

.auth-footnote {
    text-align: center;
    margin-top: 20px;
    font-size: 11.5px;
    color: #969A96;
    line-height: 1.6;
}

.auth-link {
    color: #6F5A8E;
    cursor: pointer;
}
</style>
"""



def render_auth_page():
    """Render the full-page authentication screen."""
    # Inject CSS first
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)

    # Init tab state
    if "auth_tab" not in st.session_state:
        st.session_state.auth_tab = "login"

    # Center layout
    _, mid, _ = st.columns([1, 1.6, 1])

    with mid:
        # Brand
        st.markdown(
            """
            <div class="auth-brand">
                <div class="auth-brand-name">LUMINA</div>
                <div class="auth-brand-sub">Cognitive pattern monitoring</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Tab switcher
        col_login, col_signup = st.columns(2)
        with col_login:
            if st.button(
                "Sign in",
                key="tab_login_btn",
                width="stretch",
                type="primary" if st.session_state.auth_tab == "login" else "secondary",
            ):
                st.session_state.auth_tab = "login"
                st.rerun()
        with col_signup:
            if st.button(
                "Create account",
                key="tab_signup_btn",
                width="stretch",
                type="primary" if st.session_state.auth_tab == "signup" else "secondary",
            ):
                st.session_state.auth_tab = "signup"
                st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ── Login form ──
        if st.session_state.auth_tab == "login":
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", key="login_username", placeholder="your_username")
                password = st.text_input(
                    "Password", type="password", key="login_password", placeholder="••••••••"
                )
                submitted = st.form_submit_button("Sign in", width="stretch", type="primary")

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                else:
                    with st.spinner("Signing in…"):
                        success, result = login_user(username, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = result
                        st.rerun()
                    else:
                        st.error(result)

            st.markdown(
                """
                <div class="auth-footnote">
                    By signing in you confirm any data you upload belongs to you,
                    or you have the subject's consent for it to be analyzed.<br><br>
                    <span class="auth-link">Forgot password?</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Signup form ──
        else:
            with st.form("signup_form", clear_on_submit=False):
                username = st.text_input("Username", key="signup_username", placeholder="choose_a_username")
                email    = st.text_input("Email (optional)", key="signup_email", placeholder="you@email.com")
                password = st.text_input(
                    "Password", type="password", key="signup_password", placeholder="min. 8 characters"
                )
                confirm  = st.text_input(
                    "Confirm password", type="password", key="signup_confirm", placeholder="repeat password"
                )
                user_type = st.selectbox(
                    "Account type",
                    options=["individual", "researcher"],
                    format_func=lambda x: "Individual / self-monitoring" if x == "individual" else "Researcher / caregiver",
                    key="signup_user_type",
                )
                submitted = st.form_submit_button("Create account", width="stretch", type="primary")

            if submitted:
                if not username or not password:
                    st.error("Username and password are required.")
                elif len(username) < 3:
                    st.error("Username must be at least 3 characters.")
                elif not _valid_email(email):
                    st.error("Please enter a valid email address.")
                else:
                    pw_ok, pw_msg = _valid_password(password)
                    if not pw_ok:
                        st.error(pw_msg)
                    elif password != confirm:
                        st.error("Passwords do not match.")
                    else:
                        with st.spinner("Creating your account…"):
                            success, result = register_user(username, email or None, password, user_type)
                        if success:
                            st.success(result)
                            st.info("You can now sign in using the Sign in tab.")
                        else:
                            st.error(result)

            st.markdown(
                """
                <div class="auth-footnote">
                    LUMINA analyzes behavioral patterns over time — not a clinical diagnosis.
                    Results are indicators only. Always consult a qualified healthcare provider.
                </div>
                """,
                unsafe_allow_html=True,
            )
