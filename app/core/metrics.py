"""
Prometheus metrics for Stonks application
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.registry import REGISTRY
from fastapi import Request, Response
import time

# Request metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Business metrics
FEATURE_CALCULATION_COUNT = Counter(
    'feature_calculations_total',
    'Total feature calculations',
    ['ticker', 'status']
)

ARTICLE_INGESTION_COUNT = Counter(
    'article_ingestions_total',
    'Total articles ingested',
    ['source', 'status']
)

PRICE_INGESTION_COUNT = Counter(
    'price_ingestions_total',
    'Total price data ingestions',
    ['ticker', 'status']
)

# Data health metrics
ACTIVE_TICKERS_GAUGE = Gauge(
    'active_tickers_total',
    'Total active tickers'
)

FEATURE_COVERAGE_GAUGE = Gauge(
    'feature_coverage_ratio',
    'Ratio of tickers with features vs total active tickers'
)

LAST_FEATURE_UPDATE_GAUGE = Gauge(
    'last_feature_update_timestamp',
    'Timestamp of last feature update'
)

# Database metrics
DB_CONNECTION_GAUGE = Gauge(
    'database_connections_active',
    'Active database connections'
)

# Celery metrics
CELERY_TASK_COUNT = Counter(
    'celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'status']
)

CELERY_TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task_name']
)


def get_metrics():
    """Generate Prometheus metrics"""
    return generate_latest(REGISTRY)


def record_request_metrics(request: Request, response: Response, duration: float):
    """Record HTTP request metrics"""
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)


def record_feature_calculation(ticker: str, status: str):
    """Record feature calculation metrics"""
    FEATURE_CALCULATION_COUNT.labels(ticker=ticker, status=status).inc()


def record_article_ingestion(source: str, status: str):
    """Record article ingestion metrics"""
    ARTICLE_INGESTION_COUNT.labels(source=source, status=status).inc()


def record_price_ingestion(ticker: str, status: str):
    """Record price ingestion metrics"""
    PRICE_INGESTION_COUNT.labels(ticker=ticker, status=status).inc()


def update_data_health_metrics(active_tickers: int, coverage_ratio: float, last_update: float):
    """Update data health metrics"""
    ACTIVE_TICKERS_GAUGE.set(active_tickers)
    FEATURE_COVERAGE_GAUGE.set(coverage_ratio)
    LAST_FEATURE_UPDATE_GAUGE.set(last_update)


def record_celery_task(task_name: str, status: str, duration: float = None):
    """Record Celery task metrics"""
    CELERY_TASK_COUNT.labels(task_name=task_name, status=status).inc()
    
    if duration is not None:
        CELERY_TASK_DURATION.labels(task_name=task_name).observe(duration)
