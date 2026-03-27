//+------------------------------------------------------------------+
//|                                                 TradeManager.mqh |
//|              Partial profit booking & force exit management      |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property strict

#include <Trade/Trade.mqh>

enum ENUM_SL_MODE
{
    SL_CANDLE_LOW_HIGH,   // Stop at candle low (long) / high (short)
    SL_VWAP,              // Stop at VWAP level
    SL_PIVOT              // Stop at Pivot Point level
};

class CTradeManager
{
private:
    CTrade m_trade;
    int    m_magic;
    double m_tp1Pct;     // % of position to close at TP1 (default 50%)
    double m_tp2Pct;     // % at TP2 (default 25%)
    double m_tp3Pct;     // % at TP3 (default 25%)
    bool   m_tp1Hit;
    bool   m_tp2Hit;
    int    m_forceExitHour;
    int    m_forceExitMinute;

public:
    CTradeManager() : m_magic(20250327), m_tp1Pct(50), m_tp2Pct(25), m_tp3Pct(25),
                      m_tp1Hit(false), m_tp2Hit(false),
                      m_forceExitHour(15), m_forceExitMinute(20) {}

    void Init(int magic, double slippage = 3)
    {
        m_magic = magic;
        m_trade.SetExpertMagicNumber(magic);
        m_trade.SetDeviationInPoints((ulong)slippage);
    }

    void SetPartialProfitPct(double tp1, double tp2, double tp3)
    {
        m_tp1Pct = tp1;
        m_tp2Pct = tp2;
        m_tp3Pct = tp3;
    }

    void SetForceExitTime(int hour, int minute)
    {
        m_forceExitHour = hour;
        m_forceExitMinute = minute;
    }

    void ResetTPFlags()
    {
        m_tp1Hit = false;
        m_tp2Hit = false;
    }

    //--- Open a long position
    bool OpenLong(const string symbol, double lots, double sl, string comment = "PVE Long")
    {
        ResetTPFlags();
        double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
        return m_trade.Buy(lots, symbol, ask, sl, 0, comment);
    }

    //--- Open a short position
    bool OpenShort(const string symbol, double lots, double sl, string comment = "PVE Short")
    {
        ResetTPFlags();
        double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
        return m_trade.Sell(lots, symbol, bid, sl, 0, comment);
    }

    //--- Manage partial profit booking for long positions
    void ManageLongTP(const string symbol, double currentPrice,
                      double tp1Level, double tp2Level, double tp3Level)
    {
        if(!HasPosition(symbol)) return;

        double totalLots = GetPositionLots(symbol);
        if(totalLots <= 0) return;

        // TP1: Close 50% at R1/S1
        if(!m_tp1Hit && currentPrice >= tp1Level)
        {
            double closeLots = NormalizeLots(symbol, totalLots * m_tp1Pct / 100.0);
            if(closeLots > 0)
            {
                m_trade.PositionClosePartial(symbol, closeLots);
                m_tp1Hit = true;
            }
        }

        // TP2: Close 25% at R2/S2
        if(m_tp1Hit && !m_tp2Hit && currentPrice >= tp2Level)
        {
            totalLots = GetPositionLots(symbol);
            double closeLots = NormalizeLots(symbol, totalLots * (m_tp2Pct / (m_tp2Pct + m_tp3Pct)) );
            if(closeLots > 0)
            {
                m_trade.PositionClosePartial(symbol, closeLots);
                m_tp2Hit = true;
            }
        }

        // TP3: Close remaining at R3/S3
        if(m_tp1Hit && m_tp2Hit && currentPrice >= tp3Level)
        {
            m_trade.PositionClose(symbol);
        }
    }

    //--- Manage partial profit booking for short positions
    void ManageShortTP(const string symbol, double currentPrice,
                       double tp1Level, double tp2Level, double tp3Level)
    {
        if(!HasPosition(symbol)) return;

        double totalLots = GetPositionLots(symbol);
        if(totalLots <= 0) return;

        // TP1: Close 50% at S1
        if(!m_tp1Hit && currentPrice <= tp1Level)
        {
            double closeLots = NormalizeLots(symbol, totalLots * m_tp1Pct / 100.0);
            if(closeLots > 0)
            {
                m_trade.PositionClosePartial(symbol, closeLots);
                m_tp1Hit = true;
            }
        }

        // TP2: Close 25% at S2
        if(m_tp1Hit && !m_tp2Hit && currentPrice <= tp2Level)
        {
            totalLots = GetPositionLots(symbol);
            double closeLots = NormalizeLots(symbol, totalLots * (m_tp2Pct / (m_tp2Pct + m_tp3Pct)) );
            if(closeLots > 0)
            {
                m_trade.PositionClosePartial(symbol, closeLots);
                m_tp2Hit = true;
            }
        }

        // TP3: Close remaining at S3
        if(m_tp1Hit && m_tp2Hit && currentPrice <= tp3Level)
        {
            m_trade.PositionClose(symbol);
        }
    }

    //--- Force exit all positions at market close time
    bool IsForceExitTime()
    {
        MqlDateTime dt;
        TimeToStruct(TimeCurrent(), dt);
        return (dt.hour > m_forceExitHour ||
                (dt.hour == m_forceExitHour && dt.min >= m_forceExitMinute));
    }

    void ForceExitAll(const string symbol)
    {
        if(HasPosition(symbol))
        {
            m_trade.PositionClose(symbol);
            ResetTPFlags();
        }
    }

    //--- Check if position exists for this symbol with our magic number
    bool HasPosition(const string symbol)
    {
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            if(PositionGetSymbol(i) == symbol)
            {
                if(PositionGetInteger(POSITION_MAGIC) == m_magic)
                    return true;
            }
        }
        return false;
    }

    //--- Get current position type
    ENUM_POSITION_TYPE GetPositionType(const string symbol)
    {
        if(PositionSelect(symbol))
            return (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        return POSITION_TYPE_BUY; // Default
    }

    //--- Get position lots
    double GetPositionLots(const string symbol)
    {
        if(PositionSelect(symbol))
            return PositionGetDouble(POSITION_VOLUME);
        return 0;
    }

    //--- Trail stop loss to EMA or VWAP
    void TrailStopLoss(const string symbol, double newSL)
    {
        if(!HasPosition(symbol)) return;
        if(!PositionSelect(symbol)) return;

        double currentSL = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        if(type == POSITION_TYPE_BUY && newSL > currentSL)
            m_trade.PositionModify(symbol, newSL, tp);
        else if(type == POSITION_TYPE_SELL && (currentSL == 0 || newSL < currentSL))
            m_trade.PositionModify(symbol, newSL, tp);
    }

private:
    double NormalizeLots(const string symbol, double lots)
    {
        double minLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
        double maxLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
        double stepLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

        lots = MathFloor(lots / stepLot) * stepLot;
        if(lots < minLot) lots = 0; // Can't trade below minimum
        if(lots > maxLot) lots = maxLot;
        return lots;
    }
};
