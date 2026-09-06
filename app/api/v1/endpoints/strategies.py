"""Strategies API: the social spine.

Publish a strategy, follow one, read its verified track record. Privacy and
compliance rules baked in:

- Trade feeds NEVER expose dollar amounts or quantities, side/symbol/price/
  time only. Follower identities are private; counts are public.
- Public strategies REQUIRE a disclosure statement from the owner.
- Discovery ranks by objective verified metrics (never platform picks).
- copy_mode is "notify" only here; paper_auto lands in Phase 3 and
  live_auto stays hard-blocked pending RIA registration (see plan).
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func as sa_func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_user
from app.core.database import get_db
from app.models.broker_order import BrokerOrder
from app.models.strategy import STRATEGY_VISIBILITIES, Strategy, slugify
from app.models.strategy_follow import StrategyFollow
from app.models.strategy_performance import StrategyPerformanceDaily
from app.models.user import User

router = APIRouter()

DISCLAIMER = (
    "Strategies are user-published content, not investment advice. "
    "Past performance does not guarantee future results."
)


class StrategyCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: Optional[str] = Field(None, max_length=2000)
    visibility: str = Field("private", pattern="^(private|unlisted|public)$")
    disclosure: Optional[str] = Field(None, max_length=2000)


class StrategyUpdateRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=2000)
    visibility: Optional[str] = Field(None, pattern="^(private|unlisted|public)$")
    disclosure: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class FollowRequest(BaseModel):
    # live_auto is intentionally NOT accepted: live auto-copy requires RIA
    # registration or a BD/RIA partner (see plan's legal table).
    copy_mode: str = Field("notify", pattern="^(notify|paper_auto)$")
    risk_config: Optional[Dict[str, Any]] = None  # e.g. {"copy_position_pct": 0.02}


def _validate_paper_auto(db: Session, user: User) -> None:
    """paper_auto requires an active PAPER account with explicit auto_execute opt-in."""
    from app.models.user_broker_account import UserBrokerAccount

    account = (
        db.query(UserBrokerAccount)
        .filter(UserBrokerAccount.user_id == user.id, UserBrokerAccount.is_active.is_(True))
        .first()
    )
    if account is None:
        raise HTTPException(status_code=400, detail="Link a brokerage account before enabling auto-copy.")
    if not account.paper:
        raise HTTPException(
            status_code=403,
            detail="Auto-copy is available on PAPER accounts only. Live auto-copy is not offered.",
        )
    if not account.auto_execute:
        raise HTTPException(
            status_code=400,
            detail="Enable auto-execute on your paper account first (PATCH /broker/account).",
        )


def _require_disclosure_for_public(visibility: str, disclosure: Optional[str]) -> None:
    if visibility == "public" and not (disclosure or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Public strategies require a conflict-of-interest disclosure statement.",
        )


def _follower_count(db: Session, strategy_id) -> int:
    return db.query(sa_func.count(StrategyFollow.id)).filter(
        StrategyFollow.strategy_id == strategy_id
    ).scalar() or 0


def _latest_perf(db: Session, strategy_id) -> Optional[Dict[str, Any]]:
    row = (
        db.query(StrategyPerformanceDaily)
        .filter(StrategyPerformanceDaily.strategy_id == strategy_id)
        .order_by(desc(StrategyPerformanceDaily.date))
        .first()
    )
    return row.to_dict() if row else None


def _trade_feed(db: Session, strategy_id, limit: int = 50) -> List[Dict[str, Any]]:
    """Public trade feed: deliberately omits qty/notional (privacy)."""
    orders = (
        db.query(BrokerOrder)
        .filter(
            BrokerOrder.strategy_id == strategy_id,
            BrokerOrder.status.in_(["submitted", "filled", "partially_filled"]),
        )
        .order_by(desc(BrokerOrder.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "symbol": o.symbol,
            "side": o.side,
            "order_type": o.order_type,
            "status": o.status,
            "paper": o.paper,
            "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
            "at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


def _get_visible_strategy(db: Session, slug: str, user: Optional[User]) -> Strategy:
    strategy = db.query(Strategy).filter(Strategy.slug == slug).first()
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    is_owner = user is not None and strategy.owner_user_id == user.id
    if strategy.visibility == "private" and not is_owner:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.post("", status_code=201)
async def create_strategy(
    body: StrategyCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_disclosure_for_public(body.visibility, body.disclosure)

    base_slug = slugify(body.name)
    slug = base_slug
    n = 2
    while db.query(Strategy).filter(Strategy.slug == slug).first() is not None:
        slug = f"{base_slug}-{n}"
        n += 1

    strategy = Strategy(
        owner_user_id=user.id,
        name=body.name.strip(),
        slug=slug,
        description=body.description,
        visibility=body.visibility,
        kind="manual",
        disclosure=body.disclosure,
    )
    db.add(strategy)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="You already have a strategy with this name.")
    db.refresh(strategy)
    return {"strategy": strategy.to_dict(include_private=True), "disclaimer": DISCLAIMER}


@router.get("/mine")
async def my_strategies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Strategy)
        .filter(Strategy.owner_user_id == user.id)
        .order_by(desc(Strategy.created_at))
        .all()
    )
    return {
        "strategies": [
            {
                **s.to_dict(include_private=True),
                "follower_count": _follower_count(db, s.id),
                "performance": _latest_perf(db, s.id),
            }
            for s in rows
        ]
    }


@router.get("/following/mine")
async def my_follows(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(StrategyFollow, Strategy)
        .join(Strategy, Strategy.id == StrategyFollow.strategy_id)
        .filter(StrategyFollow.follower_user_id == user.id)
        .order_by(desc(StrategyFollow.created_at))
        .all()
    )
    return {
        "following": [
            {**s.to_dict(), "copy_mode": f.copy_mode, "followed_at": f.to_dict()["created_at"]}
            for f, s in rows
        ]
    }


@router.get("/public")
async def discover_strategies(db: Session = Depends(get_db)):
    """Public discovery: ranked by objective metrics only (no platform picks)."""
    rows = (
        db.query(Strategy)
        .filter(Strategy.visibility == "public", Strategy.is_active.is_(True))
        .order_by(desc(Strategy.created_at))
        .limit(100)
        .all()
    )
    out = []
    for s in rows:
        perf = _latest_perf(db, s.id)
        out.append({
            **s.to_dict(),
            "follower_count": _follower_count(db, s.id),
            "performance": perf,
        })
    # Verified-record ranking: win rate (where it exists), then followers.
    out.sort(
        key=lambda x: (
            (x["performance"] or {}).get("win_rate") or 0.0,
            x["follower_count"],
        ),
        reverse=True,
    )
    return {"strategies": out, "disclaimer": DISCLAIMER}


@router.get("/{slug}")
async def strategy_detail(
    slug: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    strategy = _get_visible_strategy(db, slug, user)
    is_owner = user is not None and strategy.owner_user_id == user.id
    is_following = False
    if user is not None:
        is_following = (
            db.query(StrategyFollow)
            .filter(
                StrategyFollow.strategy_id == strategy.id,
                StrategyFollow.follower_user_id == user.id,
            )
            .first()
            is not None
        )

    perf_series = (
        db.query(StrategyPerformanceDaily)
        .filter(StrategyPerformanceDaily.strategy_id == strategy.id)
        .order_by(desc(StrategyPerformanceDaily.date))
        .limit(60)
        .all()
    )

    return {
        "strategy": strategy.to_dict(include_private=is_owner),
        "is_owner": is_owner,
        "is_following": is_following,
        "follower_count": _follower_count(db, strategy.id),
        "performance": [p.to_dict() for p in reversed(perf_series)],
        "trades": _trade_feed(db, strategy.id),
        "disclaimer": DISCLAIMER,
    }


@router.put("/{slug}")
async def update_strategy(
    slug: str,
    body: StrategyUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = db.query(Strategy).filter(Strategy.slug == slug).first()
    if strategy is None or strategy.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Strategy not found")

    new_visibility = body.visibility or strategy.visibility
    new_disclosure = body.disclosure if body.disclosure is not None else strategy.disclosure
    _require_disclosure_for_public(new_visibility, new_disclosure)

    if body.description is not None:
        strategy.description = body.description
    if body.visibility is not None:
        strategy.visibility = body.visibility
    if body.disclosure is not None:
        strategy.disclosure = body.disclosure
    if body.is_active is not None:
        strategy.is_active = body.is_active
    db.commit()
    db.refresh(strategy)
    return {"strategy": strategy.to_dict(include_private=True)}


@router.post("/{slug}/follow", status_code=201)
async def follow_strategy(
    slug: str,
    body: FollowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = _get_visible_strategy(db, slug, user)
    if strategy.owner_user_id == user.id:
        raise HTTPException(status_code=400, detail="You can't follow your own strategy.")
    if body.copy_mode == "paper_auto":
        _validate_paper_auto(db, user)

    existing = (
        db.query(StrategyFollow)
        .filter(
            StrategyFollow.strategy_id == strategy.id,
            StrategyFollow.follower_user_id == user.id,
        )
        .first()
    )
    if existing:
        # Re-POST updates the copy mode / risk config in place.
        existing.copy_mode = body.copy_mode
        if body.risk_config is not None:
            existing.risk_config = body.risk_config
        db.commit()
        return {"following": existing.to_dict(), "disclaimer": DISCLAIMER}

    follow = StrategyFollow(
        strategy_id=strategy.id,
        follower_user_id=user.id,
        copy_mode=body.copy_mode,
        risk_config=body.risk_config,
    )
    db.add(follow)
    db.commit()
    return {"following": follow.to_dict(), "disclaimer": DISCLAIMER}


@router.delete("/{slug}/follow")
async def unfollow_strategy(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = db.query(Strategy).filter(Strategy.slug == slug).first()
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    deleted = (
        db.query(StrategyFollow)
        .filter(
            StrategyFollow.strategy_id == strategy.id,
            StrategyFollow.follower_user_id == user.id,
        )
        .delete()
    )
    db.commit()
    return {"unfollowed": bool(deleted)}
