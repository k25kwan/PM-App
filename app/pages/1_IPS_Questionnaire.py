"""
Portfolio IPS Questionnaire
Define portfolio-level investment policy to generate allocation buckets with core+satellite approach
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
Define your portfolio strategy using a systematic approach. 
We'll generate recommended allocations with sector tilts and explanations.
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
    Generate allocation recommendations based on IPS responses with intelligent conflict resolution
    
    New Logic:
    1. Start with user's asset class selection (what they WANT to invest in)
    2. Apply risk tolerance to determine HOW MUCH of each class
    3. Apply investment objective to fine-tune and resolve conflicts
    4. Split allocations into Core (passive) vs Satellite (active)
    5. Suggest sector tilts with explanations for WHY
    """
    # Extract parameters
    asset_classes_str = responses.get(1, "")
    asset_classes = [ac.strip() for ac in asset_classes_str.split(",") if ac.strip()]
    risk_tolerance = responses.get(2, "Moderate")
    core_satellite_pct = responses.get(3, 80)  # % in passive core
    investment_objective = responses.get(4, "Balanced growth")
    
    # Initialize allocation structure
    allocations = {
        "Asset Classes": {},
        "Core (Passive)": {},
        "Satellite (Active)": {},
        "Equity Sectors": {},
        "Sector Tilts": [],  # List of (sector, weight, explanation) tuples
        "Fixed Income Sleeves": {},
        "Warnings": []
    }
    
    # Step 1: Base allocation across selected asset classes
    if not asset_classes:
        allocations["Warnings"].append("No asset classes selected - defaulting to balanced portfolio")
        asset_classes = ["Equities", "Fixed Income", "ETFs"]
    
    # Determine risk-based allocation percentages
    risk_profiles = {
        "Conservative": {"Equities": 25, "Fixed Income": 65, "Cash": 10, "ETFs": 30, "Alternatives": 5},
        "Moderate": {"Equities": 55, "Fixed Income": 30, "Cash": 10, "ETFs": 45, "Alternatives": 10},
        "Aggressive": {"Equities": 80, "Fixed Income": 10, "Cash": 5, "ETFs": 60, "Alternatives": 15}
    }
    
    base_weights = risk_profiles.get(risk_tolerance, risk_profiles["Moderate"])
    
    # Adjust for objective conflicts
    if investment_objective == "Capital preservation" and risk_tolerance == "Aggressive":
        allocations["Warnings"].append(
            "⚠️ Conflict detected: Capital preservation objective with aggressive risk tolerance. "
            "Adjusting to Moderate-Conservative allocation for safety."
        )
        base_weights = risk_profiles["Moderate"]
        # Shift more to bonds
        base_weights["Fixed Income"] += 15
        base_weights["Equities"] -= 15
        
    elif investment_objective == "Aggressive growth" and risk_tolerance == "Conservative":
        allocations["Warnings"].append(
            "⚠️ Conflict detected: Aggressive growth objective with conservative risk tolerance. "
            "Adjusting to Moderate-Aggressive allocation with protective measures."
        )
        base_weights = risk_profiles["Moderate"]
        # Shift more to equities but not extreme
        base_weights["Equities"] += 10
        base_weights["Fixed Income"] -= 10
    
    # Build allocation based on selected asset classes
    total_weight = 0
    for asset_class in asset_classes:
        if asset_class in base_weights:
            allocations["Asset Classes"][asset_class] = base_weights[asset_class]
            total_weight += base_weights[asset_class]
    
    # Normalize to 100%
    if total_weight > 0 and total_weight != 100:
        scale_factor = 100 / total_weight
        for asset_class in allocations["Asset Classes"]:
            allocations["Asset Classes"][asset_class] = round(
                allocations["Asset Classes"][asset_class] * scale_factor, 1
            )
    
    # Step 2: Split into Core vs Satellite
    core_pct = float(core_satellite_pct) / 100
    satellite_pct = 1 - core_pct
    
    for asset_class, weight in allocations["Asset Classes"].items():
        allocations["Core (Passive)"][asset_class] = round(weight * core_pct, 1)
        allocations["Satellite (Active)"][asset_class] = round(weight * satellite_pct, 1)
    
    # Step 3: Equity sector allocation with tilts and explanations
    if "Equities" in asset_classes or "ETFs" in asset_classes:
        sector_tilts = []
        
        if risk_tolerance == "Aggressive":
            allocations["Equity Sectors"] = {
                "Technology": 28,
                "Financials": 16,
                "Industrials": 14,
                "Healthcare": 12,
                "Consumer Discretionary": 12,
                "Communication Services": 10,
                "Energy": 8
            }
            sector_tilts.append(("Technology", 28, "Overweight: High growth potential aligns with aggressive risk tolerance"))
            sector_tilts.append(("Financials", 16, "Overweight: Leverage to economic growth and rising rates"))
            
        elif risk_tolerance == "Conservative":
            allocations["Equity Sectors"] = {
                "Healthcare": 20,
                "Utilities": 18,
                "Consumer Staples": 18,
                "Financials": 15,
                "Industrials": 12,
                "Technology": 10,
                "Real Estate": 7
            }
            sector_tilts.append(("Healthcare", 20, "Overweight: Defensive sector with stable demand"))
            sector_tilts.append(("Utilities", 18, "Overweight: Stable dividends and low volatility"))
            sector_tilts.append(("Consumer Staples", 18, "Overweight: Essential goods provide downside protection"))
            
        else:  # Moderate
            allocations["Equity Sectors"] = {
                "Technology": 18,
                "Financials": 15,
                "Healthcare": 14,
                "Industrials": 12,
                "Consumer Discretionary": 11,
                "Consumer Staples": 10,
                "Communication Services": 10,
                "Utilities": 10
            }
            sector_tilts.append(("Technology", 18, "Neutral-Overweight: Balanced exposure to growth"))
            sector_tilts.append(("Financials", 15, "Neutral: Diversified exposure to credit cycle"))
        
        # Adjust for objective
        if investment_objective == "Income generation":
            # Boost dividend-heavy sectors
            if "Utilities" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Utilities"] += 8
            else:
                allocations["Equity Sectors"]["Utilities"] = 8
                
            if "Financials" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Financials"] += 5
            else:
                allocations["Equity Sectors"]["Financials"] = 5
                
            # Reduce from growth sectors
            if "Technology" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Technology"] = max(5, allocations["Equity Sectors"]["Technology"] - 8)
            
            sector_tilts.append(("Utilities", allocations["Equity Sectors"].get("Utilities", 0), 
                               "Overweight: High dividend yield supports income objective"))
            sector_tilts.append(("Financials", allocations["Equity Sectors"].get("Financials", 0),
                               "Overweight: Bank dividends provide steady income stream"))
        
        elif investment_objective == "Aggressive growth":
            # Boost growth sectors
            if "Technology" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Technology"] += 7
            else:
                allocations["Equity Sectors"]["Technology"] = 7
                
            if "Communication Services" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Communication Services"] += 5
            else:
                allocations["Equity Sectors"]["Communication Services"] = 5
                
            # Reduce defensive
            if "Utilities" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Utilities"] = max(3, allocations["Equity Sectors"]["Utilities"] - 7)
            if "Consumer Staples" in allocations["Equity Sectors"]:
                allocations["Equity Sectors"]["Consumer Staples"] = max(3, allocations["Equity Sectors"]["Consumer Staples"] - 5)
            
            sector_tilts.append(("Technology", allocations["Equity Sectors"].get("Technology", 0),
                               "Overweight: Innovation and scalability drive long-term growth"))
            sector_tilts.append(("Communication Services", allocations["Equity Sectors"].get("Communication Services", 0),
                               "Overweight: Digital transformation and network effects"))
        
        allocations["Sector Tilts"] = sector_tilts
    
    # Step 4: Fixed income sleeve allocation
    if "Fixed Income" in asset_classes:
        if risk_tolerance == "Aggressive":
            allocations["Fixed Income Sleeves"] = {
                "Government Bonds": 30,
                "Investment Grade Corporate": 40,
                "High Yield": 20,
                "Emerging Market Debt": 10
            }
        elif risk_tolerance == "Conservative":
            allocations["Fixed Income Sleeves"] = {
                "Government Bonds": 60,
                "Investment Grade Corporate": 30,
                "High Yield": 5,
                "Cash/Money Market": 5
            }
        else:  # Moderate
            allocations["Fixed Income Sleeves"] = {
                "Government Bonds": 45,
                "Investment Grade Corporate": 35,
                "High Yield": 15,
                "Cash/Money Market": 5
            }
        
        # Adjust for objective
        if investment_objective == "Income generation":
            # Shift toward higher-yielding bonds
            allocations["Fixed Income Sleeves"]["High Yield"] = allocations["Fixed Income Sleeves"].get("High Yield", 0) + 10
            allocations["Fixed Income Sleeves"]["Investment Grade Corporate"] = max(10, 
                allocations["Fixed Income Sleeves"].get("Investment Grade Corporate", 0) - 5)
            allocations["Fixed Income Sleeves"]["Government Bonds"] = max(20,
                allocations["Fixed Income Sleeves"].get("Government Bonds", 0) - 5)
    
    return allocations

# Load existing responses
existing_responses = load_ips_responses(user_id)

# Initialize session state with saved responses
if 'portfolio_ips' not in st.session_state:
    st.session_state.portfolio_ips = existing_responses.copy()

st.markdown("---")

# Question 1: Asset Class Selection
st.subheader("Question 1: Asset Class Selection")
st.markdown("Select ALL asset classes you want to include in your portfolio")

all_asset_classes = ["Equities", "Fixed Income", "ETFs", "Cash", "Alternatives"]
existing_asset_classes = st.session_state.portfolio_ips.get(1, "Equities,Fixed Income,ETFs").split(",") if st.session_state.portfolio_ips.get(1) else []
selected_asset_classes = st.multiselect(
    "Asset Classes",
    options=all_asset_classes,
    default=[ac.strip() for ac in existing_asset_classes if ac.strip() in all_asset_classes] if existing_asset_classes else ["Equities", "Fixed Income", "ETFs"],
    key="asset_classes",
    help="Check all that apply. ETFs can be passive (core) or active (satellite)."
)
st.session_state.portfolio_ips[1] = ",".join(selected_asset_classes)

st.markdown("---")

# Question 2: Risk Tolerance
st.subheader("Question 2: Risk Tolerance")
q2 = st.radio(
    "How would you describe your risk tolerance?",
    options=["Conservative", "Moderate", "Aggressive"],
    index=["Conservative", "Moderate", "Aggressive"].index(st.session_state.portfolio_ips.get(2, "Moderate")) if st.session_state.portfolio_ips.get(2) in ["Conservative", "Moderate", "Aggressive"] else 1,
    key="q2_risk",
    help="Conservative: Minimize volatility, preserve capital. Moderate: Balance growth and stability. Aggressive: Maximize returns, accept high volatility."
)
st.session_state.portfolio_ips[2] = q2

st.markdown("---")

# Question 3: Core+Satellite Approach
st.subheader("Question 3: Core + Satellite Strategy")
st.markdown("""
**Core (Passive)**: Index funds/ETFs that match market returns with low fees  
**Satellite (Active)**: Individual stocks or active funds seeking to outperform
""")

existing_core_pct = st.session_state.portfolio_ips.get(3, 80)
try:
    existing_core_pct = int(existing_core_pct) if existing_core_pct else 80
except:
    existing_core_pct = 80

core_pct = st.slider(
    "What percentage should be in PASSIVE (Core) investments?",
    min_value=0,
    max_value=100,
    value=existing_core_pct,
    step=5,
    key="core_satellite",
    help="100% = Fully passive (all index funds). 0% = Fully active (all stock picking)."
)
st.session_state.portfolio_ips[3] = core_pct

col1, col2 = st.columns(2)
with col1:
    st.metric("Core (Passive)", f"{core_pct}%", help="Low-cost index tracking")
with col2:
    st.metric("Satellite (Active)", f"{100-core_pct}%", help="Opportunistic alpha seeking")

st.markdown("---")

# Question 4: Investment Objective
st.subheader("Question 4: Investment Objective")
q4 = st.radio(
    "What is your primary investment objective?",
    options=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"],
    index=["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"].index(st.session_state.portfolio_ips.get(4, "Balanced growth")) if st.session_state.portfolio_ips.get(4) in ["Capital preservation", "Income generation", "Balanced growth", "Aggressive growth"] else 2,
    key="q4_objective"
)
st.session_state.portfolio_ips[4] = q4

st.markdown("---")

# Save Button
if st.button("Generate Allocation Strategy", type="primary"):
    questions = {
        1: "Asset class selection",
        2: "Risk tolerance",
        3: "Core+Satellite percentage",
        4: "Investment objective"
    }
    
    success_count = 0
    for qid, qtext in questions.items():
        if qid in st.session_state.portfolio_ips:
            response_value = str(st.session_state.portfolio_ips[qid])
            if save_response(user_id, qid, qtext, response_value):
                success_count += 1
    
    if success_count == len(questions):
        st.success("Successfully saved all responses!")
        st.session_state.allocation_buckets_generated = True
        st.rerun()
    else:
        st.warning(f"Saved {success_count}/{len(questions)} responses. Some may have failed.")

st.markdown("---")

# Show Recommended Allocation Strategy
if len(st.session_state.portfolio_ips) >= 4 or st.session_state.get('allocation_buckets_generated'):
    st.subheader("📊 Recommended Allocation Strategy")
    
    allocations = generate_allocation_buckets(st.session_state.portfolio_ips)
    
    # Show any warnings about conflicts
    if allocations.get("Warnings"):
        for warning in allocations["Warnings"]:
            st.warning(warning)
    
    # Asset Class Allocation
    st.markdown("### Asset Class Allocation")
    if allocations["Asset Classes"]:
        cols = st.columns(len(allocations["Asset Classes"]))
        for idx, (asset_class, weight) in enumerate(allocations["Asset Classes"].items()):
            with cols[idx]:
                st.metric(asset_class, f"{weight}%")
    else:
        st.info("No asset classes selected")
    
    st.markdown("---")
    
    # Core vs Satellite Breakdown
    st.markdown("### Core + Satellite Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎯 Core (Passive)")
        st.caption("Index funds and ETFs tracking market benchmarks")
        if allocations["Core (Passive)"]:
            core_df = {
                "Asset Class": list(allocations["Core (Passive)"].keys()),
                "Allocation (%)": list(allocations["Core (Passive)"].values())
            }
            st.table(core_df)
            st.info("💡 **Implementation**: Use low-cost index ETFs (e.g., SPY, AGG, VT)")
        else:
            st.info("100% active strategy - no passive core")
    
    with col2:
        st.markdown("#### 🚀 Satellite (Active)")
        st.caption("Individual securities and active strategies")
        if allocations["Satellite (Active)"]:
            satellite_df = {
                "Asset Class": list(allocations["Satellite (Active)"].keys()),
                "Allocation (%)": list(allocations["Satellite (Active)"].values())
            }
            st.table(satellite_df)
            st.info("💡 **Implementation**: Stock picking, sector rotation, tactical tilts")
        else:
            st.info("100% passive strategy - no active satellite")
    
    st.markdown("---")
    
    # Equity Sector Allocation with Tilts
    if allocations["Equity Sectors"]:
        st.markdown("### Equity Sector Allocation")
        
        equity_df = {
            "Sector": list(allocations['Equity Sectors'].keys()),
            "Target Allocation (%)": list(allocations['Equity Sectors'].values())
        }
        st.table(equity_df)
        
        # Show sector tilt explanations
        if allocations.get("Sector Tilts"):
            st.markdown("#### 📈 Sector Tilt Rationale")
            for sector, weight, explanation in allocations["Sector Tilts"]:
                st.markdown(f"**{sector}** ({weight}%): {explanation}")
    
    st.markdown("---")
    
    # Fixed Income Sleeve Allocation
    if allocations["Fixed Income Sleeves"]:
        st.markdown("### Fixed Income Sleeve Allocation")
        fi_df = {
            "Sleeve": list(allocations['Fixed Income Sleeves'].keys()),
            "Target Allocation (%)": list(allocations['Fixed Income Sleeves'].values())
        }
        st.table(fi_df)
    
    st.markdown("---")
    
    st.success("✅ Your allocation strategy is ready!")
    st.markdown("**Next Steps:**")
    st.markdown("- **Add Portfolio**: Create a portfolio and add holdings based on these allocations")
    st.markdown("- **Security Screening**: Filter securities that match your sector preferences")
else:
    st.info("Complete all 4 questions above and click 'Generate Allocation Strategy' to see your recommended allocations.")
