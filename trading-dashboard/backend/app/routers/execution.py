from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin_or_above
from app.config import settings
from app.database import get_db
from app.models.admin_data import ExecutionControl, User
from app.schemas.execution import LiveTradingStatus, LiveTradingUpdate

router = APIRouter()

EXECUTION_ROW_ID = 1


def _get_or_create_row(db: Session) -> ExecutionControl:
    row = db.query(ExecutionControl).filter(ExecutionControl.id == EXECUTION_ROW_ID).first()
    if row is None:
        row = ExecutionControl(id=EXECUTION_ROW_ID, live_trading_enabled=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/mt5/live-trading", response_model=LiveTradingStatus)
def get_live_trading_for_mt5(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by MT5 Expert Advisor via WebRequest.
    Requires header: X-MT5-Token (must match server MT5_EXECUTION_SECRET).
    """
    if not settings.mt5_execution_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MT5 execution is not configured (MT5_EXECUTION_SECRET empty on server).",
        )
    token = request.headers.get("X-MT5-Token") or request.headers.get("x-mt5-token")
    if token != settings.mt5_execution_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-MT5-Token")
    row = _get_or_create_row(db)
    return LiveTradingStatus(live_trading_enabled=bool(row.live_trading_enabled))


@router.get("/live-trading", response_model=LiveTradingStatus)
def get_live_trading_for_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_above),
):
    row = _get_or_create_row(db)
    return LiveTradingStatus(live_trading_enabled=bool(row.live_trading_enabled))


@router.put("/live-trading", response_model=LiveTradingStatus)
def set_live_trading(
    body: LiveTradingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_above),
):
    row = _get_or_create_row(db)
    row.live_trading_enabled = body.live_trading_enabled
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return LiveTradingStatus(live_trading_enabled=bool(row.live_trading_enabled))
