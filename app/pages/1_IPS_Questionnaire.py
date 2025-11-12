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
    Returns dict with sector/sleeve allocations
    """
    # Extract key parameters
    risk_tolerance = responses.get(1, "Moderate")
    investment_objective = responses.get(2, "Balanced growth")
    time_horizon = responses.get(3, "5-10 years")
    
    # Simple allocation logic based on risk/objective
    allocations = {}
    
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
        # Increase bonds and dividend-paying sectors
        allocations["Fixed Income"] += 10
        allocations["Equities"] -= 10
        allocations["Equity Sectors"]["Utilities"] = allocations["Equity Sectors"].get("Utilities", 0) + 5
        allocations["Equity Sectors"]["Financials"] = allocations["Equity Sectors"].get("Financials", 0) + 5
    elif investment_objective == "Capital preservation":
        # More conservative
        allocations["Fixed Income"] += 15
        allocations["Equities"] -= 15
    elif investment_objective == "Aggressive growth":
        # More equity-heavy
        allocations["Equities"] += 10
        allocations["Fixed Income"] -= 10
        allocations["Equity Sectors"]["Technology"] = allocations["Equity Sectors"].get("Technology", 0) + 5
    
    return allocations

# Load existing responses
existing_responses = load_ips_responses(user_id)

# Store responses in session state
if 'portfolio_ips' not in st.session_state:
    st.session_state.portfolio_ips = existing_responses.copy()

st.markdown("---")

# Question 1: Risk Tolerance
st.subheader("Question 1: Risk Tolerance")
q1 = st.radio(
    "How would you describe your risk tolerance?",
    options=["Conservative", "Moderate", "Aggressive"],
    index=["Conservative", "Moderate", "Aggressive"].index(st.session_state.portfolio_ips.get(1, "Moderate")) if st.session_state.portfolio_ips.get(1) in ["Conservative", "Moderate", "Aggressive"] else 1,
    key="q1",
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
    key="q2"
)
st.session_state.portfolio_ips[2] = q2

st.markdown("---")

# Question 3: Time Horizon
st.subheader("Question 3: Investment Time Horizon")
q3 = st.radio(
    "What is your investment time horizon?",
    options=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"],
    index=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"].index(st.session_state.portfolio_ips.get(3, "5-10 years")) if st.session_state.portfolio_ips.get(3) in ["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"] else 3,
    key="q3"
)
st.session_state.portfolio_ips[3] = q3

st.markdown("---")

# Question 4: Maximum Position Size
st.subheader("Question 4: Maximum Single Position Size")
q4 = st.radio(
    "What is the maximum percentage of your portfolio that can be in a single position?",
    options=["2%", "5%", "10%", "20%", "No limit"],
    index=["2%", "5%", "10%", "20%", "No limit"].index(st.session_state.portfolio_ips.get(4, "10%")) if st.session_state.portfolio_ips.get(4) in ["2%", "5%", "10%", "20%", "No limit"] else 2,
    key="q4"
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
    st.markdown("**Next:** Go to 'Initial Holdings' to input existing positions or skip to 'Security Screening' to build a new portfolio.")
else:
    st.info("Complete all 4 questions above and click 'Generate Allocation Buckets' to see your recommended allocations.")

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

# Load existing responses
existing_responses = load_ips_responses(user_id)

# Store responses in session state for this page
if 'ips_responses' not in st.session_state:
    st.session_state.ips_responses = existing_responses.copy()

st.markdown("---")

# Question 1: Time Horizon
st.subheader("Question 1: Investment Time Horizon")
q1 = st.radio(
    "What is your investment time horizon?",
    options=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"],
    index=["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"].index(st.session_state.ips_responses.get(1, "5-10 years")) if st.session_state.ips_responses.get(1) in ["< 1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"] else 3,
    key="q1"
)
st.session_state.ips_responses[1] = q1

st.markdown("---")

# Question 2: Volatility Tolerance
st.subheader("Question 2: Volatility Tolerance")
q2 = st.radio(
    "How much volatility can you tolerate in your portfolio?",
    options=["Low (0-5% annual swings)", "Moderate (5-15% annual swings)", "High (15%+ annual swings)"],
    index=["Low (0-5% annual swings)", "Moderate (5-15% annual swings)", "High (15%+ annual swings)"].index(st.session_state.ips_responses.get(2, "Moderate (5-15% annual swings)")) if st.session_state.ips_responses.get(2) in ["Low (0-5% annual swings)", "Moderate (5-15% annual swings)", "High (15%+ annual swings)"] else 1,
    key="q2"
)
st.session_state.ips_responses[2] = q2

st.markdown("---")

# Question 3: Investment Objective
st.subheader("Question 3: Primary Investment Objective")
q3 = st.radio(
    "What is your primary investment objective?",
    options=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"],
    index=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"].index(st.session_state.ips_responses.get(3, "Balanced growth")) if st.session_state.ips_responses.get(3) in ["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"] else 2,
    key="q3"
)
st.session_state.ips_responses[3] = q3

st.markdown("---")

# Question 4: Sector Exclusions
st.subheader("Question 4: Sector Exclusions")
all_sectors = ["Technology", "Financials", "Healthcare", "Energy", "Utilities", "Real Estate", "Consumer", "Industrial"]
existing_exclusions = st.session_state.ips_responses.get(4, "").split(",") if st.session_state.ips_responses.get(4) else []
q4 = st.multiselect(
    "Which sectors do you want to EXCLUDE from your portfolio?",
    options=all_sectors,
    default=[s.strip() for s in existing_exclusions if s.strip() in all_sectors],
    key="q4"
)
st.session_state.ips_responses[4] = ",".join(q4)

st.markdown("---")

# Question 5: Geographic Preference
st.subheader("Question 5: Geographic Preference")
q5 = st.radio(
    "What is your geographic preference?",
    options=["US only", "Canada only", "North America", "Global", "Emerging markets"],
    index=["US only", "Canada only", "North America", "Global", "Emerging markets"].index(st.session_state.ips_responses.get(5, "North America")) if st.session_state.ips_responses.get(5) in ["US only", "Canada only", "North America", "Global", "Emerging markets"] else 2,
    key="q5"
)
st.session_state.ips_responses[5] = q5

st.markdown("---")

# Question 6: Asset Allocation
st.subheader("Question 6: Asset Class Allocation")
st.markdown("What percentage of your portfolio should be in each asset class? (Total should equal 100%)")

col1, col2, col3 = st.columns(3)

existing_allocation = st.session_state.ips_responses.get(6, "60,30,10").split(",")
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
    st.warning(f"Warning: Total allocation is {total_pct}%, should be 100%")
else:
    st.success(f"Total allocation: {total_pct}%")

st.session_state.ips_responses[6] = f"{equity_pct},{bonds_pct},{cash_pct}"

st.markdown("---")

# Question 7: Maximum Position Size
st.subheader("Question 7: Maximum Single Position Size")
q7 = st.radio(
    "What is the maximum percentage of your portfolio that can be in a single position?",
    options=["2%", "5%", "10%", "20%", "No limit"],
    index=["2%", "5%", "10%", "20%", "No limit"].index(st.session_state.ips_responses.get(7, "10%")) if st.session_state.ips_responses.get(7) in ["2%", "5%", "10%", "20%", "No limit"] else 2,
    key="q7"
)
st.session_state.ips_responses[7] = q7

st.markdown("---")

# Save All Button
st.subheader("Save Your Responses")
if st.button("Save All Responses", type="primary"):
    success_count = 0
    questions = {
        1: "Investment time horizon",
        2: "Volatility tolerance",
        3: "Primary investment objective",
        4: "Sector exclusions",
        5: "Geographic preference",
        6: "Asset allocation",
        7: "Maximum position size"
    }
    
    for qid, qtext in questions.items():
        if qid in st.session_state.ips_responses:
            if save_response(user_id, qid, qtext, st.session_state.ips_responses[qid]):
                success_count += 1
    
    if success_count == len(questions):
        st.success(f"Successfully saved all {success_count} responses!")
    else:
        st.warning(f"Saved {success_count}/{len(questions)} responses. Some may have failed.")

st.markdown("---")

# Summary
st.subheader("IPS Summary")
if len(st.session_state.ips_responses) >= 7:
    st.success("You have answered all 7 questions!")
    st.markdown("Your investment universe will be filtered based on these preferences.")
    
    with st.expander("View Your Complete IPS"):
        allocation_parts = st.session_state.ips_responses.get(6, "60,30,10").split(",")
        st.markdown(f"""
        1. **Time Horizon**: {st.session_state.ips_responses.get(1, 'Not answered')}
        2. **Volatility Tolerance**: {st.session_state.ips_responses.get(2, 'Not answered')}
        3. **Investment Objective**: {st.session_state.ips_responses.get(3, 'Not answered')}
        4. **Sector Exclusions**: {st.session_state.ips_responses.get(4, 'None')}
        5. **Geographic Preference**: {st.session_state.ips_responses.get(5, 'Not answered')}
        6. **Asset Allocation**: Equity {allocation_parts[0]}%, Bonds {allocation_parts[1]}%, Cash {allocation_parts[2]}%
        7. **Max Position Size**: {st.session_state.ips_responses.get(7, 'Not answered')}
        """)
else:
    st.warning(f"You have answered {len(st.session_state.ips_responses)}/7 questions. Please complete all questions before saving.")
