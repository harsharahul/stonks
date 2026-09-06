"""Single source of the application version: the VERSION file at the repo root."""
from pathlib import Path

_candidates = (
    Path(__file__).resolve().parents[2] / "VERSION",  # repo checkout
    Path("/app/VERSION"),  # container image
)


def _read() -> str:
    for p in _candidates:
        try:
            return p.read_text().strip()
        except OSError:
            continue
    return "0.0.0"


__version__ = _read()
