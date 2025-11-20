"""
Sentiment Comparison Module - Phase 1b Enhancement
Provides VADER rule-based sentiment and spaCy NER for comparison with AI sentiment.

Purpose:
- VADER: Fast, deterministic sentiment scoring (backtesting-friendly)
- spaCy: Named entity recognition for relevance filtering
- Comparison: Validate AI scores, identify divergences, build confidence
"""

import numpy as np
import spacy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List, Dict, Tuple


class SentimentComparator:
    """Compare multiple sentiment analysis methods for validation"""
    
    def __init__(self):
        """Initialize VADER and spaCy models"""
        self.vader = SentimentIntensityAnalyzer()
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not installed
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
    
    def analyze_with_vader(self, headlines: List[str]) -> Dict:
        """
        Analyze sentiment using VADER rule-based approach
        
        Args:
            headlines: List of news headlines
            
        Returns:
            Dict with score (0-100), individual scores, and confidence
        """
        if not headlines:
            return {
                'score': 50.0,
                'individual_scores': [],
                'confidence': 'low',
                'method': 'vader'
            }
        
        # Get compound scores for each headline (-1 to 1)
        vader_scores = []
        for headline in headlines:
            sentiment = self.vader.polarity_scores(headline)
            vader_scores.append(sentiment['compound'])
        
        # Convert to 0-100 scale (0=bearish, 50=neutral, 100=bullish)
        # Compound score ranges from -1 to 1
        avg_compound = np.mean(vader_scores)
        score_0_100 = (avg_compound * 50) + 50  # -1→0, 0→50, 1→100
        
        # Calculate confidence based on consistency
        std_dev = np.std(vader_scores)
        if std_dev < 0.2:
            confidence = 'high'
        elif std_dev < 0.4:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'score': round(score_0_100, 1),
            'individual_scores': [round(s, 2) for s in vader_scores],
            'confidence': confidence,
            'method': 'vader',
            'avg_compound': round(avg_compound, 2),
            'std_dev': round(std_dev, 2)
        }
    
    def filter_with_spacy_ner(
        self, 
        headlines: List[str], 
        ticker: str,
        company_name: str = None
    ) -> Dict:
        """
        Use spaCy NER to filter headlines for relevance
        
        Args:
            headlines: List of news headlines
            ticker: Stock ticker symbol
            company_name: Optional company name for matching
            
        Returns:
            Dict with relevant headlines and entity analysis
        """
        if not headlines:
            return {
                'relevant_headlines': [],
                'total_headlines': 0,
                'relevance_rate': 0.0,
                'entities_found': []
            }
        
        relevant_headlines = []
        all_entities = []
        
        # Common company name variations
        ticker_upper = ticker.upper()
        search_terms = [ticker_upper]
        if company_name:
            search_terms.append(company_name.lower())
        
        for headline in headlines:
            # Process with spaCy
            doc = self.nlp(headline)
            
            # Extract entities
            entities = [(ent.text, ent.label_) for ent in doc.ents]
            all_entities.extend(entities)
            
            # Check if ticker or company name mentioned
            headline_lower = headline.lower()
            ticker_mentioned = ticker_upper in headline.upper()
            company_mentioned = False
            
            if company_name:
                # Check for company name or organization entities
                company_mentioned = company_name.lower() in headline_lower
                for ent_text, ent_label in entities:
                    if ent_label == "ORG" and company_name.lower() in ent_text.lower():
                        company_mentioned = True
                        break
            
            if ticker_mentioned or company_mentioned:
                relevant_headlines.append(headline)
        
        return {
            'relevant_headlines': relevant_headlines,
            'total_headlines': len(headlines),
            'relevance_rate': round(len(relevant_headlines) / len(headlines) * 100, 1),
            'entities_found': list(set(all_entities)),
            'method': 'spacy_ner'
        }
    
    def compare_all_methods(
        self,
        headlines: List[str],
        ticker: str,
        ai_score: float = None,
        keyword_score: float = None,
        company_name: str = None
    ) -> Dict:
        """
        Compare AI, VADER, and keyword-based sentiment
        
        Args:
            headlines: List of news headlines
            ticker: Stock ticker symbol
            ai_score: Score from dual-AI validation (0-100)
            keyword_score: Score from keyword-based method (0-100)
            company_name: Optional company name for NER filtering
            
        Returns:
            Comprehensive comparison with agreement analysis
        """
        # VADER analysis
        vader_result = self.analyze_with_vader(headlines)
        
        # spaCy relevance filtering
        ner_result = self.filter_with_spacy_ner(headlines, ticker, company_name)
        
        # VADER on filtered headlines (if NER found relevant ones)
        vader_filtered = None
        if ner_result['relevant_headlines']:
            vader_filtered = self.analyze_with_vader(ner_result['relevant_headlines'])
        
        # Compare scores
        scores = {}
        if ai_score is not None:
            scores['ai'] = round(ai_score, 1)
        if keyword_score is not None:
            scores['keyword'] = round(keyword_score, 1)
        scores['vader_all'] = vader_result['score']
        if vader_filtered:
            scores['vader_filtered'] = vader_filtered['score']
        
        # Calculate agreement
        agreement_analysis = self._analyze_agreement(scores)
        
        return {
            'ticker': ticker,
            'total_headlines': len(headlines),
            'scores': scores,
            'vader_details': vader_result,
            'ner_filtering': ner_result,
            'vader_filtered_details': vader_filtered,
            'agreement': agreement_analysis,
            'recommendation': self._generate_recommendation(scores, agreement_analysis)
        }
    
    def _analyze_agreement(self, scores: Dict[str, float]) -> Dict:
        """
        Analyze agreement between different methods
        
        Args:
            scores: Dict of method names to scores
            
        Returns:
            Agreement analysis with flags and metrics
        """
        if len(scores) < 2:
            return {'status': 'insufficient_data'}
        
        score_values = list(scores.values())
        avg_score = np.mean(score_values)
        std_dev = np.std(score_values)
        score_range = max(score_values) - min(score_values)
        
        # Agreement thresholds
        if score_range <= 10:
            agreement_level = 'strong'
            flag = '✅ High confidence - all methods agree'
        elif score_range <= 20:
            agreement_level = 'moderate'
            flag = '⚠️ Moderate confidence - some divergence'
        else:
            agreement_level = 'weak'
            flag = '🚨 Low confidence - significant divergence'
        
        # Sentiment direction
        if avg_score >= 60:
            direction = 'bullish'
        elif avg_score <= 40:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        return {
            'level': agreement_level,
            'flag': flag,
            'avg_score': round(avg_score, 1),
            'std_dev': round(std_dev, 1),
            'score_range': round(score_range, 1),
            'direction': direction
        }
    
    def _generate_recommendation(
        self,
        scores: Dict[str, float],
        agreement: Dict
    ) -> str:
        """Generate actionable recommendation based on analysis"""
        
        if agreement.get('level') == 'strong':
            if agreement['direction'] == 'bullish':
                return f"Strong bullish signal (avg {agreement['avg_score']}) - all methods agree, high confidence"
            elif agreement['direction'] == 'bearish':
                return f"Strong bearish signal (avg {agreement['avg_score']}) - all methods agree, high confidence"
            else:
                return f"Neutral sentiment (avg {agreement['avg_score']}) - all methods agree, no clear direction"
        
        elif agreement.get('level') == 'moderate':
            return f"Mixed signals ({agreement['direction']} lean, avg {agreement['avg_score']}) - use caution, verify with fundamentals"
        
        else:
            # Weak agreement - identify outliers
            score_values = list(scores.values())
            outliers = [k for k, v in scores.items() if abs(v - agreement['avg_score']) > 15]
            return f"Conflicting signals - methods diverge significantly. Outliers: {', '.join(outliers)}. Require additional research."


def test_comparison():
    """Test the sentiment comparison on sample headlines"""
    
    comparator = SentimentComparator()
    
    # Sample headlines
    test_headlines = [
        "Apple reports record earnings, beats analyst expectations",
        "Apple facing regulatory challenges in Europe",
        "Tech stocks rally as AI enthusiasm builds",
        "Apple launches innovative new product line",
        "Market uncertainty weighs on technology sector"
    ]
    
    result = comparator.compare_all_methods(
        headlines=test_headlines,
        ticker="AAPL",
        ai_score=65.0,  # Simulated AI score
        keyword_score=60.0,  # Simulated keyword score
        company_name="Apple"
    )
    
    print("=== Sentiment Comparison Test ===")
    print(f"Ticker: {result['ticker']}")
    print(f"Total Headlines: {result['total_headlines']}")
    print(f"\nScores:")
    for method, score in result['scores'].items():
        print(f"  {method}: {score}")
    print(f"\nAgreement: {result['agreement']['flag']}")
    print(f"Average Score: {result['agreement']['avg_score']}")
    print(f"Score Range: {result['agreement']['score_range']}")
    print(f"\nRecommendation: {result['recommendation']}")
    print(f"\nNER Filtering:")
    print(f"  Relevance Rate: {result['ner_filtering']['relevance_rate']}%")
    print(f"  Relevant Headlines: {len(result['ner_filtering']['relevant_headlines'])}")


if __name__ == "__main__":
    test_comparison()
