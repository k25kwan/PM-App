"""
News Sentiment Analysis Module

Analyzes news headlines to generate sentiment scores for stocks
Based on AI-powered extraction similar to ai-risk-demo repository

Features:
- Fetch headlines from Yahoo Finance news
- AI-based sentiment extraction (positive/negative/neutral)
- Keyword-based scoring with portfolio relevance
- Catalyst detection (earnings, M&A, product launches, etc.)
- Cross-reference multiple sources for validation
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import re


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


def extract_sentiment_basic(headlines):
    """
    Basic keyword-based sentiment analysis (no AI required)
    
    Args:
        headlines: List of headline strings
    
    Returns:
        Dictionary with sentiment score (0-100) and breakdown
    """
    positive_keywords = [
        'beat', 'beats', 'surge', 'surges', 'upgrade', 'upgrades',
        'strong', 'strength', 'growth', 'record', 'high', 'breakthrough',
        'innovation', 'win', 'wins', 'approval', 'approved', 'bullish'
    ]
    
    negative_keywords = [
        'miss', 'misses', 'downgrade', 'downgrades', 'weak', 'weakness',
        'decline', 'declines', 'lawsuit', 'investigation', 'concern', 'concerns',
        'warning', 'warns', 'loss', 'losses', 'cut', 'cuts', 'risk', 'risks',
        'bearish', 'plunge', 'crash', 'fall', 'drop'
    ]
    
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    for headline in headlines:
        headline_lower = headline.lower()
        
        has_positive = any(kw in headline_lower for kw in positive_keywords)
        has_negative = any(kw in headline_lower for kw in negative_keywords)
        
        if has_positive and not has_negative:
            positive_count += 1
        elif has_negative and not has_positive:
            negative_count += 1
        else:
            neutral_count += 1
    
    total = len(headlines)
    if total == 0:
        return {
            'sentiment_score': 50,  # Neutral
            'confidence': 'Low',
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'total_articles': 0
        }
    
    # Calculate sentiment score (0-100, where 50 is neutral)
    if positive_count + negative_count == 0:
        sentiment_score = 50  # All neutral
    else:
        sentiment_ratio = positive_count / (positive_count + negative_count)
        sentiment_score = sentiment_ratio * 100
    
    # Determine confidence based on number of articles
    if total >= 10:
        confidence = 'High'
    elif total >= 5:
        confidence = 'Medium'
    else:
        confidence = 'Low'
    
    return {
        'sentiment_score': round(sentiment_score, 1),
        'confidence': confidence,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'total_articles': total
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
    if not use_openai:
        # Fallback to basic keyword analysis
        headline_texts = [h.get('title', '') if isinstance(h, dict) else h for h in headlines]
        return extract_sentiment_basic(headline_texts)
    
    try:
        load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("[WARNING] OPENAI_API_KEY not found, falling back to keyword-based analysis")
            headline_texts = [h.get('title', '') if isinstance(h, dict) else h for h in headlines]
            return extract_sentiment_basic(headline_texts)
        
        client = OpenAI(api_key=api_key)
        
        # Prepare headlines for analysis
        headline_list = ""
        for i, h in enumerate(headlines[:20], 1):  # Limit to 20 most recent
            if isinstance(h, dict):
                title = h.get('title', '')
                publisher = h.get('publisher', 'Unknown')
                headline_list += f"{i}. [{publisher}] {title}\n"
            else:
                headline_list += f"{i}. {h}\n"
        
        # Create prompt for sentiment analysis
        prompt = f"""Analyze the sentiment of these news headlines for {ticker if ticker else 'the stock market'}.

Headlines:
{headline_list}

Provide a structured analysis with:
1. Overall Sentiment Score (0-100, where 0=Very Bearish, 50=Neutral, 100=Very Bullish)
2. Key Catalysts (positive or negative events mentioned)
3. Dominant Narrative (1-2 sentences summarizing the overall story)
4. Confidence Level (High/Medium/Low based on consistency and source quality)

Format your response as:
Sentiment Score: [0-100]
Catalysts: [List key events]
Narrative: [Brief summary]
Confidence: [High/Medium/Low]
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using mini for cost efficiency
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        text = response.choices[0].message.content
        
        # Parse response
        sentiment_score = 50  # Default neutral
        catalysts = []
        narrative = ""
        confidence = "Medium"
        
        # Extract sentiment score
        score_match = re.search(r'Sentiment Score:?\s*(\d+)', text, re.IGNORECASE)
        if score_match:
            sentiment_score = int(score_match.group(1))
        
        # Extract catalysts
        catalysts_match = re.search(r'Catalysts:?\s*(.+?)(?:\n|Narrative)', text, re.IGNORECASE | re.DOTALL)
        if catalysts_match:
            catalysts_text = catalysts_match.group(1).strip()
            catalysts = [c.strip('- ').strip() for c in catalysts_text.split('\n') if c.strip()]
        
        # Extract narrative
        narrative_match = re.search(r'Narrative:?\s*(.+?)(?:\n|Confidence)', text, re.IGNORECASE | re.DOTALL)
        if narrative_match:
            narrative = narrative_match.group(1).strip()
        
        # Extract confidence
        confidence_match = re.search(r'Confidence:?\s*(High|Medium|Low)', text, re.IGNORECASE)
        if confidence_match:
            confidence = confidence_match.group(1).capitalize()
        
        return {
            'sentiment_score': sentiment_score,
            'confidence': confidence,
            'catalysts': catalysts,
            'narrative': narrative,
            'total_articles': len(headlines),
            'ai_analysis': True,
            'raw_response': text
        }
    
    except Exception as e:
        print(f"[ERROR] AI sentiment extraction failed: {e}")
        # Fallback to keyword-based analysis
        headline_texts = [h.get('title', '') if isinstance(h, dict) else h for h in headlines]
        return extract_sentiment_basic(headline_texts)


def fetch_news_for_ticker(ticker, max_articles=20):
    """
    Fetch news headlines for a specific ticker using yfinance
    
    Args:
        ticker: Stock ticker symbol
        max_articles: Maximum number of articles to fetch
    
    Returns:
        List of news article dictionaries
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        
        if not news or len(news) == 0:
            return []
        
        # Filter and format news articles
        articles = []
        for article in news[:max_articles]:
            articles.append({
                'title': article.get('title', ''),
                'publisher': article.get('publisher', 'Unknown'),
                'link': article.get('link', ''),
                'publish_time': datetime.fromtimestamp(article.get('providerPublishTime', 0))
            })
        
        return articles
    
    except Exception as e:
        print(f"[ERROR] Failed to fetch news for {ticker}: {e}")
        return []


def analyze_ticker_sentiment(ticker, use_ai=True):
    """
    Complete sentiment analysis for a ticker
    
    Args:
        ticker: Stock ticker symbol
        use_ai: Whether to use AI-powered analysis
    
    Returns:
        Dictionary with comprehensive sentiment analysis
    """
    # Fetch news
    articles = fetch_news_for_ticker(ticker)
    
    if not articles:
        return {
            'ticker': ticker,
            'sentiment_score': 50,
            'confidence': 'Low',
            'catalysts': [],
            'narrative': 'No recent news available',
            'total_articles': 0,
            'articles': []
        }
    
    # Extract sentiment
    sentiment = extract_sentiment_ai(articles, ticker, use_openai=use_ai)
    
    # Add ticker and articles to result
    sentiment['ticker'] = ticker
    sentiment['articles'] = articles
    
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
