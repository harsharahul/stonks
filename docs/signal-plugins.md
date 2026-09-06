# Signal source plugins

Stonks ingests market signals through a plugin SDK. A plugin is one Python
module that scrapes or derives a signal (politician trades, social momentum,
news catalysts, fund holdings, options flow) and emits it into the pipeline,
where it becomes visible signals, alerts, a weight in the consolidated
rankings, and context for the AI Trading Desk.

Every source is judged in public. A nightly scorer records the five-day
realized return of each signal it emitted; the source's win rate and average
return are served at `GET /api/v1/signals/sources/track-record` and shown in
the admin console. Sources with a poor record get less weight in the
rankings; sources with fewer than ten scored signals are treated as neutral.

## Bundled sources

| Plugin | What it shows |
|---|---|
| `app/signals/wsb_momentum.py` | Database-backed source reading the platform's own feature store; needs no keys |
| `app/signals/capitol_trades.py` | External scraper with retries, rate-limit handling, and a documented size-to-strength mapping |
| `app/signals/public_figure_mentions.py` | Curated event list with time decay plus a live news scanner |
| `app/signals/board_seat_tracker.py` | Board-seat and advisory positioning around a tracked public figure |
| `app/signals/fund_13f_tracker.py` | Quarterly 13F holdings of a tracked fund with filing-age decay |

## The contract

Implement `SignalSource` from `app/core/signal_framework.py` and register it:

```python
from datetime import datetime, timedelta
from typing import List, Optional

from app.core.signal_framework import (
    RawSignal, SignalSource, SignalSourceMetadata,
    SignalSourceType, SignalType, register_signal_source,
)


@register_signal_source("my_source", default_enabled=True)
class MySource(SignalSource):
    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="My Source",
            description="One sentence on what this emits and why it matters.",
            source_type=SignalSourceType.NEWS_FEEDS,
            supported_signal_types=[SignalType.NEWS_CATALYST],
            update_frequency=timedelta(hours=1),   # how often the dispatcher runs you
            reliability_score=0.7,
            data_quality_score=0.7,
            required_config=[],                    # config keys an operator must set (API keys)
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        return [RawSignal(
            source_id="my_source",
            source_type=SignalSourceType.NEWS_FEEDS,
            timestamp=datetime.utcnow(),
            ticker="AAPL",
            raw_data={"why": "the evidence behind this signal"},
            metadata={"fingerprint": "my_source:AAPL:2026-06-10"},  # dedupe key
            # Trading hints are required for the signal to be persisted:
            signal_type_hint="news_catalyst",
            direction="bullish",        # bullish | bearish | neutral
            strength=0.6,               # -1.0 to 1.0
            confidence=0.7,             # 0.0 to 1.0
            timeframe="daily",          # intraday | daily | weekly
        )]
```

Then add one import line to `app/signals/__init__.py`.

## How it runs

The Celery dispatcher in `app/tasks/signal_dispatch.py` runs every thirty
minutes and on demand from the admin console. It instantiates each enabled
plugin, calls `fetch_signals`, and persists the results with provenance
(`model_version = "plugin:<source_id>"`). Operators enable, disable, and
configure each source from the admin console; the state lives in the
`signal_source_states` table. A source whose `required_config` keys are
missing is skipped and reported as such, never crashed.

**Deduplication.** Set `metadata["fingerprint"]` to a stable identifier for
the underlying event (a trade id, a `ticker:date` pair). The dispatcher drops
fingerprints it has seen in the last 48 hours. Signals expire after 24 hours
unless re-emitted.

**Scoring.** The nightly scorer (23:45 UTC) takes every signal older than
five trading days, compares the close five days after the signal with the
close on the signal day, and records a win when the move agreed with the
signal's direction. Neutral signals are not scored.

## Review criteria for plugin pull requests

1. **No secrets in code.** API keys arrive through `self.config`, declared
   in `required_config`; never hardcoded, never logged.
2. **Be a polite client.** Respect rate limits, back off on failure (see the
   retry and circuit-breaker pattern in `capitol_trades`), declare a truthful
   User-Agent, and never bypass paywalls or authentication.
3. **Fail soft.** A plugin exception must not sink the batch. Raise freely,
   the dispatcher isolates you, but do not return partial junk.
4. **No ticker guessing.** If the instrument has no equity ticker (bonds,
   treasuries, private funds), emit nothing. `capitol_trades` documents the
   bond-pollution case.
5. **Documented scoring.** `strength` and `confidence` must derive from
   evidence in `raw_data`, and the mapping is written in the module docstring.
6. **Disclose conflicts.** If you trade what your plugin signals, say so in
   the pull request. Plugins exist to surface public information.
7. **Tests.** Pure-logic parts (parsers, scoring) get unit tests that run
   without network or database; `tests/test_signal_sdk.py` and
   `tests/test_new_signal_plugins.py` show the pattern.
8. **Neutral language.** Names and descriptions describe what is measured.
   No advice wording, no hype.
