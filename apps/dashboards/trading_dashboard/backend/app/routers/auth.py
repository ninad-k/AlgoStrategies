from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.orm import Session

from app.auth.jwt import (
    verify_password, create_access_token,
    create_refresh_token, hash_refresh_token, refresh_token_expiry,
)
from app.database import get_db
from app.models.admin_data import User, RefreshToken
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()

COOKIE_NAME = "refresh_token"
COOKIE_MAX_AGE = 7 * 24 * 3600


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.is_active == True).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(user.email, user.role)
    raw_refresh, hashed_refresh = create_refresh_token()
    expires = refresh_token_expiry()

    db.add(RefreshToken(user_id=user.id, token_hash=hashed_refresh, expires_at=expires))
    db.commit()

    response.set_cookie(
        key=COOKIE_NAME, value=raw_refresh,
        httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE,
    )
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str = Cookie(default=None, alias=COOKIE_NAME),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    hashed = hash_refresh_token(refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hashed,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc),
    ).first()

    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    stored.revoked = True

    raw_new, hashed_new = create_refresh_token()
    expires = refresh_token_expiry()
    db.add(RefreshToken(user_id=stored.user_id, token_hash=hashed_new, expires_at=expires))
    db.commit()

    user = db.query(User).filter(User.id == stored.user_id).first()
    access_token = create_access_token(user.email, user.role)

    response.set_cookie(
        key=COOKIE_NAME, value=raw_new,
        httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE,
    )
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str = Cookie(default=None, alias=COOKIE_NAME),
):
    if refresh_token:
        hashed = hash_refresh_token(refresh_token)
        stored = db.query(RefreshToken).filter(RefreshToken.token_hash == hashed).first()
        if stored:
            stored.revoked = True
            db.commit()
    response.delete_cookie(COOKIE_NAME)
