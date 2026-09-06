"""Brokerage integration (Alpaca) for per-user trading.

Modules:
- ``crypto``     Fernet encrypt/decrypt for credentials at rest
- ``client``     Per-user Alpaca client factory (no module-level singletons)
- ``sanity``     Pre-trade screening gates (multi-user)
- ``execution``  Order construction + submission with idempotent client IDs

Safety posture:
- Paper accounts by default; live linking is an explicit opt-in
- Per-order user confirmation in v1 (no auto-execute)
- Global halt switch: ``settings.BROKER_TRADING_HALTED``
- Sanity gates fail CLOSED for live accounts, fail open only for paper
"""
