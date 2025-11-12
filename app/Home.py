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
    page_icon="📊",
    layout="wide"
)

st.title("📊 PM-App: Portfolio Management System")
st.markdown("### Multi-User Portfolio Analytics & IPS Screening")

st.markdown("""
Welcome to PM-App! This application helps you:

- ✅ **Define your investment policy** through a guided questionnaire
- 📈 **Screen securities** that match your investment criteria
- 💼 **Track your portfolio** with institutional-grade risk metrics
- 📊 **Analyze performance** with attribution analysis
- 💰 **Log trades** and preview portfolio impacts

---

### Quick Start

1. **Complete IPS Questionnaire** → Define your investment preferences
2. **Browse Filtered Universe** → See securities matching your criteria
3. **View Security Details** → Analyze fundamentals and scoring
4. **Enter Trades** → Update your portfolio
5. **View Dashboard** → Monitor risk metrics and attribution

---

### Navigation

Use the sidebar to navigate between pages:
- **IPS Questionnaire**: Answer 10 questions to define your investment policy
- **Universe Browser**: Explore securities matching your IPS
- **Portfolio Dashboard**: View your current holdings and risk metrics
- **Trade Entry**: Buy or sell securities

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
