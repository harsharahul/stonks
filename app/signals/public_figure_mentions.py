"""Public figure mentions plugin.

Emits momentum signals when a tracked public figure names a listed company
in a public statement (a post, a speech, an interview). Two detectors:

1. A curated mention list from the source config, with linear time decay
   over ``decay_days`` (default 30). High precision, operator maintained.
2. A headline scan over a configured watchlist for the configured keywords
   (yfinance news from the last seven days). Broader, lower confidence.

Who is tracked, which keywords identify them, the mention list, and the
watchlist all come from the source config. The module carries no names.

Config keys:
    figure        display label for the tracked person
    keywords      strings that identify the figure in headlines (required)
    mentions      {ticker: {name, mention_date (YYYY-MM-DD), statement,
                            source_type, day1_return_pct, prior_position}}
    watchlist     tickers whose headlines are scanned
    decay_days    days a curated mention stays relevant (default 30)
    news_scan     false disables the headline scanner

Scoring: a curated mention starts at confidence 0.65 (0.80 when the figure
held a position before the statement) and decays linearly to a floor of
0.15; anything below 0.20 is dropped. Headline hits emit once per ticker
per day at strength 0.5 and confidence 0.6.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.core.signal_framework import (
    RawSignal,
    SignalSource,
    SignalSourceMetadata,
    SignalSourceType,
    SignalType,
    register_signal_source,
)

logger = logging.getLogger(__name__)

SOURCE_ID = "public_figure_mentions"
DEFAULT_DECAY_DAYS = 30
CONFIDENCE_FLOOR = 0.15
MIN_CONFIDENCE = 0.20
NEWS_MAX_AGE_DAYS = 7


@register_signal_source(SOURCE_ID, default_enabled=True)
class PublicFigureMentionsSource(SignalSource):
    """Post-mention momentum signals for companies a tracked public figure names."""

    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="Public Figure Mentions",
            description=(
                "Momentum signals when a tracked public figure names a listed "
                "company in a public statement: a curated mention list with "
                "time decay plus a headline scan over a watchlist. The figure, "
                "keywords, mentions, and watchlist come from the source config."
            ),
            source_type=SignalSourceType.GEOPOLITICAL,
            supported_signal_types=[SignalType.NEWS_CATALYST],
            update_frequency=timedelta(minutes=30),
            reliability_score=0.6,
            data_quality_score=0.6,
            required_config=["keywords"],
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    @property
    def figure(self) -> str:
        return str(self.config.get("figure") or "tracked public figure")

    @property
    def mentions(self) -> Dict[str, dict]:
        raw = self.config.get("mentions") or {}
        return raw if isinstance(raw, dict) else {}

    @property
    def decay_days(self) -> int:
        try:
            return max(1, int(self.config.get("decay_days") or DEFAULT_DECAY_DAYS))
        except (TypeError, ValueError):
            return DEFAULT_DECAY_DAYS

    def _curated_mention_signals(self, today_key: str) -> List[RawSignal]:
        signals: List[RawSignal] = []
        now = datetime.now(timezone.utc)

        for ticker, info in self.mentions.items():
            if not isinstance(info, dict):
                continue
            try:
                mention_dt = datetime.strptime(info["mention_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, KeyError, TypeError):
                continue
            age_days = (now - mention_dt).days
            if age_days < 0:
                continue
            decay = max(0.0, 1 - age_days / self.decay_days)
            base_conf = 0.80 if info.get("prior_position") else 0.65
            confidence = round(base_conf * decay + CONFIDENCE_FLOOR, 4)
            if confidence < MIN_CONFIDENCE:
                continue

            signals.append(
                RawSignal(
                    source_id=SOURCE_ID,
                    source_type=SignalSourceType.GEOPOLITICAL,
                    timestamp=now.replace(tzinfo=None),
                    ticker=ticker,
                    raw_data={
                        "detector": "curated_mention",
                        "figure": self.figure,
                        "mention_date": info["mention_date"],
                        "statement": info.get("statement", ""),
                        "source_type": info.get("source_type"),
                        "day1_return_pct": info.get("day1_return_pct"),
                        "age_days": age_days,
                        "prior_position": bool(info.get("prior_position", False)),
                    },
                    # Re-emits daily while the decay lasts (fingerprint keyed by day)
                    metadata={"fingerprint": f"{SOURCE_ID}:{ticker}:{info['mention_date']}:{today_key}"},
                    signal_type_hint="news_catalyst",
                    direction="bullish",
                    strength=min(1.0, confidence),
                    confidence=confidence,
                    timeframe="weekly",
                )
            )
        return signals

    def _news_scan_signals(self, today_key: str) -> List[RawSignal]:
        if self.config.get("news_scan") is False:
            return []
        keywords = [str(k) for k in (self.config.get("keywords") or []) if k]
        watchlist = [str(t).upper() for t in (self.config.get("watchlist") or []) if t]
        if not keywords or not watchlist:
            return []
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("%s: yfinance not installed, skipping the headline scan", SOURCE_ID)
            return []

        signals: List[RawSignal] = []
        now = datetime.now(timezone.utc)
        for ticker in watchlist:
            if ticker in self.mentions:
                continue
            try:
                t = yf.Ticker(ticker)
                news = t.news if hasattr(t, "news") else []
                for article in news or []:
                    # yfinance changed shapes: legacy = {title, providerPublishTime};
                    # 1.x wraps everything in {content: {title, pubDate}}.
                    content = article.get("content") if isinstance(article.get("content"), dict) else None
                    title = (content or article).get("title", "") or ""
                    pub_ts = article.get("providerPublishTime", 0)
                    if pub_ts:
                        pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                    else:
                        pub_date = (content or {}).get("pubDate") or ""
                        try:
                            pub_dt = datetime.fromisoformat(str(pub_date).replace("Z", "+00:00"))
                        except ValueError:
                            continue
                    age_days = (now - pub_dt).days
                    if age_days > NEWS_MAX_AGE_DAYS:
                        continue
                    if any(kw in title for kw in keywords):
                        signals.append(
                            RawSignal(
                                source_id=SOURCE_ID,
                                source_type=SignalSourceType.GEOPOLITICAL,
                                timestamp=now.replace(tzinfo=None),
                                ticker=ticker,
                                raw_data={
                                    "detector": "news_scan",
                                    "figure": self.figure,
                                    "headline": title,
                                    "age_days": age_days,
                                },
                                metadata={"fingerprint": f"{SOURCE_ID}:news:{ticker}:{today_key}"},
                                signal_type_hint="news_catalyst",
                                direction="bullish",
                                strength=0.5,
                                confidence=0.6,
                                timeframe="daily",
                            )
                        )
                        break  # one signal per ticker per day
            except Exception as e:
                logger.debug("%s: headline scan failed for %s: %s", SOURCE_ID, ticker, e)
        return signals

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        today_key = date.today().isoformat()
        signals = self._curated_mention_signals(today_key) + self._news_scan_signals(today_key)
        logger.info("%s: %d signals", SOURCE_ID, len(signals))
        return signals
