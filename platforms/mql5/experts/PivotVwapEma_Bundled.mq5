//+------------------------------------------------------------------+
//|                                        PivotVwapEma_Bundled.mq5  |
//|      BUNDLED: All-in-one Intraday Strategy (no #include needed)  |
//|      Pivot Points (Daily) + VWAP (Session) + 20 EMA              |
//|      Entry: All 3 aligned + candle color confirmation            |
//|      Targets: R1/S1 (50%), R2/S2 (25%), R3/S3 (25%)             |
//|      Force Exit: 15:20 IST                                       |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Bundled Pivot+VWAP+EMA intraday EA - single file, no dependencies"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| ENUMS                                                            |
//+------------------------------------------------------------------+
enum ENUM_SL_MODE
{
    SL_CANDLE_LOW_HIGH,   // Stop at candle low/high
    SL_VWAP,              // Stop at VWAP level
    SL_PIVOT              // Stop at Pivot Point level
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== Strategy Settings ==="
input int           InpEmaPeriod        = 20;              // EMA Period
input ENUM_SL_MODE  InpSLMode           = SL_VWAP;         // Stop Loss Mode
input double        InpLotSize          = 0.1;             // Lot Size
input int           InpMagic            = 20250327;        // Magic Number
input double        InpSlippage         = 3;               // Max Slippage (points)

input group "=== Session Settings (IST) ==="
input int           InpSessionStartHr   = 9;               // Session Start Hour
input int           InpSessionStartMin  = 15;              // Session Start Minute
input int           InpForceExitHr      = 15;              // Force Exit Hour
input int           InpForceExitMin     = 20;              // Force Exit Minute
input int           InpNoNewTradeHr     = 14;              // No New Trade After Hour
input int           InpNoNewTradeMin    = 30;              // No New Trade After Minute

input group "=== Profit Booking ==="
input double        InpTP1Pct           = 50;              // TP1 Close % (at R1/S1)
input double        InpTP2Pct           = 25;              // TP2 Close % (at R2/S2)
input double        InpTP3Pct           = 25;              // TP3 Close % (at R3/S3)

input group "=== Filters ==="
input bool          InpFilterBigCandle  = true;            // Skip entry if candle is too large
input double        InpMaxCandleATRMult = 2.0;             // Max candle size (x ATR)

//+------------------------------------------------------------------+
//| PIVOT POINTS - Inline                                            |
//+------------------------------------------------------------------+
double g_pivot, g_r1, g_r2, g_r3, g_s1, g_s2, g_s3;
datetime g_pivotCalcDate = 0;

bool CalculatePivotPoints()
{
    MqlRates daily[];
    ArraySetAsSeries(daily, true);

    int copied = CopyRates(_Symbol, PERIOD_D1, 1, 1, daily);
    if(copied < 1) return false;

    datetime currentDate = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
    if(g_pivotCalcDate == currentDate) return true;

    double prevH = daily[0].high;
    double prevL = daily[0].low;
    double prevC = daily[0].close;

    g_pivot = (prevH + prevL + prevC) / 3.0;
    g_r1 = 2.0 * g_pivot - prevL;
    g_s1 = 2.0 * g_pivot - prevH;
    g_r2 = g_pivot + (prevH - prevL);
    g_s2 = g_pivot - (prevH - prevL);
    g_r3 = prevH + 2.0 * (g_pivot - prevL);
    g_s3 = prevL - 2.0 * (prevH - g_pivot);

    g_pivotCalcDate = currentDate;

    Print("Pivots calculated | P:", g_pivot, " R1:", g_r1, " R2:", g_r2,
          " R3:", g_r3, " S1:", g_s1, " S2:", g_s2, " S3:", g_s3);
    return true;
}

//+------------------------------------------------------------------+
//| VWAP - Inline                                                    |
//+------------------------------------------------------------------+
double   g_vwap = 0;
datetime g_vwapSessionStart = 0;

bool CalculateVWAP()
{
    datetime currentTime = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);

    // Build today's session start
    dt.hour = InpSessionStartHr;
    dt.min  = InpSessionStartMin;
    dt.sec  = 0;
    datetime todaySession = StructToTime(dt);

    if(currentTime < todaySession)
        todaySession -= 86400;

    // Reset on new session
    if(todaySession != g_vwapSessionStart)
    {
        g_vwap = 0;
        g_vwapSessionStart = todaySession;
    }

    // Copy bars from session start
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int bars = CopyRates(_Symbol, PERIOD_CURRENT, todaySession, currentTime, rates);
    if(bars < 1) return false;

    double cumTPV = 0;
    double cumVol = 0;

    for(int i = bars - 1; i >= 0; i--)
    {
        double tp  = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
        double vol = (double)rates[i].tick_volume;
        if(vol <= 0) vol = 1;

        cumTPV += tp * vol;
        cumVol += vol;
    }

    if(cumVol > 0)
        g_vwap = cumTPV / cumVol;

    return true;
}

//+------------------------------------------------------------------+
//| TRADE MANAGER - Inline                                           |
//+------------------------------------------------------------------+
CTrade g_trade;
bool   g_tp1Hit = false;
bool   g_tp2Hit = false;

double NormalizeLots(double lots)
{
    double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

    lots = MathFloor(lots / stepLot) * stepLot;
    if(lots < minLot) lots = 0;
    if(lots > maxLot) lots = maxLot;
    return lots;
}

bool HasPosition()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionGetSymbol(i) == _Symbol)
        {
            if(PositionGetInteger(POSITION_MAGIC) == InpMagic)
                return true;
        }
    }
    return false;
}

double GetPositionLots()
{
    if(PositionSelect(_Symbol))
        return PositionGetDouble(POSITION_VOLUME);
    return 0;
}

ENUM_POSITION_TYPE GetPositionType()
{
    if(PositionSelect(_Symbol))
        return (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
    return POSITION_TYPE_BUY;
}

bool OpenLong(double lots, double sl)
{
    g_tp1Hit = false;
    g_tp2Hit = false;
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    return g_trade.Buy(lots, _Symbol, ask, sl, 0, "PVE Long");
}

bool OpenShort(double lots, double sl)
{
    g_tp1Hit = false;
    g_tp2Hit = false;
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    return g_trade.Sell(lots, _Symbol, bid, sl, 0, "PVE Short");
}

void CloseAll()
{
    if(HasPosition())
    {
        g_trade.PositionClose(_Symbol);
        g_tp1Hit = false;
        g_tp2Hit = false;
    }
}

void ManageLongTP(double price, double tp1, double tp2, double tp3)
{
    if(!HasPosition()) return;
    double totalLots = GetPositionLots();
    if(totalLots <= 0) return;

    if(!g_tp1Hit && price >= tp1)
    {
        double closeLots = NormalizeLots(totalLots * InpTP1Pct / 100.0);
        if(closeLots > 0)
        {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp1Hit = true;
            Print("TP1 hit at R1: ", tp1, " closed ", closeLots, " lots");
        }
    }

    if(g_tp1Hit && !g_tp2Hit && price >= tp2)
    {
        totalLots = GetPositionLots();
        double ratio = InpTP2Pct / (InpTP2Pct + InpTP3Pct);
        double closeLots = NormalizeLots(totalLots * ratio);
        if(closeLots > 0)
        {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp2Hit = true;
            Print("TP2 hit at R2: ", tp2, " closed ", closeLots, " lots");
        }
    }

    if(g_tp1Hit && g_tp2Hit && price >= tp3)
    {
        g_trade.PositionClose(_Symbol);
        Print("TP3 hit at R3: ", tp3, " fully closed");
    }
}

void ManageShortTP(double price, double tp1, double tp2, double tp3)
{
    if(!HasPosition()) return;
    double totalLots = GetPositionLots();
    if(totalLots <= 0) return;

    if(!g_tp1Hit && price <= tp1)
    {
        double closeLots = NormalizeLots(totalLots * InpTP1Pct / 100.0);
        if(closeLots > 0)
        {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp1Hit = true;
            Print("TP1 hit at S1: ", tp1, " closed ", closeLots, " lots");
        }
    }

    if(g_tp1Hit && !g_tp2Hit && price <= tp2)
    {
        totalLots = GetPositionLots();
        double ratio = InpTP2Pct / (InpTP2Pct + InpTP3Pct);
        double closeLots = NormalizeLots(totalLots * ratio);
        if(closeLots > 0)
        {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp2Hit = true;
            Print("TP2 hit at S2: ", tp2, " closed ", closeLots, " lots");
        }
    }

    if(g_tp1Hit && g_tp2Hit && price <= tp3)
    {
        g_trade.PositionClose(_Symbol);
        Print("TP3 hit at S3: ", tp3, " fully closed");
    }
}

void TrailStopLoss(double newSL)
{
    if(!HasPosition()) return;
    if(!PositionSelect(_Symbol)) return;

    double currentSL = PositionGetDouble(POSITION_SL);
    double tp = PositionGetDouble(POSITION_TP);
    ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

    if(type == POSITION_TYPE_BUY && newSL > currentSL)
        g_trade.PositionModify(_Symbol, newSL, tp);
    else if(type == POSITION_TYPE_SELL && (currentSL == 0 || newSL < currentSL))
        g_trade.PositionModify(_Symbol, newSL, tp);
}

//+------------------------------------------------------------------+
//| TIME HELPERS                                                     |
//+------------------------------------------------------------------+
bool IsSessionActive()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    int currentMins = dt.hour * 60 + dt.min;
    int sessionStart = InpSessionStartHr * 60 + InpSessionStartMin;
    int forceExit = InpForceExitHr * 60 + InpForceExitMin;
    return (currentMins >= sessionStart && currentMins < forceExit);
}

bool IsNoNewTradeTime()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    int currentMins = dt.hour * 60 + dt.min;
    int cutoff = InpNoNewTradeHr * 60 + InpNoNewTradeMin;
    return (currentMins >= cutoff);
}

bool IsForceExitTime()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    return (dt.hour > InpForceExitHr ||
            (dt.hour == InpForceExitHr && dt.min >= InpForceExitMin));
}

//+------------------------------------------------------------------+
//| STOP LOSS CALCULATOR                                             |
//+------------------------------------------------------------------+
double CalculateStopLoss(bool isLong, double candleExtreme, double vwapVal, double pivotVal)
{
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    double buffer = 5 * point;

    if(isLong)
    {
        switch(InpSLMode)
        {
            case SL_CANDLE_LOW_HIGH: return candleExtreme - buffer;
            case SL_VWAP:            return vwapVal - buffer;
            case SL_PIVOT:           return pivotVal - buffer;
        }
    }
    else
    {
        switch(InpSLMode)
        {
            case SL_CANDLE_LOW_HIGH: return candleExtreme + buffer;
            case SL_VWAP:            return vwapVal + buffer;
            case SL_PIVOT:           return pivotVal + buffer;
        }
    }
    return candleExtreme;
}

//+------------------------------------------------------------------+
//| GLOBAL STATE                                                     |
//+------------------------------------------------------------------+
int      emaHandle, atrHandle;
bool     g_inTrade = false;
datetime g_lastBarTime = 0;
int      g_tradeDirection = 0; // 1=long, -1=short, 0=none

//+------------------------------------------------------------------+
//| EA INIT                                                          |
//+------------------------------------------------------------------+
int OnInit()
{
    g_trade.SetExpertMagicNumber(InpMagic);
    g_trade.SetDeviationInPoints((ulong)InpSlippage);

    emaHandle = iMA(_Symbol, PERIOD_CURRENT, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
    atrHandle = iATR(_Symbol, PERIOD_CURRENT, 14);

    if(emaHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
    {
        Print("Failed to create indicator handles");
        return INIT_FAILED;
    }

    Print("PivotVwapEma BUNDLED EA initialized | Magic: ", InpMagic,
          " | EMA: ", InpEmaPeriod, " | SL Mode: ", EnumToString(InpSLMode));
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| EA DEINIT                                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(emaHandle != INVALID_HANDLE) IndicatorRelease(emaHandle);
    if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
}

//+------------------------------------------------------------------+
//| EA TICK                                                          |
//+------------------------------------------------------------------+
void OnTick()
{
    //=== FORCE EXIT CHECK (every tick) ===
    if(IsForceExitTime() && HasPosition())
    {
        Print("FORCE EXIT at ", TimeToString(TimeCurrent(), TIME_MINUTES));
        CloseAll();
        g_inTrade = false;
        g_tradeDirection = 0;
        return;
    }

    //=== NEW BAR CHECK ===
    datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
    if(currentBarTime == g_lastBarTime)
    {
        if(g_inTrade) ManagePosition();
        return;
    }
    g_lastBarTime = currentBarTime;

    //=== UPDATE ALL INDICATORS ===
    if(!CalculatePivotPoints())
    {
        Print("Pivot calculation failed");
        return;
    }

    if(!CalculateVWAP())
    {
        Print("VWAP calculation failed");
        return;
    }

    double ema[], atr[];
    ArraySetAsSeries(ema, true);
    ArraySetAsSeries(atr, true);
    if(CopyBuffer(emaHandle, 0, 0, 3, ema) < 3) return;
    if(CopyBuffer(atrHandle, 0, 0, 3, atr) < 3) return;

    //=== PRICE DATA (last closed bar) ===
    double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);
    double openPrice  = iOpen(_Symbol, PERIOD_CURRENT, 1);
    double highPrice  = iHigh(_Symbol, PERIOD_CURRENT, 1);
    double lowPrice   = iLow(_Symbol, PERIOD_CURRENT, 1);
    double prevClose  = iClose(_Symbol, PERIOD_CURRENT, 2);

    double emaValue   = ema[1];
    double atrValue   = atr[1];

    //=== MANAGE EXISTING POSITION ===
    if(g_inTrade && HasPosition())
    {
        ManagePosition();
        return;
    }

    // Reset if position was closed externally
    if(g_inTrade && !HasPosition())
    {
        g_inTrade = false;
        g_tradeDirection = 0;
    }

    //=== TIME FILTERS ===
    if(IsNoNewTradeTime()) return;
    if(!IsSessionActive()) return;

    //=== ENTRY LOGIC ===
    bool isGreenCandle = closePrice > openPrice;
    bool isRedCandle   = closePrice < openPrice;
    double candleSize  = highPrice - lowPrice;

    // Big candle filter
    if(InpFilterBigCandle && atrValue > 0 && candleSize > atrValue * InpMaxCandleATRMult)
        return;

    //--- LONG ENTRY ---
    if(isGreenCandle &&
       closePrice > g_pivot &&
       closePrice > emaValue &&
       closePrice > g_vwap)
    {
        // Crossover confirmation: prev bar was below at least one
        if(prevClose <= g_pivot || prevClose <= emaValue || prevClose <= g_vwap)
        {
            double sl = CalculateStopLoss(true, lowPrice, g_vwap, g_pivot);

            // Risk/Reward >= 1:1 to R1
            if(g_r1 > closePrice && (g_r1 - closePrice) >= (closePrice - sl))
            {
                if(OpenLong(InpLotSize, sl))
                {
                    g_inTrade = true;
                    g_tradeDirection = 1;
                    Print("LONG @ ", closePrice, " | SL: ", sl,
                          " | P:", g_pivot, " EMA:", emaValue, " VWAP:", g_vwap,
                          " | Targets R1:", g_r1, " R2:", g_r2, " R3:", g_r3);
                }
            }
        }
    }

    //--- SHORT ENTRY ---
    if(!g_inTrade && isRedCandle &&
       closePrice < g_pivot &&
       closePrice < emaValue &&
       closePrice < g_vwap)
    {
        if(prevClose >= g_pivot || prevClose >= emaValue || prevClose >= g_vwap)
        {
            double sl = CalculateStopLoss(false, highPrice, g_vwap, g_pivot);

            // Risk/Reward >= 1:1 to S1
            if(g_s1 < closePrice && (closePrice - g_s1) >= (sl - closePrice))
            {
                if(OpenShort(InpLotSize, sl))
                {
                    g_inTrade = true;
                    g_tradeDirection = -1;
                    Print("SHORT @ ", closePrice, " | SL: ", sl,
                          " | P:", g_pivot, " EMA:", emaValue, " VWAP:", g_vwap,
                          " | Targets S1:", g_s1, " S2:", g_s2, " S3:", g_s3);
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| POSITION MANAGEMENT: Partial TP + Trailing SL                    |
//+------------------------------------------------------------------+
void ManagePosition()
{
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

    if(g_tradeDirection == 1) // Long
    {
        ManageLongTP(bid, g_r1, g_r2, g_r3);

        // Trail SL to EMA
        double ema[];
        ArraySetAsSeries(ema, true);
        if(CopyBuffer(emaHandle, 0, 0, 2, ema) >= 2)
            TrailStopLoss(ema[1]);
    }
    else if(g_tradeDirection == -1) // Short
    {
        ManageShortTP(ask, g_s1, g_s2, g_s3);

        // Trail SL to EMA
        double ema[];
        ArraySetAsSeries(ema, true);
        if(CopyBuffer(emaHandle, 0, 0, 2, ema) >= 2)
            TrailStopLoss(ema[1]);
    }

    // Check if fully closed
    if(!HasPosition())
    {
        g_inTrade = false;
        g_tradeDirection = 0;
    }
}
//+------------------------------------------------------------------+
