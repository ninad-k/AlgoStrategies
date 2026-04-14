//+------------------------------------------------------------------+
//|                                          PendingOrderManager.mqh |
//|              Pending order placement, activation tracking,       |
//|              and partial TP management for signal-based trading   |
//+------------------------------------------------------------------+
#property copyright "TeleTrader"
#property strict

#include <Trade/Trade.mqh>

#define MAX_SIGNALS 10

//+------------------------------------------------------------------+
//| Per-signal tracking state                                         |
//+------------------------------------------------------------------+
struct SignalOrder
{
    string signalId;         // from API, for deduplication
    ulong  orderTicket;      // pending order ticket
    ulong  positionTicket;   // populated once pending order activates
    string symbol;
    double entryPrice;
    double stopLoss;
    double tp1;
    double tp2;
    double tp3;
    double lots;
    int    direction;        // +1 = buy, -1 = sell
    int    orderType;        // ORDER_TYPE_BUY_STOP, etc.
    bool   active;           // slot in use
    bool   activated;        // pending → position
    bool   tp1Hit;
    bool   tp2Hit;
    bool   tp3Hit;
    bool   trailingActive;   // after all 3 TPs, trail the residual
    bool   closed;           // fully closed

    void Reset()
    {
        signalId      = "";
        orderTicket   = 0;
        positionTicket = 0;
        symbol        = "";
        entryPrice    = 0;
        stopLoss      = 0;
        tp1 = tp2 = tp3 = 0;
        lots          = 0;
        direction     = 0;
        orderType     = 0;
        active        = false;
        activated     = false;
        tp1Hit = tp2Hit = tp3Hit = false;
        trailingActive = false;
        closed        = false;
    }
};

//+------------------------------------------------------------------+
//| Pending Order Manager                                             |
//+------------------------------------------------------------------+
class CPendingOrderManager
{
private:
    CTrade        m_trade;
    SignalOrder   m_signals[MAX_SIGNALS];
    int           m_magic;
    double        m_tp1Pct;
    double        m_tp2Pct;
    double        m_tp3Pct;
    double        m_residualPct;
    double        m_trailingPoints;

public:
    CPendingOrderManager() : m_magic(20260410), m_tp1Pct(30), m_tp2Pct(50),
                             m_tp3Pct(10), m_residualPct(10), m_trailingPoints(200)
    {
        for(int i = 0; i < MAX_SIGNALS; i++)
            m_signals[i].Reset();
    }

    void Init(int magic, double slippage = 3)
    {
        m_magic = magic;
        m_trade.SetExpertMagicNumber(magic);
        m_trade.SetDeviationInPoints((ulong)slippage);
    }

    void SetTPConfig(double tp1Pct, double tp2Pct, double tp3Pct, double residualPct)
    {
        m_tp1Pct      = tp1Pct;
        m_tp2Pct      = tp2Pct;
        m_tp3Pct      = tp3Pct;
        m_residualPct = residualPct;
    }

    void SetTrailingPoints(double pts) { m_trailingPoints = pts; }

    //--- Check if signal already exists (deduplication)
    bool HasSignal(const string &signalId)
    {
        for(int i = 0; i < MAX_SIGNALS; i++)
        {
            if(m_signals[i].active && m_signals[i].signalId == signalId)
                return true;
        }
        return false;
    }

    //--- Place a pending order for a parsed signal
    bool PlaceOrder(const string &signalId, const string &symbol,
                    int direction, const string &orderTypeStr,
                    double entryPrice, double stopLoss,
                    double tp1, double tp2, double tp3, double lots)
    {
        if(HasSignal(signalId))
            return false; // already placed

        int slot = _FindFreeSlot();
        if(slot < 0)
        {
            Print("PendingOrderManager: No free slots for signal ", signalId);
            return false;
        }

        // Determine MQL5 order type
        ENUM_ORDER_TYPE mqlOrderType;
        if(orderTypeStr == "buy_stop")        mqlOrderType = ORDER_TYPE_BUY_STOP;
        else if(orderTypeStr == "sell_stop")   mqlOrderType = ORDER_TYPE_SELL_STOP;
        else if(orderTypeStr == "buy_limit")   mqlOrderType = ORDER_TYPE_BUY_LIMIT;
        else if(orderTypeStr == "sell_limit")  mqlOrderType = ORDER_TYPE_SELL_LIMIT;
        else
        {
            Print("PendingOrderManager: Unknown order type: ", orderTypeStr);
            return false;
        }

        // Normalize lots
        double normLots = _NormalizeLots(symbol, lots);
        if(normLots <= 0)
        {
            Print("PendingOrderManager: Lot size too small for ", symbol);
            return false;
        }

        // Normalize prices
        int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
        double normEntry = NormalizeDouble(entryPrice, digits);
        double normSL    = NormalizeDouble(stopLoss, digits);

        string comment = "TT_" + signalId;

        bool result = m_trade.OrderOpen(
            symbol,
            mqlOrderType,
            normLots,
            0,              // limit price (0 for stop/limit orders)
            normEntry,
            normSL,
            0,              // TP managed manually
            ORDER_TIME_GTC,
            0,
            comment
        );

        if(result)
        {
            m_signals[slot].signalId      = signalId;
            m_signals[slot].orderTicket   = m_trade.ResultOrder();
            m_signals[slot].symbol        = symbol;
            m_signals[slot].entryPrice    = entryPrice;
            m_signals[slot].stopLoss      = stopLoss;
            m_signals[slot].tp1           = tp1;
            m_signals[slot].tp2           = tp2;
            m_signals[slot].tp3           = tp3;
            m_signals[slot].lots          = normLots;
            m_signals[slot].direction     = direction;
            m_signals[slot].orderType     = (int)mqlOrderType;
            m_signals[slot].active        = true;
            m_signals[slot].activated     = false;
            m_signals[slot].tp1Hit = m_signals[slot].tp2Hit = m_signals[slot].tp3Hit = false;
            m_signals[slot].trailingActive = false;
            m_signals[slot].closed        = false;

            Print("PendingOrderManager: Placed ", orderTypeStr, " for ", symbol,
                  " @ ", normEntry, " SL=", normSL,
                  " TP=[", tp1, ", ", tp2, ", ", tp3, "]",
                  " ticket=", m_signals[slot].orderTicket);
        }
        else
        {
            Print("PendingOrderManager: OrderOpen failed: ", m_trade.ResultRetcodeDescription());
        }

        return result;
    }

    //--- Call from OnTradeTransaction to detect pending order activation
    void OnTransaction(const MqlTradeTransaction &trans,
                       const MqlTradeRequest &request,
                       const MqlTradeResult &result)
    {
        // Detect when a pending order becomes a position
        if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
        {
            for(int i = 0; i < MAX_SIGNALS; i++)
            {
                if(!m_signals[i].active || m_signals[i].activated)
                    continue;

                // Check if this deal is from our pending order
                if(trans.order == m_signals[i].orderTicket ||
                   _IsPositionFromOrder(trans.position, m_signals[i].orderTicket))
                {
                    m_signals[i].positionTicket = trans.position;
                    m_signals[i].activated = true;
                    Print("PendingOrderManager: Signal ", m_signals[i].signalId,
                          " activated! Position ticket=", trans.position);
                    break;
                }
            }
        }

        // Detect when a pending order is deleted/expired
        if(trans.type == TRADE_TRANSACTION_ORDER_DELETE)
        {
            for(int i = 0; i < MAX_SIGNALS; i++)
            {
                if(!m_signals[i].active || m_signals[i].activated)
                    continue;

                if(trans.order == m_signals[i].orderTicket)
                {
                    Print("PendingOrderManager: Pending order deleted for signal ",
                          m_signals[i].signalId);
                    m_signals[i].Reset();
                    break;
                }
            }
        }
    }

    //--- Call from OnTick to manage active positions
    void ManagePositions()
    {
        for(int i = 0; i < MAX_SIGNALS; i++)
        {
            if(!m_signals[i].active || !m_signals[i].activated || m_signals[i].closed)
                continue;

            // Check if position still exists
            if(!PositionSelectByTicket(m_signals[i].positionTicket))
            {
                Print("PendingOrderManager: Position closed for signal ", m_signals[i].signalId);
                m_signals[i].closed = true;
                m_signals[i].Reset();
                continue;
            }

            string sym = m_signals[i].symbol;
            double currentPrice;

            if(m_signals[i].direction > 0)
                currentPrice = SymbolInfoDouble(sym, SYMBOL_BID);  // close price for longs
            else
                currentPrice = SymbolInfoDouble(sym, SYMBOL_ASK);  // close price for shorts

            // If all TPs hit and residual > 0, trail the stop loss
            if(m_signals[i].tp1Hit && m_signals[i].tp2Hit && m_signals[i].tp3Hit)
            {
                m_signals[i].trailingActive = true;
                _TrailStopLoss(i, currentPrice);
                continue;
            }

            // Manage partial take profits
            if(m_signals[i].direction > 0)
                _ManageLongTP(i, currentPrice);
            else
                _ManageShortTP(i, currentPrice);
        }
    }

    //--- Get count of active signals
    int ActiveCount()
    {
        int count = 0;
        for(int i = 0; i < MAX_SIGNALS; i++)
            if(m_signals[i].active) count++;
        return count;
    }

private:
    int _FindFreeSlot()
    {
        for(int i = 0; i < MAX_SIGNALS; i++)
            if(!m_signals[i].active) return i;
        return -1;
    }

    bool _IsPositionFromOrder(ulong posTicket, ulong orderTicket)
    {
        if(posTicket == 0 || orderTicket == 0) return false;
        // Check via history
        if(HistorySelectByPosition(posTicket))
        {
            int total = HistoryDealsTotal();
            for(int i = 0; i < total; i++)
            {
                ulong dealTicket = HistoryDealGetTicket(i);
                if(HistoryDealGetInteger(dealTicket, DEAL_ORDER) == (long)orderTicket)
                    return true;
            }
        }
        return false;
    }

    void _ManageLongTP(int idx, double currentPrice)
    {
        double totalLots = PositionGetDouble(POSITION_VOLUME);

        // TP1
        if(!m_signals[idx].tp1Hit && currentPrice >= m_signals[idx].tp1)
        {
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * m_tp1Pct / 100.0);
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp1Hit = true;
                Print("TeleTrader TP1 hit: closed ", closeLots, " lots @ ", currentPrice);
                // Move SL to breakeven
                _ModifySL(m_signals[idx].positionTicket, m_signals[idx].entryPrice);
            }
        }

        // TP2
        if(m_signals[idx].tp1Hit && !m_signals[idx].tp2Hit && currentPrice >= m_signals[idx].tp2)
        {
            if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
            totalLots = PositionGetDouble(POSITION_VOLUME);
            double remainPct = m_tp2Pct + m_tp3Pct + m_residualPct;
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp2Pct / remainPct));
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp2Hit = true;
                Print("TeleTrader TP2 hit: closed ", closeLots, " lots @ ", currentPrice);
            }
        }

        // TP3
        if(m_signals[idx].tp1Hit && m_signals[idx].tp2Hit && !m_signals[idx].tp3Hit && currentPrice >= m_signals[idx].tp3)
        {
            if(m_residualPct > 0)
            {
                if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
                totalLots = PositionGetDouble(POSITION_VOLUME);
                double remainPct = m_tp3Pct + m_residualPct;
                double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp3Pct / remainPct));
                if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
                {
                    m_signals[idx].tp3Hit = true;
                    Print("TeleTrader TP3 hit: closed ", closeLots, " lots @ ", currentPrice,
                          " — trailing residual");
                }
            }
            else
            {
                // No residual: close everything
                m_trade.PositionClose(m_signals[idx].positionTicket);
                m_signals[idx].tp3Hit = true;
                m_signals[idx].closed = true;
                Print("TeleTrader TP3 hit: fully closed @ ", currentPrice);
            }
        }
    }

    void _ManageShortTP(int idx, double currentPrice)
    {
        double totalLots = PositionGetDouble(POSITION_VOLUME);

        // TP1
        if(!m_signals[idx].tp1Hit && currentPrice <= m_signals[idx].tp1)
        {
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * m_tp1Pct / 100.0);
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp1Hit = true;
                Print("TeleTrader TP1 hit (short): closed ", closeLots, " lots @ ", currentPrice);
                _ModifySL(m_signals[idx].positionTicket, m_signals[idx].entryPrice);
            }
        }

        // TP2
        if(m_signals[idx].tp1Hit && !m_signals[idx].tp2Hit && currentPrice <= m_signals[idx].tp2)
        {
            if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
            totalLots = PositionGetDouble(POSITION_VOLUME);
            double remainPct = m_tp2Pct + m_tp3Pct + m_residualPct;
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp2Pct / remainPct));
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp2Hit = true;
                Print("TeleTrader TP2 hit (short): closed ", closeLots, " lots @ ", currentPrice);
            }
        }

        // TP3
        if(m_signals[idx].tp1Hit && m_signals[idx].tp2Hit && !m_signals[idx].tp3Hit && currentPrice <= m_signals[idx].tp3)
        {
            if(m_residualPct > 0)
            {
                if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
                totalLots = PositionGetDouble(POSITION_VOLUME);
                double remainPct = m_tp3Pct + m_residualPct;
                double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp3Pct / remainPct));
                if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
                {
                    m_signals[idx].tp3Hit = true;
                    Print("TeleTrader TP3 hit (short): closed ", closeLots, " lots @ ", currentPrice,
                          " — trailing residual");
                }
            }
            else
            {
                m_trade.PositionClose(m_signals[idx].positionTicket);
                m_signals[idx].tp3Hit = true;
                m_signals[idx].closed = true;
                Print("TeleTrader TP3 hit (short): fully closed @ ", currentPrice);
            }
        }
    }

    void _TrailStopLoss(int idx, double currentPrice)
    {
        if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;

        double currentSL = PositionGetDouble(POSITION_SL);
        double tp        = PositionGetDouble(POSITION_TP);
        double point     = SymbolInfoDouble(m_signals[idx].symbol, SYMBOL_POINT);
        int    digits    = (int)SymbolInfoInteger(m_signals[idx].symbol, SYMBOL_DIGITS);

        if(m_signals[idx].direction > 0)
        {
            // Long: trail SL below price
            double newSL = NormalizeDouble(currentPrice - m_trailingPoints * point, digits);
            if(newSL > currentSL && newSL > m_signals[idx].entryPrice)
                m_trade.PositionModify(m_signals[idx].positionTicket, newSL, tp);
        }
        else
        {
            // Short: trail SL above price
            double newSL = NormalizeDouble(currentPrice + m_trailingPoints * point, digits);
            if((currentSL == 0 || newSL < currentSL) && newSL < m_signals[idx].entryPrice)
                m_trade.PositionModify(m_signals[idx].positionTicket, newSL, tp);
        }
    }

    void _ModifySL(ulong posTicket, double newSL)
    {
        if(!PositionSelectByTicket(posTicket)) return;
        double tp     = PositionGetDouble(POSITION_TP);
        string symbol = PositionGetString(POSITION_SYMBOL);
        int    digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
        newSL = NormalizeDouble(newSL, digits);
        m_trade.PositionModify(posTicket, newSL, tp);
    }

    double _NormalizeLots(const string &symbol, double lots)
    {
        double minLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
        double maxLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
        double stepLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

        lots = MathFloor(lots / stepLot) * stepLot;
        if(lots < minLot) lots = 0;
        if(lots > maxLot) lots = maxLot;
        return lots;
    }
};
