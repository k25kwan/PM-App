"""
Portfolio IPS Questionnaire
Define portfolio-level investment policy to generate allocation buckets
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

st.set_page_config(page_title="Portfolio IPS", layout="wide")

st.title("Portfolio Investment Policy Statement")
st.markdown("""
Answer these questions to define your portfolio strategy. 
We'll use your answers to generate recommended allocation buckets.
""")

# Get user_id from session
user_id = st.session_state.get('user_id', 1)

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
            # Check if response exists
            cursor.execute("""
                SELECT id FROM ips_responses 
                WHERE user_id = ? AND question_id = ?
            """, (user_id, question_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update
                cursor.execute("""
                    UPDATE ips_responses 
                    SET response = ?, question_text = ?, updated_at = SYSDATETIME()
                    WHERE user_id = ? AND question_id = ?
                """, (response, question_text, user_id, question_id))
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO ips_responses (user_id, question_id, question_text, response)
                    VALUES (?, ?, ?, ?)
                """, (user_id, question_id, question_text, response))
            
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error saving response: {e}")
        return False

def generate_allocation_buckets(responses):
    """
    Generate allocation recommendations based on IPS responses
    
    Logic:
    - Risk Tolerance determines base allocation (Conservative: 30/60/10, Moderate: 60/30/10, Aggressive: 85/10/5)
    - Investment Objective adjusts allocations (Income: +bonds, Growth: +equities)
    - Sector allocations within equities vary by risk level
    - Fixed income sleeves balance safety vs yield
    """
    # Extract key parameters
    risk_tolerance = responses.get(1, "Moderate")
    investment_objective = responses.get(2, "Balanced growth")
    time_horizon = responses.get(3, "5-10 years")
    
    # Base allocation by risk tolerance
    if risk_tolerance == "Conservative":
        allocations = {
            "Equities": 30,
            "Fixed Income": 60,
            "Cash": 10,
            "Equity Sectors": {
                "Utilities": 8,
                "Consumer Staples": 8,
                "Financials": 7,
                "Healthcare": 7
            },
            "Fixed Income Sleeves": {
                "Government Bonds": 40,
                "Investment Grade Corp": 15,
                "High Yield": 5
            }
        }
    elif risk_tolerance == "Aggressive":
        allocations = {
            "Equities": 85,
            "Fixed Income": 10,
            "Cash": 5,
            "Equity Sectors": {
                "Technology": 25,
                "Financials": 15,
                "Industrials": 15,
                "Healthcare": 12,
                "Consumer": 10,
                "Energy": 8
            },
            "Fixed Income Sleeves": {
                "Government Bonds": 5,
                "Investment Grade Corp": 3,
                "High Yield": 2
            }
        }
    else:  # Moderate
        allocations = {
            "Equities": 60,
            "Fixed Income": 30,
            "Cash": 10,
            "Equity Sectors": {
                "Technology": 15,
                "Financials": 12,
                "Healthcare": 10,
                "Industrials": 8,
                "Consumer": 8,
                "Utilities": 7
            },
            "Fixed Income Sleeves": {
                "Government Bonds": 20,
                "Investment Grade Corp": 7,
                "High Yield": 3
            }
        }
    
    # Adjust for investment objective
    if investment_objective == "Income generation":
        allocations["Fixed Income"] += 10
        allocations["Equities"] -= 10
        allocations["Equity Sectors"]["Utilities"] = allocations["Equity Sectors"].get("Utilities", 0) + 5
        allocations["Equity Sectors"]["Financials"] = allocations["Equity Sectors"].get("Financials", 0) + 5
    elif investment_objective == "Capital preservation":
        allocations["Fixed Income"] += 15
        allocations["Equities"] -= 15
    elif investment_objective == "Aggressive growth":
        allocations["Equities"] += 10
        allocations["Fixed Income"] -= 10
        allocations["Equity Sectors"]["Technology"] = allocations["Equity Sectors"].get("Technology", 0) + 5
    
    return allocations

# Load existing responses
existing_responses = load_ips_responses(user_id)

# Initialize session state with saved responses
if 'portfolio_ips' not in st.session_state:
    st.session_state.portfolio_ips = existing_responses.copy()

st.markdown("---")

# Question 1: Risk Tolerance
st.subheader("Question 1: Risk Tolerance")
q1 = st.radio(
    "How would you describe your risk tolerance?",
    options=["Conservative", "Moderate", "Aggressive"],
    index=["Conservative", "Moderate", "Aggressive"].index(st.session_state.portfolio_ips.get(1, "Moderate")) if st.session_state.portfolio_ips.get(1) in ["Conservative", "Moderate", "Aggressive"] else 1,
    key="q1_risk",
    help="Conservative: Minimize volatility, preserve capital. Moderate: Balance growth and stability. Aggressive: Maximize returns, accept high volatility."
)
st.session_state.portfolio_ips[1] = q1

st.markdown("---")

# Question 2: Investment Objective
st.subheader("Question 2: Investment Objective")
q2 = st.radio(
    "What is your primary investment objective?",
    options=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"],
    index=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"].index(st.session_state.portfolio_ips.get(2, "Balanced growth")) if st.session_state.portfolio_ips.get(2) in ["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"] else 2,
    key="q2_objective"
)
st.session_state.portfolio_ips[2] = q2

st.markdown("---")

# Question 3: Time Horizon
st.subheader("Question 3: Investment Time Horizon")
q3 = st.radio(
    "What is your investment time horizon?",
    options=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"],
    index=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"].index(st.session_state.portfolio_ips.get(3, "5-10 years")) if st.session_state.portfolio_ips.get(3) in ["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"] else 3,
    key="q3_horizon"
)
st.session_state.portfolio_ips[3] = q3

st.markdown("---")

# Question 4: Maximum Position Size
st.subheader("Question 4: Maximum Single Position Size")
q4 = st.radio(
    "What is the maximum percentage of your portfolio that can be in a single position?",
    options=["2%", "5%", "10%", "20%", "No limit"],
    index=["2%", "5%", "10%", "20%", "No limit"].index(st.session_state.portfolio_ips.get(4, "10%")) if st.session_state.portfolio_ips.get(4) in ["2%", "5%", "10%", "20%", "No limit"] else 2,
    key="q4_maxpos"
)
st.session_state.portfolio_ips[4] = q4

st.markdown("---")

# Save Button
if st.button("Generate Allocation Buckets", type="primary"):
    questions = {
        1: "Risk tolerance",
        2: "Investment objective",
        3: "Time horizon",
        4: "Maximum position size"
    }
    
    success_count = 0
    for qid, qtext in questions.items():
        if qid in st.session_state.portfolio_ips:
            if save_response(user_id, qid, qtext, st.session_state.portfolio_ips[qid]):
                success_count += 1
    
    if success_count == len(questions):
        st.success("Successfully saved all responses!")
        st.session_state.allocation_buckets_generated = True
        st.rerun()
    else:
        st.warning(f"Saved {success_count}/{len(questions)} responses. Some may have failed.")

st.markdown("---")

# Show Recommended Allocation Buckets
if len(st.session_state.portfolio_ips) >= 4 or st.session_state.get('allocation_buckets_generated'):
    st.subheader("Recommended Allocation Buckets")
    
    allocations = generate_allocation_buckets(st.session_state.portfolio_ips)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Equities", f"{allocations['Equities']}%")
    with col2:
        st.metric("Fixed Income", f"{allocations['Fixed Income']}%")
    with col3:
        st.metric("Cash", f"{allocations['Cash']}%")
    
    st.markdown("#### Equity Sector Allocation")
    equity_df = {
        "Sector": list(allocations['Equity Sectors'].keys()),
        "Target Allocation (%)": list(allocations['Equity Sectors'].values())
    }
    st.table(equity_df)
    
    st.markdown("#### Fixed Income Sleeve Allocation")
    fi_df = {
        "Sleeve": list(allocations['Fixed Income Sleeves'].keys()),
        "Target Allocation (%)": list(allocations['Fixed Income Sleeves'].values())
    }
    st.table(fi_df)
    
    st.info("These allocation targets will guide your security selection in the next steps.")
    st.markdown("**Next:** Go to 'Add Portfolio' to create a new portfolio or 'Security Screening' to filter the investment universe.")
else:
    st.info("Complete all 4 questions above and click 'Generate Allocation Buckets' to see your recommended allocations.")
