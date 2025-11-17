# IPS Questionnaire Page Documentation

## Overview
The IPS (Investment Policy Statement) Questionnaire page (`app/pages/1_IPS_Questionnaire.py`) allows users to define their investment strategy through a guided 4-question process that generates personalized allocation recommendations.

## Current Implementation

### Purpose
Define portfolio-level investment policy to generate allocation buckets with a core+satellite approach and sector tilts.

### Workflow
1. User answers 4 strategic questions
2. System generates allocation recommendations
3. Allocations split into Core (passive) vs Satellite (active)
4. Sector tilts suggested with explanations
5. Results saved to database for portfolio creation

### The 4 Key Questions

#### Question 1: Asset Class Selection
**What to invest in**
- Options: Equities, Fixed Income, Real Estate, Commodities, Alternatives
- Multi-select allowed
- Determines the universe of investable assets

#### Question 2: Risk Tolerance
**How much of each class**
- Options: Conservative, Moderate, Aggressive
- Determines allocation percentages
- Maps to volatility targets:
  - Conservative: 60% bonds, 40% stocks
  - Moderate: 40% bonds, 60% stocks
  - Aggressive: 20% bonds, 80% stocks

#### Question 3: Core-Satellite Split
**Passive vs Active management**
- Slider: 0-100% to passive core
- Core = Index funds, ETFs (low cost, broad exposure)
- Satellite = Active picks, sector bets (higher conviction)
- Default: 80% passive, 20% active

#### Question 4: Sector Tilt
**Strategic overweights**
- Options:
  - Defensive (preservation focus)
  - Income (dividend focus)
  - Growth (capital appreciation)
  - Cyclical (economic sensitivity)
  - Balanced (diversified)
- Generates specific sector recommendations

### Allocation Generation Logic

**Conflict Resolution Hierarchy:**
1. Start with asset classes (user preference)
2. Apply risk tolerance (sizing)
3. Apply sector tilt (refinement)
4. Split into core/satellite

**Example Output:**
```
Core Holdings (80%):
- 48% S&P 500 Index (Equity - Large Cap)
- 32% Aggregate Bond Index (Fixed Income)

Satellite Holdings (20%):
- 12% Technology Sector (Growth tilt)
- 8% High Yield Bonds (Income tilt)

Sector Tilts:
- Technology +5% (Growth objective)
- Healthcare +3% (Defensive positioning)
- Energy -2% (Risk management)
```

### Database Schema
**Table: `ips_responses`**
- `id`: Primary key
- `user_id`: Foreign key to users
- `question_id`: 1-4 for the questions
- `question_text`: Full question text
- `response`: User's answer
- `created_at`: Timestamp
- `updated_at`: Timestamp

## Technical Details

### Key Functions

1. **`load_ips_responses(user_id)`**
   - Fetches existing responses from database
   - Returns dict: {question_id: response}
   - Used to pre-populate form

2. **`save_response(user_id, question_id, question_text, response)`**
   - Upserts response to database
   - Handles both insert and update
   - Returns success boolean

3. **`generate_allocation_buckets(responses)`**
   - Core algorithm for allocation generation
   - Applies conflict resolution logic
   - Returns structured allocation dictionary
   - Includes explanations for each recommendation

4. **`display_allocation_results(allocations)`**
   - Renders allocation recommendations
   - Shows core vs satellite breakdown
   - Displays sector tilts with rationale
   - Provides next steps

### Data Flow
```
User answers questions → Save to database → Generate allocations → Display results → User proceeds to Add Portfolio
```

### Validation
- Question 1: Must select at least one asset class
- Question 2: Must select risk tolerance
- Question 3: Percentage validated (0-100)
- Question 4: Must select sector tilt

## Next Steps

### Discussed Improvements

1. **Enhance Allocation Algorithm**
   - Add more granular asset class options (e.g., International Equities, Emerging Markets)
   - Include real-time market data for dynamic adjustments
   - Factor in user's age/retirement horizon
   - Consider tax implications (tax-advantaged accounts)

2. **Visualization Enhancements**
   - Add pie chart for allocation breakdown
   - Show efficient frontier based on inputs
   - Compare to sample portfolios (e.g., "60/40", "All Weather")
   - Historical performance backtest of recommended allocation

3. **Questionnaire Expansion**
   - Add question on investment horizon (short/medium/long term)
   - Include liquidity needs assessment
   - ESG (Environmental, Social, Governance) preferences
   - Tax situation (taxable vs tax-advantaged accounts)

4. **Smart Defaults & Guidance**
   - Industry benchmarks based on user profile
   - "People like you typically choose..." suggestions
   - Warning system for extreme allocations
   - Rebalancing frequency recommendations

5. **Integration with Portfolio Creation**
   - Auto-populate Add Portfolio page with IPS allocations
   - Suggest specific ETFs/funds for each bucket
   - One-click portfolio creation from IPS
   - Compare actual portfolio to IPS targets

### Technical Debt
- Currently hardcoded `user_id = 1` - needs authentication
- Allocation logic could be more sophisticated (optimize for Sharpe ratio)
- No validation against impossible combinations
- Missing unit tests for allocation generation

### Known Limitations
- Binary core/satellite split (no hybrid instruments)
- Sector tilts are suggestions only (not enforced)
- No consideration of existing holdings
- Allocation percentages are static (not market-adaptive)

## Dependencies
- `streamlit`: UI framework
- `src.core.utils_db`: Database connection utilities
- SQL Server database with `ips_responses` table

## File Location
`c:\Users\Kevin Kwan\PM-app\app\pages\1_IPS_Questionnaire.py`

## Related Files
- `sql/schemas/01_core_portfolio.sql` - Database schema
- `app/pages/2_Add_Portfolio.py` - Next step in workflow
