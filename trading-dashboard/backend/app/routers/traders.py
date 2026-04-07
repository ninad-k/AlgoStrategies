from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin_or_above, get_current_user
from app.database import get_db
from app.models.admin_data import Trader, AuditLog, User
from app.schemas.trader import TraderCreate, TraderUpdate, TraderRead

router = APIRouter()


@router.get("", response_model=list[TraderRead])
def list_traders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Trader).all()


@router.post("", response_model=TraderRead)
def create_trader(
    body: TraderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    trader = Trader(**body.model_dump())
    db.add(trader)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create_trader", entity_type="trader", entity_id=trader.id))
    db.commit()
    db.refresh(trader)
    return trader


@router.get("/{trader_id}", response_model=TraderRead)
def get_trader(trader_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trader = db.query(Trader).filter(Trader.id == trader_id).first()
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    return trader


@router.put("/{trader_id}", response_model=TraderRead)
def update_trader(
    trader_id: int,
    body: TraderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    trader = db.query(Trader).filter(Trader.id == trader_id).first()
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(trader, k, v)
    db.add(AuditLog(user_id=user.id, action="update_trader", entity_type="trader", entity_id=trader_id))
    db.commit()
    db.refresh(trader)
    return trader


@router.delete("/{trader_id}", status_code=204)
def delete_trader(
    trader_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    if trader_id == 0:
        raise HTTPException(status_code=400, detail="Cannot delete Guest/Common trader")
    trader = db.query(Trader).filter(Trader.id == trader_id).first()
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    db.delete(trader)
    db.add(AuditLog(user_id=user.id, action="delete_trader", entity_type="trader", entity_id=trader_id))
    db.commit()
