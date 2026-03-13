import streamlit as st
import time
from api_client import get_api_client
import extra_streamlit_components as stx

# Configure page - ONLY ONCE
st.set_page_config(
    page_title="Gemini AI Chat",
    page_icon="favicon.ico",
    layout="wide",
    initial_sidebar_state="auto",
)

# ==================== Cookie Manager ====================

cookie_manager = stx.CookieManager(key="gemini_cookie_manager")

# ==================== Session Initialization ====================

def restore_session_from_cookie():
    """Try to restore user session from browser cookie."""
    if st.session_state.get("jwt_token"):
        return True

    token = cookie_manager.get("gemini_jwt_token")
    user_id = cookie_manager.get("gemini_user_id")
    username = cookie_manager.get("gemini_username")

    if token and user_id:
        # Validate token by calling /auth/me
        api_client = get_api_client()
        api_client.set_token(token)
        user_info = api_client.get_me()
        if user_info and user_info.get("user_id"):
            st.session_state.jwt_token = token
            st.session_state.user_id = user_id
            st.session_state.username = username or user_id
            st.session_state.authentication_status = True
            st.session_state.backend_user_id = user_id
            return True
        else:
            # Token expired or invalid — clear cookies
            cookie_manager.delete("gemini_jwt_token")
            cookie_manager.delete("gemini_user_id")
            cookie_manager.delete("gemini_username")
    return False

def save_session_to_cookie(token: str, user_id: str, username: str):
    """Save session to browser cookies for persistence across refreshes."""
    cookie_manager.set("gemini_jwt_token", token, max_age=86400)  # 1 day
    cookie_manager.set("gemini_user_id", user_id, max_age=86400)
    cookie_manager.set("gemini_username", username, max_age=86400)

def clear_session_cookies():
    """Clear all session cookies on logout."""
    cookie_manager.delete("gemini_jwt_token")
    cookie_manager.delete("gemini_user_id")
    cookie_manager.delete("gemini_username")

# ==================== Handle Logout ====================

if st.session_state.get("do_logout"):
    clear_session_cookies()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ==================== Auth Check ====================

session_restored = restore_session_from_cookie()

if not session_restored and not st.session_state.get("authentication_status"):
    # Show login/register UI
    st.title("Gemini AI Chat")
    st.markdown("---")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        st.subheader("Login")
        with st.form("login_form", clear_on_submit=False):
            login_user_id = st.text_input("User ID", key="login_uid")
            login_password = st.text_input("Password", type="password", key="login_pwd")
            login_submit = st.form_submit_button("Login", use_container_width=True)

        if login_submit:
            if not login_user_id or not login_password:
                st.error("Please enter both User ID and Password")
            else:
                api_client = get_api_client()
                result = api_client.login(login_user_id, login_password)
                if "error" in result:
                    st.error(result["error"])
                elif "access_token" in result:
                    st.session_state.jwt_token = result["access_token"]
                    st.session_state.user_id = result["user_id"]
                    st.session_state.username = result["username"]
                    st.session_state.authentication_status = True
                    st.session_state.backend_user_id = result["user_id"]
                    save_session_to_cookie(
                        result["access_token"],
                        result["user_id"],
                        result["username"],
                    )
                    st.success("Login successful!")
                    time.sleep(0.5)
                    st.rerun()

    with tab_register:
        st.subheader("Create Account")
        with st.form("register_form", clear_on_submit=False):
            reg_user_id = st.text_input("User ID", key="reg_uid",
                                        help="Choose a unique user ID (e.g., johndoe)")
            reg_username = st.text_input("Display Name", key="reg_name",
                                         help="Your display name")
            reg_email = st.text_input("Email (optional)", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_pwd",
                                         help="Minimum 6 characters")
            reg_password_confirm = st.text_input("Confirm Password", type="password",
                                                  key="reg_pwd_confirm")
            reg_submit = st.form_submit_button("Register", use_container_width=True)

        if reg_submit:
            if not reg_user_id or not reg_username or not reg_password:
                st.error("Please fill in User ID, Display Name, and Password")
            elif len(reg_password) < 6:
                st.error("Password must be at least 6 characters")
            elif reg_password != reg_password_confirm:
                st.error("Passwords do not match")
            else:
                api_client = get_api_client()
                result = api_client.register(
                    reg_user_id, reg_username, reg_password,
                    email=reg_email if reg_email else None
                )
                if "error" in result:
                    st.error(result["error"])
                elif "access_token" in result:
                    st.session_state.jwt_token = result["access_token"]
                    st.session_state.user_id = result["user_id"]
                    st.session_state.username = result["username"]
                    st.session_state.authentication_status = True
                    st.session_state.backend_user_id = result["user_id"]
                    save_session_to_cookie(
                        result["access_token"],
                        result["user_id"],
                        result["username"],
                    )
                    st.success("Account created successfully!")
                    time.sleep(0.5)
                    st.rerun()

    st.stop()

# ==================== Authenticated App ====================

# Ensure API client has token set
api_client = get_api_client()
if st.session_state.get("jwt_token"):
    api_client.set_token(st.session_state.jwt_token)

# Add user info and logout to sidebar
with st.sidebar:
    username = st.session_state.get("username", "User")
    st.write(f"Welcome, **{username}**")

    if st.button("Logout", type="secondary", use_container_width=True):
        api_client.clear_token()
        st.session_state.do_logout = True
        st.rerun()

# Add mobile viewport meta tag
st.markdown(
    """
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    @media (max-width: 768px) {
        .stApp > div:first-child {
            padding-top: 0rem;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)

# Navigate to the main chat app
pages = {
    "Chat": [
        st.Page("multimodal_chat.py", title="Multimodal Chat", default=True),
    ]
}

pg = st.navigation(pages)
pg.run()
