from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin_or_above, get_current_user
from app.database import get_db
from app.models.admin_data import AttributionRule, AuditLog, User
from app.schemas.attribution_rule import AttributionRuleCreate, AttributionRuleUpdate, AttributionRuleRead

router = APIRouter()


@router.get("", response_model=list[AttributionRuleRead])
def list_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(AttributionRule).order_by(AttributionRule.priority).all()


@router.post("", response_model=AttributionRuleRead)
def create_rule(
    body: AttributionRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    rule = AttributionRule(**body.model_dump())
    db.add(rule)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create_rule", entity_type="attribution_rule", entity_id=rule.id))
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=AttributionRuleRead)
def update_rule(
    rule_id: int,
    body: AttributionRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    rule = db.query(AttributionRule).filter(AttributionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(rule, k, v)
    db.add(AuditLog(user_id=user.id, action="update_rule", entity_type="attribution_rule", entity_id=rule_id))
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_above),
):
    rule = db.query(AttributionRule).filter(AttributionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.add(AuditLog(user_id=user.id, action="delete_rule", entity_type="attribution_rule", entity_id=rule_id))
    db.commit()
