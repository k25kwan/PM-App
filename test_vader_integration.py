"""
Quick test of Phase 1b VADER/spaCy integration
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src" / "investment framework" / "news sentiment"))

# Load environment
from dotenv import load_dotenv
load_dotenv()

from sentiment_calculation import analyze_ticker_sentiment

# Test on a sample ticker
print("Testing Phase 1b: VADER + spaCy integration")
print("=" * 60)

ticker = "AAPL"
print(f"\nAnalyzing {ticker} with multi-method comparison...")

result = analyze_ticker_sentiment(
    ticker=ticker,
    use_ai=True,
    days_back=7,
    include_vader_comparison=True
)

print(f"\n✅ Analysis complete!")
print(f"Total articles: {result.get('total_articles', 0)}")
print(f"AI Sentiment Score: {result.get('overall_score', 'N/A')}")

if result.get('vader_comparison'):
    comp = result['vader_comparison']
    print(f"\n📊 Method Comparison:")
    print(f"  - AI Score: {comp['scores'].get('ai', 'N/A')}")
    print(f"  - VADER (All): {comp['scores'].get('vader_all', 'N/A')}")
    if comp['scores'].get('vader_filtered'):
        print(f"  - VADER (Filtered): {comp['scores'].get('vader_filtered', 'N/A')}")
    
    print(f"\n{comp['agreement']['flag']}")
    print(f"Average Score: {comp['agreement']['avg_score']:.1f}")
    print(f"Score Range: {comp['agreement']['score_range']:.1f}")
    print(f"Direction: {comp['agreement']['direction']}")
    
    print(f"\n💡 Recommendation: {comp['recommendation']}")
    
    if comp.get('ner_filtering'):
        ner = comp['ner_filtering']
        print(f"\n🔍 Relevance Filtering (spaCy NER):")
        print(f"  - Relevant: {len(ner['relevant_headlines'])} of {ner['total_headlines']} ({ner['relevance_rate']:.1f}%)")
else:
    print("\n⚠️ VADER/spaCy comparison not available")

print("\n" + "=" * 60)
print("✅ Phase 1b implementation test complete!")
