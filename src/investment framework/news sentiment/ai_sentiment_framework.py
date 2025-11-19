"""
AI Sentiment Analysis Framework

This module provides structured guidance to the AI for interpreting
financial news headlines with nuance and context awareness.
"""

# Severity Assessment Framework
SEVERITY_FRAMEWORK = """
When analyzing financial metrics (earnings, revenue, guidance), assess magnitude:

MAGNITUDE SCALE:
- MINOR: <5% beat/miss, small adjustments, in-line with expectations
  Example: "EPS $1.02 vs $1.00 expected" → Score: 55-58
  
- MODERATE: 5-15% variance, notable but not shocking
  Example: "Revenue misses by 10%, guidance unchanged" → Score: 35-45
  
- MAJOR: 15-30% variance, significant surprise to market
  Example: "Profit crashes 25%, announces restructuring" → Score: 20-35
  
- EXTREME: >30% variance, or multiple major negatives
  Example: "Revenue down 40%, guidance withdrawn, CEO resigns" → Score: 5-20

CONTEXT MULTIPLIERS:
- First occurrence vs pattern (first miss less severe than 3rd straight)
- Industry-wide vs company-specific (macro headwinds less severe)
- Guidance forward-looking (future outlook often more impactful than past results)
- Management credibility (trusted CEO warning = more serious)
"""

# Scoring Examples for Few-Shot Learning
SCORING_EXAMPLES = """
EXAMPLE SCORING CASES:

1. MODEST BEAT:
Headline: "Apple beats Q3 earnings by 2 cents per share"
Analysis:
- Magnitude: Minor (2¢ on ~$2 EPS = 1%)
- Context: Beat is positive but small
- Score: 57/100 (slightly bullish)
Reasoning: Beat expectations but margin was thin, market likely neutral

2. SEVERE MISS WITH GUIDANCE CUT:
Headline: "Tesla misses revenue by 15%, cuts 2025 guidance by 20%"
Analysis:
- Magnitude: Major (15% miss) + Extreme (20% guidance cut)
- Context: Double negative, forward-looking concern
- Score: 22/100 (very bearish)
Reasoning: Large miss compounded by worse outlook = severe

3. STRONG QUALITATIVE BEAT:
Headline: "Microsoft reports strong earnings, beats on all metrics"
Analysis:
- Magnitude: Unclear but "all metrics" suggests broad strength
- Context: No specifics but tone very positive
- Score: 72/100 (bullish)
- Confidence: Medium (would be High with numbers)
Reasoning: Qualitative strength without red flags

4. MIXED SIGNALS:
Headline: "Amazon beats earnings but lowers holiday forecast"
Analysis:
- Magnitude: Past good + Future bad = offsetting
- Context: Holiday is critical for retail
- Score: 48/100 (neutral with slight bearish tilt)
Reasoning: Near-term beat offset by important future concern

5. AMBIGUOUS DESCRIPTOR:
Headline: "Pfizer reports weak quarterly results"
Analysis:
- Magnitude: Unknown ("weak" is vague)
- Context: Need specifics - weak vs what?
- Score: 42/100 (assume mildly bearish)
- Confidence: Low
Reasoning: Lacking specifics, assume moderate negative

APPLY THIS LOGIC TO NEW HEADLINES
"""

# Financial Keyword Guidance
KEYWORD_INTERPRETATION_GUIDE = {
    'earnings_results': {
        'positive_indicators': ['beat', 'beats', 'exceeds', 'tops', 'crushes'],
        'negative_indicators': ['miss', 'misses', 'below', 'disappoints'],
        'ambiguous_terms': ['reports', 'announces', 'posts'],
        'look_for': [
            'Percentage or dollar amount of beat/miss',
            'Which metrics (EPS, revenue, both)',
            'Year-over-year comparison',
            'Analyst reaction mentioned'
        ],
        'typical_ranges': {
            'major_beat': (70, 90),
            'modest_beat': (55, 70),
            'in_line': (48, 52),
            'modest_miss': (30, 45),
            'major_miss': (10, 30)
        }
    },
    
    'guidance_outlook': {
        'positive_indicators': ['raises', 'increases', 'upgrades', 'lifts'],
        'negative_indicators': ['lowers', 'cuts', 'reduces', 'withdraws'],
        'ambiguous_terms': ['maintains', 'reaffirms', 'updates'],
        'look_for': [
            'Magnitude of change',
            'Time period affected (Q vs full year)',
            'Reason provided',
            'Previous guidance history'
        ],
        'weight_multiplier': 1.2,  # Guidance often more impactful than past results
        'typical_ranges': {
            'major_raise': (75, 95),
            'modest_raise': (60, 75),
            'maintained': (48, 52),
            'modest_cut': (25, 40),
            'withdrawn': (10, 25)
        }
    },
    
    'acquisitions': {
        'acquirer_perspective': {
            'positive_indicators': ['strategic', 'accretive', 'synergies', 'strengthens'],
            'negative_indicators': ['overpays', 'expensive', 'questioned', 'debt-funded'],
            'look_for': ['Deal size vs company size', 'Premium paid', 'Analyst reaction']
        },
        'target_perspective': {
            'consideration': 'Being acquired can be positive (premium) or negative (independence loss)',
            'look_for': ['Premium percentage', 'Stock vs cash', 'Friendly vs hostile']
        }
    }
}

# Multi-Headline Analysis Instructions
BATCH_ANALYSIS_INSTRUCTIONS = """
When analyzing multiple headlines together:

1. IDENTIFY DOMINANT THEME:
   - Earnings season cluster? (multiple companies reporting)
   - Single company multi-story? (different aspects same company)
   - Industry trend? (regulatory change affecting sector)

2. WEIGHT BY FACTORS:
   - Recency: Recent news > old news (decay factor)
   - Source: Major outlets (WSJ, Bloomberg, Reuters) > blogs
   - Specificity: Numbers and facts > adjectives and opinions
   - Uniqueness: Exclusive info > rehashed stories

3. HANDLE CONTRADICTIONS:
   - "Beats earnings" + "Lowers guidance" = Analyze which matters more
   - Multiple sources same story = Higher confidence
   - Conflicting reports = Lower confidence, note uncertainty

4. DETECT OUTLIERS:
   - If 8/10 headlines bullish, 2 bearish = Bullish overall but note concerns
   - If perfectly split = High uncertainty, neutral score with low confidence
   
5. PROVIDE REASONING:
   - Explain dominant narrative
   - Note key catalysts
   - Highlight contradictions or uncertainties
"""

def build_ai_prompt(headlines: list, ticker: str = None) -> str:
    """
    Build comprehensive AI prompt with framework and examples.
    """
    headline_list = "\n".join([f"{i+1}. {h}" for i, h in enumerate(headlines)])
    
    ticker_context = f" for {ticker}" if ticker else ""
    
    prompt = f"""
{SEVERITY_FRAMEWORK}

{SCORING_EXAMPLES}

Now analyze these headlines{ticker_context}:

{headline_list}

IMPORTANT: You must format your response EXACTLY as follows (no extra sections):

Overall Sentiment Score: [number 0-100]
Confidence: [High/Medium/Low]
Magnitude Assessment: [Minor/Moderate/Major/Extreme]
Key Catalysts:
- [Catalyst 1]
- [Catalyst 2]
- [Catalyst 3]
Dominant Narrative: [2-3 concise sentences explaining the overall story and key factors]

Apply the magnitude framework above. Be concise - avoid repeating information.
"""
    return prompt
