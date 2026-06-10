"""Capitol Trades plugin — REAL politician stock trades.

Ported from the earlier project's scraper (Apache 2.0,
an earlier project). Scrapes capitoltrades.com/trades (server-side
rendered HTML — no browser needed) and emits political_trade signals.

Replaces the mock PoliticianTradesSource as the registered politician
source; congress.gov leadership enrichment is intentionally omitted in the
plugin (keeps it key-free) — the 6-factor scorer port can add it later.
"""
import logging
import re
import time as time_mod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from app.core.signal_framework import (
    RawSignal,
    SignalSource,
    SignalSourceMetadata,
    SignalSourceType,
    SignalType,
    register_signal_source,
)

logger = logging.getLogger(__name__)

CAPITOL_TRADES_URL = "https://www.capitoltrades.com/trades"
SCRAPE_MAX_RETRIES = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Stonks/1.0; Research)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

SIZE_MAP = {
    "1k–15k":    (1_000, 15_000),
    "15k–50k":   (15_000, 50_000),
    "50k–100k":  (50_000, 100_000),
    "100k–250k": (100_000, 250_000),
    "250k–500k": (250_000, 500_000),
    "500k–1m":   (500_000, 1_000_000),
    "1m–5m":     (1_000_000, 5_000_000),
    "5m–25m":    (5_000_000, 25_000_000),
    "25m–50m":   (25_000_000, 50_000_000),
    "50m+":      (50_000_000, None),
    "1k - 15k":   (1_000, 15_000),
    "15k - 50k":  (15_000, 50_000),
    "50k - 100k": (50_000, 100_000),
    "100k - 250k": (100_000, 250_000),
    "250k - 500k": (250_000, 500_000),
    "500k - 1m":  (500_000, 1_000_000),
    "1m - 5m":    (1_000_000, 5_000_000),
    "5m - 25m":   (5_000_000, 25_000_000),
}

_RELATIVE_DAY_RE = re.compile(r'\b(today|yesterday)\b', re.IGNORECASE)
_DAYS_AGO_RE = re.compile(r'(\d+)\s*days?\s*ago', re.IGNORECASE)


def parse_size_range(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse Capitol Trades size range text into (min_usd, max_usd)."""
    if not text:
        return None, None
    norm = text.lower().replace("$", "").replace(",", "").strip()
    if norm in SIZE_MAP:
        return SIZE_MAP[norm]
    nums = re.findall(r'[\d.]+[kmb]?', norm)
    if not nums:
        return None, None

    def to_int(s):
        s = s.strip()
        if s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        if s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        if s.endswith('b'):
            return int(float(s[:-1]) * 1_000_000_000)
        try:
            return int(float(s))
        except ValueError:
            return None

    low = to_int(nums[0]) if nums else None
    high = to_int(nums[1]) if len(nums) > 1 else None
    return low, high


def parse_date(text: str) -> Optional[datetime]:
    """Parse Capitol Trades date strings (absolute, short, and relative forms)."""
    if not text:
        return None
    text = text.strip()

    rel = _RELATIVE_DAY_RE.search(text)
    if rel:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return today if rel.group(1).lower() == "today" else today - timedelta(days=1)

    ago = _DAYS_AGO_RE.search(text)
    if ago:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return today - timedelta(days=int(ago.group(1)))

    text = re.sub(r'^\d{1,2}:\d{2}\s+', '', text).strip()
    for fmt in ("%d %b %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.strptime(text, "%d %b").replace(year=datetime.utcnow().year)
    except ValueError:
        return None


def _parse_row(row) -> Optional[Dict]:
    """Parse a single <tr> into a trade dict (auto-detects old/new column layout)."""
    cells = row.find_all("td")
    if len(cells) < 7:
        return None

    _c4 = cells[4].get_text(strip=True).lower()
    _new_layout = bool(re.search(r'days?\s*\d+|\b\d+\s*days?\b', _c4)) or (
        not any(kw in _c4 for kw in ("spouse", "joint", "self", "child", "undisclosed"))
        and re.search(r'\d', _c4) is not None
    )
    _o = 1 if _new_layout else 0

    trade: Dict = {}

    pol_cell = cells[0]
    pol_link = pol_cell.find("a", href=re.compile(r"/politicians/"))
    if pol_link:
        href = pol_link.get("href", "")
        bg_match = re.search(r"/politicians/([A-Z]\d+)", href)
        trade["bioguide_id"] = bg_match.group(1) if bg_match else None
        trade["politician_name"] = pol_link.get_text(" ", strip=True)
    else:
        trade["politician_name"] = pol_cell.get_text(" ", strip=True).split("\n")[0].strip()
        trade["bioguide_id"] = None

    pol_text = pol_cell.get_text(" ", strip=True)
    trade["party"] = "R" if "republican" in pol_text.lower() else "D" if "democrat" in pol_text.lower() else None
    trade["chamber"] = "senate" if "senate" in pol_text.lower() else "house" if "house" in pol_text.lower() else None
    state_match = re.search(r'\b([A-Z]{2})\b', pol_text)
    trade["state"] = state_match.group(1) if state_match else None

    # Equities show "<COMPANY NAME> <TICKER>:US"; bonds/treasuries show "N/A"
    # and stay ticker-less — never guess (bond-ticker pollution lesson).
    iss_text = cells[1].get_text(" ", strip=True)
    ticker_match = re.search(r'\b([A-Z]{1,5}):US\b', iss_text)
    trade["ticker"] = ticker_match.group(1) if ticker_match else None
    company = re.sub(r'\s+[A-Z]{1,5}:US\s*$', '', iss_text).strip()
    company = re.sub(r'\s+N/A\s*$', '', company).strip()
    trade["company_name"] = company or iss_text

    trade["published_date"] = parse_date(cells[2].get_text(" ", strip=True))
    trade["traded_date"] = parse_date(cells[3].get_text(" ", strip=True))
    if trade["published_date"] and trade["traded_date"]:
        trade["filed_after_days"] = max((trade["published_date"] - trade["traded_date"]).days, 0)
    else:
        trade["filed_after_days"] = None

    owner_text = cells[4 + _o].get_text(strip=True).lower() if len(cells) > 4 + _o else ""
    for owner in ("spouse", "joint", "self", "child"):
        if owner in owner_text:
            trade["owner_type"] = owner
            break
    else:
        trade["owner_type"] = "undisclosed"

    type_text = cells[5 + _o].get_text(strip=True).lower() if len(cells) > 5 + _o else ""
    if "buy" in type_text or "purchase" in type_text:
        trade["trade_type"] = "buy"
    elif "sell" in type_text or "sale" in type_text:
        trade["trade_type"] = "sell"
    elif "exchange" in type_text:
        trade["trade_type"] = "exchange"
    else:
        trade["trade_type"] = type_text or None

    if len(cells) > 6 + _o:
        size_text = cells[6 + _o].get_text(strip=True)
        trade["size_range"] = size_text
        trade["size_min_usd"], trade["size_max_usd"] = parse_size_range(size_text)
    else:
        trade["size_range"], trade["size_min_usd"], trade["size_max_usd"] = None, None, None

    if len(cells) > 7 + _o:
        price_text = cells[7 + _o].get_text(strip=True).replace("$", "").replace(",", "").strip()
        try:
            trade["price_at_trade"] = float(price_text)
        except (ValueError, TypeError):
            trade["price_at_trade"] = None
    else:
        trade["price_at_trade"] = None

    trade_link = row.find("a", href=re.compile(r"/trades/\d+"))
    if trade_link:
        trade["trade_id"] = trade_link["href"].rstrip("/").split("/")[-1]
    else:
        parts = [trade.get("politician_name", ""), trade.get("ticker", ""),
                 str(trade.get("traded_date", "")), trade.get("trade_type", "")]
        trade["trade_id"] = "-".join(p for p in parts if p)

    return trade


def scrape_page(page: int = 1, session: Optional[requests.Session] = None) -> List[Dict]:
    """Scrape a single page of Capitol Trades with retry logic."""
    s = session or requests.Session()
    url = f"{CAPITOL_TRADES_URL}?page={page}"
    resp = None
    for attempt in range(SCRAPE_MAX_RETRIES):
        try:
            resp = s.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < SCRAPE_MAX_RETRIES - 1:
                delay = 2 ** (attempt + 1)
                logger.warning("capitol_trades page %d attempt %d failed: %s — retry in %ds", page, attempt + 1, e, delay)
                time_mod.sleep(delay)
            else:
                raise
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("table tbody tr")
    if not rows:
        logger.warning("capitol_trades: no rows on page %d — selector may have changed", page)
        return []

    trades = []
    for row in rows:
        try:
            t = _parse_row(row)
            if t and t.get("trade_id"):
                trades.append(t)
        except Exception as e:
            logger.debug("capitol_trades row parse error: %s", e)
    return trades


def _trade_to_strength(trade: Dict) -> float:
    """Signed strength: direction from buy/sell, magnitude from trade size."""
    size = trade.get("size_min_usd") or 1_000
    # 1k → ~0.25, 100k → ~0.55, 1m → ~0.8, 25m+ → 1.0
    import math
    magnitude = min(1.0, 0.25 + 0.11 * math.log10(max(size, 1_000) / 1_000))
    sign = 1 if trade.get("trade_type") == "buy" else -1 if trade.get("trade_type") == "sell" else 0
    return sign * magnitude


@register_signal_source("capitol_trades", default_enabled=True)
class CapitolTradesSource(SignalSource):
    """Real politician trades from capitoltrades.com (STOCK Act disclosures)."""

    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="Capitol Trades",
            description=(
                "Scrapes capitoltrades.com STOCK Act disclosures and emits a "
                "political_trade signal per equity trade: bullish on buys, "
                "bearish on sells, strength scaled by disclosed size."
            ),
            source_type=SignalSourceType.POLITICIAN_TRADES,
            supported_signal_types=[SignalType.POLITICAL_TRADE],
            update_frequency=timedelta(hours=6),
            reliability_score=0.9,
            data_quality_score=0.8,
            cost_per_signal=0.0,
            rate_limits={"requests_per_hour": 60},
            required_config=[],
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        num_pages = int(self.config.get("num_pages", 3))
        max_age_days = int(self.config.get("max_age_days", 14))
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)

        session = requests.Session()
        signals: List[RawSignal] = []
        consecutive_failures = 0
        for page in range(1, num_pages + 1):
            try:
                trades = scrape_page(page, session)
                consecutive_failures = 0
            except requests.RequestException as e:
                consecutive_failures += 1
                logger.warning("capitol_trades page %d failed: %s", page, e)
                if consecutive_failures >= 3:
                    break
                continue

            for trade in trades:
                # Equity trades only — treasuries/bonds have no ticker by design.
                if not trade.get("ticker") or trade.get("trade_type") not in ("buy", "sell"):
                    continue
                published = trade.get("published_date")
                if published and published < cutoff:
                    continue

                filed_after = trade.get("filed_after_days")
                # Fresher filings are more actionable: <30d filing → higher confidence.
                confidence = 0.7 if (filed_after is not None and filed_after <= 30) else 0.45
                if trade.get("owner_type") == "self":
                    confidence = min(1.0, confidence + 0.1)

                signals.append(
                    RawSignal(
                        source_id="capitol_trades",
                        source_type=SignalSourceType.POLITICIAN_TRADES,
                        timestamp=published or datetime.utcnow(),
                        ticker=trade["ticker"],
                        raw_data={
                            **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in trade.items()},
                        },
                        metadata={"fingerprint": f"capitol_trades:{trade['trade_id']}"},
                        signal_type_hint="political_trade",
                        direction="bullish" if trade["trade_type"] == "buy" else "bearish",
                        strength=_trade_to_strength(trade),
                        confidence=confidence,
                        timeframe="weekly",
                    )
                )
            if page < num_pages:
                time_mod.sleep(1.0)

        logger.info("capitol_trades: %d tradable signals from %d pages", len(signals), num_pages)
        return signals
