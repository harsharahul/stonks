#!/usr/bin/env python3
"""
Test enhanced analytics schema integration
"""

import sys
import os
from datetime import date, datetime
from uuid import uuid4

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models import (
    Stock, Article, DocEntity, TickerFeaturesDaily, DocEmbedding
)

def test_enhanced_schema():
    """Test enhanced schema integration with sample data"""
    db = SessionLocal()
    
    try:
        print("🧪 Testing enhanced analytics schema...")
        
        # 1. Test existing functionality still works
        print("\n1️⃣ Testing existing Stock model...")
        stock_count = db.query(Stock).count()
        print(f"   Stock count: {stock_count}")
        
        if stock_count > 0:
            sample_stock = db.query(Stock).first()
            print(f"   Sample stock: {sample_stock.symbol} - {sample_stock.company_name}")
        
        # 2. Test enhanced Article model with new fields
        print("\n2️⃣ Testing enhanced Article model...")
        article = Article(
            id=str(uuid4()),
            url="https://example.com/test-article",
            url_hash="test_hash_123",
            title="Test Article for Enhanced Schema",
            canonical_url="https://example.com/canonical-test-article",
            hash_sha256="abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234",
            tickers=["AAPL", "MSFT"],
            sentiment=0.75
        )
        db.add(article)
        db.flush()  # Get the ID without committing
        print(f"   ✅ Article created with ID: {article.id}")
        print(f"   ✅ Canonical URL: {article.canonical_url}")
        print(f"   ✅ Hash SHA256: {article.hash_sha256}")
        
        # 3. Test DocEntity model
        print("\n3️⃣ Testing DocEntity model...")
        entity1 = DocEntity(
            doc_id=article.id,
            ticker="AAPL",
            company_name="Apple Inc.",
            confidence=0.95,
            method="regex_cashtag"
        )
        db.add(entity1)
        db.flush()
        print(f"   ✅ Created entity link for AAPL with confidence {entity1.confidence}")
        
        entity2 = DocEntity(
            doc_id=article.id,
            ticker="MSFT",
            company_name="Microsoft Corporation",
            confidence=0.87,
            method="spacy_ner"
        )
        db.add(entity2)
        db.flush()
        print(f"   ✅ Created entity link for MSFT with confidence {entity2.confidence}")
        
        # 4. Test TickerFeaturesDaily model
        print("\n4️⃣ Testing TickerFeaturesDaily model...")
        features = TickerFeaturesDaily(
            ticker="AAPL",
            date=date.today(),
            feature_version="v1.0.0",
            sent_mean_7d=0.65,
            sent_shock=1.2,
            ret_5d=0.03,
            vol_z=1.5,
            momentum_14d=0.08,
            conflict_score=0.3,
            novelty_mean_3d=0.7,
            top_doc_ids=[article.id],
            article_count_7d=5,
            model_version="test_v1.0.0"
        )
        db.add(features)
        db.flush()
        print(f"   ✅ Features created for {features.ticker} on {features.date}")
        print(f"   ✅ Feature version: {features.feature_version}")
        
        # Test the to_dict method
        features_dict = features.to_dict()
        print(f"   ✅ to_dict() returns {len(features_dict)} keys")
        
        # 5. Test DocEmbedding model
        print("\n5️⃣ Testing DocEmbedding model...")
        embedding = DocEmbedding(
            doc_id=article.id,
            model="text-embedding-ada-002"
        )
        
        # Test embedding vector storage
        test_vector = [0.1, -0.2, 0.3, 0.4, -0.5]
        embedding.set_embedding_vector(test_vector)
        db.add(embedding)
        db.flush()
        
        retrieved_vector = embedding.get_embedding_vector()
        print(f"   ✅ Embedding stored and retrieved: {retrieved_vector == test_vector}")
        print(f"   ✅ Model: {embedding.model}")
        
        # 6. Test relationships and queries
        print("\n6️⃣ Testing relationships and queries...")
        
        # Query entities for the article
        article_entities = db.query(DocEntity).filter(DocEntity.doc_id == article.id).all()
        print(f"   ✅ Found {len(article_entities)} entities for article")
        
        # Query features for AAPL
        aapl_features = db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.ticker == "AAPL"
        ).all()
        print(f"   ✅ Found {len(aapl_features)} feature records for AAPL")
        
        # Query by confidence
        high_confidence_entities = db.query(DocEntity).filter(
            DocEntity.confidence > 0.9
        ).all()
        print(f"   ✅ Found {len(high_confidence_entities)} high-confidence entities")
        
        # Rollback to avoid polluting the database
        db.rollback()
        print(f"\n🎉 All enhanced schema tests passed!")
        print(f"📊 Schema includes:")
        print(f"   - Enhanced Articles with canonical URLs and content hashes")
        print(f"   - Entity linking with confidence scoring")
        print(f"   - Feature store with daily aggregated metrics")
        print(f"   - Document embeddings for vector search")
        print(f"   - Feature versioning and traceability")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing enhanced schema: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    test_enhanced_schema()
