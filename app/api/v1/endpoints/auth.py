"""
Auth endpoints — user profile management
"""
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db

router = APIRouter()

_PREFS_MAX_SIZE = 10 * 1024  # 10 KB
_PREFS_MAX_DEPTH = 3


def _check_depth(obj: Any, depth: int = 0) -> None:
    """H7: Prevent deeply nested preference payloads."""
    if depth > _PREFS_MAX_DEPTH:
        raise ValueError(f"Preferences nesting exceeds max depth of {_PREFS_MAX_DEPTH}")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_depth(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _check_depth(v, depth + 1)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

    @field_validator("preferences")
    @classmethod
    def validate_preferences(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v
        raw = json.dumps(v)
        if len(raw) > _PREFS_MAX_SIZE:
            raise ValueError(f"Preferences JSON exceeds {_PREFS_MAX_SIZE} bytes")
        _check_depth(v)
        return v


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return user.to_dict()


@router.put("/me")
async def update_me(body: UpdateProfileRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Update the current user's name or preferences."""
    from app.models.user import User

    db_user = db.query(User).filter(User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name is not None:
        db_user.name = body.name
    if body.preferences is not None:
        db_user.preferences = {**(db_user.preferences or {}), **body.preferences}
    db.commit()
    db.refresh(db_user)
    return db_user.to_dict()
