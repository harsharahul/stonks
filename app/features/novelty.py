"""
Novelty and content diversity feature calculators
"""

from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from statistics import mean
from dataclasses import dataclass
from sqlalchemy.orm import Session
import re
import math
from collections import Counter

from app.models.article import Article
from app.models.doc_entity import DocEntity


@dataclass
class NoveltyMetrics:
    """Container for novelty and content diversity metrics"""
    novelty_mean_3d: Optional[float] = None
    content_diversity: Optional[float] = None
    source_diversity: Optional[float] = None
    topic_breadth: Optional[float] = None


class NoveltyFeatures:
    """Content novelty and diversity feature calculations"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text for analysis"""
        if not text:
            return ""
        
        # Convert to lowercase and remove non-alphanumeric
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text
    
    @staticmethod
    def extract_keywords(text: str, min_length: int = 3, max_words: int = 100) -> List[str]:
        """Extract keywords from text content"""
        if not text:
            return []
        
        # Common stop words to filter out
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'that', 'this', 'these', 'those',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may',
            'might', 'must', 'shall', 'a', 'an', 'as', 'if', 'than', 'when', 'where',
            'why', 'how', 'what', 'which', 'who', 'whom', 'whose', 'all', 'any', 'both',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'very', 'one', 'two', 'first', 'last'
        }
        
        words = NoveltyFeatures.clean_text(text).split()
        keywords = [
            word for word in words 
            if len(word) >= min_length and word not in stop_words
        ]
        
        return keywords[:max_words]
    
    @staticmethod
    def calculate_jaccard_similarity(set1: set, set2: set) -> float:
        """Calculate Jaccard similarity between two sets"""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def calculate_cosine_similarity(text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts using TF vectors"""
        words1 = NoveltyFeatures.extract_keywords(text1)
        words2 = NoveltyFeatures.extract_keywords(text2)
        
        if not words1 or not words2:
            return 0.0
        
        # Create term frequency vectors
        counter1 = Counter(words1)
        counter2 = Counter(words2)
        
        # Get all unique terms
        all_terms = set(counter1.keys()).union(set(counter2.keys()))
        
        # Create vectors
        vector1 = [counter1.get(term, 0) for term in all_terms]
        vector2 = [counter2.get(term, 0) for term in all_terms]
        
        # Calculate cosine similarity
        dot_product = sum(v1 * v2 for v1, v2 in zip(vector1, vector2))
        magnitude1 = math.sqrt(sum(v1 * v1 for v1 in vector1))
        magnitude2 = math.sqrt(sum(v2 * v2 for v2 in vector2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    @staticmethod
    def calculate_content_novelty(
        current_text: str, 
        historical_texts: List[str],
        method: str = "cosine"
    ) -> float:
        """
        Calculate how novel current content is compared to historical content
        
        Args:
            current_text: Current article text
            historical_texts: List of historical article texts
            method: Similarity method ("cosine" or "jaccard")
            
        Returns:
            Novelty score (1.0 = completely novel, 0.0 = identical to existing)
        """
        if not historical_texts or not current_text:
            return 1.0  # Completely novel if no history
        
        similarities = []
        
        for hist_text in historical_texts:
            if method == "jaccard":
                current_keywords = set(NoveltyFeatures.extract_keywords(current_text))
                hist_keywords = set(NoveltyFeatures.extract_keywords(hist_text))
                sim = NoveltyFeatures.calculate_jaccard_similarity(current_keywords, hist_keywords)
            else:  # cosine
                sim = NoveltyFeatures.calculate_cosine_similarity(current_text, hist_text)
            
            similarities.append(sim)
        
        # Novelty is inverse of maximum similarity
        max_similarity = max(similarities) if similarities else 0.0
        return 1.0 - max_similarity
    
    @staticmethod
    def calculate_source_diversity(sources: List[str]) -> float:
        """
        Calculate diversity of news sources
        
        Args:
            sources: List of source names/URLs
            
        Returns:
            Diversity score (1.0 = all different sources, 0.0 = single source)
        """
        if not sources:
            return 0.0
        
        unique_sources = set(sources)
        total_sources = len(sources)
        
        if total_sources == 1:
            return 0.0
        
        return len(unique_sources) / total_sources
    
    @staticmethod
    def calculate_for_ticker(
        db: Session, 
        ticker: str, 
        target_date: date,
        lookback_days: int = 30
    ) -> NoveltyMetrics:
        """
        Calculate novelty features for a ticker on a specific date
        
        Args:
            db: Database session
            ticker: Stock ticker symbol
            target_date: Date to calculate features for
            lookback_days: Days to look back for historical comparison
            
        Returns:
            NoveltyMetrics with calculated features
        """
        
        # Get articles for this ticker in the lookback period
        start_date = target_date - timedelta(days=lookback_days)
        recent_3d = target_date - timedelta(days=3)
        
        articles_query = db.query(Article).join(DocEntity).filter(
            DocEntity.ticker == ticker,
            Article.raw_content.isnot(None),
            Article.published_at >= start_date,
            Article.published_at <= target_date
        ).order_by(Article.published_at.desc())
        
        all_articles = articles_query.all()
        
        if not all_articles:
            return NoveltyMetrics()
        
        # Separate recent vs historical articles
        recent_articles = [a for a in all_articles if a.published_at.date() >= recent_3d]
        historical_articles = [a for a in all_articles if a.published_at.date() < recent_3d]
        
        metrics = NoveltyMetrics()
        
        # Calculate novelty for recent articles
        if recent_articles and historical_articles:
            novelty_scores = []
            historical_texts = [a.raw_content or a.title or "" for a in historical_articles]
            
            for article in recent_articles:
                current_text = article.raw_content or article.title or ""
                novelty = NoveltyFeatures.calculate_content_novelty(
                    current_text, historical_texts
                )
                novelty_scores.append(novelty)
            
            if novelty_scores:
                metrics.novelty_mean_3d = mean(novelty_scores)
        
        # Calculate content diversity (how diverse are the recent articles among themselves)
        if len(recent_articles) > 1:
            recent_texts = [a.raw_content or a.title or "" for a in recent_articles]
            similarities = []
            
            for i in range(len(recent_texts)):
                for j in range(i + 1, len(recent_texts)):
                    sim = NoveltyFeatures.calculate_cosine_similarity(
                        recent_texts[i], recent_texts[j]
                    )
                    similarities.append(sim)
            
            if similarities:
                avg_similarity = mean(similarities)
                metrics.content_diversity = 1.0 - avg_similarity
        
        # Calculate source diversity
        if recent_articles:
            sources = [a.url.split('/')[2] if a.url else 'unknown' for a in recent_articles]
            metrics.source_diversity = NoveltyFeatures.calculate_source_diversity(sources)
        
        # Calculate topic breadth (simplified - count unique keywords)
        if recent_articles:
            all_keywords = set()
            for article in recent_articles:
                text = article.raw_content or article.title or ""
                keywords = NoveltyFeatures.extract_keywords(text)
                all_keywords.update(keywords)
            
            # Normalize by number of articles
            if len(recent_articles) > 0:
                metrics.topic_breadth = len(all_keywords) / len(recent_articles)
        
        return metrics
    
    @staticmethod
    def calculate_bulk(
        db: Session,
        tickers: List[str],
        target_date: date
    ) -> Dict[str, NoveltyMetrics]:
        """
        Calculate novelty features for multiple tickers efficiently
        
        Args:
            db: Database session
            tickers: List of ticker symbols
            target_date: Date to calculate features for
            
        Returns:
            Dictionary mapping ticker -> NoveltyMetrics
        """
        results = {}
        
        # TODO: Optimize with bulk queries when we have more data
        for ticker in tickers:
            results[ticker] = NoveltyFeatures.calculate_for_ticker(
                db, ticker, target_date
            )
        
        return results
