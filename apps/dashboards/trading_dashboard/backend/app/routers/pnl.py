from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.admin_data import Trader, Strategy, User
from app.models.trade_data import Trade, TradeAttribution, RiskMetrics
from app.schemas.pnl import PnlSummary, PnlByCategory, RiskSummary, TradeRow

router = APIRouter()


def _net(t: Trade) -> float:
    return float((t.profit or 0) + (t.commission or 0) + (t.swap or 0))


def _date_filter(query, date_from: Optional[str], date_to: Optional[str]):
    if date_from:
        query = query.filter(Trade.open_time >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Trade.open_time <= datetime.fromisoformat(date_to))
    return query


def _pnl_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"total_profit": 0, "trade_count": 0, "win_count": 0, "loss_count": 0,
                "win_rate": 0, "avg_profit_per_trade": 0, "best_trade": 0, "worst_trade": 0}
    nets = [_net(t) for t in trades]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n <= 0]
    total = sum(nets)
    count = len(nets)
    return {
        "total_profit": round(total, 2),
        "trade_count": count,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / count, 4) if count else 0,
        "avg_profit_per_trade": round(total / count, 2) if count else 0,
        "best_trade": round(max(nets), 2) if nets else 0,
        "worst_trade": round(min(nets), 2) if nets else 0,
    }


def _risk_stats(trade_ids: list[int], db: Session) -> dict:
    metrics = db.query(RiskMetrics).filter(RiskMetrics.trade_id.in_(trade_ids)).all()
    with_risk = [m for m in metrics if m.planned_rr is not None]
    no_risk = len(metrics) - len(with_risk)
    avg_planned = round(sum(float(m.planned_rr) for m in with_risk) / len(with_risk), 4) if with_risk else None
    with_realised = [m for m in metrics if m.realised_rr is not None]
    avg_realised = round(sum(float(m.realised_rr) for m in with_realised) / len(with_realised), 4) if with_realised else None
    return {"avg_planned_rr": avg_planned, "avg_realised_rr": avg_realised, "no_risk_data_count": no_risk}


@router.get("/summary", response_model=PnlSummary)
def pnl_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Trade)
    q = _date_filter(q, date_from, date_to)
    trades = q.all()
    return PnlSummary(**_pnl_stats(trades))


@router.get("/by-trader", response_model=list[PnlByCategory])
def pnl_by_trader(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    results = []

    # Guest
    guest_attrs = db.query(TradeAttribution).filter(TradeAttribution.category_type == "guest").all()
    guest_trade_ids = [a.trade_id for a in guest_attrs]
    if guest_trade_ids:
        q = db.query(Trade).filter(Trade.id.in_(guest_trade_ids))
        q = _date_filter(q, date_from, date_to)
        trades = q.all()
        if trades:
            stats = _pnl_stats(trades)
            risk = _risk_stats([t.id for t in trades], db)
            results.append(PnlByCategory(category_id=None, category_name="Guest/Common",
                                         category_type="trader", **stats, **risk))

    # Real traders
    for trader in db.query(Trader).filter(Trader.id != 0).all():
        attrs = db.query(TradeAttribution).filter(
            TradeAttribution.category_type == "trader",
            TradeAttribution.category_id == trader.id,
        ).all()
        trade_ids = [a.trade_id for a in attrs]
        if not trade_ids:
            continue
        q = db.query(Trade).filter(Trade.id.in_(trade_ids))
        q = _date_filter(q, date_from, date_to)
        trades = q.all()
        if not trades:
            continue
        stats = _pnl_stats(trades)
        risk = _risk_stats([t.id for t in trades], db)
        results.append(PnlByCategory(category_id=trader.id, category_name=trader.name,
                                     category_type="trader", **stats, **risk))

    return sorted(results, key=lambda r: r.total_profit, reverse=True)


@router.get("/by-strategy", response_model=list[PnlByCategory])
def pnl_by_strategy(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    results = []
    for strategy in db.query(Strategy).all():
        attrs = db.query(TradeAttribution).filter(
            TradeAttribution.category_type == "strategy",
            TradeAttribution.category_id == strategy.id,
        ).all()
        trade_ids = [a.trade_id for a in attrs]
        if not trade_ids:
            continue
        q = db.query(Trade).filter(Trade.id.in_(trade_ids))
        q = _date_filter(q, date_from, date_to)
        trades = q.all()
        if not trades:
            continue
        stats = _pnl_stats(trades)
        risk = _risk_stats([t.id for t in trades], db)
        results.append(PnlByCategory(category_id=strategy.id, category_name=strategy.name,
                                     category_type="strategy", **stats, **risk))
    return sorted(results, key=lambda r: r.total_profit, reverse=True)


@router.get("/by-symbol", response_model=list[PnlByCategory])
def pnl_by_symbol(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    category_type: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Trade)
    if category_type and category_id is not None:
        attr_ids = db.query(TradeAttribution.trade_id).filter(
            TradeAttribution.category_type == category_type,
            TradeAttribution.category_id == category_id,
        )
        q = q.filter(Trade.id.in_(attr_ids))
    q = _date_filter(q, date_from, date_to)
    trades = q.all()

    by_symbol: dict[str, list] = {}
    for t in trades:
        by_symbol.setdefault(t.symbol, []).append(t)

    results = []
    for symbol, sym_trades in by_symbol.items():
        stats = _pnl_stats(sym_trades)
        risk = _risk_stats([t.id for t in sym_trades], db)
        results.append(PnlByCategory(category_id=None, category_name=symbol,
                                     category_type="symbol", **stats, **risk))
    return sorted(results, key=lambda r: r.total_profit, reverse=True)


@router.get("/by-account", response_model=list[PnlByCategory])
def pnl_by_account(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Trade)
    q = _date_filter(q, date_from, date_to)
    trades = q.all()

    by_acct: dict[str, list] = {}
    for t in trades:
        by_acct.setdefault(t.account_id, []).append(t)

    results = []
    for acct_id, acct_trades in by_acct.items():
        stats = _pnl_stats(acct_trades)
        risk = _risk_stats([t.id for t in acct_trades], db)
        results.append(PnlByCategory(category_id=None, category_name=acct_id,
                                     category_type="account", **stats, **risk))
    return sorted(results, key=lambda r: r.total_profit, reverse=True)


@router.get("/traders/{trader_id}/trades", response_model=list[TradeRow])
def trader_trades(
    trader_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _trades_for_category("trader", trader_id, date_from, date_to, page, page_size, db)


@router.get("/strategies/{strategy_id}/trades", response_model=list[TradeRow])
def strategy_trades(
    strategy_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _trades_for_category("strategy", strategy_id, date_from, date_to, page, page_size, db)


@router.get("/traders/{trader_id}/risk", response_model=RiskSummary)
def trader_risk(
    trader_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    trades = _trades_for_category("trader", trader_id, date_from, date_to, 1, 10000, db)
    trade_ids = [t.id for t in trades]
    stats = _risk_stats(trade_ids, db)
    metrics = db.query(RiskMetrics).filter(RiskMetrics.trade_id.in_(trade_ids)).all()
    with_dev = [m for m in metrics if m.rr_deviation is not None]
    avg_dev = round(sum(float(m.rr_deviation) for m in with_dev) / len(with_dev), 4) if with_dev else None
    return RiskSummary(**stats, avg_rr_deviation=avg_dev, trades_with_risk=len([m for m in metrics if m.planned_rr]))


@router.get("/strategies/{strategy_id}/risk", response_model=RiskSummary)
def strategy_risk(
    strategy_id: int,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    trades = _trades_for_category("strategy", strategy_id, date_from, date_to, 1, 10000, db)
    trade_ids = [t.id for t in trades]
    stats = _risk_stats(trade_ids, db)
    metrics = db.query(RiskMetrics).filter(RiskMetrics.trade_id.in_(trade_ids)).all()
    with_dev = [m for m in metrics if m.rr_deviation is not None]
    avg_dev = round(sum(float(m.rr_deviation) for m in with_dev) / len(with_dev), 4) if with_dev else None
    return RiskSummary(**stats, avg_rr_deviation=avg_dev, trades_with_risk=len([m for m in metrics if m.planned_rr]))


def _trades_for_category(cat_type, cat_id, date_from, date_to, page, page_size, db) -> list[TradeRow]:
    attr_ids = db.query(TradeAttribution.trade_id).filter(
        TradeAttribution.category_type == cat_type,
        TradeAttribution.category_id == cat_id,
    )
    q = db.query(Trade, TradeAttribution, RiskMetrics).join(
        TradeAttribution, Trade.id == TradeAttribution.trade_id
    ).outerjoin(
        RiskMetrics, Trade.id == RiskMetrics.trade_id
    ).filter(
        Trade.id.in_(attr_ids),
        TradeAttribution.category_type == cat_type,
        TradeAttribution.category_id == cat_id,
    )
    if date_from:
        q = q.filter(Trade.open_time >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Trade.open_time <= datetime.fromisoformat(date_to))
    q = q.order_by(Trade.open_time.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)

    rows = []
    for trade, attr, risk in q.all():
        rows.append(TradeRow(
            id=trade.id,
            open_time=trade.open_time,
            close_time=trade.close_time,
            symbol=trade.symbol,
            type=trade.type,
            lots=float(trade.lots),
            open_price=float(trade.open_price),
            close_price=float(trade.close_price) if trade.close_price else None,
            sl=float(trade.sl) if trade.sl else None,
            tp=float(trade.tp) if trade.tp else None,
            profit=float(trade.profit or 0),
            commission=float(trade.commission or 0),
            swap=float(trade.swap or 0),
            net_profit=float((trade.profit or 0) + (trade.commission or 0) + (trade.swap or 0)),
            planned_rr=float(risk.planned_rr) if risk and risk.planned_rr else None,
            realised_rr=float(risk.realised_rr) if risk and risk.realised_rr else None,
            rr_deviation=float(risk.rr_deviation) if risk and risk.rr_deviation else None,
            attribution_level=attr.attribution_level,
        ))
    return rows
