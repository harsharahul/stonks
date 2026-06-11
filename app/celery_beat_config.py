"""
Celery Beat Configuration for Scheduled Tasks

Defines periodic tasks for real-time monitoring and analytics.
"""

from celery.schedules import crontab

# Celery Beat Schedule Configuration
beat_schedule = {
    # Continuous anomaly monitoring - every 15 minutes
    'continuous-anomaly-monitoring': {
        'task': 'app.tasks.anomaly_detection.continuous_anomaly_monitoring_task',
        'schedule': 900.0,  # 15 minutes in seconds
        'options': {
            'expires': 600,  # Task expires after 10 minutes if not executed
        }
    },
    
    # Daily signal generation - every day at 6 AM UTC
    'daily-signal-generation': {
        'task': 'app.tasks.signal_generation.daily_signal_generation_task',
        'schedule': crontab(hour=6, minute=0),
        'options': {
            'expires': 3600,  # Task expires after 1 hour
        }
    },
    
    # Daily recommendation generation - every day at 6:30 AM UTC (after signals at 6 AM)
    'daily-recommendation-generation': {
        'task': 'app.tasks.recommendation_generation.generate_daily_recommendations_task',
        'schedule': crontab(hour=6, minute=30),
        'options': {
            'expires': 3600,
        }
    },

    # Alert generation from recent signals - every 5 minutes
    'alert-generation': {
        'task': 'app.tasks.signal_generation.generate_alerts_task',
        'schedule': 300.0,  # 5 minutes in seconds
        'args': (1,),  # Process signals from last 1 hour
        'options': {
            'expires': 240,  # Task expires after 4 minutes
        }
    },
    
    # Daily feature calculation - every day at 5 AM UTC
    'daily-feature-calculation': {
        'task': 'app.tasks.feature_calculation.calculate_daily_features',
        'schedule': crontab(hour=5, minute=0),
        'options': {
            'expires': 7200,  # Task expires after 2 hours
        }
    },
    
    # Cleanup expired signals - every 6 hours
    'cleanup-expired-signals': {
        'task': 'app.tasks.signal_generation.cleanup_expired_signals_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'args': (7,),  # Remove signals older than 7 days
        'options': {
            'expires': 1800,  # Task expires after 30 minutes
        }
    },
    
    # RSS/News ingestion - every 10 minutes
    'news-ingestion': {
        'task': 'app.tasks.data_ingestion.ingest_rss_feeds_task',
        'schedule': 600.0,  # 10 minutes in seconds
        'options': {
            'expires': 480,  # Task expires after 8 minutes
        }
    },

    # Post-ingestion processing - every 15 minutes (after RSS ingestion)
    'post-ingest-processing': {
        'task': 'app.tasks.post_ingest_hooks.process_new_articles',
        'schedule': 900.0,  # 15 minutes
        'args': (1, 100),  # hours_back=1, batch_size=100
        'options': {
            'expires': 600,
        }
    },
    
    # Price data ingestion - every hour during market hours
    'price-ingestion': {
        'task': 'app.tasks.price_ingestion.fetch_prices_for_all_stocks',
        'schedule': crontab(minute=0),  # Every hour
        'options': {
            'expires': 3000,  # Task expires after 50 minutes
        }
    },
    
    # WSB Enhanced ingestion - every 30 minutes
    'wsb-enhanced-ingestion': {
        'task': 'app.tasks.reddit_wsb_enhanced.fetch_wsb_enhanced',
        'schedule': 1800.0,  # 30 minutes in seconds
        'args': (100, 'hot'),  # limit, sort
        'options': {
            'expires': 1500,  # Task expires after 25 minutes
        }
    },

    # Signal plugin dispatcher — runs every enabled SignalSource plugin
    # (registry-driven; per-source enable/config in signal_source_states)
    'signal-source-dispatch': {
        'task': 'app.tasks.signal_dispatch.dispatch_signal_sources_task',
        'schedule': 1800.0,  # 30 minutes
        'options': {'expires': 1500},
    },

    # Signal outcome scoring — per-source track records, nightly 23:45 UTC
    # (after desk outcomes 23:00 and strategy performance 23:30)
    'signal-outcome-scoring': {
        'task': 'app.tasks.signal_outcomes.score_signal_outcomes_task',
        'schedule': crontab(hour=23, minute=45),
        'options': {'expires': 3600},
    },

    # Strategy verified track records — nightly after desk outcome scoring (23:00)
    'strategy-performance': {
        'task': 'app.tasks.strategy_performance.compute_strategy_performance_task',
        'schedule': crontab(hour=23, minute=30),
        'options': {'expires': 3600},
    },

    # SEC EDGAR basic - RSS feed of 8-K/10-K/10-Q filings, every 2 hours
    'sec-edgar-ingestion': {
        'task': 'app.tasks.sec_edgar_ingestion.fetch_sec_edgar_rss',
        'schedule': 7200.0,  # 2 hours
        'args': (['8-K', '10-K', '10-Q'], 1),  # filing_types, days_back
        'options': {'expires': 6000},
    },

    # SEC EDGAR CIK→ticker mapping - resolves filing articles to tickers
    'sec-edgar-cik-mapping': {
        'task': 'app.tasks.sec_edgar_ingestion.map_cik_to_tickers',
        'schedule': crontab(minute=30, hour='*/2'),  # offset 30 min after RSS fetch
        'args': (100,),
        'options': {'expires': 6000},
    },

    # SEC EDGAR Enhanced - DISABLED: sec-downloader/sec-parser dependencies
    # are commented out in requirements.txt. Re-enable when restored.
    # 'sec-edgar-enhanced-ingestion': {
    #     'task': 'app.tasks.sec_edgar_enhanced.fetch_sec_edgar_enhanced',
    #     'schedule': 7200.0,
    #     'args': (1, ['8-K', '10-K', '10-Q'], None),
    #     'options': {
    #         'expires': 6000,
    #     }
    # },

    # Earnings Calendar ingestion - daily at 7 AM UTC
    'earnings-calendar-ingestion': {
        'task': 'app.tasks.earnings_calendar.fetch_nasdaq_earnings_calendar',
        'schedule': crontab(hour=7, minute=0),  # Daily at 7 AM UTC
        'args': (7, 3),  # days_ahead, days_back
        'options': {
            'expires': 3600,  # Task expires after 1 hour
        }
    },

    # Article cleanup (tiered): null content 30–90d, full delete 90d+ — daily at 3 AM
    'cleanup-old-articles': {
        'task': 'app.tasks.post_ingest_hooks.cleanup_old_articles',
        'schedule': crontab(hour=3, minute=0),
        'options': {'expires': 3600},
    },

    # ETL job run cleanup: delete rows older than 30 days — daily at 3:15 AM
    'cleanup-old-etl-runs': {
        'task': 'app.tasks.post_ingest_hooks.cleanup_old_etl_runs',
        'schedule': crontab(hour=3, minute=15),
        'options': {'expires': 1800},
    },

    # Stock knowledge update: evolving per-ticker intelligence — daily at 2:30 AM
    # Runs BEFORE cleanup (3:00 AM) so articles are distilled before deletion
    'update-stock-knowledge': {
        'task': 'app.tasks.stock_knowledge.update_stock_knowledge_task',
        'schedule': crontab(hour=2, minute=30),
        'options': {'expires': 7200},
    },

    # AI Trading Desk — Phase 1 schedule.
    # Universe refresh: every Sunday at 00:00 UTC.
    'desk-refresh-universe': {
        'task': 'app.tasks.agent_pipeline.refresh_universe_membership_task',
        'schedule': crontab(hour=0, minute=0, day_of_week='sun'),
        'options': {'expires': 3600},
    },

    # Nightly desk batch: 7:15 AM UTC, after features (5am), signals (6am),
    # and recommendations (6:30am).
    'desk-nightly-batch': {
        'task': 'app.tasks.agent_pipeline.run_desk_universe_nightly_task',
        'schedule': crontab(hour=7, minute=15),
        'options': {'expires': 6 * 3600},
    },

    # Retrospective scoring: 23:00 UTC daily (after market close).
    'desk-score-outcomes': {
        'task': 'app.tasks.agent_pipeline.score_past_decisions_task',
        'schedule': crontab(hour=23, minute=0),
        'options': {'expires': 3600},
    },
}

# Timezone for scheduled tasks
timezone = 'UTC'

# Task routing (optional - for multiple workers)
task_routes = {
    'app.tasks.anomaly_detection.*': {'queue': 'analytics'},
    'app.tasks.signal_generation.*': {'queue': 'analytics'},
    'app.tasks.recommendation_generation.*': {'queue': 'analytics'},
    'app.tasks.feature_calculation.*': {'queue': 'compute'},
    'app.tasks.data_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.price_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.reddit_wsb_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.signal_dispatch.*': {'queue': 'ingestion'},
    'app.tasks.signal_outcomes.*': {'queue': 'analytics'},
    'app.tasks.strategy_performance.*': {'queue': 'analytics'},
    'app.tasks.strategy_mirror.*': {'queue': 'compute'},
    'app.tasks.sec_edgar_enhanced.*': {'queue': 'ingestion'},
    'app.tasks.reddit_wsb_enhanced.*': {'queue': 'ingestion'},
    'app.tasks.sec_edgar_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.earnings_calendar.*': {'queue': 'ingestion'},
    'app.tasks.post_ingest_hooks.*': {'queue': 'compute'},
    'app.tasks.stock_knowledge.*': {'queue': 'compute'},
    'app.tasks.agent_pipeline.*': {'queue': 'analytics'},
}
