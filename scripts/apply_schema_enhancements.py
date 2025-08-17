#!/usr/bin/env python3
"""
Apply enhanced analytics schema additions to the database
"""

import sys
import os
from sqlalchemy import text

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal

# Enhanced schema SQL statements
SCHEMA_ENHANCEMENTS = """
-- Enhance articles table with better deduplication and canonicalization
ALTER TABLE articles 
ADD COLUMN IF NOT EXISTS canonical_url TEXT,
ADD COLUMN IF NOT EXISTS hash_sha256 TEXT;

-- Add unique index on content hash for better deduplication
CREATE UNIQUE INDEX IF NOT EXISTS articles_hash_sha256_idx ON articles(hash_sha256) 
WHERE hash_sha256 IS NOT NULL;

-- Enhanced entity linking table
CREATE TABLE IF NOT EXISTS doc_entity (
    doc_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    company_name TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    method TEXT NOT NULL, -- 'regex_cashtag' | 'spacy_ner' | 'alias_table' | 'fuzzy_match'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (doc_id, ticker, method)
);

-- Indexes for efficient entity lookups
CREATE INDEX IF NOT EXISTS doc_entity_ticker_confidence_idx ON doc_entity(ticker, confidence DESC);
CREATE INDEX IF NOT EXISTS doc_entity_doc_id_idx ON doc_entity(doc_id);

-- Feature store for daily aggregated metrics
CREATE TABLE IF NOT EXISTS ticker_features_daily (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    
    -- Sentiment features
    sent_mean_3d REAL,
    sent_mean_7d REAL, 
    sent_mean_10d REAL,
    sent_shock REAL,        -- z-score vs 90d baseline
    sent_volume_weighted REAL,
    
    -- Market features  
    ret_1d REAL,
    ret_5d REAL,
    ret_20d REAL,
    vol_z REAL,            -- volume z-score
    momentum_14d REAL,     -- 14-day momentum
    
    -- Context features
    earnings_d SMALLINT,    -- signed days to earnings
    conflict_score REAL,   -- variance across sources
    novelty_mean_3d REAL,  -- content novelty score
    
    -- Document references
    top_doc_ids UUID[],    -- most relevant articles
    article_count_7d INTEGER DEFAULT 0,
    
    -- Versioning and metadata
    feature_version TEXT NOT NULL DEFAULT 'v1.0.0',
    model_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (ticker, date, feature_version)
);

-- Indexes for efficient feature store queries
CREATE INDEX IF NOT EXISTS ticker_features_daily_ticker_date_idx ON ticker_features_daily(ticker, date DESC);
CREATE INDEX IF NOT EXISTS ticker_features_daily_date_idx ON ticker_features_daily(date DESC);

-- Document embeddings for optional vector search
CREATE TABLE IF NOT EXISTS doc_embedding (
    doc_id UUID PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    embedding TEXT, -- Store as JSON text for now, convert to VECTOR if pgvector available
    model TEXT NOT NULL DEFAULT 'text-embedding-ada-002',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add feature store reference to recommendations for traceability
ALTER TABLE recommendations 
ADD COLUMN IF NOT EXISTS feature_date DATE,
ADD COLUMN IF NOT EXISTS feature_version TEXT;

-- Add indexes for feature store integration
CREATE INDEX IF NOT EXISTS recommendations_feature_ref_idx 
ON recommendations(stock_id, feature_date, feature_version) 
WHERE feature_date IS NOT NULL;
"""

def apply_schema_enhancements():
    """Apply enhanced analytics schema to the database"""
    db = SessionLocal()
    
    try:
        print("🔧 Applying enhanced analytics schema...")
        
        # Execute statements in logical order
        statements = [
            # 1. Enhance existing tables first
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS canonical_url TEXT",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS hash_sha256 TEXT",
            
            # 2. Create new tables
            """CREATE TABLE IF NOT EXISTS doc_entity (
                doc_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                company_name TEXT,
                confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
                method TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (doc_id, ticker, method)
            )""",
            
            """CREATE TABLE IF NOT EXISTS ticker_features_daily (
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                sent_mean_3d REAL,
                sent_mean_7d REAL, 
                sent_mean_10d REAL,
                sent_shock REAL,
                sent_volume_weighted REAL,
                ret_1d REAL,
                ret_5d REAL,
                ret_20d REAL,
                vol_z REAL,
                momentum_14d REAL,
                earnings_d SMALLINT,
                conflict_score REAL,
                novelty_mean_3d REAL,
                top_doc_ids UUID[],
                article_count_7d INTEGER DEFAULT 0,
                feature_version TEXT NOT NULL DEFAULT 'v1.0.0',
                model_version TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (ticker, date, feature_version)
            )""",
            
            """CREATE TABLE IF NOT EXISTS doc_embedding (
                doc_id UUID PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
                embedding TEXT,
                model TEXT NOT NULL DEFAULT 'text-embedding-ada-002',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""",
            
            "ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS feature_date DATE",
            "ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS feature_version TEXT",
            
            # 3. Create indexes last
            "CREATE UNIQUE INDEX IF NOT EXISTS articles_hash_sha256_idx ON articles(hash_sha256) WHERE hash_sha256 IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS doc_entity_ticker_confidence_idx ON doc_entity(ticker, confidence DESC)",
            "CREATE INDEX IF NOT EXISTS doc_entity_doc_id_idx ON doc_entity(doc_id)",
            "CREATE INDEX IF NOT EXISTS ticker_features_daily_ticker_date_idx ON ticker_features_daily(ticker, date DESC)",
            "CREATE INDEX IF NOT EXISTS ticker_features_daily_date_idx ON ticker_features_daily(date DESC)",
            "CREATE INDEX IF NOT EXISTS recommendations_feature_ref_idx ON recommendations(stock_id, feature_date, feature_version) WHERE feature_date IS NOT NULL",
        ]
        
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if statement:
                print(f"[{i}/{len(statements)}] Executing: {statement[:50]}...")
                db.execute(text(statement))
        
        db.commit()
        print("✅ Schema enhancements applied successfully!")
        
        # Verify new tables exist
        print("\n📋 Verifying new tables...")
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        
        tables = [row[0] for row in result]
        print("Available tables:")
        for table in tables:
            print(f"  - {table}")
        
        # Check for our new tables specifically
        new_tables = ['doc_entity', 'ticker_features_daily', 'doc_embedding']
        for table in new_tables:
            if table in tables:
                print(f"✅ {table} - created successfully")
            else:
                print(f"❌ {table} - not found")
        
        # Check enhanced columns
        print("\n📋 Verifying enhanced columns...")
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'articles' AND table_schema = 'public'
            ORDER BY column_name
        """))
        
        columns = [row[0] for row in result]
        enhanced_columns = ['canonical_url', 'hash_sha256']
        for column in enhanced_columns:
            if column in columns:
                print(f"✅ articles.{column} - added successfully")
            else:
                print(f"❌ articles.{column} - not found")
        
        print(f"\n🎉 Enhanced analytics schema ready!")
        print(f"Total tables: {len(tables)}")
        
    except Exception as e:
        print(f"❌ Error applying schema enhancements: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    apply_schema_enhancements()
