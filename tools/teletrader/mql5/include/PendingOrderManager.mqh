//+------------------------------------------------------------------+
//|                                          PendingOrderManager.mqh |
//|              Pending order placement, activation tracking,       |
//|              and partial TP management for signal-based trading   |
//+------------------------------------------------------------------+
#property copyright "TeleTrader"
#property strict

#include <Trade/Trade.mqh>

#define MAX_SIGNALS 10
#define MAX_NOTIFICATIONS 20
#define MAX_TRADE_EVENTS 20

//+------------------------------------------------------------------+
//| Structured trade event for API reporting                          |
//+------------------------------------------------------------------+
struct TradeEvent
{
    string signalId;
    string eventType;   // order_placed, order_failed, activated, tp1_hit, tp2_hit, tp3_hit, closed, symbol_not_found
    string symbol;
    string direction;   // buy or sell
    double lots;
    double price;
    double pnl;
    string source;
    string details;
    bool   used;

    void Reset()
    {
        signalId  = "";
        eventType = "";
        symbol    = "";
        direction = "";
        lots      = 0;
        price     = 0;
        pnl       = 0;
        source    = "";
        details   = "";
        used      = false;
    }
};

//+------------------------------------------------------------------+
//| Per-signal tracking state                                         |
//+------------------------------------------------------------------+
struct SignalOrder
{
    string signalId;         // from API, for deduplication
    ulong  orderTicket;      // pending order ticket
    ulong  positionTicket;   // populated once pending order activates
    string symbol;
    string source;           // signal source for trade event reporting
    double entryPrice;
    double stopLoss;
    double tp1;
    double tp2;
    double tp3;
    double lots;
    int    direction;        // +1 = buy, -1 = sell
    int    orderType;        // ORDER_TYPE_BUY_STOP, etc.
    bool   active;           // slot in use
    bool   activated;        // pending -> position
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
        source        = "unknown";
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
//| Lifetime stats for dashboard                                      |
//+------------------------------------------------------------------+
struct TradeStats
{
    int    totalSignals;      // signals received from API
    int    ordersPlaced;      // successfully placed
    int    ordersFailed;      // failed to place
    int    buyCount;          // buy orders placed
    int    sellCount;         // sell orders placed
    int    positionsActivated; // pending -> live
    int    positionsClosed;   // fully closed
    double realizedPnL;       // from closed positions
    int    tp1Hits;
    int    tp2Hits;
    int    tp3Hits;

    void Reset()
    {
        totalSignals = 0;
        ordersPlaced = 0;
        ordersFailed = 0;
        buyCount = 0;
        sellCount = 0;
        positionsActivated = 0;
        positionsClosed = 0;
        realizedPnL = 0;
        tp1Hits = 0;
        tp2Hits = 0;
        tp3Hits = 0;
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
    bool          m_enablePartialTP;
    bool          m_enableTrailing;

    // Notification queue — EA drains this via PopNotification()
    string        m_notifications[MAX_NOTIFICATIONS];
    int           m_notifyCount;

    // Trade event queue — EA drains this via PopTradeEvent()
    TradeEvent    m_tradeEvents[MAX_TRADE_EVENTS];
    int           m_eventCount;

public:
    TradeStats    Stats;  // public so EA can read for dashboard

    CPendingOrderManager() : m_magic(20260410), m_tp1Pct(30), m_tp2Pct(50),
                             m_tp3Pct(10), m_residualPct(10), m_trailingPoints(200),
                             m_enablePartialTP(true), m_enableTrailing(true),
                             m_notifyCount(0), m_eventCount(0)
    {
        for(int i = 0; i < MAX_SIGNALS; i++)
            m_signals[i].Reset();
        Stats.Reset();
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
    void SetPartialTPEnabled(bool enabled) { m_enablePartialTP = enabled; }
    void SetTrailingEnabled(bool enabled)  { m_enableTrailing = enabled; }

    //--- Notification queue ---
    bool HasNotifications()     { return m_notifyCount > 0; }
    int  NotificationCount()    { return m_notifyCount; }

    string PopNotification()
    {
        if(m_notifyCount <= 0) return "";
        string msg = m_notifications[0];
        // Shift remaining
        for(int i = 1; i < m_notifyCount; i++)
            m_notifications[i-1] = m_notifications[i];
        m_notifyCount--;
        return msg;
    }

    //--- Trade event queue ---
    bool HasTradeEvents()       { return m_eventCount > 0; }

    bool PopTradeEvent(TradeEvent &evt)
    {
        if(m_eventCount <= 0) return false;
        evt = m_tradeEvents[0];
        // Shift remaining
        for(int i = 1; i < m_eventCount; i++)
            m_tradeEvents[i-1] = m_tradeEvents[i];
        m_eventCount--;
        return true;
    }

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
                    double tp1, double tp2, double tp3, double lots,
                    const string &source)
    {
        Stats.totalSignals++;

        if(HasSignal(signalId))
            return false; // already placed

        int slot = _FindFreeSlot();
        if(slot < 0)
        {
            PrintFormat("[ORDER] ERROR: No free slots for signal %s (max %d)", signalId, MAX_SIGNALS);
            Stats.ordersFailed++;
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
            PrintFormat("[ORDER] ERROR: Unknown order type: %s (signal %s)", orderTypeStr, signalId);
            Stats.ordersFailed++;
            return false;
        }

        // Normalize lots
        double normLots = _NormalizeLots(symbol, lots);
        if(normLots <= 0)
        {
            PrintFormat("[ORDER] ERROR: Lot size too small for %s (requested %.4f)", symbol, lots);
            Stats.ordersFailed++;
            return false;
        }

        // Normalize prices
        int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
        double normEntry = NormalizeDouble(entryPrice, digits);
        double normSL    = NormalizeDouble(stopLoss, digits);

        string comment = "TT_" + signalId;

        PrintFormat("[ORDER] Placing %s: %s %.2f lots @ %.5f  SL=%.5f  TP=[%.5f, %.5f, %.5f]",
                    orderTypeStr, symbol, normLots, normEntry, normSL, tp1, tp2, tp3);

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
            m_signals[slot].source        = source;
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

            Stats.ordersPlaced++;
            if(direction > 0) Stats.buyCount++;
            else              Stats.sellCount++;

            PrintFormat("[ORDER] SUCCESS: %s %s ticket=%d, signal=%s",
                        orderTypeStr, symbol, m_signals[slot].orderTicket, signalId);

            string dir = (direction > 0) ? "BUY" : "SELL";
            _QueueNotification(StringFormat(
                "<b>Order Placed</b>\n"
                "%s %s %s\n"
                "Entry: %.5f\n"
                "SL: %.5f\n"
                "TP1: %.5f | TP2: %.5f | TP3: %.5f\n"
                "Lots: %.2f\n"
                "Partial TP: %s | Trailing: %s",
                symbol, dir, orderTypeStr,
                normEntry, normSL, tp1, tp2, tp3, normLots,
                m_enablePartialTP ? "ON" : "OFF",
                m_enableTrailing ? "ON" : "OFF"
            ));
            _QueueTradeEvent(signalId, "order_placed", symbol, dir,
                             normLots, normEntry, 0, source,
                             StringFormat("SL=%.5f TP1=%.5f TP2=%.5f TP3=%.5f", normSL, tp1, tp2, tp3));
        }
        else
        {
            Stats.ordersFailed++;
            PrintFormat("[ORDER] FAILED: %s - %s (retcode=%d)",
                        signalId, m_trade.ResultRetcodeDescription(), m_trade.ResultRetcode());

            _QueueNotification(StringFormat(
                "<b>Order FAILED</b>\n"
                "%s %s\n"
                "Error: %s (code %d)",
                symbol, orderTypeStr,
                m_trade.ResultRetcodeDescription(), m_trade.ResultRetcode()
            ));
            string dirStr = (direction > 0) ? "buy" : "sell";
            _QueueTradeEvent(signalId, "order_failed", symbol, dirStr,
                             lots, entryPrice, 0, source,
                             StringFormat("Error: %s (code %d)", m_trade.ResultRetcodeDescription(), m_trade.ResultRetcode()));
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
                    Stats.positionsActivated++;

                    string dir = (m_signals[i].direction > 0) ? "BUY" : "SELL";
                    PrintFormat("[ACTIVATE] Signal %s activated! %s %s @ %.5f, position=%d",
                                m_signals[i].signalId, m_signals[i].symbol,
                                dir, m_signals[i].entryPrice, trans.position);

                    _QueueNotification(StringFormat(
                        "<b>Position Activated</b>\n"
                        "%s %s @ %.5f\n"
                        "Lots: %.2f | Position: %d",
                        m_signals[i].symbol, dir,
                        m_signals[i].entryPrice,
                        m_signals[i].lots, trans.position
                    ));
                    string dirLower = (m_signals[i].direction > 0) ? "buy" : "sell";
                    _QueueTradeEvent(m_signals[i].signalId, "activated", m_signals[i].symbol,
                                     dirLower, m_signals[i].lots, m_signals[i].entryPrice, 0,
                                     m_signals[i].source, StringFormat("position=%d", trans.position));
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
                    PrintFormat("[ORDER] Pending order DELETED for signal %s (%s)",
                                m_signals[i].signalId, m_signals[i].symbol);

                    _QueueNotification(StringFormat(
                        "<b>Order Deleted</b>\n"
                        "%s pending order removed",
                        m_signals[i].symbol
                    ));
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
                double pnl = _GetPositionPnLFromHistory(m_signals[i].positionTicket);
                Stats.realizedPnL += pnl;
                Stats.positionsClosed++;
                PrintFormat("[CLOSE] Position closed externally for signal %s (%s), P&L=%.2f",
                            m_signals[i].signalId, m_signals[i].symbol, pnl);

                string closedDir = (m_signals[i].direction > 0) ? "buy" : "sell";
                _QueueNotification(StringFormat(
                    "<b>Position Closed</b>\n"
                    "%s closed externally\n"
                    "P&L: %.2f",
                    m_signals[i].symbol, pnl
                ));
                _QueueTradeEvent(m_signals[i].signalId, "closed", m_signals[i].symbol,
                                 closedDir, 0, 0, pnl, m_signals[i].source, "Closed externally");
                m_signals[i].closed = true;
                m_signals[i].Reset();
                continue;
            }

            string sym = m_signals[i].symbol;
            double currentPrice;

            if(m_signals[i].direction > 0)
                currentPrice = SymbolInfoDouble(sym, SYMBOL_BID);
            else
                currentPrice = SymbolInfoDouble(sym, SYMBOL_ASK);

            // If partial TP is disabled, just close 100% at TP1
            if(!m_enablePartialTP)
            {
                _ManageFullCloseTP(i, currentPrice);
                continue;
            }

            // If all TPs hit and residual > 0, trail the stop loss
            if(m_signals[i].tp1Hit && m_signals[i].tp2Hit && m_signals[i].tp3Hit)
            {
                if(m_enableTrailing)
                {
                    m_signals[i].trailingActive = true;
                    _TrailStopLoss(i, currentPrice);
                }
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

    //--- Get count of pending (not yet activated) orders
    int PendingCount()
    {
        int count = 0;
        for(int i = 0; i < MAX_SIGNALS; i++)
            if(m_signals[i].active && !m_signals[i].activated) count++;
        return count;
    }

    //--- Get count of live (activated, not closed) positions
    int LiveCount()
    {
        int count = 0;
        for(int i = 0; i < MAX_SIGNALS; i++)
            if(m_signals[i].active && m_signals[i].activated && !m_signals[i].closed) count++;
        return count;
    }

    //--- Get total unrealized P&L across all live positions
    double GetUnrealizedPnL()
    {
        double total = 0;
        for(int i = 0; i < MAX_SIGNALS; i++)
        {
            if(!m_signals[i].active || !m_signals[i].activated || m_signals[i].closed)
                continue;
            if(PositionSelectByTicket(m_signals[i].positionTicket))
                total += PositionGetDouble(POSITION_PROFIT);
        }
        return total;
    }

    //--- Build dashboard string for chart Comment()
    string GetDashboardText(bool apiConnected, datetime lastPollTime, int lastSeq)
    {
        double unrealizedPnL = GetUnrealizedPnL();
        double totalPnL = Stats.realizedPnL + unrealizedPnL;

        string dash = "";
        dash += "========================================\n";
        dash += "         TELETRADER EA v2.0\n";
        dash += "========================================\n";
        dash += "\n";

        // Connection
        dash += StringFormat("API Status:    %s\n", apiConnected ? "CONNECTED" : "DISCONNECTED");
        dash += StringFormat("Last Poll:     %s\n", (lastPollTime > 0) ? TimeToString(lastPollTime, TIME_DATE|TIME_SECONDS) : "Never");
        dash += StringFormat("Signal Cursor: %d\n", lastSeq);
        dash += "\n";

        // Account
        dash += StringFormat("Balance:  %.2f %s\n", AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoString(ACCOUNT_CURRENCY));
        dash += StringFormat("Equity:   %.2f\n", AccountInfoDouble(ACCOUNT_EQUITY));
        dash += StringFormat("Margin:   %.2f\n", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
        dash += "\n";

        // P&L
        dash += "--- P&L ---\n";
        dash += StringFormat("Realized:    %+.2f\n", Stats.realizedPnL);
        dash += StringFormat("Unrealized:  %+.2f\n", unrealizedPnL);
        dash += StringFormat("Total:       %+.2f\n", totalPnL);
        dash += "\n";

        // Trade counts
        dash += "--- Trades ---\n";
        dash += StringFormat("Signals:     %d\n", Stats.totalSignals);
        dash += StringFormat("Placed:      %d  (Buy: %d | Sell: %d)\n", Stats.ordersPlaced, Stats.buyCount, Stats.sellCount);
        dash += StringFormat("Failed:      %d\n", Stats.ordersFailed);
        dash += StringFormat("Activated:   %d\n", Stats.positionsActivated);
        dash += StringFormat("Closed:      %d\n", Stats.positionsClosed);
        dash += "\n";

        // TP Stats
        if(m_enablePartialTP)
        {
            dash += "--- Partial TP ---\n";
            dash += StringFormat("TP1 Hits:  %d\n", Stats.tp1Hits);
            dash += StringFormat("TP2 Hits:  %d\n", Stats.tp2Hits);
            dash += StringFormat("TP3 Hits:  %d\n", Stats.tp3Hits);
            dash += "\n";
        }

        // Active positions detail
        dash += "--- Active Positions ---\n";
        int liveCount = 0;
        for(int i = 0; i < MAX_SIGNALS; i++)
        {
            if(!m_signals[i].active || !m_signals[i].activated || m_signals[i].closed)
                continue;

            liveCount++;
            string dir = (m_signals[i].direction > 0) ? "BUY" : "SELL";
            string tpStatus = "";
            if(m_signals[i].tp1Hit) tpStatus += "TP1 ";
            if(m_signals[i].tp2Hit) tpStatus += "TP2 ";
            if(m_signals[i].tp3Hit) tpStatus += "TP3 ";
            if(m_signals[i].trailingActive) tpStatus += "[TRAIL]";
            if(tpStatus == "") tpStatus = "Waiting";

            double posPnL = 0;
            double posVol = 0;
            if(PositionSelectByTicket(m_signals[i].positionTicket))
            {
                posPnL = PositionGetDouble(POSITION_PROFIT);
                posVol = PositionGetDouble(POSITION_VOLUME);
            }

            dash += StringFormat("  %s %s %.2f lots | P&L: %+.2f | %s\n",
                                 m_signals[i].symbol, dir, posVol, posPnL, tpStatus);
        }

        // Pending orders
        for(int i = 0; i < MAX_SIGNALS; i++)
        {
            if(!m_signals[i].active || m_signals[i].activated)
                continue;

            string dir = (m_signals[i].direction > 0) ? "BUY" : "SELL";
            dash += StringFormat("  %s %s @ %.5f [PENDING]\n",
                                 m_signals[i].symbol, dir, m_signals[i].entryPrice);
            liveCount++;
        }

        if(liveCount == 0)
            dash += "  (none)\n";

        dash += "========================================\n";
        return dash;
    }

private:
    void _QueueNotification(const string &msg)
    {
        if(m_notifyCount >= MAX_NOTIFICATIONS)
        {
            // Drop oldest
            for(int i = 1; i < MAX_NOTIFICATIONS; i++)
                m_notifications[i-1] = m_notifications[i];
            m_notifyCount = MAX_NOTIFICATIONS - 1;
        }
        m_notifications[m_notifyCount] = msg;
        m_notifyCount++;
    }

    void _QueueTradeEvent(const string &signalId, const string &eventType,
                          const string &symbol, const string &dir,
                          double lots, double price, double pnl,
                          const string &source, const string &details)
    {
        if(m_eventCount >= MAX_TRADE_EVENTS)
        {
            // Drop oldest
            for(int i = 1; i < MAX_TRADE_EVENTS; i++)
                m_tradeEvents[i-1] = m_tradeEvents[i];
            m_eventCount = MAX_TRADE_EVENTS - 1;
        }
        m_tradeEvents[m_eventCount].signalId  = signalId;
        m_tradeEvents[m_eventCount].eventType = eventType;
        m_tradeEvents[m_eventCount].symbol    = symbol;
        m_tradeEvents[m_eventCount].direction = dir;
        m_tradeEvents[m_eventCount].lots      = lots;
        m_tradeEvents[m_eventCount].price     = price;
        m_tradeEvents[m_eventCount].pnl       = pnl;
        m_tradeEvents[m_eventCount].source    = source;
        m_tradeEvents[m_eventCount].details   = details;
        m_tradeEvents[m_eventCount].used      = false;
        m_eventCount++;
    }

    int _FindFreeSlot()
    {
        for(int i = 0; i < MAX_SIGNALS; i++)
            if(!m_signals[i].active) return i;
        return -1;
    }

    bool _IsPositionFromOrder(ulong posTicket, ulong orderTicket)
    {
        if(posTicket == 0 || orderTicket == 0) return false;
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

    double _GetPositionPnLFromHistory(ulong posTicket)
    {
        double totalPnL = 0;
        if(HistorySelectByPosition(posTicket))
        {
            int total = HistoryDealsTotal();
            for(int i = 0; i < total; i++)
            {
                ulong dealTicket = HistoryDealGetTicket(i);
                totalPnL += HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
                totalPnL += HistoryDealGetDouble(dealTicket, DEAL_SWAP);
                totalPnL += HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
            }
        }
        return totalPnL;
    }

    //--- Simple mode: close 100% at TP1 (no partial booking)
    void _ManageFullCloseTP(int idx, double currentPrice)
    {
        bool hitTP = false;
        if(m_signals[idx].direction > 0)
            hitTP = (currentPrice >= m_signals[idx].tp1);
        else
            hitTP = (currentPrice <= m_signals[idx].tp1);

        if(hitTP)
        {
            if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
            double volume = PositionGetDouble(POSITION_VOLUME);

            if(m_trade.PositionClose(m_signals[idx].positionTicket))
            {
                m_signals[idx].tp1Hit = true;
                m_signals[idx].closed = true;
                double finalPnL = _GetPositionPnLFromHistory(m_signals[idx].positionTicket);
                Stats.realizedPnL += finalPnL;
                Stats.positionsClosed++;
                Stats.tp1Hits++;
                PrintFormat("[CLOSE] %s signal=%s: TP1 hit, closed %.2f lots @ %.5f, P&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            volume, currentPrice, finalPnL);

                _QueueNotification(StringFormat(
                    "<b>TP1 Hit - Full Close</b>\n"
                    "%s closed %.2f lots @ %.5f\n"
                    "P&L: %+.2f",
                    m_signals[idx].symbol, volume, currentPrice, finalPnL
                ));
                string fcDir = (m_signals[idx].direction > 0) ? "buy" : "sell";
                _QueueTradeEvent(m_signals[idx].signalId, "tp1_hit", m_signals[idx].symbol,
                                 fcDir, volume, currentPrice, finalPnL, m_signals[idx].source, "Full close at TP1");
                _QueueTradeEvent(m_signals[idx].signalId, "closed", m_signals[idx].symbol,
                                 fcDir, 0, currentPrice, finalPnL, m_signals[idx].source, "TP1 full close");
            }
        }
    }

    void _ManageLongTP(int idx, double currentPrice)
    {
        double totalLots = PositionGetDouble(POSITION_VOLUME);
        double unrealizedPnL = PositionGetDouble(POSITION_PROFIT);

        // TP1
        if(!m_signals[idx].tp1Hit && currentPrice >= m_signals[idx].tp1)
        {
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * m_tp1Pct / 100.0);
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp1Hit = true;
                Stats.tp1Hits++;
                double remainLots = totalLots - closeLots;
                PrintFormat("[TP1] %s signal=%s: closed %.2f lots @ %.5f, remaining=%.2f lots, unrealizedP&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            closeLots, currentPrice, remainLots, unrealizedPnL);
                _ModifySL(m_signals[idx].positionTicket, m_signals[idx].entryPrice);
                PrintFormat("[TP1] SL moved to breakeven @ %.5f", m_signals[idx].entryPrice);

                _QueueNotification(StringFormat(
                    "<b>TP1 Hit</b>\n"
                    "%s closed %.2f lots @ %.5f\n"
                    "Remaining: %.2f lots\n"
                    "SL moved to breakeven (%.5f)",
                    m_signals[idx].symbol, closeLots, currentPrice,
                    remainLots, m_signals[idx].entryPrice
                ));
                _QueueTradeEvent(m_signals[idx].signalId, "tp1_hit", m_signals[idx].symbol,
                                 "buy", closeLots, currentPrice, 0, m_signals[idx].source,
                                 StringFormat("Remaining: %.2f lots, SL to BE", remainLots));
            }
        }

        // TP2
        if(m_signals[idx].tp1Hit && !m_signals[idx].tp2Hit && currentPrice >= m_signals[idx].tp2)
        {
            if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
            totalLots = PositionGetDouble(POSITION_VOLUME);
            unrealizedPnL = PositionGetDouble(POSITION_PROFIT);
            double remainPct = m_tp2Pct + m_tp3Pct + m_residualPct;
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp2Pct / remainPct));
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp2Hit = true;
                Stats.tp2Hits++;
                double remainLots = totalLots - closeLots;
                PrintFormat("[TP2] %s signal=%s: closed %.2f lots @ %.5f, remaining=%.2f lots, unrealizedP&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            closeLots, currentPrice, remainLots, unrealizedPnL);

                _QueueNotification(StringFormat(
                    "<b>TP2 Hit</b>\n"
                    "%s closed %.2f lots @ %.5f\n"
                    "Remaining: %.2f lots",
                    m_signals[idx].symbol, closeLots, currentPrice, remainLots
                ));
                _QueueTradeEvent(m_signals[idx].signalId, "tp2_hit", m_signals[idx].symbol,
                                 "buy", closeLots, currentPrice, 0, m_signals[idx].source,
                                 StringFormat("Remaining: %.2f lots", remainLots));
            }
        }

        // TP3
        if(m_signals[idx].tp1Hit && m_signals[idx].tp2Hit && !m_signals[idx].tp3Hit && currentPrice >= m_signals[idx].tp3)
        {
            if(m_residualPct > 0)
            {
                if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
                totalLots = PositionGetDouble(POSITION_VOLUME);
                unrealizedPnL = PositionGetDouble(POSITION_PROFIT);
                double remainPct = m_tp3Pct + m_residualPct;
                double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp3Pct / remainPct));
                if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
                {
                    m_signals[idx].tp3Hit = true;
                    Stats.tp3Hits++;
                    double remainLots = totalLots - closeLots;
                    double realizedPnL = _GetPositionPnLFromHistory(m_signals[idx].positionTicket);
                    PrintFormat("[TP3] %s signal=%s: closed %.2f lots @ %.5f, trailing residual=%.2f lots",
                                m_signals[idx].symbol, m_signals[idx].signalId,
                                closeLots, currentPrice, remainLots);
                    PrintFormat("[TP3] Realized P&L so far: %.2f, unrealized: %.2f", realizedPnL, unrealizedPnL);

                    string trailMsg = m_enableTrailing ? "Trailing SL active" : "No trailing (disabled)";
                    _QueueNotification(StringFormat(
                        "<b>TP3 Hit</b>\n"
                        "%s closed %.2f lots @ %.5f\n"
                        "Residual: %.2f lots\n"
                        "%s",
                        m_signals[idx].symbol, closeLots, currentPrice, remainLots, trailMsg
                    ));
                    _QueueTradeEvent(m_signals[idx].signalId, "tp3_hit", m_signals[idx].symbol,
                                     "buy", closeLots, currentPrice, 0, m_signals[idx].source,
                                     StringFormat("Residual: %.2f lots, %s", remainLots, trailMsg));
                }
            }
            else
            {
                if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
                unrealizedPnL = PositionGetDouble(POSITION_PROFIT);
                m_trade.PositionClose(m_signals[idx].positionTicket);
                m_signals[idx].tp3Hit = true;
                m_signals[idx].closed = true;
                Stats.tp3Hits++;
                double finalPnL = _GetPositionPnLFromHistory(m_signals[idx].positionTicket);
                Stats.realizedPnL += finalPnL;
                Stats.positionsClosed++;
                PrintFormat("[CLOSE] %s signal=%s: fully closed @ %.5f, final P&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            currentPrice, finalPnL);

                _QueueNotification(StringFormat(
                    "<b>All TPs Hit - Closed</b>\n"
                    "%s fully closed @ %.5f\n"
                    "Final P&L: %+.2f",
                    m_signals[idx].symbol, currentPrice, finalPnL
                ));
                _QueueTradeEvent(m_signals[idx].signalId, "tp3_hit", m_signals[idx].symbol,
                                 "buy", 0, currentPrice, finalPnL, m_signals[idx].source, "All TPs hit");
                _QueueTradeEvent(m_signals[idx].signalId, "closed", m_signals[idx].symbol,
                                 "buy", 0, currentPrice, finalPnL, m_signals[idx].source, "Fully closed");
            }
        }
    }

    void _ManageShortTP(int idx, double currentPrice)
    {
        double totalLots = PositionGetDouble(POSITION_VOLUME);
        double unrealizedPnL = PositionGetDouble(POSITION_PROFIT);

        // TP1
        if(!m_signals[idx].tp1Hit && currentPrice <= m_signals[idx].tp1)
        {
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * m_tp1Pct / 100.0);
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp1Hit = true;
                Stats.tp1Hits++;
                double remainLots = totalLots - closeLots;
                PrintFormat("[TP1] %s signal=%s (short): closed %.2f lots @ %.5f, remaining=%.2f lots, unrealizedP&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            closeLots, currentPrice, remainLots, unrealizedPnL);
                _ModifySL(m_signals[idx].positionTicket, m_signals[idx].entryPrice);
                PrintFormat("[TP1] SL moved to breakeven @ %.5f", m_signals[idx].entryPrice);

                _QueueNotification(StringFormat(
                    "<b>TP1 Hit (Short)</b>\n"
                    "%s closed %.2f lots @ %.5f\n"
                    "Remaining: %.2f lots\n"
                    "SL moved to breakeven (%.5f)",
                    m_signals[idx].symbol, closeLots, currentPrice,
                    remainLots, m_signals[idx].entryPrice
                ));
                _QueueTradeEvent(m_signals[idx].signalId, "tp1_hit", m_signals[idx].symbol,
                                 "sell", closeLots, currentPrice, 0, m_signals[idx].source,
                                 StringFormat("Remaining: %.2f lots, SL to BE", remainLots));
            }
        }

        // TP2
        if(m_signals[idx].tp1Hit && !m_signals[idx].tp2Hit && currentPrice <= m_signals[idx].tp2)
        {
            if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
            totalLots = PositionGetDouble(POSITION_VOLUME);
            unrealizedPnL = PositionGetDouble(POSITION_PROFIT);
            double remainPct = m_tp2Pct + m_tp3Pct + m_residualPct;
            double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp2Pct / remainPct));
            if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
            {
                m_signals[idx].tp2Hit = true;
                Stats.tp2Hits++;
                double remainLots = totalLots - closeLots;
                PrintFormat("[TP2] %s signal=%s (short): closed %.2f lots @ %.5f, remaining=%.2f lots, unrealizedP&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            closeLots, currentPrice, remainLots, unrealizedPnL);

                _QueueNotification(StringFormat(
                    "<b>TP2 Hit (Short)</b>\n"
                    "%s closed %.2f lots @ %.5f\n"
                    "Remaining: %.2f lots",
                    m_signals[idx].symbol, closeLots, currentPrice, remainLots
                ));
                _QueueTradeEvent(m_signals[idx].signalId, "tp2_hit", m_signals[idx].symbol,
                                 "sell", closeLots, currentPrice, 0, m_signals[idx].source,
                                 StringFormat("Remaining: %.2f lots", remainLots));
            }
        }

        // TP3
        if(m_signals[idx].tp1Hit && m_signals[idx].tp2Hit && !m_signals[idx].tp3Hit && currentPrice <= m_signals[idx].tp3)
        {
            if(m_residualPct > 0)
            {
                if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
                totalLots = PositionGetDouble(POSITION_VOLUME);
                unrealizedPnL = PositionGetDouble(POSITION_PROFIT);
                double remainPct = m_tp3Pct + m_residualPct;
                double closeLots = _NormalizeLots(m_signals[idx].symbol, totalLots * (m_tp3Pct / remainPct));
                if(closeLots > 0 && m_trade.PositionClosePartial(m_signals[idx].positionTicket, closeLots))
                {
                    m_signals[idx].tp3Hit = true;
                    Stats.tp3Hits++;
                    double remainLots = totalLots - closeLots;
                    double realizedPnL = _GetPositionPnLFromHistory(m_signals[idx].positionTicket);
                    PrintFormat("[TP3] %s signal=%s (short): closed %.2f lots @ %.5f, trailing residual=%.2f lots",
                                m_signals[idx].symbol, m_signals[idx].signalId,
                                closeLots, currentPrice, remainLots);
                    PrintFormat("[TP3] Realized P&L so far: %.2f, unrealized: %.2f", realizedPnL, unrealizedPnL);

                    string trailMsg = m_enableTrailing ? "Trailing SL active" : "No trailing (disabled)";
                    _QueueNotification(StringFormat(
                        "<b>TP3 Hit (Short)</b>\n"
                        "%s closed %.2f lots @ %.5f\n"
                        "Residual: %.2f lots\n"
                        "%s",
                        m_signals[idx].symbol, closeLots, currentPrice, remainLots, trailMsg
                    ));
                    _QueueTradeEvent(m_signals[idx].signalId, "tp3_hit", m_signals[idx].symbol,
                                     "sell", closeLots, currentPrice, 0, m_signals[idx].source,
                                     StringFormat("Residual: %.2f lots, %s", remainLots, trailMsg));
                }
            }
            else
            {
                if(!PositionSelectByTicket(m_signals[idx].positionTicket)) return;
                unrealizedPnL = PositionGetDouble(POSITION_PROFIT);
                m_trade.PositionClose(m_signals[idx].positionTicket);
                m_signals[idx].tp3Hit = true;
                m_signals[idx].closed = true;
                Stats.tp3Hits++;
                double finalPnL = _GetPositionPnLFromHistory(m_signals[idx].positionTicket);
                Stats.realizedPnL += finalPnL;
                Stats.positionsClosed++;
                PrintFormat("[CLOSE] %s signal=%s (short): fully closed @ %.5f, final P&L=%.2f",
                            m_signals[idx].symbol, m_signals[idx].signalId,
                            currentPrice, finalPnL);

                _QueueNotification(StringFormat(
                    "<b>All TPs Hit - Closed (Short)</b>\n"
                    "%s fully closed @ %.5f\n"
                    "Final P&L: %+.2f",
                    m_signals[idx].symbol, currentPrice, finalPnL
                ));
                _QueueTradeEvent(m_signals[idx].signalId, "tp3_hit", m_signals[idx].symbol,
                                 "sell", 0, currentPrice, finalPnL, m_signals[idx].source, "All TPs hit");
                _QueueTradeEvent(m_signals[idx].signalId, "closed", m_signals[idx].symbol,
                                 "sell", 0, currentPrice, finalPnL, m_signals[idx].source, "Fully closed");
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
            double newSL = NormalizeDouble(currentPrice - m_trailingPoints * point, digits);
            if(newSL > currentSL && newSL > m_signals[idx].entryPrice)
            {
                if(m_trade.PositionModify(m_signals[idx].positionTicket, newSL, tp))
                {
                    PrintFormat("[TRAIL] %s signal=%s: SL %.5f -> %.5f (price=%.5f)",
                                m_signals[idx].symbol, m_signals[idx].signalId,
                                currentSL, newSL, currentPrice);
                }
            }
        }
        else
        {
            double newSL = NormalizeDouble(currentPrice + m_trailingPoints * point, digits);
            if((currentSL == 0 || newSL < currentSL) && newSL < m_signals[idx].entryPrice)
            {
                if(m_trade.PositionModify(m_signals[idx].positionTicket, newSL, tp))
                {
                    PrintFormat("[TRAIL] %s signal=%s (short): SL %.5f -> %.5f (price=%.5f)",
                                m_signals[idx].symbol, m_signals[idx].signalId,
                                currentSL, newSL, currentPrice);
                }
            }
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
