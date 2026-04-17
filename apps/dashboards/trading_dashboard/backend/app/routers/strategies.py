from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin_or_above, get_current_user
from app.database import get_db
from app.models.admin_data import Strategy, AuditLog, User
from app.schemas.strategy import StrategyCreate, StrategyUpdate, StrategyRead

router = APIRouter()


@router.get("", response_model=list[StrategyRead])
def list_strategies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Strategy).all()


@router.post("", response_model=StrategyRead)
def create_strategy(
    body: StrategyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    strategy = Strategy(**body.model_dump())
    db.add(strategy)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create_strategy", entity_type="strategy", entity_id=strategy.id))
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("/{strategy_id}", response_model=StrategyRead)
def get_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


@router.put("/{strategy_id}", response_model=StrategyRead)
def update_strategy(
    strategy_id: int,
    body: StrategyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.add(AuditLog(user_id=user.id, action="update_strategy", entity_type="strategy", entity_id=strategy_id))
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{strategy_id}", status_code=204)
def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    db.delete(s)
    db.add(AuditLog(user_id=user.id, action="delete_strategy", entity_type="strategy", entity_id=strategy_id))
    db.commit()
