"""
IPS Questionnaire Page
Collect user investment preferences to filter securities universe
"""

import streamlit as st
import sys
from pathlib import Path
import pyodbc
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

st.set_page_config(page_title="IPS Questionnaire", page_icon="📋", layout="wide")

st.title("📋 Investment Policy Statement (IPS) Questionnaire")
st.markdown("""
Answer the following questions to help us filter the securities universe to match your investment goals.
Your responses will be saved automatically.
""")

# Get user_id from session
user_id = st.session_state.get('user_id', 1)

# Load existing responses if any
def load_ips_responses(user_id):
    """Load user's existing IPS responses from database"""
    responses = {}
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("""
                SELECT question_id, response 
                FROM ips_responses 
                WHERE user_id = ?
            """, (user_id,))
            
            for row in cursor.fetchall():
                responses[row[0]] = row[1]
    except Exception as e:
        st.error(f"Error loading responses: {e}")
    
    return responses

def save_response(user_id, question_id, question_text, response):
    """Save a single IPS response to database"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("""
                MERGE INTO ips_responses AS target
                USING (SELECT ? AS user_id, ? AS question_id) AS source
                ON target.user_id = source.user_id AND target.question_id = source.question_id
                WHEN MATCHED THEN
                    UPDATE SET response = ?, question_text = ?, updated_at = SYSDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (user_id, question_id, question_text, response)
                    VALUES (?, ?, ?, ?);
            """, (user_id, question_id, response, question_text, user_id, question_id, question_text, response))
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error saving response: {e}")
        return False

# Load existing responses
existing_responses = load_ips_responses(user_id)

st.markdown("---")

# Question 1: Time Horizon
st.subheader("1️⃣ Investment Time Horizon")
q1 = st.radio(
    "What is your investment time horizon?",
    options=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"],
    index=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"].index(existing_responses.get(1, "5-10 years")),
    key="q1"
)
if st.button("Save", key="save_q1"):
    if save_response(user_id, 1, "Investment time horizon", q1):
        st.success("✓ Saved")

st.markdown("---")

# Question 2: Volatility Tolerance
st.subheader("2️⃣ Volatility Tolerance")
q2 = st.radio(
    "How much volatility can you tolerate in your portfolio?",
    options=["Low (0-5% annual swings)", "Moderate (5-15% annual swings)", "High (15%+ annual swings)"],
    index=["Low (0-5% annual swings)", "Moderate (5-15% annual swings)", "High (15%+ annual swings)"].index(existing_responses.get(2, "Moderate (5-15% annual swings)")),
    key="q2"
)
if st.button("Save", key="save_q2"):
    if save_response(user_id, 2, "Volatility tolerance", q2):
        st.success("✓ Saved")

st.markdown("---")

# Question 3: Investment Objective
st.subheader("3️⃣ Primary Investment Objective")
q3 = st.radio(
    "What is your primary investment objective?",
    options=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"],
    index=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"].index(existing_responses.get(3, "Balanced growth")),
    key="q3"
)
if st.button("Save", key="save_q3"):
    if save_response(user_id, 3, "Primary investment objective", q3):
        st.success("✓ Saved")

st.markdown("---")

# Question 4: Target Return
st.subheader("4️⃣ Target Annual Return")
q4 = st.radio(
    "What is your target annual return?",
    options=["0-3%", "3-5%", "5-8%", "8-12%", "12%+"],
    index=["0-3%", "3-5%", "5-8%", "8-12%", "12%+"].index(existing_responses.get(4, "5-8%")),
    key="q4"
)
if st.button("Save", key="save_q4"):
    if save_response(user_id, 4, "Target annual return", q4):
        st.success("✓ Saved")

st.markdown("---")

# Question 5: Sector Exclusions
st.subheader("5️⃣ Sector Exclusions")
all_sectors = ["Technology", "Financials", "Healthcare", "Energy", "Utilities", "Real Estate", "Consumer", "Industrial"]
existing_exclusions = existing_responses.get(5, "").split(",") if existing_responses.get(5) else []
q5 = st.multiselect(
    "Which sectors do you want to EXCLUDE from your portfolio?",
    options=all_sectors,
    default=[s.strip() for s in existing_exclusions if s.strip() in all_sectors],
    key="q5"
)
if st.button("Save", key="save_q5"):
    if save_response(user_id, 5, "Sector exclusions", ",".join(q5)):
        st.success("✓ Saved")

st.markdown("---")

# Question 6: Geographic Preference
st.subheader("6️⃣ Geographic Preference")
q6 = st.radio(
    "What is your geographic preference?",
    options=["US only", "Canada only", "North America", "Global", "Emerging markets"],
    index=["US only", "Canada only", "North America", "Global", "Emerging markets"].index(existing_responses.get(6, "North America")),
    key="q6"
)
if st.button("Save", key="save_q6"):
    if save_response(user_id, 6, "Geographic preference", q6):
        st.success("✓ Saved")

st.markdown("---")

# Question 7: Asset Allocation
st.subheader("7️⃣ Asset Class Allocation")
st.markdown("What percentage of your portfolio should be in each asset class? (Total should equal 100%)")

col1, col2, col3 = st.columns(3)

existing_allocation = existing_responses.get(7, "60,30,10").split(",")
default_equity = int(existing_allocation[0]) if len(existing_allocation) > 0 else 60
default_bonds = int(existing_allocation[1]) if len(existing_allocation) > 1 else 30
default_cash = int(existing_allocation[2]) if len(existing_allocation) > 2 else 10

with col1:
    equity_pct = st.number_input("Equities (%)", min_value=0, max_value=100, value=default_equity, key="equity")
with col2:
    bonds_pct = st.number_input("Bonds (%)", min_value=0, max_value=100, value=default_bonds, key="bonds")
with col3:
    cash_pct = st.number_input("Cash (%)", min_value=0, max_value=100, value=default_cash, key="cash")

total_pct = equity_pct + bonds_pct + cash_pct
if total_pct != 100:
    st.warning(f"⚠️ Total allocation is {total_pct}%, should be 100%")
else:
    st.success(f"✓ Total allocation: {total_pct}%")

if st.button("Save", key="save_q7"):
    if save_response(user_id, 7, "Asset allocation", f"{equity_pct},{bonds_pct},{cash_pct}"):
        st.success("✓ Saved")

st.markdown("---")

# Question 8: Maximum Position Size
st.subheader("8️⃣ Maximum Single Position Size")
q8 = st.radio(
    "What is the maximum percentage of your portfolio that can be in a single position?",
    options=["2%", "5%", "10%", "20%", "No limit"],
    index=["2%", "5%", "10%", "20%", "No limit"].index(existing_responses.get(8, "10%")),
    key="q8"
)
if st.button("Save", key="save_q8"):
    if save_response(user_id, 8, "Maximum position size", q8):
        st.success("✓ Saved")

st.markdown("---")

# Question 9: ESG Preferences
st.subheader("9️⃣ ESG Preferences")
q9 = st.radio(
    "Do you have any ESG (Environmental, Social, Governance) preferences?",
    options=["None", "Exclude tobacco/weapons", "Exclude fossil fuels", "Full ESG screening"],
    index=["None", "Exclude tobacco/weapons", "Exclude fossil fuels", "Full ESG screening"].index(existing_responses.get(9, "None")),
    key="q9"
)
if st.button("Save", key="save_q9"):
    if save_response(user_id, 9, "ESG preferences", q9):
        st.success("✓ Saved")

st.markdown("---")

# Question 10: Dividend Requirements
st.subheader("🔟 Dividend Requirements")
q10 = st.radio(
    "Do you have any dividend requirements?",
    options=["No preference", "Dividend payers only", "High yield (4%+)"],
    index=["No preference", "Dividend payers only", "High yield (4%+)"].index(existing_responses.get(10, "No preference")),
    key="q10"
)
if st.button("Save", key="save_q10"):
    if save_response(user_id, 10, "Dividend requirements", q10):
        st.success("✓ Saved")

st.markdown("---")

# Summary
st.subheader("📊 IPS Summary")
if len(existing_responses) == 10:
    st.success("✅ You have completed all 10 questions!")
    st.markdown("Your investment universe will be filtered based on these preferences.")
    
    with st.expander("View Your Complete IPS"):
        st.markdown(f"""
        1. **Time Horizon**: {existing_responses.get(1, 'Not answered')}
        2. **Volatility Tolerance**: {existing_responses.get(2, 'Not answered')}
        3. **Investment Objective**: {existing_responses.get(3, 'Not answered')}
        4. **Target Return**: {existing_responses.get(4, 'Not answered')}
        5. **Sector Exclusions**: {existing_responses.get(5, 'None')}
        6. **Geographic Preference**: {existing_responses.get(6, 'Not answered')}
        7. **Asset Allocation**: Equity {existing_allocation[0]}%, Bonds {existing_allocation[1]}%, Cash {existing_allocation[2]}%
        8. **Max Position Size**: {existing_responses.get(8, 'Not answered')}
        9. **ESG Preferences**: {existing_responses.get(9, 'Not answered')}
        10. **Dividend Requirements**: {existing_responses.get(10, 'Not answered')}
        """)
else:
    st.warning(f"⚠️ You have answered {len(existing_responses)}/10 questions. Please complete all questions.")
