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

from src.analytics.news_sentiment import (
    analyze_ticker_sentiment,
    batch_analyze_tickers,
    fetch_news_for_ticker
)
from src.analytics.sector_benchmarks import SectorBenchmarks

st.set_page_config(page_title="News Sentiment", layout="wide")

st.title("📰 News Sentiment Analysis")
st.markdown("Analyze market sentiment from recent news headlines to identify catalysts and trends")

# Check for OpenAI API key
import os
from dotenv import load_dotenv
load_dotenv()
has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))

if not has_openai_key:
    st.warning("⚠️ OpenAI API key not found. Using keyword-based sentiment analysis. "
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
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    
    if analyze_btn and ticker_input:
        with st.spinner(f"Analyzing sentiment for {ticker_input}..."):
            sentiment = analyze_ticker_sentiment(ticker_input, use_ai=use_ai)
            
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
                    st.metric("Articles Analyzed", sentiment['total_articles'])
                with col4:
                    # Signal strength
                    if sentiment['confidence'] == 'High' and (score > 65 or score < 35):
                        signal = "🟢 Strong"
                    elif sentiment['confidence'] in ['High', 'Medium']:
                        signal = "🟡 Moderate"
                    else:
                        signal = "🔴 Weak"
                    st.metric("Signal Strength", signal)
                
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
                
                # Display narrative and catalysts if AI analysis
                if sentiment.get('ai_analysis'):
                    st.subheader("📋 AI Analysis")
                    
                    if sentiment.get('narrative'):
                        st.info(f"**Market Narrative:** {sentiment['narrative']}")
                    
                    if sentiment.get('catalysts'):
                        st.markdown("**Key Catalysts:**")
                        for catalyst in sentiment['catalysts']:
                            st.markdown(f"• {catalyst}")
                else:
                    # Show basic stats for keyword analysis
                    st.subheader("📊 Sentiment Breakdown")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Positive Articles", sentiment.get('positive_count', 0))
                    with col2:
                        st.metric("Neutral Articles", sentiment.get('neutral_count', 0))
                    with col3:
                        st.metric("Negative Articles", sentiment.get('negative_count', 0))
                
                # Display recent headlines
                st.subheader("📰 Recent Headlines")
                articles = sentiment.get('articles', [])
                if articles:
                    for i, article in enumerate(articles[:10], 1):
                        with st.expander(f"{i}. {article['title']}"):
                            st.markdown(f"**Publisher:** {article['publisher']}")
                            st.markdown(f"**Published:** {article['publish_time'].strftime('%Y-%m-%d %H:%M')}")
                            if article.get('link'):
                                st.markdown(f"[Read Article]({article['link']})")

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
        batch_analyze_btn = st.button("🔍 Analyze All", type="primary", use_container_width=True)
    
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
                sentiment = analyze_ticker_sentiment(ticker, use_ai=use_ai)
                results.append({
                    'Ticker': ticker,
                    'Sentiment Score': sentiment['sentiment_score'],
                    'Signal': '🟢 Bullish' if sentiment['sentiment_score'] >= 65 else 
                             '🟡 Neutral' if sentiment['sentiment_score'] >= 45 else 
                             '🔴 Bearish',
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
            st.subheader("📊 Sentiment Scores")
            
            # Color code the sentiment scores
            def color_sentiment(val):
                if isinstance(val, (int, float)):
                    if val >= 70:
                        return 'background-color: darkgreen; color: white'
                    elif val >= 55:
                        return 'background-color: lightgreen'
                    elif val >= 45:
                        return 'background-color: lightgray'
                    elif val >= 30:
                        return 'background-color: orange'
                    else:
                        return 'background-color: red; color: white'
                return ''
            
            styled_df = df_results.style.applymap(color_sentiment, subset=['Sentiment Score'])
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            # Sentiment distribution chart
            st.subheader("📈 Sentiment Distribution")
            fig = px.bar(
                df_results.sort_values('Sentiment Score', ascending=False),
                x='Ticker',
                y='Sentiment Score',
                color='Sentiment Score',
                color_continuous_scale=['red', 'yellow', 'green'],
                title="Sentiment Scores by Ticker"
            )
            fig.update_layout(showlegend=False)
            fig.add_hline(y=50, line_dash="dash", line_color="gray", 
                         annotation_text="Neutral (50)")
            st.plotly_chart(fig, use_container_width=True)

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
st.caption("💡 **Tip:** Sentiment analysis works best when combined with fundamental analysis. "
          "Use this as one input in your investment decision process.")
