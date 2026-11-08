"""Unit tests for the FDA device clearances plugin: pure logic, fictional data, no network."""
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional

from app.signals.fda_device_clearances import (
    FDADeviceClearancesSource,
    Fundamentals,
    build_name_index,
    compute_fundamentals,
    grade_fundamentals,
    grade_to_signal,
    headline_company,
    is_clearance_headline,
    normalize_company_name,
    parse_openfda_results,
    parse_rss_items,
    resolve_ticker,
)

SEC_TICKERS = {
    "0": {"cik_str": 1111, "ticker": "AAAA", "title": "Alpha Medical, Inc."},
    "1": {"cik_str": 2222, "ticker": "BBBB", "title": "BETA-BONE CORP"},
    "2": {"cik_str": 2222, "ticker": "BBBC", "title": "Beta-Bone Corp"},  # second class, same name
    "3": {"cik_str": 3333, "ticker": "CCCC", "title": "Gamma Devices Holdings Ltd"},
}
INDEX = build_name_index(SEC_TICKERS)


def _q(end: str, val: float, start: Optional[str] = None, form: str = "10-Q"):
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    start = start or (end_d - timedelta(days=90)).isoformat()
    return {"start": start, "end": end, "val": val, "form": form}


def facts(revenue=None, net_income=None, cash=None, shares=None, investments=None):
    gaap = {}
    if revenue is not None:
        gaap["Revenues"] = {"units": {"USD": [_q(e, v) for e, v in revenue]}}
    if net_income is not None:
        gaap["NetIncomeLoss"] = {"units": {"USD": [_q(e, v) for e, v in net_income]}}
    if cash is not None:
        gaap["CashAndCashEquivalentsAtCarryingValue"] = {"units": {"USD": [{"end": e, "val": v, "form": "10-Q"} for e, v in cash]}}
    if investments is not None:
        gaap["ShortTermInvestments"] = {"units": {"USD": [{"end": e, "val": v, "form": "10-Q"} for e, v in investments]}}
    dei = {}
    if shares is not None:
        dei["EntityCommonStockSharesOutstanding"] = {"units": {"shares": [{"end": e, "val": v, "form": "10-Q"} for e, v in shares]}}
    return {"facts": {"us-gaap": gaap, "dei": dei}}


class TestNames:
    def test_normalize_drops_suffixes_and_punctuation(self):
        assert normalize_company_name("SI-BONE, Inc.") == "si bone"
        assert normalize_company_name("Gamma Devices Holdings Ltd") == "gamma devices"
        assert normalize_company_name("") == ""

    def test_first_share_class_wins(self):
        assert INDEX["beta bone"][0] == "BBBB"

    def test_headline_company(self):
        assert headline_company("Alpha Medical Receives FDA 510(k) Clearance for Widget - GlobeNewswire") == "Alpha Medical"
        assert headline_company("Beta-Bone Announces FDA Clearance of Its Screw") == "Beta-Bone"
        assert headline_company("Why device stocks rallied today") is None

    def test_clearance_filter(self):
        assert is_clearance_headline("X Receives FDA 510(k) Clearance")
        assert is_clearance_headline("X gets FDA clearance for scanner")
        assert not is_clearance_headline("X wins FDA approval for drug")

    def test_resolve_exact_name_or_exchange_tag_only(self):
        assert resolve_ticker("Alpha Medical", "", INDEX)[0] == "AAAA"
        assert resolve_ticker("Alpha", "", INDEX) is None  # no fuzzy guessing
        assert resolve_ticker("Unknown Co", "text (Nasdaq: CCCC) more", INDEX)[0] == "CCCC"
        assert resolve_ticker("Unknown Co", "text (Nasdaq: ZZZZ)", INDEX) is None


class TestParsers:
    def test_rss_keeps_clearance_headlines_with_dates(self):
        entries = [
            {"title": "Alpha Medical Receives FDA 510(k) Clearance - Wire", "link": "u1", "published": "Mon, 02 Nov 2026 13:00:00 GMT"},
            {"title": "Alpha Medical reports Q3 results", "link": "u2"},
        ]
        items = parse_rss_items(entries)
        assert [i["link"] for i in items] == ["u1"]
        assert items[0]["published"] == datetime(2026, 11, 2, 13, 0)

    def test_openfda_keeps_substantially_equivalent(self):
        rows = parse_openfda_results([
            {"applicant": "Alpha Medical, Inc.", "k_number": "K260001", "device_name": "Widget", "decision_code": "SESE", "decision_date": "2026-10-20"},
            {"applicant": "Beta-Bone Corp", "k_number": "K260002", "device_name": "Screw", "decision_code": "SN", "decision_date": "2026-10-21"},
            {"applicant": "Gamma", "k_number": "K260003", "decision_code": "SESE", "decision_date": "bad"},
        ])
        assert [r["k_number"] for r in rows] == ["K260001"]
        assert rows[0]["decision_date"] == date(2026, 10, 20)


class TestFundamentals:
    def test_growth_runway_dilution(self):
        f = compute_fundamentals(facts(
            revenue=[("2025-09-30", 10e6), ("2026-06-30", 12e6), ("2026-09-30", 13e6)],
            net_income=[("2026-06-30", -4e6), ("2026-09-30", -6e6)],
            cash=[("2026-09-30", 40e6)],
            investments=[("2026-09-30", 10e6)],
            shares=[("2025-10-30", 20e6), ("2026-10-30", 22e6)],
        ))
        assert round(f.revenue_yoy, 2) == 0.30
        assert f.cash_usd == 50e6
        assert f.runway_quarters == 10.0
        assert round(f.dilution_1y, 2) == 0.10
        assert f.complete and not f.profitable
        assert grade_fundamentals(f)[0] == "strong"

    def test_short_runway_is_weak(self):
        f = compute_fundamentals(facts(
            revenue=[("2025-09-30", 50e6), ("2026-09-30", 60e6)],
            net_income=[("2026-06-30", -14e6), ("2026-09-30", -14e6)],
            cash=[("2026-09-30", 8e6)],
            shares=[("2026-10-30", 65e6)],
        ))
        grade, reasons = grade_fundamentals(f)
        assert grade == "weak"
        assert "quarters" in reasons[0]

    def test_heavy_dilution_is_weak(self):
        f = Fundamentals(revenue_yoy=0.5, runway_quarters=10, dilution_1y=0.63, has_revenue=True, complete=True)
        assert grade_fundamentals(f)[0] == "weak"

    def test_pre_revenue_short_cash_is_weak(self):
        f = Fundamentals(runway_quarters=3, has_revenue=False, complete=True)
        assert grade_fundamentals(f)[0] == "weak"

    def test_profitable_slow_growth_is_middle(self):
        f = Fundamentals(revenue_yoy=0.08, profitable=True, has_revenue=True, complete=True)
        assert grade_fundamentals(f)[0] == "middle"

    def test_missing_cash_is_incomplete(self):
        f = compute_fundamentals(facts(revenue=[("2026-09-30", 1e6)], net_income=[("2026-09-30", -1e6)]))
        assert grade_fundamentals(f)[0] == "incomplete"

    def test_grade_to_signal_mapping(self):
        assert grade_to_signal("strong", 0.5)[:3] == ("bullish", 0.7, 0.6)
        assert grade_to_signal("strong", 0.25)[1] == 0.6
        assert grade_to_signal("weak", None)[:2] == ("bearish", -0.4)
        assert grade_to_signal("middle", None)[:2] == ("bullish", 0.25)
        assert grade_to_signal("incomplete", None)[:2] == ("neutral", 0.0)


class FakeSource(FDADeviceClearancesSource):
    """Network-free source: canned news, FDA rows, facts and prices."""

    def __init__(self, config, news=(), fda=(), facts_by_cik=None, prices=None, recent=()):
        super().__init__(config)
        self._news, self._fda = list(news), list(fda)
        self._facts, self._prices, self._recent = facts_by_cik or {}, prices or {}, set(recent)

    def name_index(self):
        return INDEX

    def fetch_news_items(self, lookback_days):
        return self._news

    def fetch_openfda_rows(self, lookback_days):
        return self._fda

    def fetch_facts(self, cik):
        return self._facts.get(cik)

    def last_price(self, ticker):
        return self._prices.get(ticker)

    def recently_signalled(self, tickers, days):
        return self._recent & set(tickers)


STRONG = facts(
    revenue=[("2025-09-30", 10e6), ("2026-09-30", 15e6)],
    net_income=[("2026-06-30", -5e6), ("2026-09-30", -5e6)],
    cash=[("2026-09-30", 60e6)],
    shares=[("2025-10-30", 30e6), ("2026-10-30", 31e6)],
)
WEAK = facts(
    revenue=[("2025-09-30", 10e6), ("2026-09-30", 10e6)],
    net_income=[("2026-06-30", -9e6), ("2026-09-30", -9e6)],
    cash=[("2026-09-30", 5e6)],
    shares=[("2026-10-30", 40e6)],
)


class TestFetchSignals:
    def _news(self, title, days_ago=0):
        return {"title": title, "summary": "", "link": "https://example.com/pr",
                "published": datetime.utcnow() - timedelta(days=days_ago)}

    def test_press_release_strong_company_is_bullish(self):
        src = FakeSource({}, news=[self._news("Alpha Medical Receives FDA 510(k) Clearance - Wire")],
                         facts_by_cik={1111: STRONG}, prices={"AAAA": 10.0})
        sigs = asyncio.run(src.fetch_signals())
        assert len(sigs) == 1
        s = sigs[0]
        assert (s.ticker, s.direction, s.signal_type_hint, s.timeframe) == ("AAAA", "bullish", "news_catalyst", "weekly")
        assert s.raw_data["grade"] == "strong" and s.raw_data["discovered_via"] == "press_release"
        assert s.raw_data["market_cap_usd"] == 310_000_000
        assert s.metadata["fingerprint"].startswith("fda_device_clearances:AAAA:")

    def test_fda_row_weak_company_is_bearish(self):
        src = FakeSource({}, fda=[{"applicant": "Beta-Bone Corp", "k_number": "K260002", "device_name": "Screw", "decision_date": date.today()}],
                         facts_by_cik={2222: WEAK}, prices={"BBBB": 2.0})
        s = asyncio.run(src.fetch_signals())[0]
        assert (s.ticker, s.direction, s.strength) == ("BBBB", "bearish", -0.4)
        assert s.raw_data["k_number"] == "K260002"
        assert s.metadata["fingerprint"] == "fda_device_clearances:BBBB:K260002"

    def test_large_cap_stale_news_and_repeats_are_skipped(self):
        src = FakeSource(
            {"max_market_cap_usd": 1_000_000_000},
            news=[
                self._news("Alpha Medical Receives FDA 510(k) Clearance", days_ago=0),
                self._news("Gamma Devices Receives FDA Clearance", days_ago=10),  # older than lookback
            ],
            fda=[{"applicant": "Beta-Bone Corp", "k_number": "K1", "device_name": "x", "decision_date": date.today()}],
            facts_by_cik={1111: STRONG, 2222: WEAK, 3333: STRONG},
            prices={"AAAA": 1000.0, "BBBB": 2.0, "CCCC": 5.0},  # AAAA is 31 B market cap
            recent={"BBBB"},
        )
        assert asyncio.run(src.fetch_signals()) == []

    def test_unmatched_company_emits_nothing(self):
        src = FakeSource({}, news=[self._news("Private Startup Receives FDA 510(k) Clearance")])
        assert asyncio.run(src.fetch_signals()) == []

    def test_sources_can_be_switched_off(self):
        src = FakeSource({"use_news": "false", "use_openfda": False},
                         news=[self._news("Alpha Medical Receives FDA 510(k) Clearance")],
                         facts_by_cik={1111: STRONG}, prices={"AAAA": 10.0})
        assert asyncio.run(src.fetch_signals()) == []

    def test_metadata_needs_no_keys(self):
        meta = FDADeviceClearancesSource({}).get_metadata()
        assert meta.required_config == []
        assert asyncio.run(FDADeviceClearancesSource({}).validate_config()) == []
