from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_super_admin, require_admin_or_above
from app.auth.jwt import hash_password
from app.database import get_db
from app.models.admin_data import User, AuditLog
from app.schemas.user import UserCreate, UserUpdate, UserRead

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), current: User = Depends(require_admin_or_above)):
    return db.query(User).all()


@router.post("/users", response_model=UserRead)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_super_admin),
):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, hashed_password=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    db.add(AuditLog(user_id=current.id, action="create_user", entity_type="user", entity_id=user.id))
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    db.add(AuditLog(user_id=current.id, action="update_user", entity_type="user", entity_id=user_id))
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_super_admin),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.add(AuditLog(user_id=current.id, action="delete_user", entity_type="user", entity_id=user_id))
    db.commit()
