from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin_or_above, get_current_user
from app.database import get_db
from app.models.trade_data import Account
from app.models.admin_data import User
from app.schemas.account import AccountCreate, AccountRead

router = APIRouter()


@router.get("", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Account).all()


@router.post("", response_model=AccountRead)
def create_account(
    body: AccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    existing = db.query(Account).filter(Account.account_id == body.account_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account already exists")
    acct = Account(**body.model_dump())
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct
