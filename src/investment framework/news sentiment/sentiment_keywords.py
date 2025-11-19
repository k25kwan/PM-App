"""
Sentiment Keywords Configuration with Weighted Scoring

This module contains the keyword universe for sentiment analysis with weights
representing the strength of sentiment each keyword conveys.

Weight Scale:
- 1.0: Mild sentiment indicator
- 2.0: Moderate sentiment indicator
- 3.0: Strong sentiment indicator
- 4.0: Very strong sentiment indicator (major market-moving events)

Keyword Categories:
- POSITIVE_KEYWORDS: Unambiguously bullish signals
- NEGATIVE_KEYWORDS: Unambiguously bearish signals  
- CONTEXT_DEPENDENT_KEYWORDS: Ambiguous - require AI analysis for accurate scoring

Strategy:
- Simple headlines with clear keywords → Fast keyword scoring
- Headlines with context-dependent keywords → AI deep-dive analysis
- This optimizes cost (AI only when needed) and accuracy (AI handles nuance)
"""

# Unambiguous Positive Keywords with Weights
# These are ALWAYS bullish regardless of context
POSITIVE_KEYWORDS = {
    # Strong Growth & Performance (3.0-4.0) - UNAMBIGUOUS
    'breakthrough': 4.0,
    'blockbuster': 4.0,
    'record-breaking': 4.0,
    'surges': 3.5,
    'soars': 3.5,
    'skyrockets': 3.5,
    'rallies': 3.0,
    'jumps': 3.0,
    'climbs': 3.0,
    'crushes': 3.5,
    'exceeds': 3.0,
    'outperforms': 3.0,
    'accelerates': 3.0,
    
    # Earnings & Financial - UNAMBIGUOUS (always good)
    'beat earnings': 4.0,
    'beats earnings': 4.0,
    'beat estimates': 4.0,
    'beats estimates': 4.0,
    'beat expectations': 4.0,
    'beats expectations': 4.0,
    'crushes estimates': 4.5,
    'crush estimates': 4.5,
    'strong earnings': 3.5,
    'revenue growth': 3.0,
    'profit surge': 3.5,
    'margin expansion': 3.0,
    'eps beat': 3.5,
    'guidance raised': 4.0,
    'raises outlook': 4.0,
    'raises guidance': 4.0,
    'raises forecast': 4.0,
    'tops estimates': 4.0,
    'better than expected': 3.5,
    
    # Analyst Actions - UNAMBIGUOUS (always bullish signals)
    'upgraded': 3.5,
    'upgrade to buy': 4.0,
    'price target raised': 3.5,
    'price target increased': 3.5,
    'analyst upgrade': 3.5,
    'overweight rating': 3.0,
    'outperform rating': 3.0,
    'strong buy': 3.5,
    'buy rating': 3.0,
    
    # Corporate Actions - UNAMBIGUOUS
    # NOTE: Removed simple 'acquires' - moved to context-dependent
    'completes acquisition': 2.5,  # Completion is mildly positive (deal uncertainty removed)
    'stock buyback': 3.5,
    'share repurchase': 3.5,
    'buyback program': 3.5,
    'dividend increase': 3.5,
    'dividend hike': 3.5,
    'raises dividend': 3.5,
    'special dividend': 3.5,
    
    # Regulatory & Approvals - UNAMBIGUOUS (always positive)
    'fda approval': 4.0,
    'fda approves': 4.0,
    'regulatory approval': 4.0,
    'wins approval': 4.0,
    'gets approval': 3.5,
    'clears regulatory': 3.5,
    'patent granted': 3.5,
    'patent approved': 3.5,
    
    # Product Success - UNAMBIGUOUS
    'breakthrough product': 3.5,
    'successful trial': 3.5,
    'positive trial results': 4.0,
    'trial success': 4.0,
    'strong sales': 3.0,
    'record sales': 3.5,
    'best-selling': 3.0,
    
    # Market Position - UNAMBIGUOUS
    'market leader': 2.5,
    'dominates market': 3.0,
    'gains market share': 3.0,
    'market share gains': 3.0,
    'competitive advantage': 2.5,
    
    # General Positive - UNAMBIGUOUS
    'bullish outlook': 2.5,
    'optimistic outlook': 2.5,
    'strong momentum': 2.5,
    'building momentum': 2.0,
}

# Unambiguous Negative Keywords with Weights (negative values)
# These are ALWAYS bearish regardless of context
NEGATIVE_KEYWORDS = {
    # Strong Decline & Performance - UNAMBIGUOUS (always bad)
    'crashes': -4.0,
    'collapses': -4.0,
    'plunges': -3.5,
    'plummets': -3.5,
    'tumbles': -3.5,
    'tanks': -3.5,
    'nosedives': -4.0,
    'craters': -4.0,
    
    # Earnings & Financial - UNAMBIGUOUS (always bad)
    'misses earnings': -4.0,
    'misses estimates': -4.0,
    'earnings miss': -4.0,
    'revenue miss': -3.5,
    'below estimates': -3.5,
    'worse than expected': -3.5,
    'profit warning': -4.0,
    'guidance cut': -4.0,
    'lowers guidance': -4.0,
    'lowers outlook': -4.0,
    'cuts forecast': -4.0,
    'warns': -3.5,
    'profit decline': -3.0,
    'revenue decline': -3.0,
    'weak earnings': -3.5,
    'disappointing earnings': -3.5,
    'margin compression': -3.0,
    
    # Analyst Actions - UNAMBIGUOUS (always bearish)
    'downgraded': -3.5,
    'downgrade to sell': -4.0,
    'price target cut': -3.5,
    'price target lowered': -3.5,
    'analyst downgrade': -3.5,
    'sell rating': -3.5,
    'underweight rating': -3.0,
    'underperform rating': -3.0,
    
    # Legal & Regulatory - UNAMBIGUOUS (always bad)
    'lawsuit filed': -3.5,
    'sued': -3.5,
    'faces lawsuit': -3.5,
    'investigation launched': -3.5,
    'criminal investigation': -4.0,
    'probe': -3.5,
    'fraud allegations': -4.0,
    'fraud charges': -4.0,
    'fined': -3.5,
    'penalty imposed': -3.0,
    'regulatory violation': -3.0,
    'fda rejection': -4.0,
    'rejected by fda': -4.0,
    'fails to get approval': -3.5,
    
    # Corporate Crisis - UNAMBIGUOUS (always terrible)
    'bankruptcy': -4.0,
    'files for bankruptcy': -4.5,
    'bankruptcy protection': -4.0,
    'insolvency': -4.0,
    'defaulted': -4.0,
    'debt default': -4.0,
    'announces layoffs': -3.0,
    'job cuts': -3.0,
    'mass layoffs': -3.5,
    'plant closure': -3.5,
    'closes plant': -3.5,
    'product recall': -4.0,
    'recalls product': -4.0,
    'safety recall': -4.0,
    'scandal': -4.0,
    'crisis': -3.5,
    
    # Acquisition as Target - UNAMBIGUOUS (company losing independence)
    'acquired by': -2.0,  # Company is being bought
    'takeover bid': -1.5,  # Could be hostile
    'hostile takeover': -3.0,
    
    # Market Position Loss - UNAMBIGUOUS
    'loses market share': -3.0,
    'market share loss': -3.0,
    'loses to competitor': -2.5,
    
    # General Negative - UNAMBIGUOUS
    'bearish outlook': -2.5,
    'pessimistic outlook': -2.5,
    'losing momentum': -2.0,
}

# Context-Dependent Keywords
# These require surrounding words to determine sentiment direction
# Only add keywords here if they genuinely have mixed meanings
# Context-Dependent Keywords
# These keywords are AMBIGUOUS and should trigger AI analysis
# Rather than trying to pattern-match context, we flag these for the AI to interpret

CONTEXT_DEPENDENT_KEYWORDS = {
    # Corporate Actions
    'acquisition': 'Strategic vs overpaid, buyer vs target - requires context',
    'acquires': 'Generally positive but depends on price and strategy',
    'merger': 'Could be value-creating or defensive - needs analysis',
    'restructuring': 'Could be turnaround (good) or distress (bad)',
    'partnership': 'Strategic partnerships good, desperate ones questionable',
    
    # Financial Metrics
    'debt': 'Paying down debt = good, taking on debt = depends on use',
    'growth': 'Accelerating = good, slowing = bad',
    'expansion': 'Market expansion = good, overextension = bad',
    'guidance': 'Raising = good, lowering = bad, withdrawing = very bad',
    
    # Regulatory/Approvals
    'approved': 'Approval = good, rejection = bad',
    'trial': 'Trial success = good, trial failure = bad',
    'deal': 'Deal signed = good, deal falls through = bad',
    
    # Market Events
    'outlook': 'Positive outlook = good, negative outlook = bad',
    'forecast': 'Raised forecast = good, lowered forecast = bad',
    'expectations': 'Beats = good, misses = bad, in-line = neutral',
    
    # Operational
    'changes': 'Leadership changes, strategy changes - could be either',
    'announces': 'Announcement content determines sentiment',
    'plans': 'Expansion plans = good, cost-cutting plans = mixed',
}

# Helper: Check if headline contains context-dependent keywords
def contains_ambiguous_keywords(headline: str) -> bool:
    """
    Check if headline contains any context-dependent keywords
    that would benefit from AI analysis.
    
    Returns:
        True if AI analysis recommended, False if keyword scoring sufficient
    """
    headline_lower = headline.lower()
    return any(keyword in headline_lower for keyword in CONTEXT_DEPENDENT_KEYWORDS.keys())


def get_ambiguous_keywords_found(headline: str) -> list:
    """
    Return list of context-dependent keywords found in headline.
    """
    headline_lower = headline.lower()
    found = []
    for keyword, reason in CONTEXT_DEPENDENT_KEYWORDS.items():
        if keyword in headline_lower:
            found.append({'keyword': keyword, 'reason': reason})
    return found


# Negation words that flip sentiment
NEGATION_WORDS = {
    'not', 'no', 'never', 'neither', 'nor', 'none', 
    'nobody', 'nothing', 'without', "n't", "don't", "doesn't",
    "didn't", "won't", "wouldn't", "shouldn't", "couldn't"
}

# Intensifiers that boost weight
INTENSIFIERS = {
    'very': 1.3,
    'extremely': 1.5,
    'significantly': 1.4,
    'substantially': 1.4,
    'dramatically': 1.5,
    'massively': 1.5,
    'hugely': 1.4,
    'sharply': 1.3,
    'strongly': 1.3,
}

# Diminishers that reduce weight
DIMINISHERS = {
    'slightly': 0.6,
    'somewhat': 0.7,
    'marginally': 0.5,
    'barely': 0.4,
    'modestly': 0.7,
    'mildly': 0.6,
}
