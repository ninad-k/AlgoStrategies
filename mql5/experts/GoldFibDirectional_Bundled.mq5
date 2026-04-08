//+------------------------------------------------------------------+
//|                                  GoldFibDirectional_Bundled.mq5   |
//|      BUNDLED: Gold Fib Directional Strategy - Single file EA      |
//|      No hedge. BUY or SELL based on EMA trend + Fib levels       |
//|      22H + Session Fib levels, EMA 200/50, optional SuperTrend   |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Gold Fib Directional EA - trend-following entries at fib level bounces"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| ENUMS                                                            |
//+------------------------------------------------------------------+
enum ENUM_SL_MODE
{
    SL_SUPERTREND,   // SuperTrend value
    SL_FIXED_PIPS,   // Fixed pips
    SL_PREV_LEVEL    // Previous fib level
};

enum ENUM_TP_MODE
{
    TP_NEXT_LEVEL,   // Next opposing fib level
    TP_FIXED_PIPS,   // Fixed pips
    TP_RR_RATIO      // Risk-Reward ratio
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== Fibonacci Settings ==="
input double        InpFibLevel1       = 0.44;          // Fib Level 1
input double        InpFibLevel2       = 0.50;          // Fib Level 2
input int           InpH22Lookback     = 30;            // 22H Lookback (days)
input double        InpOverlapPips     = 50;            // Overlap Threshold (pips)

input group "=== EMA Settings ==="
input int           InpEmaFast         = 50;            // EMA Fast Period
input int           InpEmaSlow         = 200;           // EMA Slow Period

input group "=== SuperTrend (Optional) ==="
input bool          InpUseSuperTrend   = true;          // Enable SuperTrend Filter
input int           InpSTperiod        = 10;            // SuperTrend ATR Period
input double        InpSTmultiplier    = 3.0;           // SuperTrend Multiplier

input group "=== Trade Settings ==="
input double        InpLotSize         = 0.1;           // Lot Size
input int           InpMagic           = 20250329;      // Magic Number
input double        InpSlippage        = 5;             // Max Slippage (points)
input int           InpDailyCloseHr    = 21;            // Daily Close Hour (UTC)
input int           InpDailyCloseMin   = 0;             // Daily Close Minute
input int           InpCooldownBars    = 10;            // Cooldown bars after trade

input group "=== Stop Loss ==="
input ENUM_SL_MODE  InpSLMode          = SL_SUPERTREND; // SL Mode
input double        InpFixedSLPips     = 50;            // Fixed SL (pips) - if SL_FIXED_PIPS

input group "=== Take Profit ==="
input ENUM_TP_MODE  InpTPMode          = TP_NEXT_LEVEL; // TP Mode
input double        InpFixedTPPips     = 100;           // Fixed TP (pips) - if TP_FIXED_PIPS
input double        InpRRratio         = 2.0;           // Risk:Reward ratio - if TP_RR_RATIO

input group "=== Trailing Stop (Optional) ==="
input bool          InpUseTrailing     = false;         // Enable Trailing Stop
input double        InpTrailPips       = 30;            // Trail Distance (pips)
input double        InpTrailStartPips  = 20;            // Start Trail After (pips profit)
input bool          InpTrailByST       = false;         // Trail by SuperTrend Value

input group "=== Display ==="
input bool          InpPlotLevels      = true;          // Plot Fib Level Lines
input bool          InpShowDashboard   = true;          // Show Dashboard
input color         InpH22Color        = clrGold;       // 22H Level Color
input color         InpSession23Color  = clrOrange;     // 23:00 Level Color
input color         InpSession07Color  = clrCyan;       // 07:00 Level Color
input color         InpSession12Color  = clrMagenta;    // 12:00 Level Color
input color         InpOverlapColor    = clrWhite;      // Overlap Level Color

//+------------------------------------------------------------------+
//| STRUCTURES                                                       |
//+------------------------------------------------------------------+
struct FibLevel
{
    double   price;
    string   source;
    datetime created;
    int      confidence;
};

//+------------------------------------------------------------------+
//| GLOBALS                                                          |
//+------------------------------------------------------------------+
CTrade   g_trade;
FibLevel g_levels[];
int      g_levelCount    = 0;
#define  MAX_LEVELS 200

int g_emaFastHandle, g_emaSlowHandle, g_atrHandle;

//--- SuperTrend
double g_stValue         = 0;
bool   g_stBullish       = true;
double g_stPrevUpper     = 0;
double g_stPrevLower     = 0;
bool   g_stPrevBull      = true;

//--- Bar tracking
datetime g_lastBarTime   = 0;
datetime g_lastCalcTime  = 0;

//--- Cooldown
int    g_barsSinceExit   = 999;

//--- Dashboard
double g_sessionPnL      = 0;
double g_cumulativePnL   = 0;
int    g_totalTrades     = 0;
int    g_buyTradeCount   = 0;
int    g_sellTradeCount  = 0;
int    g_winCount        = 0;

//--- Nearest levels
double g_nearSupport     = 0;
double g_nearResist      = 0;
int    g_nearSupConf     = 0;
int    g_nearResConf     = 0;
double g_nextSupport     = 0;  // second nearest support
double g_nextResist      = 0;  // second nearest resistance

string g_objPrefix = "GFD_";

//+------------------------------------------------------------------+
int OnInit()
{
    g_trade.SetExpertMagicNumber(InpMagic);
    g_trade.SetDeviationInPoints((ulong)InpSlippage);
    g_trade.SetTypeFilling(ORDER_FILLING_IOC);

    g_emaFastHandle = iMA(_Symbol, PERIOD_M1, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
    g_emaSlowHandle = iMA(_Symbol, PERIOD_M1, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
    g_atrHandle     = iATR(_Symbol, PERIOD_M1, InpSTperiod);

    if(g_emaFastHandle == INVALID_HANDLE || g_emaSlowHandle == INVALID_HANDLE || g_atrHandle == INVALID_HANDLE)
    {
        Print("Failed to create indicator handles");
        return INIT_FAILED;
    }

    ArrayResize(g_levels, MAX_LEVELS);
    g_levelCount = 0;

    Print("GoldFibDirectional EA initialized. Magic=", InpMagic);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(g_emaFastHandle != INVALID_HANDLE) IndicatorRelease(g_emaFastHandle);
    if(g_emaSlowHandle != INVALID_HANDLE) IndicatorRelease(g_emaSlowHandle);
    if(g_atrHandle     != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
    ObjectsDeleteAll(0, g_objPrefix);
    Comment("");
}

//+------------------------------------------------------------------+
void OnTick()
{
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

    //--- Daily close
    if(IsDailyCloseTime())
    {
        ClosePosition("Daily close - swap avoidance");
        return;
    }

    //--- Trailing stop (every tick)
    if(InpUseTrailing && HasPosition()) ManageTrailingStop();

    //--- New M1 bar
    datetime curBarTime = iTime(_Symbol, PERIOD_M1, 0);
    if(curBarTime == g_lastBarTime) return;
    g_lastBarTime = curBarTime;
    g_barsSinceExit++;

    //--- Recalculate levels
    RecalculateLevels();
    DetectOverlaps();
    FindNearestLevels(bid);

    if(InpPlotLevels) DrawLevelLines();

    //--- Get EMAs
    double emaF[3], emaS[3];
    if(CopyBuffer(g_emaFastHandle, 0, 0, 3, emaF) < 3) return;
    if(CopyBuffer(g_emaSlowHandle, 0, 0, 3, emaS) < 3) return;

    double ema50      = emaF[0];
    double ema200     = emaS[0];
    double prevEma50  = emaF[1];
    double prevEma200 = emaS[1];

    //--- SuperTrend
    if(InpUseSuperTrend) CalculateSuperTrend();

    //--- Trend determination
    bool bullishTrend = (bid > ema200) && (ema50 > ema200);
    bool bearishTrend = (bid < ema200) && (ema50 < ema200);

    //--- EMA cross exit
    if(HasPosition())
    {
        bool emaCrossBear = (prevEma50 >= prevEma200) && (ema50 < ema200);
        bool emaCrossBull = (prevEma50 <= prevEma200) && (ema50 > ema200);

        int posDir = GetPositionDirection();

        if(posDir == 1 && emaCrossBear)
        {
            ClosePosition("EMA cross bearish - exit BUY");
        }
        else if(posDir == -1 && emaCrossBull)
        {
            ClosePosition("EMA cross bullish - exit SELL");
        }

        // SuperTrend flip exit
        if(InpUseSuperTrend && HasPosition())
        {
            posDir = GetPositionDirection();
            if(posDir == 1 && !g_stBullish)
                ClosePosition("SuperTrend bearish flip - exit BUY");
            else if(posDir == -1 && g_stBullish)
                ClosePosition("SuperTrend bullish flip - exit SELL");
        }
    }

    //--- Entry logic (only if no position and cooldown passed)
    if(!HasPosition() && g_barsSinceExit >= InpCooldownBars)
    {
        //--- Get latest M1 candle info
        MqlRates m1[];
        ArraySetAsSeries(m1, true);
        if(CopyRates(_Symbol, PERIOD_M1, 1, 2, m1) < 2) return;

        double prevClose = m1[0].close;
        double prevOpen  = m1[0].open;
        bool   bullCandle = (prevClose > prevOpen);
        bool   bearCandle = (prevClose < prevOpen);

        //--- BUY: bullish trend + price bounces off support + bullish candle
        if(bullishTrend && g_nearSupport > 0)
        {
            double distToSup = bid - g_nearSupport;
            double threshold = InpOverlapPips * _Point * 10;

            // Price near support and bouncing (bullish candle close above support)
            if(distToSup >= 0 && distToSup <= threshold * 3 && bullCandle && prevClose > g_nearSupport)
            {
                // SuperTrend confirmation (optional)
                if(!InpUseSuperTrend || g_stBullish)
                {
                    double sl = CalculateSL(true, bid);
                    double tp = CalculateTP(true, bid, sl);
                    double lots = ValidateLots(InpLotSize);

                    if(g_trade.Buy(lots, _Symbol, ask, sl, tp,
                       StringFormat("GFD BUY @sup %.2f [x%d]", g_nearSupport, g_nearSupConf)))
                    {
                        g_buyTradeCount++;
                        g_totalTrades++;
                        Print("BUY at ", ask, " | SL:", sl, " TP:", tp,
                              " | Support:", g_nearSupport, " Conf:", g_nearSupConf);
                    }
                }
            }
        }

        //--- SELL: bearish trend + price rejects resistance + bearish candle
        if(bearishTrend && g_nearResist > 0 && !HasPosition())
        {
            double distToRes = g_nearResist - bid;
            double threshold = InpOverlapPips * _Point * 10;

            if(distToRes >= 0 && distToRes <= threshold * 3 && bearCandle && prevClose < g_nearResist)
            {
                if(!InpUseSuperTrend || !g_stBullish)
                {
                    double sl = CalculateSL(false, bid);
                    double tp = CalculateTP(false, bid, sl);
                    double lots = ValidateLots(InpLotSize);

                    if(g_trade.Sell(lots, _Symbol, bid, sl, tp,
                       StringFormat("GFD SELL @res %.2f [x%d]", g_nearResist, g_nearResConf)))
                    {
                        g_sellTradeCount++;
                        g_totalTrades++;
                        Print("SELL at ", bid, " | SL:", sl, " TP:", tp,
                              " | Resist:", g_nearResist, " Conf:", g_nearResConf);
                    }
                }
            }
        }
    }

    //--- Dashboard
    if(InpShowDashboard) UpdateDashboard(bid, ema50, ema200);
}

//+------------------------------------------------------------------+
//| STOP LOSS CALCULATION                                            |
//+------------------------------------------------------------------+
double CalculateSL(bool isBuy, double price)
{
    double sl = 0;
    double pipValue = _Point * 10;

    switch(InpSLMode)
    {
        case SL_SUPERTREND:
            if(InpUseSuperTrend && g_stValue > 0)
                sl = g_stValue;
            else
                sl = isBuy ? price - InpFixedSLPips * pipValue : price + InpFixedSLPips * pipValue;
            break;

        case SL_FIXED_PIPS:
            sl = isBuy ? price - InpFixedSLPips * pipValue : price + InpFixedSLPips * pipValue;
            break;

        case SL_PREV_LEVEL:
            if(isBuy && g_nextSupport > 0)
                sl = g_nextSupport - 5 * pipValue; // 5 pip buffer below next support
            else if(!isBuy && g_nextResist > 0)
                sl = g_nextResist + 5 * pipValue;
            else
                sl = isBuy ? price - InpFixedSLPips * pipValue : price + InpFixedSLPips * pipValue;
            break;
    }

    return NormalizeDouble(sl, _Digits);
}

//+------------------------------------------------------------------+
//| TAKE PROFIT CALCULATION                                          |
//+------------------------------------------------------------------+
double CalculateTP(bool isBuy, double price, double sl)
{
    double tp = 0;
    double pipValue = _Point * 10;

    switch(InpTPMode)
    {
        case TP_NEXT_LEVEL:
            if(isBuy && g_nearResist > 0)
                tp = g_nearResist;
            else if(!isBuy && g_nearSupport > 0)
                tp = g_nearSupport;
            else
                tp = isBuy ? price + InpFixedTPPips * pipValue : price - InpFixedTPPips * pipValue;
            break;

        case TP_FIXED_PIPS:
            tp = isBuy ? price + InpFixedTPPips * pipValue : price - InpFixedTPPips * pipValue;
            break;

        case TP_RR_RATIO:
        {
            double risk = MathAbs(price - sl);
            tp = isBuy ? price + risk * InpRRratio : price - risk * InpRRratio;
            break;
        }
    }

    return NormalizeDouble(tp, _Digits);
}

//+------------------------------------------------------------------+
//| VALIDATE LOT SIZE                                                |
//+------------------------------------------------------------------+
double ValidateLots(double lots)
{
    double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

    lots = MathMax(lots, minLot);
    lots = MathMin(lots, maxLot);
    lots = MathRound(lots / lotStep) * lotStep;
    return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| POSITION HELPERS                                                 |
//+------------------------------------------------------------------+
bool HasPosition()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        return true;
    }
    return false;
}

int GetPositionDirection()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        return (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
    }
    return 0;
}

double GetPositionProfit()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        return PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
    }
    return 0;
}

//+------------------------------------------------------------------+
//| CLOSE POSITION                                                   |
//+------------------------------------------------------------------+
void ClosePosition(string reason)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

        double profit = PositionGetDouble(POSITION_PROFIT);
        g_cumulativePnL += profit;
        if(profit > 0) g_winCount++;

        g_trade.PositionClose(ticket);
        g_barsSinceExit = 0;
        Print(reason, " | Profit: ", profit);
    }
}

//+------------------------------------------------------------------+
//| DAILY CLOSE CHECK                                                |
//+------------------------------------------------------------------+
bool IsDailyCloseTime()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    return (dt.hour == InpDailyCloseHr && dt.min >= InpDailyCloseMin && dt.min < InpDailyCloseMin + 2);
}

//+------------------------------------------------------------------+
//| TRAILING STOP                                                    |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
    double trailPts = InpTrailPips * _Point * 10;
    double startPts = InpTrailStartPips * _Point * 10;

    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

        double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        double curSL     = PositionGetDouble(POSITION_SL);
        long   posType   = PositionGetInteger(POSITION_TYPE);

        if(posType == POSITION_TYPE_BUY)
        {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            if(bid - openPrice >= startPts)
            {
                double newSL;
                if(InpTrailByST && InpUseSuperTrend && g_stBullish && g_stValue > 0)
                    newSL = g_stValue;
                else
                    newSL = bid - trailPts;

                newSL = NormalizeDouble(newSL, _Digits);
                if(newSL > curSL + _Point)
                    g_trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
            }
        }
        else
        {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            if(openPrice - ask >= startPts)
            {
                double newSL;
                if(InpTrailByST && InpUseSuperTrend && !g_stBullish && g_stValue > 0)
                    newSL = g_stValue;
                else
                    newSL = ask + trailPts;

                newSL = NormalizeDouble(newSL, _Digits);
                if(newSL < curSL - _Point || curSL == 0)
                    g_trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 22H LEVEL CALCULATION (from H1 bars)                             |
//+------------------------------------------------------------------+
void Calculate22HLevels()
{
    MqlRates h1[];
    ArraySetAsSeries(h1, true);
    int barsNeeded = InpH22Lookback * 24 + 48;
    int copied = CopyRates(_Symbol, PERIOD_H1, 0, barsNeeded, h1);
    if(copied < 48) return;

    datetime cutoff = TimeCurrent() - InpH22Lookback * 86400;
    int found = 0;

    for(int i = 0; i < copied - 22 && found < InpH22Lookback; i++)
    {
        MqlDateTime dt;
        TimeToStruct(h1[i].time, dt);
        if(dt.hour != 20) continue;
        if(h1[i].time < cutoff) break;
        if(i + 21 >= copied) continue;

        double cHigh = -DBL_MAX, cLow = DBL_MAX;
        for(int j = i; j < i + 22 && j < copied; j++)
        {
            if(h1[j].high > cHigh) cHigh = h1[j].high;
            if(h1[j].low  < cLow)  cLow  = h1[j].low;
        }

        double range = cHigh - cLow;
        if(range < _Point) continue;

        AddLevel(cHigh - InpFibLevel1 * range, "H22", h1[i].time);
        AddLevel(cHigh - InpFibLevel2 * range, "H22", h1[i].time);
        found++;
    }
}

//+------------------------------------------------------------------+
//| SESSION LEVEL CALCULATION (from M30 bars)                        |
//+------------------------------------------------------------------+
void CalculateSessionLevels()
{
    MqlRates m30[];
    ArraySetAsSeries(m30, true);
    int copied = CopyRates(_Symbol, PERIOD_M30, 0, 200, m30);
    if(copied < 10) return;

    datetime twoDaysAgo = TimeCurrent() - 2 * 86400;
    bool found23 = false, found07 = false, found12 = false;
    bool waitRed = false;
    datetime time23 = 0;

    for(int i = 0; i < copied; i++)
    {
        if(m30[i].time < twoDaysAgo) break;

        MqlDateTime dt;
        TimeToStruct(m30[i].time, dt);

        // 23:00 - first red candle after
        if(dt.hour == 23 && dt.min == 0 && !waitRed && !found23)
        {
            waitRed = true;
            time23 = m30[i].time;
            continue;
        }
        if(waitRed && !found23 && m30[i].time > time23)
        {
            if(m30[i].close < m30[i].open)
            {
                double range = m30[i].high - m30[i].low;
                if(range > _Point)
                {
                    AddLevel(m30[i].high - InpFibLevel1 * range, "S23", m30[i].time);
                    AddLevel(m30[i].high - InpFibLevel2 * range, "S23", m30[i].time);
                    found23 = true;
                    waitRed = false;
                }
            }
        }

        // 07:00
        if(dt.hour == 7 && dt.min == 0 && !found07)
        {
            double range = m30[i].high - m30[i].low;
            if(range > _Point)
            {
                AddLevel(m30[i].high - InpFibLevel1 * range, "S07", m30[i].time);
                AddLevel(m30[i].high - InpFibLevel2 * range, "S07", m30[i].time);
                found07 = true;
            }
        }

        // 12:00
        if(dt.hour == 12 && dt.min == 0 && !found12)
        {
            double range = m30[i].high - m30[i].low;
            if(range > _Point)
            {
                AddLevel(m30[i].high - InpFibLevel1 * range, "S12", m30[i].time);
                AddLevel(m30[i].high - InpFibLevel2 * range, "S12", m30[i].time);
                found12 = true;
            }
        }
    }
}

//+------------------------------------------------------------------+
void AddLevel(double price, string source, datetime created)
{
    if(g_levelCount >= MAX_LEVELS) return;
    g_levels[g_levelCount].price      = NormalizeDouble(price, _Digits);
    g_levels[g_levelCount].source     = source;
    g_levels[g_levelCount].created    = created;
    g_levels[g_levelCount].confidence = 1;
    g_levelCount++;
}

void RecalculateLevels()
{
    if(TimeCurrent() - g_lastCalcTime < 60) return;
    g_lastCalcTime = TimeCurrent();
    g_levelCount = 0;
    Calculate22HLevels();
    CalculateSessionLevels();
}

//+------------------------------------------------------------------+
//| OVERLAP DETECTION                                                |
//+------------------------------------------------------------------+
void DetectOverlaps()
{
    double threshold = InpOverlapPips * _Point * 10;
    for(int i = 0; i < g_levelCount; i++)
        g_levels[i].confidence = 1;

    for(int i = 0; i < g_levelCount; i++)
        for(int j = i + 1; j < g_levelCount; j++)
            if(MathAbs(g_levels[i].price - g_levels[j].price) <= threshold)
            {
                g_levels[i].confidence++;
                g_levels[j].confidence++;
            }
}

//+------------------------------------------------------------------+
//| FIND NEAREST LEVELS (support, resist, + next beyond those)       |
//+------------------------------------------------------------------+
void FindNearestLevels(double price)
{
    g_nearSupport = 0; g_nearResist = 0;
    g_nextSupport = 0; g_nextResist = 0;
    g_nearSupConf = 0; g_nearResConf = 0;

    // Collect all supports and resistances
    double supports[];
    int    supConfs[];
    double resists[];
    int    resConfs[];
    ArrayResize(supports, 0);
    ArrayResize(supConfs, 0);
    ArrayResize(resists, 0);
    ArrayResize(resConfs, 0);

    for(int i = 0; i < g_levelCount; i++)
    {
        if(g_levels[i].price < price)
        {
            int sz = ArraySize(supports);
            ArrayResize(supports, sz + 1);
            ArrayResize(supConfs, sz + 1);
            supports[sz] = g_levels[i].price;
            supConfs[sz] = g_levels[i].confidence;
        }
        else
        {
            int sz = ArraySize(resists);
            ArrayResize(resists, sz + 1);
            ArrayResize(resConfs, sz + 1);
            resists[sz] = g_levels[i].price;
            resConfs[sz] = g_levels[i].confidence;
        }
    }

    // Sort supports descending (nearest first)
    for(int i = 0; i < ArraySize(supports) - 1; i++)
        for(int j = i + 1; j < ArraySize(supports); j++)
            if(supports[j] > supports[i])
            {
                double tmp = supports[i]; supports[i] = supports[j]; supports[j] = tmp;
                int    tc  = supConfs[i]; supConfs[i] = supConfs[j]; supConfs[j] = tc;
            }

    // Sort resists ascending (nearest first)
    for(int i = 0; i < ArraySize(resists) - 1; i++)
        for(int j = i + 1; j < ArraySize(resists); j++)
            if(resists[j] < resists[i])
            {
                double tmp = resists[i]; resists[i] = resists[j]; resists[j] = tmp;
                int    tc  = resConfs[i]; resConfs[i] = resConfs[j]; resConfs[j] = tc;
            }

    if(ArraySize(supports) >= 1) { g_nearSupport = supports[0]; g_nearSupConf = supConfs[0]; }
    if(ArraySize(supports) >= 2) { g_nextSupport = supports[1]; }
    if(ArraySize(resists) >= 1)  { g_nearResist  = resists[0];  g_nearResConf = resConfs[0]; }
    if(ArraySize(resists) >= 2)  { g_nextResist  = resists[1]; }
}

//+------------------------------------------------------------------+
//| SUPERTREND                                                       |
//+------------------------------------------------------------------+
void CalculateSuperTrend()
{
    double atr[];
    ArraySetAsSeries(atr, true);
    if(CopyBuffer(g_atrHandle, 0, 0, 2, atr) < 2) return;

    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    if(CopyRates(_Symbol, PERIOD_M1, 0, 3, rates) < 3) return;

    double hl2 = (rates[0].high + rates[0].low) / 2.0;
    double upper = hl2 + InpSTmultiplier * atr[0];
    double lower = hl2 - InpSTmultiplier * atr[0];

    if(g_stPrevLower > 0 && lower < g_stPrevLower && rates[1].close > g_stPrevLower)
        lower = g_stPrevLower;
    if(g_stPrevUpper > 0 && upper > g_stPrevUpper && rates[1].close < g_stPrevUpper)
        upper = g_stPrevUpper;

    if(rates[0].close > upper) g_stBullish = true;
    else if(rates[0].close < lower) g_stBullish = false;
    else g_stBullish = g_stPrevBull;

    g_stValue     = g_stBullish ? lower : upper;
    g_stPrevUpper = upper;
    g_stPrevLower = lower;
    g_stPrevBull  = g_stBullish;
}

//+------------------------------------------------------------------+
//| DRAW LEVEL LINES                                                 |
//+------------------------------------------------------------------+
void DrawLevelLines()
{
    ObjectsDeleteAll(0, g_objPrefix + "LVL_");
    ObjectsDeleteAll(0, g_objPrefix + "LBL_");

    for(int i = 0; i < g_levelCount; i++)
    {
        string name = g_objPrefix + "LVL_" + IntegerToString(i);
        color  clr  = InpH22Color;
        int    w    = 1;

        if(g_levels[i].source == "S23")      clr = InpSession23Color;
        else if(g_levels[i].source == "S07") clr = InpSession07Color;
        else if(g_levels[i].source == "S12") clr = InpSession12Color;

        if(g_levels[i].confidence >= 2) { clr = InpOverlapColor; w = 2; }
        if(g_levels[i].confidence >= 3) w = 3;

        ObjectCreate(0, name, OBJ_HLINE, 0, 0, g_levels[i].price);
        ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
        ObjectSetInteger(0, name, OBJPROP_WIDTH, w);
        ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
        ObjectSetInteger(0, name, OBJPROP_BACK, true);
        ObjectSetString(0, name, OBJPROP_TOOLTIP,
            StringFormat("%s %.2f [x%d]", g_levels[i].source, g_levels[i].price, g_levels[i].confidence));

        string lbl = g_objPrefix + "LBL_" + IntegerToString(i);
        ObjectCreate(0, lbl, OBJ_TEXT, 0, TimeCurrent(), g_levels[i].price);
        ObjectSetString(0, lbl, OBJPROP_TEXT,
            StringFormat("%.2f %s x%d", g_levels[i].price, g_levels[i].source, g_levels[i].confidence));
        ObjectSetInteger(0, lbl, OBJPROP_COLOR, clr);
        ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE, 8);
    }
    ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| DASHBOARD                                                        |
//+------------------------------------------------------------------+
void UpdateDashboard(double price, double ema50, double ema200)
{
    double openPnL = GetPositionProfit();
    g_sessionPnL = openPnL;
    int posDir = GetPositionDirection();

    double posLots = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        posLots += PositionGetDouble(POSITION_VOLUME);
    }

    double winRate = (g_totalTrades > 0) ? (double)g_winCount / g_totalTrades * 100.0 : 0;

    string sep = "------------------------------------------------\n";
    string d = "";
    d += "   GOLD FIB DIRECTIONAL - DASHBOARD\n";
    d += sep;
    d += StringFormat("  Price:           %.2f\n", price);
    d += StringFormat("  Open P&L:        %.2f\n", openPnL);
    d += StringFormat("  Cumulative P&L:  %.2f\n", g_cumulativePnL);
    d += sep;

    string posStr = (posDir == 1) ? "BUY" : (posDir == -1) ? "SELL" : "FLAT";
    color  posClr = (posDir == 1) ? clrLime : (posDir == -1) ? clrRed : clrGray;
    d += StringFormat("  Position:  %s  (%.2f lots)\n", posStr, posLots);
    d += sep;

    d += StringFormat("  Total Trades:    %d\n", g_totalTrades);
    d += StringFormat("  Buy Trades:      %d\n", g_buyTradeCount);
    d += StringFormat("  Sell Trades:     %d\n", g_sellTradeCount);
    d += StringFormat("  Win Rate:        %.1f%%\n", winRate);
    d += sep;

    d += StringFormat("  Next Resist:  %.2f [Conf: %d]\n", g_nearResist, g_nearResConf);
    d += StringFormat("  Next Support: %.2f [Conf: %d]\n", g_nearSupport, g_nearSupConf);
    if(g_nextResist > 0)
        d += StringFormat("  2nd Resist:   %.2f\n", g_nextResist);
    if(g_nextSupport > 0)
        d += StringFormat("  2nd Support:  %.2f\n", g_nextSupport);
    d += sep;

    d += StringFormat("  EMA 50:  %.2f  |  EMA 200: %.2f\n", ema50, ema200);
    string trend = (price > ema200 && ema50 > ema200) ? "BULLISH" :
                   (price < ema200 && ema50 < ema200) ? "BEARISH" : "MIXED";
    d += StringFormat("  Trend:   %s\n", trend);

    if(InpUseSuperTrend)
        d += StringFormat("  ST:      %.2f (%s)\n", g_stValue, g_stBullish ? "BULL" : "BEAR");

    d += StringFormat("  SL Mode: %s  |  TP Mode: %s\n",
        EnumToString(InpSLMode), EnumToString(InpTPMode));

    if(InpUseTrailing)
        d += StringFormat("  Trail:   ON (%.0f pips, start %.0f)\n", InpTrailPips, InpTrailStartPips);
    d += sep;

    d += StringFormat("  Active Levels: %d\n", g_levelCount);
    int h22c=0, s23c=0, s07c=0, s12c=0;
    for(int i=0; i<g_levelCount; i++)
    {
        if(g_levels[i].source == "H22") h22c++;
        else if(g_levels[i].source == "S23") s23c++;
        else if(g_levels[i].source == "S07") s07c++;
        else if(g_levels[i].source == "S12") s12c++;
    }
    d += StringFormat("    22H:%d | 23:00:%d | 07:00:%d | 12:00:%d\n", h22c, s23c, s07c, s12c);
    d += sep;

    Comment(d);
}
//+------------------------------------------------------------------+
