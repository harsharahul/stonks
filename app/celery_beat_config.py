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

    # SEC EDGAR Enhanced ingestion - every 2 hours
    'sec-edgar-enhanced-ingestion': {
        'task': 'app.tasks.sec_edgar_enhanced.fetch_sec_edgar_enhanced',
        'schedule': 7200.0,  # 2 hours in seconds
        'args': (1, ['8-K', '10-K', '10-Q'], None),  # days_back, filing_types, tickers
        'options': {
            'expires': 6000,  # Task expires after 100 minutes
        }
    },

    # Earnings Calendar ingestion - daily at 7 AM UTC
    'earnings-calendar-ingestion': {
        'task': 'app.tasks.earnings_calendar.fetch_nasdaq_earnings_calendar',
        'schedule': crontab(hour=7, minute=0),  # Daily at 7 AM UTC
        'args': (7, 3),  # days_ahead, days_back
        'options': {
            'expires': 3600,  # Task expires after 1 hour
        }
    }
}

# Timezone for scheduled tasks
timezone = 'UTC'

# Task routing (optional - for multiple workers)
task_routes = {
    'app.tasks.anomaly_detection.*': {'queue': 'analytics'},
    'app.tasks.signal_generation.*': {'queue': 'analytics'},
    'app.tasks.feature_calculation.*': {'queue': 'compute'},
    'app.tasks.data_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.price_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.reddit_wsb_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.sec_edgar_enhanced.*': {'queue': 'ingestion'},
    'app.tasks.reddit_wsb_enhanced.*': {'queue': 'ingestion'},
    'app.tasks.sec_edgar_ingestion.*': {'queue': 'ingestion'},
    'app.tasks.earnings_calendar.*': {'queue': 'ingestion'},
}
