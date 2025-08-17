#!/usr/bin/env python3
"""
Test RSS ingestion functionality
"""

import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.tasks.data_ingestion import test_rss_ingestion, RSS_SOURCES
from app.models import Article, DataSource, DocEntity


def test_rss_ingestion_sync():
    """Test RSS ingestion synchronously"""
    db = SessionLocal()
    
    try:
        print("🧪 Testing RSS ingestion...")
        print(f"📰 Available RSS sources: {len(RSS_SOURCES)}")
        
        for i, source in enumerate(RSS_SOURCES[:2], 1):  # Test first 2 sources
            print(f"{i}. {source['name']} - {source['url']}")
        
        # Count existing articles before ingestion
        initial_article_count = db.query(Article).count()
        initial_entity_count = db.query(DocEntity).count()
        
        print(f"\n📊 Before ingestion:")
        print(f"   Articles: {initial_article_count}")
        print(f"   Entity links: {initial_entity_count}")
        
        # Run test ingestion
        result = test_rss_ingestion.apply_async(args=[2]).get()
        
        # Count articles after ingestion
        final_article_count = db.query(Article).count()
        final_entity_count = db.query(DocEntity).count()
        
        print(f"\n📊 After ingestion:")
        print(f"   Articles: {final_article_count} (+{final_article_count - initial_article_count})")
        print(f"   Entity links: {final_entity_count} (+{final_entity_count - initial_entity_count})")
        
        print(f"\n✅ Test Results:")
        print(f"   Sources tested: {result['sources_tested']}")
        print(f"   Test mode: {result['test_mode']}")
        
        for source_result in result['results']:
            if source_result['status'] == 'success':
                print(f"   ✅ {source_result['source_name']}: {source_result['articles_new']} new, {source_result['articles_duplicate']} duplicates")
            else:
                print(f"   ❌ {source_result['source_name']}: {source_result.get('error', 'Unknown error')}")
        
        # Show sample articles
        if final_article_count > initial_article_count:
            print(f"\n📰 Sample new articles:")
            recent_articles = db.query(Article).order_by(Article.created_at.desc()).limit(3).all()
            
            for article in recent_articles:
                print(f"   • {article.title[:60]}..." if len(article.title) > 60 else f"   • {article.title}")
                print(f"     URL: {article.url}")
                print(f"     Tickers: {article.tickers}")
                print(f"     Published: {article.published_at}")
                
                # Show entity links
                entities = db.query(DocEntity).filter(DocEntity.doc_id == article.id).all()
                if entities:
                    print(f"     Entity links: {[f'{e.ticker}({e.confidence})' for e in entities]}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing RSS ingestion: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    test_rss_ingestion_sync()
