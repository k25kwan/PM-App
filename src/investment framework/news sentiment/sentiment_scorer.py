"""
Enhanced Sentiment Scoring with Transparency and AI Feedback Loop

This module provides detailed sentiment scoring with full visibility into
the decision-making process at each step.

Tiered Scoring Approach:
1. Keywords for obvious sentiment (FREE)
2. AI for ambiguous headlines (GPT-4o-mini, ~$0.00004/headline)
3. Aggregate AI analysis for overall narrative (already implemented)
"""

import re
import os
from typing import List, Dict, Tuple
from dotenv import load_dotenv
from sentiment_keywords import (
    POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS, CONTEXT_DEPENDENT_KEYWORDS,
    NEGATION_WORDS, INTENSIFIERS, DIMINISHERS,
    contains_ambiguous_keywords, get_ambiguous_keywords_found
)
from openai import OpenAI


def score_headline_with_ai(headline: str, ticker: str = None) -> Dict:
    """
    Use AI to score a single ambiguous headline
    
    Cost: ~$0.00004 per headline (GPT-4o-mini)
    Only called for headlines that keyword scoring can't handle
    
    Args:
        headline: The headline text
        ticker: Stock ticker symbol
    
    Returns:
        Dict with score and reasoning
    """
    try:
        # Load .env from project root (3 levels up from this file)
        env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
        load_dotenv(dotenv_path=env_path, override=True)  # Force reload to get latest key
        api_key = os.environ.get("OPENAI_API_KEY", "").strip().strip('"').strip("'")
        
        # Debug: Print key info (first/last 4 chars only for security)
        if api_key:
            print(f"[DEBUG] API key loaded: {api_key[:7]}...{api_key[-4:]}, length: {len(api_key)}")
        else:
            print(f"[DEBUG] No API key found in environment")
            
        if not api_key:
            return {'score': 50, 'reasoning': 'No API key', 'ai_scored': False}
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""Score this stock headline for sentiment on a scale of 0-100:
- 0 = Extremely negative (bankruptcy, fraud, collapse)
- 25 = Moderately negative (missed earnings, downgrades, losses)
- 50 = Neutral (mixed signals, informational only)
- 75 = Moderately positive (beat earnings, partnerships, growth)
- 100 = Extremely positive (breakthrough innovation, massive beat)

Headline: "{headline}"
{f'Ticker: {ticker}' if ticker else ''}

Respond with ONLY a number 0-100. No explanation."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=10
        )
        
        score_text = response.choices[0].message.content.strip()
        score = float(re.search(r'\d+', score_text).group())
        score = max(0, min(100, score))  # Clamp to 0-100
        
        return {
            'score': round(score, 1),
            'reasoning': 'AI scored (ambiguous headline)',
            'ai_scored': True
        }
        
    except Exception as e:
        print(f"[WARNING] AI scoring failed for headline: {e}")
        return {'score': 50, 'reasoning': f'AI error: {str(e)}', 'ai_scored': False}


def analyze_headline_detailed(headline: str, ticker: str = None) -> Dict:
    """
    Analyze a single headline with full transparency into scoring decisions.
    
    Returns:
        Dict with headline, matches, adjustments, final_score, and reasoning
    """
    headline_lower = headline.lower()
    words = headline_lower.split()
    
    # Track all matches
    positive_matches = []
    negative_matches = []
    negations_found = []
    intensifiers_found = []
    diminishers_found = []
    
    base_score = 0.0
    reasoning_steps = []
    
    # Step 1: Find keyword matches with context
    for i, word in enumerate(words):
        # Check for negations in previous 3 words
        has_negation = False
        if i > 0:
            context = words[max(0, i-3):i]
            for neg in NEGATION_WORDS:
                if neg in context:
                    has_negation = True
                    negations_found.append(neg)
                    break
        
        # Check for intensifiers/diminishers in previous 2 words
        modifier = 1.0
        modifier_word = None
        if i > 0:
            prev_words = words[max(0, i-2):i]
            for word_check in prev_words:
                if word_check in INTENSIFIERS:
                    modifier = INTENSIFIERS[word_check]
                    modifier_word = word_check
                    intensifiers_found.append(word_check)
                    break
                elif word_check in DIMINISHERS:
                    modifier = DIMINISHERS[word_check]
                    modifier_word = word_check
                    diminishers_found.append(word_check)
                    break
        
        # Check positive keywords (including phrases)
        for phrase, weight in POSITIVE_KEYWORDS.items():
            if phrase in headline_lower:
                adjusted_weight = weight * modifier
                if has_negation:
                    adjusted_weight *= -1  # Flip sentiment
                    reasoning_steps.append(
                        f"Found '{phrase}' (weight={weight:.1f}) with negation, flipped to {adjusted_weight:.1f}"
                    )
                else:
                    reasoning_steps.append(
                        f"Found '{phrase}' (base weight={weight:.1f}, modifier={modifier:.1f}, final={adjusted_weight:.1f})"
                    )
                positive_matches.append({
                    'keyword': phrase,
                    'base_weight': weight,
                    'modifier': modifier,
                    'modifier_word': modifier_word,
                    'negated': has_negation,
                    'final_weight': adjusted_weight
                })
                base_score += adjusted_weight
        
        # Check negative keywords (including phrases)
        for phrase, weight in NEGATIVE_KEYWORDS.items():
            if phrase in headline_lower:
                adjusted_weight = weight * modifier
                if has_negation:
                    adjusted_weight *= -1  # Flip sentiment (double negative = positive)
                    reasoning_steps.append(
                        f"Found '{phrase}' (weight={weight:.1f}) with negation, flipped to {adjusted_weight:.1f}"
                    )
                else:
                    reasoning_steps.append(
                        f"Found '{phrase}' (base weight={weight:.1f}, modifier={modifier:.1f}, final={adjusted_weight:.1f})"
                    )
                negative_matches.append({
                    'keyword': phrase,
                    'base_weight': weight,
                    'modifier': modifier,
                    'modifier_word': modifier_word,
                    'negated': has_negation,
                    'final_weight': adjusted_weight
                })
                base_score += adjusted_weight
    
    # Step 1.5: Check for context-dependent (ambiguous) keywords
    # These flag the headline for AI analysis rather than pattern matching
    ambiguous_keywords = get_ambiguous_keywords_found(headline)
    requires_ai = len(ambiguous_keywords) > 0
    
    # If no keyword matches AND ambiguous, definitely needs AI
    if len(positive_matches) == 0 and len(negative_matches) == 0 and requires_ai:
        reasoning_steps.append("No keyword matches found - using AI for scoring")
    
    if ambiguous_keywords:
        reasoning_steps.append(
            f"⚠️ Found {len(ambiguous_keywords)} ambiguous keyword(s) - using AI scoring"
        )
        for kw in ambiguous_keywords:
            reasoning_steps.append(f"  • '{kw['keyword']}': {kw['reason']}")
    
    # Step 2: Ticker/company mention check for relevance weighting
    ticker_mentioned = False
    relevance_weight = 0.0  # Default: zero relevance
    
    if ticker:
        ticker_lower = ticker.lower()
        
        # Map common tickers to company names for better detection
        company_name_map = {
            'aapl': 'apple',
            'msft': 'microsoft',
            'googl': 'google',
            'goog': 'google',
            'amzn': 'amazon',
            'nvda': 'nvidia',
            'tsla': 'tesla',
            'meta': 'meta',
            'nflx': 'netflix',
            'orcl': 'oracle',
            'crm': 'salesforce',
            'intc': 'intel',
            'amd': 'amd',
            'qcom': 'qualcomm',
            'adbe': 'adobe',
            'csco': 'cisco',
            'ibm': 'ibm',
            'pypl': 'paypal',
            'uber': 'uber',
            'shop': 'shopify',
            'sq': 'square',
            'zm': 'zoom',
            'docu': 'docusign',
            'crwd': 'crowdstrike',
            'snow': 'snowflake',
            'team': 'atlassian',
            'now': 'servicenow',
            'wday': 'workday',
            'panw': 'palo alto',
            'ftnt': 'fortinet',
            'ddog': 'datadog',
            'net': 'cloudflare',
            'mndy': 'monday.com'
        }
        
        company_name = company_name_map.get(ticker_lower, ticker_lower)
        
        # Check if ticker OR company name is mentioned in headline
        if ticker_lower in headline_lower or company_name in headline_lower:
            ticker_mentioned = True
            relevance_weight = 1.0  # High relevance - headline is about this stock
            reasoning_steps.append(f"✓ '{ticker}' or '{company_name}' mentioned → relevance: 100%")
        else:
            # Check for sector/market terms that could influence the stock
            sector_terms = [
                'tech', 'technology', 'semiconductor', 'chip', 'ai', 'artificial intelligence',
                'market', 'stocks', 'nasdaq', 'dow', 's&p', 'wall street', 'trading',
                'economy', 'fed', 'federal reserve', 'inflation', 'interest rate'
            ]
            
            has_market_context = any(term in headline_lower for term in sector_terms)
            
            if has_market_context:
                relevance_weight = 0.3  # Medium relevance - sector/market news
                reasoning_steps.append(f"⚠ '{ticker}' NOT mentioned but sector/market context found → relevance: 30%")
            else:
                # Ticker NOT mentioned and no sector/market context - completely irrelevant
                relevance_weight = 0.0  # Zero relevance
                reasoning_steps.append(f"✗ '{ticker}' NOT mentioned, no sector/market context → relevance: 0% (irrelevant)")
    else:
        relevance_weight = 1.0  # No ticker provided, assume all headlines relevant
    
    # Step 3: Decide scoring method
    ai_scored = False
    normalized_score = 50.0
    
    # Use AI if ambiguous OR no keyword matches
    if requires_ai or (len(positive_matches) == 0 and len(negative_matches) == 0):
        ai_result = score_headline_with_ai(headline, ticker)
        if ai_result['ai_scored']:
            normalized_score = ai_result['score']
            ai_scored = True
            reasoning_steps.append(f"AI scored: {normalized_score}/100")
        else:
            # AI failed, fall back to keyword score
            raw_score = base_score
            normalized_score = 50 + (raw_score * 2.5)  # Scale to 0-100
    else:
        # Use keyword score
        raw_score = base_score
        normalized_score = 50 + (raw_score * 2.5)  # Scale to 0-100
        reasoning_steps.append(f"Keyword scored: raw={raw_score:.2f}")
    
    # Step 4: Apply relevance weighting
    # Low relevance pulls score toward neutral if not relevant
    if relevance_weight < 1.0:
        # Interpolate between current score and 50 based on relevance
        original_score = normalized_score
        normalized_score = 50 + (normalized_score - 50) * relevance_weight
        reasoning_steps.append(f"Applied relevance weight {relevance_weight:.1f}: {original_score:.1f} → {normalized_score:.1f}")
    
    normalized_score = max(0, min(100, normalized_score))  # Clamp
    
    return {
        'headline': headline,
        'raw_score': round(base_score, 2),
        'normalized_score': round(normalized_score, 1),
        'ticker_mentioned': ticker_mentioned,
        'relevance_weight': relevance_weight,
        'positive_matches': positive_matches,
        'negative_matches': negative_matches,
        'ambiguous_keywords': ambiguous_keywords,
        'requires_ai_analysis': requires_ai,
        'ai_scored': ai_scored,  # NEW: Track if AI was used
        'negations': list(set(negations_found)),
        'intensifiers': list(set(intensifiers_found)),
        'diminishers': list(set(diminishers_found)),
        'reasoning': reasoning_steps,
        'classification': 'Bullish' if normalized_score >= 60 else 'Bearish' if normalized_score <= 40 else 'Neutral'
    }


def analyze_headlines_batch(headlines: List[str], ticker: str = None) -> Dict:
    """
    Analyze multiple headlines with aggregated scoring.
    
    Uses tiered approach:
    - Keywords for obvious sentiment
    - AI for ambiguous headlines
    - Relevance weighting for all
    
    Returns comprehensive breakdown for UI display.
    """
    if not headlines:
        return {
            'overall_score': 50.0,
            'confidence': 'Low',
            'headline_details': [],
            'summary': {
                'total_headlines': 0,
                'bullish_count': 0,
                'neutral_count': 0,
                'bearish_count': 0,
                'avg_score': 50.0,
                'score_std': 0.0
            }
        }
    
    headline_details = []
    scores = []
    ambiguous_count = 0
    ai_scored_count = 0
    
    for headline in headlines:
        if isinstance(headline, dict):
            headline_text = headline.get('title', '')
        else:
            headline_text = str(headline)
        
        if not headline_text:
            continue
            
        # First pass: keyword-based analysis
        detail = analyze_headline_detailed(headline_text, ticker)
        
        # Second pass: Use AI for ambiguous or neutral headlines
        if detail.get('requires_ai_analysis') or (detail['normalized_score'] == 50 and len(detail['positive_matches']) == 0 and len(detail['negative_matches']) == 0):
            # No keywords matched OR ambiguous keywords found → Use AI
            ai_result = score_headline_with_ai(headline_text, ticker)
            
            if ai_result['ai_scored']:
                # Update score with AI result
                detail['normalized_score'] = ai_result['score']
                detail['classification'] = 'Bullish' if ai_result['score'] >= 60 else 'Bearish' if ai_result['score'] <= 40 else 'Neutral'
                detail['ai_scored'] = True
                detail['reasoning'].insert(0, f"AI scored this headline: {ai_result['score']:.1f}/100 (keyword analysis was ambiguous)")
                ai_scored_count += 1
            else:
                detail['ai_scored'] = False
        else:
            detail['ai_scored'] = False
        
        headline_details.append(detail)
        scores.append(detail['normalized_score'])
        
        if detail.get('requires_ai_analysis'):
            ambiguous_count += 1
    
    # Calculate aggregate statistics with relevance weighting
    if scores:
        # Weighted average: headlines with higher relevance have more impact
        relevance_weights = [detail.get('relevance_weight', 1.0) for detail in headline_details]
        total_weight = sum(relevance_weights)
        
        if total_weight > 0:
            weighted_avg_score = sum(score * weight for score, weight in zip(scores, relevance_weights)) / total_weight
        else:
            weighted_avg_score = sum(scores) / len(scores)
        
        # Also calculate unweighted for comparison
        unweighted_avg = sum(scores) / len(scores)
        
        variance = sum((s - weighted_avg_score) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        bullish_count = sum(1 for s in scores if s >= 60)
        neutral_count = sum(1 for s in scores if 40 < s < 60)
        bearish_count = sum(1 for s in scores if s <= 40)
        
        # Count high-relevance headlines
        high_relevance_count = sum(1 for w in relevance_weights if w >= 0.9)
    else:
        weighted_avg_score = 50.0
        unweighted_avg = 50.0
        std_dev = 0.0
        bullish_count = neutral_count = bearish_count = 0
        high_relevance_count = 0
    
    # Confidence calculation
    article_count = len(scores)
    consistency = 100 - std_dev  # Lower std = higher consistency
    
    # Adjust confidence based on high-relevance headline count
    if article_count >= 10 and consistency >= 70 and high_relevance_count >= 5:
        confidence = 'High'
    elif article_count >= 5 and consistency >= 50 and high_relevance_count >= 2:
        confidence = 'Medium'
    else:
        confidence = 'Low'
    
    return {
        'overall_score': round(weighted_avg_score, 1),
        'confidence': confidence,
        'confidence_factors': {
            'article_count': article_count,
            'high_relevance_count': high_relevance_count,
            'ai_scored_count': ai_scored_count,
            'keyword_scored_count': article_count - ai_scored_count,
            'consistency_score': round(consistency, 1),
            'std_deviation': round(std_dev, 1),
            'weighted_avg': round(weighted_avg_score, 1),
            'unweighted_avg': round(unweighted_avg, 1),
            'ambiguous_headlines': ambiguous_count  # NEW: How many need AI
        },
        'requires_ai': ambiguous_count > 0,  # NEW: Recommend AI analysis
        'headline_details': headline_details,
        'summary': {
            'total_headlines': len(headlines),
            'analyzed_headlines': len(scores),
            'ai_scored_count': ai_scored_count,
            'keyword_scored_count': len(scores) - ai_scored_count,
            'bullish_count': bullish_count,
            'neutral_count': neutral_count,
            'bearish_count': bearish_count,
            'high_relevance_count': high_relevance_count,
            'avg_score': round(weighted_avg_score, 1),
            'score_std': round(std_dev, 1),
            'score_min': round(min(scores), 1) if scores else 50,
            'score_max': round(max(scores), 1) if scores else 50,
            'ambiguous_count': ambiguous_count  # NEW: For UI display
        }
    }


def calibrate_with_ai(headline_analysis: Dict, ai_score: float, ai_reasoning: str) -> Dict:
    """
    AI Feedback Loop: Compare keyword-based scoring with AI analysis
    to identify areas for keyword improvement.
    
    Args:
        headline_analysis: Result from analyze_headlines_batch
        ai_score: Score from AI analysis (0-100)
        ai_reasoning: AI's explanation
    
    Returns:
        Calibration report with discrepancies and suggestions
    """
    keyword_score = headline_analysis['overall_score']
    difference = abs(ai_score - keyword_score)
    
    # Identify misclassified headlines
    mismatches = []
    for detail in headline_analysis['headline_details']:
        keyword_classification = detail['classification']
        
        # Determine what AI likely classified it as based on overall AI score
        if ai_score >= 60:
            expected_classification = 'Bullish'
        elif ai_score <= 40:
            expected_classification = 'Bearish'
        else:
            expected_classification = 'Neutral'
        
        if keyword_classification != expected_classification:
            mismatches.append({
                'headline': detail['headline'],
                'keyword_score': detail['normalized_score'],
                'keyword_classification': keyword_classification,
                'expected_classification': expected_classification,
                'keywords_found': {
                    'positive': [m['keyword'] for m in detail['positive_matches']],
                    'negative': [m['keyword'] for m in detail['negative_matches']]
                }
            })
    
    # Generate suggestions
    suggestions = []
    if difference > 15:
        suggestions.append(f"Large discrepancy ({difference:.1f} points) - review keyword weights")
    if mismatches:
        suggestions.append(f"{len(mismatches)} headlines misclassified - analyze for missing keywords")
    
    accuracy = 100 - (difference / 100 * 100)
    
    return {
        'keyword_score': keyword_score,
        'ai_score': ai_score,
        'difference': round(difference, 1),
        'accuracy_percent': round(accuracy, 1),
        'agreement': 'High' if difference < 10 else 'Medium' if difference < 20 else 'Low',
        'mismatched_headlines': mismatches,
        'suggestions': suggestions,
        'ai_reasoning': ai_reasoning
    }
