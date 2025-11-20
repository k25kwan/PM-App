"""
News Sentiment Analysis Module - AI-First Approach with VADER/spaCy Validation

Analyzes news headlines using:
1. Dual-AI validation (primary method)
2. VADER rule-based sentiment (validation/backup)
3. spaCy NER for relevance filtering (enhancement)

Phase 1b enhancement: Multi-method comparison for confidence building.
"""

import os
import re
from dotenv import load_dotenv
from openai import OpenAI
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from sentiment_scorer import analyze_headlines_batch, calibrate_with_ai
from ai_sentiment_framework import build_ai_prompt

# Phase 1b: Import sentiment comparison module
try:
    from sentiment_comparison import SentimentComparator
    VADER_SPACY_AVAILABLE = True
except ImportError:
    VADER_SPACY_AVAILABLE = False
    print("[INFO] VADER/spaCy not available. Install with: pip install vaderSentiment spacy")
    print("[INFO] Then run: python -m spacy download en_core_web_sm")


def validate_narrative_with_ai(ticker: str, narrative: str, overall_score: float, 
                                relevant_headlines: list, client) -> dict:
    """
    AI-to-AI validation: Second AI reviews the sentiment narrative for logical consistency.
    
    Args:
        ticker: Stock ticker symbol
        narrative: The narrative summary from first AI
        overall_score: The score from first AI (0-100)
        relevant_headlines: List of headlines that were deemed relevant
        client: OpenAI client instance
    
    Returns:
        Dict with validation results:
        - makes_sense: bool
        - issues: list of concerns
        - alternative_score: float (if AI disagrees)
        - reasoning: str
    """
    try:
        # Build validation prompt
        headlines_summary = "\n".join([f"- {h}" for h in relevant_headlines[:10]])  # First 10 for context
        
        validation_prompt = f"""You are reviewing a sentiment analysis for ticker: {ticker}

FIRST AI's ANALYSIS:
Overall Score: {overall_score}/100 (0=very bearish, 50=neutral, 100=very bullish)
Narrative: {narrative}

HEADLINES ANALYZED:
{headlines_summary}
{f"...and {len(relevant_headlines) - 10} more" if len(relevant_headlines) > 10 else ""}

YOUR TASK:
Review this analysis for logical consistency given:
1. Your knowledge of {ticker} and recent market context
2. The headlines provided
3. Whether the score matches the narrative
4. Whether important signals were missed or over-weighted

Respond in this format:
MAKES_SENSE: [Yes/No/Partially]
SCORE_REASONABLE: [Yes/No - does the {overall_score} score match the narrative?]
ISSUES: [List any logical inconsistencies, missing context, or over/under reactions]
ALTERNATIVE_SCORE: [Your suggested score 0-100, if different]
REASONING: [2-3 sentences explaining your assessment]

Be critical but fair. Consider that the first AI only saw headlines, not full articles."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior financial analyst reviewing junior analyst work. Be thorough and identify logical flaws."},
                {"role": "user", "content": validation_prompt}
            ],
            temperature=0.5,  # Slightly higher for independent thinking
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        print(f"[DEBUG] AI Validation for {ticker}:\n{result_text}")
        
        # Parse validation response
        makes_sense = 'Yes'
        score_reasonable = 'Yes'
        issues = []
        alternative_score = None
        reasoning = ''
        
        for line in result_text.split('\n'):
            line = line.strip()
            if 'MAKES_SENSE:' in line:
                makes_sense = line.split(':', 1)[1].strip()
            elif 'SCORE_REASONABLE:' in line:
                score_reasonable = line.split(':', 1)[1].strip()
            elif 'ISSUES:' in line:
                issues_text = line.split(':', 1)[1].strip()
                if issues_text and issues_text.lower() != 'none':
                    issues.append(issues_text)
            elif 'ALTERNATIVE_SCORE:' in line:
                try:
                    alt_score_text = line.split(':', 1)[1].strip()
                    alternative_score = float(re.search(r'\d+', alt_score_text).group())
                except:
                    pass
            elif 'REASONING:' in line:
                reasoning = line.split(':', 1)[1].strip()
        
        return {
            'makes_sense': makes_sense,
            'score_reasonable': score_reasonable,
            'issues': issues,
            'alternative_score': alternative_score,
            'reasoning': reasoning,
            'validated': makes_sense.lower() == 'yes' and score_reasonable.lower() == 'yes'
        }
        
    except Exception as e:
        print(f"[WARNING] AI validation failed for {ticker}: {e}")
        return {
            'makes_sense': 'Unknown',
            'score_reasonable': 'Unknown',
            'issues': [],
            'alternative_score': None,
            'reasoning': f'Validation error: {str(e)}',
            'validated': None
        }


def ai_filter_and_score_headlines(headlines: list, ticker: str) -> dict:
    """
    Use AI to filter headlines for relevance and score sentiment.
    
    This is the new primary method - no keyword logic, just AI.
    
    Args:
        headlines: List of headline texts or dicts with 'title' key
        ticker: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        Dict with:
        - overall_score: 0-100 sentiment score
        - confidence: High/Medium/Low
        - relevant_headlines: List of headlines AI deemed relevant
        - headline_details: Detailed scoring for each relevant headline
        - filtered_count: How many headlines were filtered out
    """
    try:
        load_dotenv(override=True)
        api_key = os.environ.get("OPENAI_API_KEY", "").strip().strip('"').strip("'")
        
        if not api_key:
            print(f"[WARNING] No OpenAI API key found, falling back to keyword analysis")
            return analyze_headlines_batch(headlines, ticker)
        
        client = OpenAI(api_key=api_key)
        
        # Extract headline texts
        headline_texts = []
        for h in headlines:
            if isinstance(h, dict):
                headline_texts.append(h.get('title', ''))
            else:
                headline_texts.append(str(h))
        
        # Build AI prompt for filtering and scoring
        headlines_list = "\n".join([f"{i+1}. {h}" for i, h in enumerate(headline_texts)])
        
        prompt = f"""You are analyzing news headlines for ticker: {ticker}

CRITICAL CLASSIFICATION RULES:

RELEVANT - Include if headline mentions the company by ticker symbol ({ticker}) OR by the company name associated with this ticker.
Examples of relevant mentions:
- Ticker symbol: {ticker}
- Company name (e.g., "Apple" for AAPL, "Microsoft" for MSFT, "Nvidia" for NVDA)
- Common product/brand names strongly associated with the company

Include headlines that:
- Explicitly mention {ticker} or the associated company name
- Discuss the company's products, services, or leadership (CEO, executives)
- Report financial results (earnings, revenue, guidance)
- Announce company-specific events (product launches, acquisitions, lawsuits)
- Discuss analyst ratings/price targets specifically for {ticker}
- Report market share changes or competitive positioning for {ticker}
- Mention {ticker} or company name in portfolio moves by major investors

IRRELEVANT - Exclude if headline:
- Only mentions other companies without discussing {ticker}
- General market commentary without {ticker}-specific impact
- Industry trends that don't single out {ticker}
- Lists of multiple stocks where {ticker} is just one of many
- Competitor news without direct {ticker} comparison

SCORING GUIDELINES (0-100 scale):

BEARISH (0-40):
- Earnings misses, revenue declines, lowered guidance
- Negative regulatory actions, lawsuits, investigations
- Product failures, recalls, or cancellations
- Leadership departures or scandals
- Analyst downgrades, price target cuts
- Market share losses, competitive threats
- Major investor selling stakes

NEUTRAL (40-60):
- Mixed news (both positive and negative elements)
- Routine announcements without clear market impact
- Analyst maintains rating (no upgrade/downgrade)
- General mentions without specific positive/negative context
- Speculative articles without concrete developments

BULLISH (60-100):
- Earnings beats, revenue growth, raised guidance
- New product launches, innovation breakthroughs
- Market share gains, strong demand signals
- Analyst upgrades, increased price targets
- Strategic partnerships, acquisitions
- Major investor buying stakes
- Positive regulatory approvals

CONTEXT WEIGHTING:
- Price action mentions ("stock up/down") - weight the fundamental reason, not just the movement
- Multiple factors - consider net impact (e.g., "earnings beat but outlook weak" = neutral-to-slightly-positive)
- Magnitude matters - "surge", "plunge", "record" indicate stronger moves than "rise", "fall", "increase"
- Speculation vs. fact - confirmed news scores higher than rumors

Headlines to analyze:
{headlines_list}

Respond in this EXACT format:
RELEVANT_HEADLINES:
[number]: [score 0-100] - [specific reason for relevance and score]

OVERALL_SCORE: [weighted average, 0-100]
CONFIDENCE: [High if 5+ relevant headlines with clear signals | Medium if 2-4 headlines or mixed signals | Low if 0-1 headlines or unclear impact]
SUMMARY: [2-3 sentences explaining the dominant themes, key developments, and overall sentiment direction]

Example:
RELEVANT_HEADLINES:
4: 75 - Strong product demand indicates robust sales
12: 35 - Major investor reducing stake raises concerns about confidence
28: 80 - Revenue growth demonstrates strong market position
37: 45 - Leadership uncertainty creates questions about future direction

OVERALL_SCORE: 59
CONFIDENCE: High
SUMMARY: Mixed sentiment with strong product performance offset by investor confidence concerns. Stake reduction and succession uncertainty weigh on bullish sales data. Net neutral with slight bullish bias from operational strength."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial analyst specializing in sentiment analysis. Be precise and objective."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        result_text = response.choices[0].message.content
        print(f"[DEBUG] AI filtering response for {ticker}:\n{result_text[:500]}...")
        
        # Parse the response
        relevant_headlines = []
        headline_details = []
        
        lines = result_text.split('\n')
        in_relevant_section = False
        overall_score = 50
        confidence = 'Medium'
        summary = ''
        
        for line in lines:
            line = line.strip()
            
            if 'RELEVANT_HEADLINES:' in line:
                in_relevant_section = True
                continue
            elif 'OVERALL_SCORE:' in line:
                in_relevant_section = False
                try:
                    overall_score = float(re.search(r'\d+', line).group())
                except:
                    pass
            elif 'CONFIDENCE:' in line:
                confidence = line.split(':')[1].strip()
            elif 'SUMMARY:' in line:
                summary = line.split(':', 1)[1].strip()
            elif in_relevant_section and ':' in line and line[0].isdigit():
                # Parse: "1: 75 - Positive earnings beat"
                try:
                    parts = line.split(':', 1)
                    idx = int(parts[0]) - 1  # Convert to 0-indexed
                    rest = parts[1].strip()
                    
                    score_match = re.search(r'(\d+)', rest)
                    if score_match:
                        score = float(score_match.group())
                        reason = rest.split('-', 1)[1].strip() if '-' in rest else 'AI scored'
                        
                        if 0 <= idx < len(headline_texts):
                            relevant_headlines.append(headline_texts[idx])
                            headline_details.append({
                                'headline': headline_texts[idx],
                                'normalized_score': score,
                                'classification': 'Bullish' if score >= 60 else 'Bearish' if score <= 40 else 'Neutral',
                                'ai_scored': True,
                                'ticker_mentioned': True,  # AI filtered these as relevant
                                'relevance_weight': 1.0,
                                'reasoning': [reason]
                            })
                except Exception as e:
                    print(f"[DEBUG] Failed to parse line: {line}, error: {e}")
                    continue
        
        filtered_count = len(headline_texts) - len(relevant_headlines)
        
        print(f"[INFO] AI filtered {ticker}: {len(relevant_headlines)} relevant out of {len(headline_texts)} total")
        
        # AI-to-AI validation: Second AI reviews the narrative
        validation_result = validate_narrative_with_ai(
            ticker=ticker,
            narrative=summary,
            overall_score=overall_score,
            relevant_headlines=relevant_headlines,
            client=client
        )
        
        # Use validator score if available, otherwise use original score
        final_score = validation_result.get('alternative_score') or overall_score
        
        result = {
            'overall_score': round(final_score, 1),  # Use validator's score
            'confidence': confidence,
            'relevant_headlines': relevant_headlines,
            'headline_details': headline_details,
            'filtered_count': filtered_count,
            'total_headlines': len(headline_texts),
            'validation': validation_result,  # Keep for debugging/logging
            'narrative': summary,  # Add narrative for UI display
            'ai_analysis': True,  # Flag to show AI analysis section in UI
            'summary': {
                'total_headlines': len(headline_texts),
                'analyzed_headlines': len(relevant_headlines),
                'filtered_out': filtered_count,
                'bullish_count': sum(1 for d in headline_details if d['normalized_score'] >= 60),
                'neutral_count': sum(1 for d in headline_details if 40 < d['normalized_score'] < 60),
                'bearish_count': sum(1 for d in headline_details if d['normalized_score'] <= 40),
                'avg_score': round(final_score, 1),
                'ai_scored_count': len(headline_details),
                'keyword_scored_count': 0,
                'high_relevance_count': len(relevant_headlines)
            },
            'requires_ai': False  # Already used AI
        }
        
        print(f"[DEBUG] Using validator score {final_score} (original: {overall_score}) for {ticker}")
        
        return result
        
    except Exception as e:
        print(f"[ERROR] AI filtering failed for {ticker}: {e}")
        # Fall back to keyword-based approach
        return analyze_headlines_batch(headlines, ticker)


def score_headline_relevance(headline, ticker=None):
    """
    Score headline for portfolio relevance using keyword matching
    
    Args:
        headline: News headline text
        ticker: Optional ticker symbol to boost score if mentioned
    
    Returns:
        Relevance score (0-10)
    """
    score = 0
    headline_lower = headline.lower()
    
    # Market-moving keywords
    market_keywords = [
        'earnings', 'revenue', 'profit', 'guidance', 'outlook', 'forecast',
        'upgrade', 'downgrade', 'acquisition', 'merger', 'buyback',
        'lawsuit', 'investigation', 'approval', 'fda', 'launch',
        'beat', 'miss', 'surge', 'plunge', 'record', 'breakthrough'
    ]
    
    # Sentiment keywords
    positive_keywords = [
        'beat', 'beats', 'surge', 'surges', 'upgrade', 'upgrades',
        'strong', 'strength', 'growth', 'record', 'high', 'breakthrough',
        'innovation', 'win', 'wins', 'approval', 'approved', 'bullish'
    ]
    
    negative_keywords = [
        'miss', 'misses', 'downgrade', 'downgrades', 'weak', 'weakness',
        'decline', 'declines', 'lawsuit', 'investigation', 'concern', 'concerns',
        'warning', 'warns', 'loss', 'losses', 'cut', 'cuts', 'risk', 'risks',
        'bearish', 'plunge', 'crash'
    ]
    
    # Score market-moving keywords
    for keyword in market_keywords:
        if keyword in headline_lower:
            score += 2
    
    # Boost if ticker mentioned
    if ticker and ticker.lower() in headline_lower:
        score += 5
    
    return min(score, 10)  # Cap at 10


def extract_sentiment_basic(headlines, ticker=None):
    """
    Enhanced keyword-based sentiment analysis with detailed scoring
    
    Args:
        headlines: List of headline strings or dicts
        ticker: Optional ticker symbol for context
    
    Returns:
        Dictionary with sentiment score (0-100) and detailed breakdown
    """
    # Debug logging
    print(f"[DEBUG] extract_sentiment_basic called with {len(headlines) if headlines else 0} headlines for {ticker}")
    
    # Use the new detailed analyzer
    result = analyze_headlines_batch(headlines, ticker)
    
    # Debug: Check what keys are returned
    print(f"[DEBUG] analyze_headlines_batch returned keys: {result.keys() if result else 'None'}")
    
    # Convert to expected format for backwards compatibility
    return {
        'sentiment_score': result['overall_score'],
        'confidence': result['confidence'],
        'confidence_factors': result['confidence_factors'],
        'positive_count': result['summary']['bullish_count'],
        'negative_count': result['summary']['bearish_count'],
        'neutral_count': result['summary']['neutral_count'],
        'total_articles': result['summary']['total_headlines'],
        'headline_details': result['headline_details'],  # NEW: Full breakdown
        'summary': result['summary']  # NEW: Statistics
    }


def extract_sentiment_ai(headlines, ticker=None, use_openai=True):
    """
    AI-powered sentiment analysis using OpenAI
    
    Args:
        headlines: List of headline dictionaries with 'title' and 'publisher'
        ticker: Stock ticker symbol
        use_openai: Whether to use OpenAI (requires API key)
    
    Returns:
        Dictionary with sentiment analysis results
    """
    # Extract headline texts for keyword analysis
    headline_texts = [h.get('title', '') if isinstance(h, dict) else str(h) for h in headlines]
    
    if not use_openai:
        # Fallback to basic keyword analysis
        return extract_sentiment_basic(headline_texts)
    
    try:
        load_dotenv(override=True)  # Force reload to get latest key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print(f"[INFO] No OpenAI API key found for {ticker}, using keyword-based analysis")
            return extract_sentiment_basic(headline_texts)
        
        # Debug: Check if key is being read correctly
        if len(api_key) < 100:
            print(f"[WARNING] OpenAI API key appears truncated (length: {len(api_key)}), using keyword-based analysis")
            return extract_sentiment_basic(headline_texts)
        
        client = OpenAI(api_key=api_key)
        
        # Prepare headlines for analysis
        headline_texts = []
        for h in headlines[:20]:  # Limit to 20 most recent
            if isinstance(h, dict):
                title = h.get('title', '')
                headline_texts.append(title)
            else:
                headline_texts.append(h)
        
        # Debug: Print what we're sending to AI
        print(f"[DEBUG] Sending {len(headline_texts)} headlines to AI for {ticker}")
        print(f"[DEBUG] First headline sample: {headline_texts[0] if headline_texts else 'None'}")
        
        # Use the comprehensive AI framework
        prompt = build_ai_prompt(headline_texts, ticker)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using mini for cost efficiency
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        text = response.choices[0].message.content
        
        # Debug: Print AI response
        print(f"[DEBUG] AI response for {ticker}:")
        print(f"[DEBUG] {text[:500]}...")  # First 500 chars
        
        # Parse response using new framework format
        sentiment_score = 50  # Default neutral
        catalysts = []
        narrative = ""
        confidence = "Medium"
        magnitude = "Unknown"
        
        # Extract overall sentiment score
        score_match = re.search(r'(?:Overall\s+)?Sentiment Score:?\s*(\d+)', text, re.IGNORECASE)
        if score_match:
            sentiment_score = int(score_match.group(1))
            print(f"[DEBUG] Extracted sentiment score: {sentiment_score}")
        else:
            print(f"[WARNING] Could not extract sentiment score from AI response for {ticker}")
        
        # Extract confidence
        confidence_match = re.search(r'Confidence:?\s*(High|Medium|Low)', text, re.IGNORECASE)
        if confidence_match:
            confidence = confidence_match.group(1).capitalize()
        
        # Extract key catalysts
        catalysts_match = re.search(r'Key Catalysts:?\s*(.+?)(?:\n(?:Dominant|Magnitude)|$)', text, re.IGNORECASE | re.DOTALL)
        if catalysts_match:
            catalysts_text = catalysts_match.group(1).strip()
            # Parse numbered or bulleted list
            catalysts = [c.strip('- ').strip() for c in re.split(r'\n\d+\.|\n-', catalysts_text) if c.strip()]
        
        # Extract dominant narrative
        narrative_match = re.search(r'Dominant Narrative:?\s*(.+?)(?:\n(?:Confidence|Magnitude)|$)', text, re.IGNORECASE | re.DOTALL)
        if narrative_match:
            narrative = narrative_match.group(1).strip()
        
        # Extract magnitude assessment
        magnitude_match = re.search(r'Magnitude Assessment:?\s*(Minor|Moderate|Major|Extreme)', text, re.IGNORECASE)
        if magnitude_match:
            magnitude = magnitude_match.group(1).capitalize()
        
        # AI Feedback Loop: Compare with keyword-based analysis (optional, don't fail if it errors)
        keyword_analysis = None
        calibration = None
        try:
            # Get raw result from batch analyzer for calibration
            raw_keyword_result = analyze_headlines_batch(headline_texts, ticker)
            calibration = calibrate_with_ai(
                headline_analysis=raw_keyword_result,
                ai_score=sentiment_score,
                ai_reasoning=narrative
            )
            # Also store formatted version for UI
            keyword_analysis = extract_sentiment_basic(headline_texts, ticker)
        except Exception as calib_error:
            print(f"[WARNING] Calibration failed for {ticker}: {calib_error}")
            # Continue without calibration
        
        return {
            'sentiment_score': sentiment_score,
            'confidence': confidence,
            'catalysts': catalysts,
            'narrative': narrative,
            'magnitude': magnitude,  # NEW: Magnitude assessment from AI
            'total_articles': len(headlines),
            'ai_analysis': True,
            'raw_response': text,
            'keyword_analysis': keyword_analysis,  # Full keyword breakdown (may be None)
            'calibration': calibration  # AI vs Keyword comparison (may be None)
        }
    
    except Exception as e:
        error_msg = str(e)
        # Show detailed error for debugging
        print(f"[DEBUG] OpenAI API Error for {ticker}: {type(e).__name__} - {error_msg}")
        if "401" in error_msg or "invalid_api_key" in error_msg:
            print(f"[INFO] OpenAI API key authentication failed for {ticker}, using keyword-based analysis")
        else:
            print(f"[ERROR] AI sentiment extraction failed: {e}")
        
        # Fallback to keyword-based analysis
        try:
            print(f"[DEBUG] Falling back to keyword analysis for {ticker}")
            return extract_sentiment_basic(headline_texts, ticker)
        except Exception as fallback_error:
            print(f"[ERROR] Keyword fallback also failed: {fallback_error}")
            # Return neutral score if everything fails
            return {
                'sentiment_score': 50,
                'confidence': 'Low',
                'total_articles': len(headlines),
                'ai_analysis': False,
                'error': str(fallback_error)
            }


def fetch_news_for_ticker(ticker, max_articles=100, days_back=7):
    """
    Fetch news headlines for a specific ticker using yfinance
    
    Args:
        ticker: Stock ticker symbol
        max_articles: Maximum number of articles to fetch (default 100 for better coverage)
        days_back: How many days back to include news (default 7 for weekly view)
    
    Returns:
        List of news article dictionaries within the timeframe
    """
    try:
        stock = yf.Ticker(ticker)
        # Use get_news() method with count parameter for more articles
        # This already filters news FOR this specific ticker, so no additional filtering needed
        news = stock.get_news(count=max_articles)
        
        if not news or len(news) == 0:
            return []
        
        # Calculate cutoff date for timeframe filtering
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        print(f"[DEBUG] Fetching news for {ticker}, cutoff date: {cutoff_date}, total raw articles: {len(news)}")
        
        # Filter and format news articles (only by date, not by relevance since get_news already filtered by ticker)
        articles = []
        for article in news:
            # yfinance changed structure - data is now nested in 'content'
            content = article.get('content', {})
            
            # Extract title from nested structure
            title = content.get('title', article.get('title', ''))
            
            # Extract publisher
            provider = content.get('provider', {})
            publisher = provider.get('displayName', article.get('publisher', 'Unknown'))
            
            # Extract link
            canonical_url = content.get('canonicalUrl', {})
            link = canonical_url.get('url', article.get('link', ''))
            
            # Handle publish time - check both new and old structure
            publish_time_raw = content.get('pubDate') or article.get('providerPublishTime')
            if publish_time_raw:
                try:
                    # If it's a string (ISO format), parse it
                    if isinstance(publish_time_raw, str):
                        from dateutil import parser
                        publish_time = parser.parse(publish_time_raw)
                        # Remove timezone info to make it naive
                        if publish_time.tzinfo is not None:
                            publish_time = publish_time.replace(tzinfo=None)
                    # If it's a timestamp number
                    elif isinstance(publish_time_raw, (int, float)):
                        # If timestamp is very large, it's likely in milliseconds
                        if publish_time_raw > 10000000000:
                            publish_time = datetime.fromtimestamp(publish_time_raw / 1000)
                        else:
                            publish_time = datetime.fromtimestamp(publish_time_raw)
                    else:
                        publish_time = datetime.now()
                except:
                    publish_time = datetime.now()
            else:
                publish_time = datetime.now()
            
            # Only filter by timeframe (get_news already filtered by ticker relevance)
            if publish_time >= cutoff_date:
                articles.append({
                    'title': title,
                    'publisher': publisher,
                    'link': link,
                    'publish_time': publish_time
                })
                print(f"[DEBUG] Article {len(articles)}: {title[:80]}... | {publish_time.strftime('%Y-%m-%d %H:%M')}")
            
            # Stop if we have enough articles
            if len(articles) >= max_articles:
                break
        
        print(f"[INFO] Found {len(articles)} articles for {ticker} within {days_back} day(s)")
        return articles
    
    except Exception as e:
        print(f"[ERROR] Failed to fetch news for {ticker}: {e}")
        return []


def analyze_ticker_sentiment(ticker, use_ai=True, days_back=7, include_vader_comparison=True):
    """
    Complete sentiment analysis for a ticker using AI-first approach with optional VADER/spaCy validation
    
    Args:
        ticker: Stock ticker symbol
        use_ai: Whether to use AI-powered analysis (default True)
        days_back: How many days of news to analyze
        include_vader_comparison: Whether to include VADER/spaCy comparison (Phase 1b)
    
    Returns:
        Dictionary with comprehensive sentiment analysis including multi-method comparison
    """
    # Fetch news
    articles = fetch_news_for_ticker(ticker, days_back=days_back)
    
    if not articles:
        return {
            'ticker': ticker,
            'sentiment_score': 50,
            'overall_score': 50,
            'confidence': 'Low',
            'catalysts': [],
            'narrative': 'No recent news available',
            'total_articles': 0,
            'articles': [],
            'summary': {
                'total_headlines': 0,
                'analyzed_headlines': 0,
                'filtered_out': 0,
                'bullish_count': 0,
                'neutral_count': 0,
                'bearish_count': 0,
                'avg_score': 50,
                'ai_scored_count': 0,
                'keyword_scored_count': 0,
                'high_relevance_count': 0
            },
            'headline_details': [],
            'vader_comparison': None  # Phase 1b
        }
    
    # Use AI-first approach if enabled
    if use_ai:
        result = ai_filter_and_score_headlines(articles, ticker)
        result['ticker'] = ticker
        result['articles'] = articles
        result['sentiment_score'] = result.get('overall_score', 50)  # Alias for compatibility
        result['total_articles'] = result.get('total_headlines', 0)  # Alias for compatibility
        result['catalysts'] = []  # Can be extracted from headline_details if needed
        
        # Create a full details map for UI display
        # Mark all non-relevant articles as filtered/irrelevant
        relevant_titles = {d['headline'] for d in result.get('headline_details', [])}
        full_headline_details = list(result.get('headline_details', []))
        
        for article in articles:
            title = article.get('title', '')
            if title not in relevant_titles:
                # Add filtered articles with 0 score
                full_headline_details.append({
                    'headline': title,
                    'normalized_score': 50,  # Neutral score
                    'classification': 'Filtered',
                    'ai_scored': True,
                    'ticker_mentioned': False,
                    'relevance_weight': 0.0,
                    'reasoning': ['Not directly relevant to ticker']
                })
        
        result['headline_details'] = full_headline_details
        
        # Phase 1b: Add VADER/spaCy comparison if available
        if include_vader_comparison and VADER_SPACY_AVAILABLE:
            try:
                comparator = SentimentComparator()
                all_headlines = [a.get('title', '') for a in articles if a.get('title')]
                
                # Get company name from yfinance
                try:
                    ticker_info = yf.Ticker(ticker)
                    company_name = ticker_info.info.get('longName', ticker)
                except:
                    company_name = ticker
                
                comparison = comparator.compare_all_methods(
                    headlines=all_headlines,
                    ticker=ticker,
                    ai_score=result.get('overall_score'),
                    keyword_score=None,  # We don't have keyword-based score in this flow
                    company_name=company_name
                )
                
                result['vader_comparison'] = comparison
            except Exception as e:
                print(f"[WARNING] VADER/spaCy comparison failed: {e}")
                result['vader_comparison'] = None
        else:
            result['vader_comparison'] = None
        
        return result
    else:
        # Fallback to keyword-based approach
        sentiment = extract_sentiment_ai(articles, ticker, use_openai=False)
        sentiment['ticker'] = ticker
        sentiment['articles'] = articles
        sentiment['vader_comparison'] = None  # Not available in fallback mode
        return sentiment


def batch_analyze_tickers(tickers, use_ai=True, max_concurrent=5):
    """
    Analyze sentiment for multiple tickers
    
    Args:
        tickers: List of ticker symbols
        use_ai: Whether to use AI-powered analysis
        max_concurrent: Maximum concurrent API calls
    
    Returns:
        DataFrame with sentiment scores for all tickers
    """
    results = []
    
    for i, ticker in enumerate(tickers):
        print(f"Analyzing {ticker} ({i+1}/{len(tickers)})...")
        sentiment = analyze_ticker_sentiment(ticker, use_ai=use_ai)
        results.append({
            'ticker': ticker,
            'sentiment_score': sentiment['sentiment_score'],
            'confidence': sentiment['confidence'],
            'total_articles': sentiment['total_articles'],
            'catalysts': ', '.join(sentiment.get('catalysts', [])),
            'narrative': sentiment.get('narrative', '')
        })
    
    return pd.DataFrame(results)


if __name__ == "__main__":
    # Test with a few tickers
    test_tickers = ['AAPL', 'MSFT', 'NVDA']
    
    print("Testing News Sentiment Analysis")
    print("=" * 80)
    
    for ticker in test_tickers:
        print(f"\n{ticker}:")
        sentiment = analyze_ticker_sentiment(ticker, use_ai=False)
        print(f"  Sentiment Score: {sentiment['sentiment_score']}/100")
        print(f"  Confidence: {sentiment['confidence']}")
        print(f"  Articles: {sentiment['total_articles']}")
        if sentiment.get('narrative'):
            print(f"  Narrative: {sentiment['narrative']}")
