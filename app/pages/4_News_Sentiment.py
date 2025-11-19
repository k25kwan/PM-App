"""
News Sentiment Analysis Page

Analyze market sentiment from news headlines for stocks
Uses AI-powered sentiment extraction to identify catalysts and trends
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "investment framework" / "news sentiment"))
sys.path.insert(0, str(project_root / "src" / "investment framework" / "fundamental analysis"))

from sentiment_calculation import (
    analyze_ticker_sentiment,
    batch_analyze_tickers,
    fetch_news_for_ticker
)
from sector_benchmarks import SectorBenchmarks

st.set_page_config(page_title="News Sentiment", layout="wide")

st.title("News Sentiment Analysis")
st.markdown("Analyze market sentiment from recent news headlines to identify catalysts and trends")

# Check for OpenAI API key
import os
from dotenv import load_dotenv
load_dotenv()
has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))

if not has_openai_key:
    st.warning("OpenAI API key not found. Using keyword-based sentiment analysis. "
               "For AI-powered analysis, add OPENAI_API_KEY to your .env file.")

# Sidebar configuration
st.sidebar.header("Configuration")

# Analysis mode
use_ai = st.sidebar.checkbox(
    "Use AI Analysis",
    value=has_openai_key,
    disabled=not has_openai_key,
    help="AI analysis provides more nuanced sentiment and catalyst detection"
)

# News timeframe
news_days = st.sidebar.selectbox(
    "News Timeframe",
    options=[3, 7, 14, 30],
    index=1,  # Default to 7 days
    help="How many days back to analyze news (longer = more context, less noise)"
)

st.sidebar.markdown(f"**Analyzing news from last {news_days} days**")
if news_days == 3:
    st.sidebar.info("Short-term: Recent catalysts and immediate events")
elif news_days == 7:
    st.sidebar.info("Weekly: Good balance of trend and recency")
elif news_days == 14:
    st.sidebar.info("Bi-weekly: Clearer trends, less daily noise")
else:
    st.sidebar.info("Monthly: Long-term narrative and major developments")

# Initialize benchmarks for ticker universe
if 'benchmarks' not in st.session_state or 'sp500_tickers' not in st.session_state:
    try:
        benchmarks = SectorBenchmarks()
        if benchmarks.load_from_cache():
            st.session_state.benchmarks = benchmarks
            fresh_tickers = benchmarks.get_sp1500_tickers()
            st.session_state.sp500_tickers = fresh_tickers
        else:
            st.session_state.sp500_tickers = []
    except Exception as e:
        st.session_state.sp500_tickers = []

# Tabs for different analysis modes
tab1, tab2, tab3 = st.tabs(["Single Stock", "Batch Analysis", "Market Overview"])

# Tab 1: Single Stock Analysis
with tab1:
    st.subheader("Analyze Individual Stock Sentiment")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        ticker_input = st.text_input(
            "Enter Ticker Symbol",
            value="AAPL",
            help="Enter a stock ticker (e.g., AAPL, MSFT, NVDA)"
        ).upper()
    
    with col2:
        analyze_btn = st.button("Analyze", type="primary", width="stretch")
    
    if analyze_btn and ticker_input:
        with st.spinner(f"Analyzing sentiment for {ticker_input}..."):
            sentiment = analyze_ticker_sentiment(ticker_input, use_ai=use_ai, days_back=news_days)
            
            if sentiment['total_articles'] == 0:
                st.warning(f"No recent news found for {ticker_input}")
            else:
                # Display sentiment score with color coding
                score = sentiment['sentiment_score']
                if score >= 70:
                    color = "green"
                    label = "Bullish"
                elif score >= 55:
                    color = "lightgreen"
                    label = "Slightly Bullish"
                elif score >= 45:
                    color = "gray"
                    label = "Neutral"
                elif score >= 30:
                    color = "orange"
                    label = "Slightly Bearish"
                else:
                    color = "red"
                    label = "Bearish"
                
                # Metrics row
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Sentiment Score", f"{score}/100", label)
                with col2:
                    st.metric("Confidence", sentiment['confidence'])
                with col3:
                    # Show magnitude if available from new framework
                    magnitude = sentiment.get('magnitude', 'N/A')
                    st.metric("Magnitude", magnitude)
                with col4:
                    st.metric("Articles Analyzed", sentiment['total_articles'])
                
                # Sentiment gauge chart
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Sentiment Score"},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': color},
                        'steps': [
                            {'range': [0, 30], 'color': "lightcoral"},
                            {'range': [30, 45], 'color': "lightyellow"},
                            {'range': [45, 55], 'color': "lightgray"},
                            {'range': [55, 70], 'color': "lightgreen"},
                            {'range': [70, 100], 'color': "darkgreen"}
                        ],
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': 50
                        }
                    }
                ))
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
                
                # AI Analysis Section
                if sentiment.get('ai_analysis'):
                    st.subheader("AI Analysis")
                    
                    # Market Narrative
                    if sentiment.get('narrative'):
                        st.info(f"**Market Narrative:** {sentiment['narrative']}")
                
                # Display recent headlines with detailed scoring
                # Get headline details from either direct field or keyword_analysis
                headline_details = sentiment.get('headline_details', [])
                if not headline_details and sentiment.get('keyword_analysis'):
                    headline_details = sentiment['keyword_analysis'].get('headline_details', [])
                
                # Filter to only show relevant headlines (exclude filtered/irrelevant ones)
                relevant_details = [d for d in headline_details if d.get('classification') != 'Filtered']
                
                st.subheader(f"Relevant Headlines ({len(relevant_details)} of {sentiment.get('total_articles', 0)} total)")
                articles = sentiment.get('articles', [])
                
                # Create a mapping of headlines to their details
                details_map = {}
                for detail in relevant_details:
                    details_map[detail['headline']] = detail
                
                if articles and relevant_details:
                    display_count = 0
                    for article in articles:
                        title = article['title']
                        detail = details_map.get(title)
                        
                        # Skip if not in relevant details
                        if not detail:
                            continue
                        
                        display_count += 1
                        score = detail.get('normalized_score', 50)
                        classification = detail.get('classification', 'Neutral')
                        relevance = detail.get('relevance_weight', 1.0)
                        ticker_mentioned = detail.get('ticker_mentioned', False)
                        ai_scored = detail.get('ai_scored', False)
                        
                        # Color code the expander title based on sentiment
                        score_indicator = "[BULL]" if score >= 60 else "[BEAR]" if score <= 40 else "[NEUT]"
                        
                        ai_indicator = "[AI]" if ai_scored else "[KW]"
                        
                        with st.expander(f"{display_count}. {score_indicator} {ai_indicator} [{score:.0f}] {title}"):
                            col1, col2 = st.columns([1, 2])
                            
                            with col1:
                                st.markdown(f"**Score:** {score:.1f}/100")
                                st.markdown(f"**Classification:** {classification}")
                                st.markdown(f"**Scoring Method:** {'AI (GPT-4o-mini)' if ai_scored else 'Keywords'}")
                                st.markdown(f"**Relevance:** ✓ Directly relevant to {ticker_input}")
                                
                                st.markdown(f"**Publisher:** {article['publisher']}")
                                st.markdown(f"**Published:** {article['publish_time'].strftime('%Y-%m-%d %H:%M')}")
                                if article.get('link'):
                                    st.markdown(f"[Read Article]({article['link']})")
                            
                            with col2:
                                if detail:
                                    st.markdown("**Scoring Breakdown:**")
                                    
                                    # Positive matches
                                    if detail.get('positive_matches'):
                                        st.markdown("*Positive Keywords:*")
                                        for match in detail['positive_matches']:
                                            negated = " (NEGATED)" if match.get('negated') else ""
                                            modifier_info = f" × {match['modifier']:.1f}" if match.get('modifier', 1.0) != 1.0 else ""
                                            st.markdown(f"- **{match['keyword']}**: {match['base_weight']:.1f}{modifier_info} = {match['final_weight']:.1f}{negated}")
                                    
                                    # Negative matches
                                    if detail.get('negative_matches'):
                                        st.markdown("*Negative Keywords:*")
                                        for match in detail['negative_matches']:
                                            negated = " (NEGATED)" if match.get('negated') else ""
                                            modifier_info = f" × {match['modifier']:.1f}" if match.get('modifier', 1.0) != 1.0 else ""
                                            st.markdown(f"- **{match['keyword']}**: {match['base_weight']:.1f}{modifier_info} = {match['final_weight']:.1f}{negated}")
                                    
                                    # Ambiguous keywords
                                    if detail.get('ambiguous_keywords'):
                                        st.markdown("*Ambiguous Keywords (AI analysis recommended):*")
                                        for kw in detail['ambiguous_keywords']:
                                            st.markdown(f"- **{kw['keyword']}**: {kw['reason']}")
                                    
                                    # Modifiers
                                    if detail.get('intensifiers') or detail.get('diminishers') or detail.get('negations'):
                                        st.markdown("*Modifiers Found:*")
                                        if detail.get('intensifiers'):
                                            st.markdown(f"- Intensifiers: {', '.join(detail['intensifiers'])}")
                                        if detail.get('diminishers'):
                                            st.markdown(f"- Diminishers: {', '.join(detail['diminishers'])}")
                                        if detail.get('negations'):
                                            st.markdown(f"- Negations: {', '.join(detail['negations'])}")
                                    
                                    st.markdown(f"**Raw Score:** {detail.get('raw_score', 0):.2f} → Normalized: {score:.1f}/100")
                                else:
                                    st.markdown("*No scoring details available for this headline*")

# Tab 2: Batch Analysis
with tab2:
    st.subheader("Batch Sentiment Analysis")
    st.markdown("Analyze sentiment for multiple stocks at once")
    
    # Ticker selection
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Default to some popular tickers
        default_tickers = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA"
        
        ticker_list_input = st.text_area(
            "Enter Tickers (comma-separated)",
            value=default_tickers,
            height=100,
            help="Enter multiple tickers separated by commas"
        )
    
    with col2:
        st.markdown("") # Spacing
        st.markdown("") # Spacing
        batch_analyze_btn = st.button("Analyze All", type="primary", use_container_width=True)
    
    if batch_analyze_btn:
        # Parse tickers
        tickers = [t.strip().upper() for t in ticker_list_input.split(',') if t.strip()]
        
        if not tickers:
            st.warning("Please enter at least one ticker symbol")
        else:
            st.info(f"Analyzing {len(tickers)} stocks...")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            for i, ticker in enumerate(tickers):
                status_text.text(f"Analyzing {ticker} ({i+1}/{len(tickers)})...")
                sentiment = analyze_ticker_sentiment(ticker, use_ai=use_ai, days_back=news_days)
                results.append({
                    'Ticker': ticker,
                    'Sentiment Score': sentiment['sentiment_score'],
                    'Signal': 'Bullish' if sentiment['sentiment_score'] >= 65 else 
                             'Neutral' if sentiment['sentiment_score'] >= 45 else 
                             'Bearish',
                    'Confidence': sentiment['confidence'],
                    'Articles': sentiment['total_articles'],
                    'Narrative': sentiment.get('narrative', 'N/A')[:100] + '...' if sentiment.get('narrative') else 'N/A'
                })
                progress_bar.progress((i + 1) / len(tickers))
                time.sleep(0.5)  # Rate limiting
            
            progress_bar.empty()
            status_text.empty()
            
            # Display results
            df_results = pd.DataFrame(results)
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                bullish_count = len(df_results[df_results['Sentiment Score'] >= 65])
                st.metric("Bullish Stocks", bullish_count)
            with col2:
                neutral_count = len(df_results[(df_results['Sentiment Score'] >= 45) & 
                                              (df_results['Sentiment Score'] < 65)])
                st.metric("Neutral Stocks", neutral_count)
            with col3:
                bearish_count = len(df_results[df_results['Sentiment Score'] < 45])
                st.metric("Bearish Stocks", bearish_count)
            with col4:
                avg_score = df_results['Sentiment Score'].mean()
                st.metric("Average Sentiment", f"{avg_score:.1f}")
            
            # Results table
            st.subheader("Sentiment Scores")
            
            # Color code the sentiment scores with red-white-green gradient
            def color_sentiment(val):
                if isinstance(val, (int, float)):
                    # Green gradient for bullish (65-100)
                    if val >= 80:
                        return 'background-color: #006400; color: white'  # Dark green
                    elif val >= 70:
                        return 'background-color: #228B22; color: white'  # Forest green
                    elif val >= 60:
                        return 'background-color: #32CD32; color: black'  # Lime green
                    elif val >= 55:
                        return 'background-color: #90EE90; color: black'  # Light green
                    # White/neutral for middle range (45-55)
                    elif val >= 45:
                        return 'background-color: #FFFFFF; color: black'  # White
                    # Red gradient for bearish (0-45)
                    elif val >= 40:
                        return 'background-color: #FFB6C1; color: black'  # Light red
                    elif val >= 30:
                        return 'background-color: #FF6B6B; color: black'  # Medium red
                    elif val >= 20:
                        return 'background-color: #DC143C; color: white'  # Crimson
                    else:
                        return 'background-color: #8B0000; color: white'  # Dark red
                return ''
            
            styled_df = df_results.style.map(color_sentiment, subset=['Sentiment Score'])
            st.dataframe(styled_df, width="stretch", height=400)

# Tab 3: Market Overview
with tab3:
    st.subheader("Market Sentiment Overview")
    st.markdown("Coming soon: Market-wide sentiment analysis and sector trends")
    
    st.info("""
    **Planned Features:**
    - S&P 500 sentiment heatmap
    - Sector-level sentiment trends
    - Most bullish/bearish stocks
    - Catalyst calendar (upcoming events)
    - Historical sentiment tracking
    """)

# Footer
st.markdown("---")
