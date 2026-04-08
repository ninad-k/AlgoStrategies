from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import require_admin_or_above
from app.database import get_db
from app.models.admin_data import Trader, Strategy, User, AuditLog
from app.models.trade_data import Account, Trade, TradeAttribution, RiskMetrics
from app.schemas.upload import UploadResponse, AttributionSummary
from app.services.parser import parse_file
from app.services.attribution import attribute_trade
from app.services.risk import compute_risk_metrics

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.post("/trades", response_model=UploadResponse)
def upload_trades(
    file: UploadFile = File(...),
    account_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_above),
):
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    file_bytes = file.file.read()

    try:
        rows, warnings = parse_file(file_bytes, file.filename, account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ensure account exists
    acct = db.query(Account).filter(Account.account_id == account_id).first()
    if not acct:
        acct = Account(account_id=account_id)
        db.add(acct)
        db.flush()

    # Load traders and strategies for attribution
    traders = [
        {
            "id": t.id, "name": t.name,
            "default_lot_size": float(t.default_lot_size) if t.default_lot_size else None,
            "linked_accounts": [],  # Phase 2: load from account-trader mapping
        }
        for t in db.query(Trader).all()
    ]
    strategies = [
        {
            "id": s.id, "name": s.name,
            "magic_number": s.magic_number,
            "lot_size": float(s.lot_size) if s.lot_size else None,
            "symbol_filter": list(s.symbol_filter or []),
        }
        for s in db.query(Strategy).all()
    ]

    inserted = 0
    skipped = 0
    attr_trader = 0
    attr_strategy = 0
    attr_guest = 0

    for row in rows:
        trade = Trade(**row)
        try:
            db.add(trade)
            db.flush()
        except IntegrityError:
            db.rollback()
            skipped += 1
            continue

        # Risk metrics
        risk = compute_risk_metrics(row)
        db.add(RiskMetrics(trade_id=trade.id, **risk))

        # Attribution
        attr_results = attribute_trade(row, traders, strategies)
        if not attr_results:
            db.add(TradeAttribution(trade_id=trade.id, category_type="guest", category_id=None, attribution_level=7))
            attr_guest += 1
        else:
            for ar in attr_results:
                db.add(TradeAttribution(
                    trade_id=trade.id,
                    category_type=ar.category_type,
                    category_id=ar.category_id,
                    attribution_level=ar.attribution_level,
                    confidence=ar.confidence,
                ))
                if ar.category_type == "trader":
                    attr_trader += 1
                else:
                    attr_strategy += 1

        inserted += 1

    db.add(AuditLog(
        user_id=current_user.id,
        action="upload_trades",
        entity_type="account",
        metadata={"account_id": account_id, "inserted": inserted, "skipped": skipped},
    ))
    db.commit()

    batch_id = str(rows[0]["upload_batch_id"]) if rows else "no-rows"
    return UploadResponse(
        batch_id=batch_id,
        total_rows=len(rows),
        inserted=inserted,
        skipped_duplicates=skipped,
        attribution_summary=AttributionSummary(
            attributed_trader=attr_trader,
            attributed_strategy=attr_strategy,
            guest=attr_guest,
        ),
    )
