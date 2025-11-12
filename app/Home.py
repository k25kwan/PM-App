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
2. **Initial Holdings** - Input existing portfolio or start fresh
3. **Security Screening** - Filter investable universe by sector/geography
4. **Portfolio Dashboard** - View risk metrics and attribution
5. **Trade Entry** - Buy or sell securities

---

### Navigation

Use the sidebar to navigate between pages:
- **Portfolio IPS**: Answer 4 questions to define your investment policy
- **Initial Holdings**: Input existing positions or skip
- **Security Screening**: Filter securities by sector and geography
- **Portfolio Dashboard**: View holdings and risk metrics
- **Trade Entry**: Execute trades

---

**Note**: This is an MVP prototype. For production use, authentication (Clerk.com) will be added.
""")

st.sidebar.success("Select a page above to get started.")

# For MVP, use a hardcoded test user
if 'user_id' not in st.session_state:
    st.session_state.user_id = 1  # Test user
    st.session_state.user_name = "Test User"

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Logged in as**: {st.session_state.user_name}")
st.sidebar.markdown(f"**User ID**: {st.session_state.user_id}")
