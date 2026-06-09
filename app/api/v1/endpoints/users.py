"""
User-specific endpoints: watchlist and alert subscriptions
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_current_user
from app.core.database import get_db

router = APIRouter()

# H4: Reusable path parameter for stock symbols
_SYMBOL_PATH = Path(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

class AddWatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")
    notes: Optional[str] = Field(None, max_length=500)  # M5


class UpdateWatchlistNotesRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)  # M5


@router.get("/me/watchlist")
async def get_watchlist(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current user's watchlist with stock details."""
    from app.models.watchlist import WatchlistItem

    items = (
        db.query(WatchlistItem)
        .options(joinedload(WatchlistItem.stock))
        .filter(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )
    return {
        "watchlist": [item.to_dict() for item in items],
        "count": len(items),
    }


@router.post("/me/watchlist", status_code=201)
async def add_to_watchlist(body: AddWatchlistRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a stock to the user's watchlist by symbol."""
    from app.models.watchlist import WatchlistItem
    from app.models.stock import Stock

    stock = db.query(Stock).filter(Stock.symbol == body.symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{body.symbol}' not found")

    item = WatchlistItem(
        user_id=user.id,
        stock_id=stock.id,
        notes=body.notes,
    )
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
        item.stock = stock
        return item.to_dict()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"'{body.symbol}' is already in your watchlist")


@router.delete("/me/watchlist/{symbol}", status_code=200)
async def remove_from_watchlist(
    symbol: str = _SYMBOL_PATH,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a stock from the user's watchlist by symbol."""
    from app.models.watchlist import WatchlistItem
    from app.models.stock import Stock

    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")

    deleted = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.stock_id == stock.id)
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"'{symbol}' is not in your watchlist")
    return {"removed": True, "symbol": symbol.upper()}


@router.patch("/me/watchlist/{symbol}")
async def update_watchlist_notes(
    body: UpdateWatchlistNotesRequest,
    symbol: str = _SYMBOL_PATH,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update notes for a watchlist item."""
    from app.models.watchlist import WatchlistItem
    from app.models.stock import Stock

    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")

    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.stock_id == stock.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"'{symbol}' is not in your watchlist")

    item.notes = body.notes
    db.commit()
    db.refresh(item)
    item.stock = stock
    return item.to_dict()


# ---------------------------------------------------------------------------
# Alert subscriptions (user-specific)
# ---------------------------------------------------------------------------

class CreateAlertSubscriptionRequest(BaseModel):
    ticker: Optional[str] = None  # None = all tickers
    alert_types: List[str]
    delivery_methods: List[str] = ["websocket"]
    thresholds: Optional[dict] = None


@router.get("/me/alerts")
async def get_alert_subscriptions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """List the current user's alert subscriptions."""
    from app.models.alert import AlertSubscription

    subs = (
        db.query(AlertSubscription)
        .filter(AlertSubscription.user_id == user.id)
        .all()
    )
    return {"subscriptions": [s.to_dict() for s in subs], "count": len(subs)}


@router.post("/me/alerts", status_code=201)
async def create_alert_subscription(
    body: CreateAlertSubscriptionRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new alert subscription for the current user."""
    from app.models.alert import AlertSubscription

    sub = AlertSubscription(
        user_id=user.id,
        ticker=body.ticker.upper() if body.ticker else None,
        alert_types=body.alert_types,
        delivery_methods=body.delivery_methods,
        thresholds=body.thresholds,
        active=True,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub.to_dict()


@router.delete("/me/alerts/{subscription_id}", status_code=200)
async def delete_alert_subscription(
    subscription_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an alert subscription."""
    from app.models.alert import AlertSubscription

    deleted = (
        db.query(AlertSubscription)
        .filter(AlertSubscription.id == subscription_id, AlertSubscription.user_id == user.id)
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"deleted": True, "id": subscription_id}
