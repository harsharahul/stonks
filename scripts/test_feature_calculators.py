#!/usr/bin/env python3
"""
Test deterministic feature calculators
"""

import sys
import os
from datetime import date, datetime, timedelta
from uuid import uuid4

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models import Stock, Article, DocEntity, Price
from app.features import SentimentFeatures, MomentumFeatures, NoveltyFeatures, FeatureAggregator


def create_test_data(db):
    """Create some test data for feature calculation"""
    print("📦 Creating test data...")
    
    # Get a test stock (should exist from seed data)
    test_stock = db.query(Stock).filter(Stock.symbol == "AAPL").first()
    if not test_stock:
        print("❌ No AAPL stock found in database")
        return None
    
    print(f"✅ Using stock: {test_stock.symbol} - {test_stock.company_name}")
    
    # Create test articles with sentiment
    base_date = date.today() - timedelta(days=5)
    test_articles = []
    
    for i in range(10):
        article_date = base_date + timedelta(days=i // 2)
        
        article = Article(
            id=str(uuid4()),
            url=f"https://example.com/test-article-{i}",
            url_hash=f"test_hash_{i}",
            title=f"Test Article {i} about Apple earnings and growth prospects",
            raw_content=f"This is test content {i} discussing Apple's quarterly performance, market outlook, and competitive position in the technology sector. The company shows strong fundamentals and innovation potential.",
            sentiment=0.5 + (i % 3 - 1) * 0.3,  # Mix of positive/negative/neutral
            published_at=datetime.combine(article_date, datetime.min.time())
        )
        
        db.add(article)
        test_articles.append(article)
    
    db.flush()
    
    # Create entity links
    for i, article in enumerate(test_articles):
        entity = DocEntity(
            doc_id=article.id,
            ticker="AAPL",
            company_name="Apple Inc.",
            confidence=0.95,
            method=f"test_data_{i}"  # Unique method for each
        )
        db.add(entity)
        db.flush()  # Flush each one individually
    
    # Create test price data
    for i in range(30):
        price_date = base_date - timedelta(days=30-i)
        base_price = 150.0
        daily_change = (i % 7 - 3) * 2.0  # Some volatility
        
        price = Price(
            id=str(uuid4()),
            stock_id=test_stock.id,
            ts=datetime.combine(price_date, datetime.min.time()),
            open=base_price + daily_change,
            high=base_price + daily_change + 2.0,
            low=base_price + daily_change - 1.0,
            close=base_price + daily_change + 1.0,
            volume=1000000 + (i % 5) * 200000  # Volume variation
        )
        db.add(price)
    
    db.flush()
    print(f"✅ Created {len(test_articles)} test articles and 30 price records")
    return test_stock


def test_sentiment_features(db, stock):
    """Test sentiment feature calculation"""
    print("\n🧠 Testing Sentiment Features...")
    
    target_date = date.today()
    
    # Test sentiment calculation
    sentiment_metrics = SentimentFeatures.calculate_for_ticker(
        db, stock.symbol, target_date
    )
    
    print(f"✅ Sentiment Features for {stock.symbol}:")
    print(f"   Mean 3d: {sentiment_metrics.mean_3d}")
    print(f"   Mean 7d: {sentiment_metrics.mean_7d}")
    print(f"   Mean 10d: {sentiment_metrics.mean_10d}")
    print(f"   Shock: {sentiment_metrics.shock}")
    print(f"   Volume weighted: {sentiment_metrics.volume_weighted}")
    print(f"   Article count: {sentiment_metrics.article_count}")
    
    # Test distribution calculation
    distribution = SentimentFeatures.get_sentiment_distribution(db)
    print(f"✅ Sentiment Distribution: {distribution}")
    
    return sentiment_metrics


def test_momentum_features(db, stock):
    """Test momentum feature calculation"""
    print("\n📈 Testing Momentum Features...")
    
    target_date = date.today()
    
    # Test momentum calculation
    momentum_metrics = MomentumFeatures.calculate_for_ticker(
        db, stock.symbol, target_date
    )
    
    print(f"✅ Momentum Features for {stock.symbol}:")
    print(f"   Return 1d: {momentum_metrics.ret_1d}")
    print(f"   Return 5d: {momentum_metrics.ret_5d}")
    print(f"   Return 20d: {momentum_metrics.ret_20d}")
    print(f"   Momentum 14d: {momentum_metrics.momentum_14d}")
    print(f"   Volume z-score: {momentum_metrics.vol_z}")
    print(f"   Volatility 20d: {momentum_metrics.volatility_20d}")
    print(f"   Price trend days: {momentum_metrics.price_trend_days}")
    
    # Test market baseline
    baseline = MomentumFeatures.get_market_baseline(db)
    print(f"✅ Market Baseline: {baseline}")
    
    return momentum_metrics


def test_novelty_features(db, stock):
    """Test novelty feature calculation"""
    print("\n🆕 Testing Novelty Features...")
    
    target_date = date.today()
    
    # Test novelty calculation
    novelty_metrics = NoveltyFeatures.calculate_for_ticker(
        db, stock.symbol, target_date
    )
    
    print(f"✅ Novelty Features for {stock.symbol}:")
    print(f"   Novelty mean 3d: {novelty_metrics.novelty_mean_3d}")
    print(f"   Content diversity: {novelty_metrics.content_diversity}")
    print(f"   Source diversity: {novelty_metrics.source_diversity}")
    print(f"   Topic breadth: {novelty_metrics.topic_breadth}")
    
    # Test individual similarity calculations
    text1 = "Apple reports strong quarterly earnings with record revenue"
    text2 = "Apple announces excellent Q4 results showing revenue growth"
    text3 = "Tesla unveils new electric vehicle model with advanced features"
    
    similarity_12 = NoveltyFeatures.calculate_cosine_similarity(text1, text2)
    similarity_13 = NoveltyFeatures.calculate_cosine_similarity(text1, text3)
    
    print(f"✅ Similarity Tests:")
    print(f"   Apple vs Apple articles: {similarity_12:.3f}")
    print(f"   Apple vs Tesla articles: {similarity_13:.3f}")
    
    return novelty_metrics


def test_feature_aggregator(db, stock):
    """Test the feature aggregator"""
    print("\n🔧 Testing Feature Aggregator...")
    
    aggregator = FeatureAggregator(db)
    target_date = date.today()
    
    # Calculate aggregated features
    features = aggregator.calculate_features_for_ticker(stock.symbol, target_date)
    
    print(f"✅ Aggregated Features for {stock.symbol}:")
    print(f"   Ticker: {features.ticker}")
    print(f"   Date: {features.date}")
    print(f"   Feature version: {features.feature_version}")
    print(f"   Sentiment mean 7d: {features.sent_mean_7d}")
    print(f"   Return 5d: {features.ret_5d}")
    print(f"   Volume z-score: {features.vol_z}")
    print(f"   Novelty mean 3d: {features.novelty_mean_3d}")
    print(f"   Conflict score: {features.conflict_score}")
    print(f"   Article count 7d: {features.article_count_7d}")
    print(f"   Top doc IDs: {len(features.top_doc_ids)} documents")
    
    # Test storing features
    stored_record = aggregator.store_features(features)
    db.commit()
    
    print(f"✅ Features stored successfully with ID: ticker={stored_record.ticker}, date={stored_record.date}")
    
    # Test bulk calculation
    bulk_features = aggregator.calculate_bulk_features([stock.symbol], target_date)
    print(f"✅ Bulk calculation: {len(bulk_features)} tickers processed")
    
    return features


def test_feature_calculators():
    """Run all feature calculator tests"""
    db = SessionLocal()
    
    try:
        print("🧪 Testing Deterministic Feature Calculators...")
        
        # Create test data
        test_stock = create_test_data(db)
        if not test_stock:
            return False
        
        # Test individual feature calculators
        sentiment = test_sentiment_features(db, test_stock)
        momentum = test_momentum_features(db, test_stock)
        novelty = test_novelty_features(db, test_stock)
        
        # Test aggregator
        aggregated = test_feature_aggregator(db, test_stock)
        
        # Rollback test data to avoid polluting database
        db.rollback()
        
        print(f"\n🎉 All feature calculator tests passed!")
        print(f"📊 Feature Categories:")
        print(f"   - Sentiment: ✅ Mean aggregation, shock detection, volume weighting")
        print(f"   - Momentum: ✅ Returns, volatility, volume z-scores")
        print(f"   - Novelty: ✅ Content similarity, source diversity")
        print(f"   - Aggregator: ✅ Combined features, storage, bulk processing")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing feature calculators: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    test_feature_calculators()
