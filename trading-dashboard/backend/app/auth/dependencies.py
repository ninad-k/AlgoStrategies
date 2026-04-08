from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.models.admin_data import User

bearer_scheme = HTTPBearer()

ROLE_HIERARCHY = {
    "super_admin": 5,
    "admin": 4,
    "editor": 3,
    "viewer": 2,
    "trader": 1,
}


def _get_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user(user: User = Depends(_get_user_from_token)) -> User:
    return user


def require_role(min_role: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if ROLE_HIERARCHY.get(user.role, 0) < ROLE_HIERARCHY.get(min_role, 0):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin required")
    return user


def require_admin_or_above(user: User = Depends(get_current_user)) -> User:
    if ROLE_HIERARCHY.get(user.role, 0) < ROLE_HIERARCHY["admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or above required")
    return user
