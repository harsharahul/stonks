"""FDA device clearances plugin: small-cap 510(k) clearances, graded by fundamentals.

Emits a ``news_catalyst`` signal when a listed small-cap company receives an
FDA 510(k) device clearance, then grades the company on its own SEC filings
(sales growth, cash runway, share dilution). The nightly scorer then keeps a
public track record of whether these clearances were followed by a move in
the graded direction. Needs no API key.

Discovery (both are public and keyless):
    1. Company press releases found through the Google News RSS search for
       "510(k)" / "FDA clearance" headlines. This is the fast path: most
       companies announce within a few days of the FDA decision.
    2. openFDA's 510(k) dataset (decision code SESE, substantially
       equivalent). Slower (openFDA refreshes about monthly), but it also
       catches clearances a company never announced.

A clearance is matched to an equity ticker only when the company name, after
removing legal suffixes, equals a name in the SEC ticker list, or when the
headline carries an explicit exchange tag such as ``(Nasdaq: ABCD)``. No
fuzzy guessing; unmatched clearances emit nothing.

Fundamentals (SEC XBRL company facts):
    revenue_yoy      latest quarterly revenue vs the same quarter a year earlier
    runway_quarters  (cash + short-term investments) / average quarterly net
                     loss of the last two quarters; None when profitable
    dilution_1y      shares outstanding now vs about one year earlier

Grade and signal mapping:
    strong      revenue_yoy >= 20 %, profitable or runway >= 6 quarters, and
                dilution_1y <= 25 %
                -> bullish, strength 0.6 (0.7 when revenue_yoy >= 40 %), confidence 0.6
    weak        runway < 2 quarters, or dilution_1y > 40 %, or no revenue with
                runway < 4 quarters
                -> bearish (new shares likely), strength -0.4, confidence 0.5
    middle      anything else with complete data
                -> bullish, strength 0.25, confidence 0.35
    incomplete  no cash or no net income in the filings
                -> neutral, strength 0, confidence 0.2 (shown, not scored)

Config keys (all optional):
    max_market_cap_usd     upper size bound (default 2_000_000_000)
    min_market_cap_usd     lower size bound (default 0)
    news_lookback_days     how far back press releases count (default 3)
    fda_lookback_days      how far back openFDA decisions count (default 35)
    repeat_window_days     skip a ticker this plugin already signalled within
                           this many days (default 45)
    max_companies_per_run  cap on graded companies per run (default 25)
    use_news               search press releases (default true)
    use_openfda            read the openFDA dataset (default true)
    sec_contact            contact address for the SEC User-Agent; falls back
                           to the SEC_CONTACT_EMAIL setting
"""
import logging
import re
import time as time_mod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import requests

from app.core.signal_framework import (
    RawSignal,
    SignalSource,
    SignalSourceMetadata,
    SignalSourceType,
    SignalType,
    register_signal_source,
)

logger = logging.getLogger(__name__)

SOURCE_ID = "fda_device_clearances"

OPENFDA_510K_URL = "https://api.fda.gov/device/510k.json"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

NEWS_QUERIES = ('"510(k)" clearance', '"FDA clearance" device')

DEFAULT_MAX_CAP = 2_000_000_000
DEFAULT_NEWS_LOOKBACK_DAYS = 3
DEFAULT_FDA_LOOKBACK_DAYS = 35
DEFAULT_REPEAT_WINDOW_DAYS = 45
DEFAULT_MAX_COMPANIES = 25
HTTP_TIMEOUT = 30
TICKER_CACHE_TTL = 24 * 3600

_LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited",
    "llc", "plc", "nv", "sa", "ag", "se", "lp", "holdings", "holding", "group", "the",
}
_CLEARANCE_RE = re.compile(r"510\s*\(\s*k\s*\)|\bfda[\s-]+clear(?:ance|ed|s)?\b", re.IGNORECASE)
_EXCHANGE_TAG_RE = re.compile(r"\((?:nasdaq|nyse|nyse american|nyse mkt|amex)\s*:\s*([A-Z]{1,5})\)", re.IGNORECASE)
_HEADLINE_VERB_RE = re.compile(
    r"^(.{2,80}?)\s+(?:receives?|announces?|granted|secures?|obtains?|gets?|earns?|wins?|"
    r"achieves?|lands?|awarded|receiving|has received|received)\b",
    re.IGNORECASE,
)
_REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
)
_CASH_TAGS = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "Cash",
)
_SHORT_TERM_INVESTMENT_TAGS = (
    "ShortTermInvestments",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "MarketableSecuritiesCurrent",
)

_ticker_cache: Dict[str, Any] = {"at": 0.0, "by_name": {}}


# --------------------------------------------------------------------------
# Pure helpers (unit tested without network)
# --------------------------------------------------------------------------

def normalize_company_name(name: str) -> str:
    """Lowercase, drop punctuation and legal suffixes: 'SI-BONE, Inc.' -> 'si bone'."""
    if not name:
        return ""
    text = name.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w not in _LEGAL_SUFFIXES]
    return " ".join(words).strip()


def build_name_index(sec_tickers: Dict[str, dict]) -> Dict[str, Tuple[str, int, str]]:
    """Map normalized company name -> (ticker, cik, title) from SEC company_tickers.json.

    The SEC file lists the largest share class first, so the first ticker seen
    for a name wins.
    """
    index: Dict[str, Tuple[str, int, str]] = {}
    rows: Iterable[dict] = sec_tickers.values() if isinstance(sec_tickers, dict) else sec_tickers
    for row in rows:
        try:
            ticker = str(row["ticker"]).upper()
            cik = int(row["cik_str"])
            title = str(row["title"])
        except (KeyError, TypeError, ValueError):
            continue
        key = normalize_company_name(title)
        if key and key not in index:
            index[key] = (ticker, cik, title)
    return index


def headline_company(title: str) -> Optional[str]:
    """Company name at the start of a press-release headline, or None."""
    if not title:
        return None
    clean = re.split(r"\s+[-|]\s+[^-|]+$", title.strip())[0]  # drop " - GlobeNewswire"
    match = _HEADLINE_VERB_RE.match(clean)
    return match.group(1).strip(" ,:'\"") if match else None


def is_clearance_headline(text: str) -> bool:
    return bool(text and _CLEARANCE_RE.search(text))


def resolve_ticker(name: Optional[str], text: str, index: Dict[str, Tuple[str, int, str]]) -> Optional[Tuple[str, int, str]]:
    """Exact normalized-name match, or an explicit '(Nasdaq: TICK)' tag. No guessing."""
    tag = _EXCHANGE_TAG_RE.search(text or "")
    if tag:
        ticker = tag.group(1).upper()
        for value in index.values():
            if value[0] == ticker:
                return value
    key = normalize_company_name(name or "")
    if key and key in index:
        return index[key]
    return None


def parse_rss_items(feed_entries: Iterable[dict]) -> List[dict]:
    """Keep clearance headlines; return dicts with title, link, published (datetime|None)."""
    items = []
    for entry in feed_entries:
        title = (entry.get("title") or "").strip()
        summary = entry.get("summary") or ""
        if not is_clearance_headline(title):
            continue
        published = None
        raw_date = entry.get("published") or entry.get("updated")
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date).replace(tzinfo=None)
            except (TypeError, ValueError):
                published = None
        items.append({"title": title, "summary": summary, "link": entry.get("link"), "published": published})
    return items


def parse_openfda_results(results: Iterable[dict]) -> List[dict]:
    """openFDA 510(k) rows -> dicts with applicant, k_number, device_name, decision_date."""
    rows = []
    for r in results:
        if (r.get("decision_code") or "").upper() not in ("SESE", "SESD", "SESP", "SESU", "SESK"):
            continue
        try:
            decided = datetime.strptime(r.get("decision_date", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        rows.append({
            "applicant": r.get("applicant") or "",
            "k_number": r.get("k_number") or "",
            "device_name": (r.get("device_name") or "").strip(),
            "decision_date": decided,
        })
    return rows


def _units(facts: dict, namespace: str, tag: str, unit: str) -> List[dict]:
    try:
        return list(facts["facts"][namespace][tag]["units"][unit])
    except (KeyError, TypeError):
        return []


def _days(start: str, end: str) -> int:
    return (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days


def _quarterly(facts: dict, tags: Iterable[str]) -> List[Tuple[date, float]]:
    """Quarter-length (80-100 day) duration values for the first tag that has any."""
    for tag in tags:
        out: Dict[date, float] = {}
        for row in _units(facts, "us-gaap", tag, "USD"):
            start, end = row.get("start"), row.get("end")
            if not start or not end or row.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
                continue
            if 80 <= _days(start, end) <= 100:
                out[datetime.strptime(end, "%Y-%m-%d").date()] = float(row["val"])
        if out:
            return sorted(out.items())
    return []


def _instant(facts: dict, namespace: str, tags: Iterable[str], unit: str = "USD") -> List[Tuple[date, float]]:
    for tag in tags:
        out: Dict[date, float] = {}
        for row in _units(facts, namespace, tag, unit):
            if row.get("end") and "start" not in row:
                out[datetime.strptime(row["end"], "%Y-%m-%d").date()] = float(row["val"])
        if out:
            return sorted(out.items())
    return []


def _year_earlier(series: List[Tuple[date, float]], when: date) -> Optional[float]:
    target = when - timedelta(days=365)
    best = None
    for d, v in series:
        if abs((d - target).days) <= 20:
            best = v
    return best


@dataclass
class Fundamentals:
    revenue_yoy: Optional[float] = None
    runway_quarters: Optional[float] = None   # None = profitable or unknown (see profitable)
    profitable: bool = False
    dilution_1y: Optional[float] = None
    has_revenue: bool = False
    shares_outstanding: Optional[float] = None
    cash_usd: Optional[float] = None
    complete: bool = False
    reasons: List[str] = field(default_factory=list)


def compute_fundamentals(facts: dict) -> Fundamentals:
    f = Fundamentals()
    revenue = _quarterly(facts, _REVENUE_TAGS)
    if revenue:
        last_end, last_val = revenue[-1]
        f.has_revenue = last_val > 0
        prior = _year_earlier(revenue, last_end)
        if prior and prior > 0:
            f.revenue_yoy = last_val / prior - 1.0

    net_income = _quarterly(facts, ("NetIncomeLoss",))
    cash = _instant(facts, "us-gaap", _CASH_TAGS)
    investments = _instant(facts, "us-gaap", _SHORT_TERM_INVESTMENT_TAGS)
    shares = _instant(facts, "dei", ("EntityCommonStockSharesOutstanding",), unit="shares")

    if cash:
        cash_date, cash_val = cash[-1]
        extra = dict(investments).get(cash_date, 0.0)
        f.cash_usd = cash_val + extra
    if shares:
        f.shares_outstanding = shares[-1][1]
        prior = _year_earlier(shares, shares[-1][0])
        if prior and prior > 0:
            f.dilution_1y = shares[-1][1] / prior - 1.0

    if net_income and f.cash_usd is not None:
        last_two = [v for _, v in net_income[-2:]]
        avg = sum(last_two) / len(last_two)
        if avg >= 0:
            f.profitable = True
        else:
            f.runway_quarters = f.cash_usd / -avg
        f.complete = True
    return f


def grade_fundamentals(f: Fundamentals) -> Tuple[str, List[str]]:
    """Return (grade, reasons). Grades: strong | middle | weak | incomplete."""
    if not f.complete:
        return "incomplete", ["cash or net income missing from SEC filings"]
    reasons: List[str] = []
    runway = None if f.profitable else f.runway_quarters
    if runway is not None and runway < 2:
        reasons.append(f"cash covers about {runway:.1f} quarters of losses")
    if f.dilution_1y is not None and f.dilution_1y > 0.40:
        reasons.append(f"shares outstanding up {f.dilution_1y:.0%} in a year")
    if not f.has_revenue and runway is not None and runway < 4:
        reasons.append("no product revenue and under a year of cash")
    if reasons:
        return "weak", reasons
    growth_ok = f.revenue_yoy is not None and f.revenue_yoy >= 0.20
    cash_ok = f.profitable or (runway is not None and runway >= 6)
    dilution_ok = f.dilution_1y is None or f.dilution_1y <= 0.25
    if growth_ok and cash_ok and dilution_ok:
        reasons.append(f"revenue up {f.revenue_yoy:.0%} year over year")
        reasons.append("profitable" if f.profitable else f"cash covers about {runway:.0f} quarters")
        return "strong", reasons
    if f.revenue_yoy is not None:
        reasons.append(f"revenue {f.revenue_yoy:+.0%} year over year")
    reasons.append("profitable" if f.profitable else f"cash covers about {runway:.1f} quarters" if runway is not None else "runway unknown")
    return "middle", reasons


def grade_to_signal(grade: str, revenue_yoy: Optional[float]) -> Tuple[str, float, float, int]:
    """(direction, strength, confidence, priority) for a grade; see the module docstring."""
    if grade == "strong":
        strength = 0.7 if (revenue_yoy or 0) >= 0.40 else 0.6
        return "bullish", strength, 0.6, 7
    if grade == "weak":
        return "bearish", -0.4, 0.5, 5
    if grade == "middle":
        return "bullish", 0.25, 0.35, 5
    return "neutral", 0.0, 0.2, 3


# --------------------------------------------------------------------------
# The plugin
# --------------------------------------------------------------------------

@register_signal_source(SOURCE_ID, default_enabled=True)
class FDADeviceClearancesSource(SignalSource):
    """Small-cap FDA 510(k) clearances, graded by the company's SEC fundamentals."""

    def get_metadata(self) -> SignalSourceMetadata:
        return SignalSourceMetadata(
            name="FDA Device Clearances",
            description=(
                "Small-cap companies that received an FDA 510(k) device clearance, "
                "found in press releases and the openFDA dataset, graded by sales "
                "growth, cash runway, and share dilution from SEC filings."
            ),
            source_type=SignalSourceType.REGULATORY,
            supported_signal_types=[SignalType.NEWS_CATALYST, SignalType.REGULATORY_CHANGE],
            update_frequency=timedelta(hours=6),
            reliability_score=0.6,
            data_quality_score=0.8,
            required_config=[],
        )

    async def configure(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    # ---- config helpers ---------------------------------------------------

    def _num(self, key: str, default: float) -> float:
        try:
            return float(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    def _flag(self, key: str, default: bool = True) -> bool:
        value = self.config.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() not in ("0", "false", "no", "off")
        return bool(value)

    def _sec_headers(self) -> Dict[str, str]:
        contact = self.config.get("sec_contact")
        if not contact:
            try:
                from app.core.config import settings
                contact = settings.SEC_CONTACT_EMAIL
            except Exception:  # pragma: no cover - settings import failure
                contact = ""
        contact = contact or "contact@example.com"
        return {"User-Agent": f"Stonks/1.0 (research; {contact})", "From": contact, "Accept": "application/json"}

    # ---- network (overridable in tests) -------------------------------------

    def _get(self, url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[requests.Response]:
        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, headers=headers or {}, timeout=HTTP_TIMEOUT)
            except requests.RequestException as e:
                logger.warning("%s: GET %s failed (%s)", SOURCE_ID, url, type(e).__name__)
                time_mod.sleep(2 ** attempt)
                continue
            if resp.status_code == 404:
                return None
            if resp.status_code in (429, 500, 502, 503, 504):
                time_mod.sleep(2 ** (attempt + 1))
                continue
            return resp if resp.ok else None
        return None

    def name_index(self) -> Dict[str, Tuple[str, int, str]]:
        now = time_mod.time()
        if _ticker_cache["by_name"] and now - _ticker_cache["at"] < TICKER_CACHE_TTL:
            return _ticker_cache["by_name"]
        resp = self._get(SEC_TICKERS_URL, headers=self._sec_headers())
        if resp is None:
            return _ticker_cache["by_name"]
        _ticker_cache["by_name"] = build_name_index(resp.json())
        _ticker_cache["at"] = now
        return _ticker_cache["by_name"]

    def fetch_news_items(self, lookback_days: int) -> List[dict]:
        import feedparser

        items: List[dict] = []
        for query in NEWS_QUERIES:
            params = {"q": f"{query} when:{max(1, lookback_days)}d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
            resp = self._get(GOOGLE_NEWS_RSS, params=params, headers={"User-Agent": "Mozilla/5.0 (compatible; Stonks/1.0; Research)"})
            if resp is None:
                continue
            items.extend(parse_rss_items(feedparser.parse(resp.content).entries))
        return items

    def fetch_openfda_rows(self, lookback_days: int) -> List[dict]:
        end = date.today()
        start = end - timedelta(days=lookback_days)
        search = f"decision_date:[{start:%Y%m%d} TO {end:%Y%m%d}]"
        rows: List[dict] = []
        for skip in range(0, 5000, 1000):
            resp = self._get(OPENFDA_510K_URL, params={"search": search, "limit": 1000, "skip": skip})
            if resp is None:
                break
            results = resp.json().get("results", [])
            rows.extend(parse_openfda_results(results))
            if len(results) < 1000:
                break
        return rows

    def fetch_facts(self, cik: int) -> Optional[dict]:
        resp = self._get(SEC_FACTS_URL.format(cik=cik), headers=self._sec_headers())
        time_mod.sleep(0.15)  # stay far under the SEC's 10 requests per second
        return resp.json() if resp is not None else None

    def last_price(self, ticker: str) -> Optional[float]:
        try:
            import yfinance as yf

            hist = yf.Ticker(ticker).history(period="5d")
            return float(hist["Close"].iloc[-1]) if not hist.empty else None
        except Exception as e:
            logger.info("%s: no price for %s (%s)", SOURCE_ID, ticker, type(e).__name__)
            return None

    def recently_signalled(self, tickers: Iterable[str], days: int) -> set:
        """Tickers this plugin already signalled within ``days`` (fail-soft: empty set)."""
        tickers = list(tickers)
        if not tickers:
            return set()
        try:
            from sqlalchemy import select

            from app.core.database import SessionLocal
            from app.models.signal import Signal

            cutoff = datetime.utcnow() - timedelta(days=days)
            with SessionLocal() as db:
                rows = db.execute(
                    select(Signal.ticker).where(
                        Signal.model_version == f"plugin:{SOURCE_ID}",
                        Signal.ticker.in_(tickers),
                        Signal.generated_at >= cutoff,
                    )
                ).scalars().all()
            return {t.upper() for t in rows}
        except Exception as e:
            logger.info("%s: repeat check unavailable (%s)", SOURCE_ID, type(e).__name__)
            return set()

    # ---- main ---------------------------------------------------------------

    def collect_events(self, index: Dict[str, Tuple[str, int, str]]) -> Dict[str, dict]:
        """Clearance events keyed by ticker (press release wins over the FDA row)."""
        events: Dict[str, dict] = {}
        if self._flag("use_news"):
            lookback = int(self._num("news_lookback_days", DEFAULT_NEWS_LOOKBACK_DAYS))
            cutoff = datetime.utcnow() - timedelta(days=lookback)
            for item in self.fetch_news_items(lookback):
                if item["published"] and item["published"] < cutoff:
                    continue
                match = resolve_ticker(headline_company(item["title"]), f"{item['title']} {item['summary']}", index)
                if not match or match[0] in events:
                    continue
                events[match[0]] = {
                    "ticker": match[0], "cik": match[1], "company": match[2],
                    "discovered_via": "press_release", "headline": item["title"], "url": item["link"],
                    "published": item["published"].isoformat() if item["published"] else None,
                }
        if self._flag("use_openfda"):
            for row in self.fetch_openfda_rows(int(self._num("fda_lookback_days", DEFAULT_FDA_LOOKBACK_DAYS))):
                match = resolve_ticker(row["applicant"], "", index)
                if not match:
                    continue
                event = events.get(match[0])
                if event is None:
                    events[match[0]] = event = {
                        "ticker": match[0], "cik": match[1], "company": match[2],
                        "discovered_via": "fda_database",
                    }
                event.setdefault("k_number", row["k_number"])
                event.setdefault("device_name", row["device_name"])
                event.setdefault("decision_date", row["decision_date"].isoformat())
        return events

    async def fetch_signals(self, since: Optional[datetime] = None) -> List[RawSignal]:
        index = self.name_index()
        if not index:
            logger.warning("%s: SEC ticker list unavailable, emitting nothing", SOURCE_ID)
            return []
        events = self.collect_events(index)
        repeat_days = int(self._num("repeat_window_days", DEFAULT_REPEAT_WINDOW_DAYS))
        already = self.recently_signalled(events.keys(), repeat_days)
        max_cap = self._num("max_market_cap_usd", DEFAULT_MAX_CAP)
        min_cap = self._num("min_market_cap_usd", 0)
        budget = int(self._num("max_companies_per_run", DEFAULT_MAX_COMPANIES))

        signals: List[RawSignal] = []
        for ticker, event in events.items():
            if ticker in already or budget <= 0:
                continue
            facts = self.fetch_facts(event["cik"])
            if not facts:
                continue
            fundamentals = compute_fundamentals(facts)
            if not fundamentals.shares_outstanding:
                continue
            price = self.last_price(ticker)
            if not price:
                continue
            market_cap = fundamentals.shares_outstanding * price
            if market_cap > max_cap or market_cap < min_cap:
                continue
            budget -= 1
            grade, reasons = grade_fundamentals(fundamentals)
            direction, strength, confidence, priority = grade_to_signal(grade, fundamentals.revenue_yoy)
            event_key = event.get("k_number") or event.get("published") or date.today().isoformat()
            signals.append(
                RawSignal(
                    source_id=SOURCE_ID,
                    source_type=SignalSourceType.REGULATORY,
                    timestamp=datetime.utcnow(),
                    ticker=ticker,
                    priority=priority,
                    raw_data={
                        **event,
                        "last_price": round(price, 4),
                        "market_cap_usd": round(market_cap),
                        "grade": grade,
                        "grade_reasons": reasons,
                        "revenue_yoy": None if fundamentals.revenue_yoy is None else round(fundamentals.revenue_yoy, 4),
                        "runway_quarters": None if fundamentals.runway_quarters is None else round(fundamentals.runway_quarters, 2),
                        "profitable": fundamentals.profitable,
                        "dilution_1y": None if fundamentals.dilution_1y is None else round(fundamentals.dilution_1y, 4),
                    },
                    metadata={"fingerprint": f"{SOURCE_ID}:{ticker}:{event_key}"},
                    signal_type_hint="news_catalyst",
                    direction=direction,
                    strength=strength,
                    confidence=confidence,
                    timeframe="weekly",
                )
            )
        logger.info("%s: %d events, %d signals", SOURCE_ID, len(events), len(signals))
        return signals
