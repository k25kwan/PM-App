"""
PM-App: Investment Policy Statement (IPS) Questionnaire
Multi-page Streamlit application for portfolio management
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.auth import init_db, create_user, verify_user, get_user

st.set_page_config(
    page_title="PM-App - Portfolio Management",
    page_icon="chart_with_upwards_trend",
    layout="wide"
)

st.title("PM-App: Portfolio Management System")
st.markdown("### Multi-User Portfolio Analytics & IPS Screening")

st.markdown("""
Welcome to PM-App! This application helps you:

- **Define your investment policy** through a guided questionnaire
- **Screen securities** that match your investment criteria
- **Track your portfolio** with institutional-grade risk metrics
- **Analyze performance** with attribution analysis
- **Log trades** and preview portfolio impacts

---

### Quick Start

1. **Portfolio IPS** - Define risk tolerance and objectives to generate allocation buckets
2. **Add Portfolio** - Create/manage multiple portfolios and input holdings
3. **Security Screening** - Filter investable universe by sector/geography (connects to real data)
4. **Portfolio Dashboard** - View risk metrics and attribution
5. **Trade Entry** - Buy or sell securities

---

### Navigation

Use the sidebar to navigate between pages:
- **Portfolio IPS**: Answer 4 questions to define your investment policy
- **Add Portfolio**: Create, view, edit, or delete portfolios with holdings
- **Security Screening**: Filter securities by sector and geography using yfinance data
- **Portfolio Dashboard**: View holdings and risk metrics
- **Trade Entry**: Execute trades

---

**Note**: This is an MVP prototype. For production use, authentication (Clerk.com) will be added.
""")

st.sidebar.success("Select a page above to get started.")

# Initialize local user DB
init_db()

# If the session has a user_id but that user doesn't exist (stale/test session), clear it so login shows
if st.session_state.get('user_id'):
    try:
        existing = get_user(st.session_state.get('user_id'))
        if existing is None:
            for k in ['user_id', 'user_name']:
                if k in st.session_state:
                    del st.session_state[k]
            st.experimental_rerun()
    except Exception:
        # If DB lookup fails, clear session to be safe
        for k in ['user_id', 'user_name']:
            if k in st.session_state:
                del st.session_state[k]
        st.experimental_rerun()

# Authentication UI (only on Home)
if st.session_state.get('user_id'):
    st.sidebar.markdown(f"**Logged in as**: {st.session_state.get('user_name')}")
    st.sidebar.markdown(f"**User ID**: {st.session_state.get('user_id')}")
    if st.sidebar.button("Log out"):
        # Clear entire session state to remove any selected portfolio or cached user-scoped keys
        try:
            st.session_state.clear()
        except Exception:
            # Fallback to deleting known keys
            for k in ['user_id', 'user_name']:
                if k in st.session_state:
                    del st.session_state[k]
        st.experimental_rerun()
else:
    st.sidebar.markdown("**Account**")
    with st.sidebar.expander("Log in / Create account", expanded=False):
        tab1, tab2 = st.tabs(["Log in", "Sign up"])
        with tab1:
            email = st.text_input("Email", key="home_login_email")
            password = st.text_input("Password", type="password", key="home_login_pwd")
            if st.button("Log in", key="home_login_btn"):
                user_id = verify_user(email, password)
                if user_id:
                    user = get_user(user_id)
                    st.session_state.user_id = user_id
                    st.session_state.user_name = user.get('username') or user.get('email')
                    st.success(f"Logged in as {st.session_state.user_name}")
                    st.experimental_rerun()
                else:
                    st.error("Invalid credentials. If you're new, please sign up.")

        with tab2:
            username = st.text_input("Display name", key="home_signup_name")
            email_s = st.text_input("Email (for login)", key="home_signup_email")
            password_s = st.text_input("Password", type="password", key="home_signup_pwd")
            password_s2 = st.text_input("Confirm password", type="password", key="home_signup_pwd2")
            if st.button("Create account", key="home_signup_btn"):
                if not username or not email_s or not password_s:
                    st.error("Please provide name, email and password.")
                elif password_s != password_s2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        new_id = create_user(username, email_s, password_s)
                    except Exception as e:
                        st.error(f"Account creation failed: {e}")
                    else:
                        if new_id:
                            st.session_state.user_id = new_id
                            st.session_state.user_name = username
                            st.success("Account created and logged in.")
                            st.experimental_rerun()
                        else:
                            st.error("Account creation failed: email may already be in use.")

    st.sidebar.markdown("---")
