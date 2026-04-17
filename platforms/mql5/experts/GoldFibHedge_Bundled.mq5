//+------------------------------------------------------------------+
//|                                       GoldFibHedge_Bundled.mq5   |
//|      BUNDLED: Gold Fibonacci Hedge Strategy - Full EA             |
//|      22H + Session Fib Levels + EMA 200/50 + SuperTrend          |
//|      Full hedge: always BUY+SELL, exit losing leg at levels      |
//|      Daily close to avoid swap, max 2 trades                     |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Gold Fib Hedge EA - Bundled single file, no dependencies except Trade.mqh"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== Fibonacci Settings ==="
input double   InpFibLevel1       = 0.44;          // Fib Level 1
input double   InpFibLevel2       = 0.50;          // Fib Level 2
input int      InpH22Lookback     = 30;            // 22H Lookback (days)
input double   InpOverlapPips     = 50;            // Overlap Threshold (pips)

input group "=== EMA Settings ==="
input int      InpEmaFast         = 50;            // EMA Fast Period
input int      InpEmaSlow         = 200;           // EMA Slow Period

input group "=== SuperTrend (Optional) ==="
input bool     InpUseSuperTrend   = true;          // Enable SuperTrend
input int      InpSTperiod        = 10;            // SuperTrend ATR Period
input double   InpSTmultiplier    = 3.0;           // SuperTrend Multiplier

input group "=== Trade Settings ==="
input double   InpLotSize         = 0.1;           // Lot Size per Leg
input int      InpMagic           = 20250328;      // Magic Number
input double   InpSlippage        = 5;             // Max Slippage (points)
input int      InpDailyCloseHr    = 21;            // Daily Close Hour (UTC)
input int      InpDailyCloseMin   = 0;             // Daily Close Minute (UTC)

input group "=== Risk:Reward Profit Booking ==="
input bool     InpUseRR           = true;          // Enable RR-based Profit Booking
input double   InpRRratio         = 3.0;           // Risk:Reward Ratio (1:X)
input double   InpRRriskPips      = 30;            // Risk reference (pips) for RR calc

input group "=== Loss Re-Hedge ==="
input bool     InpLossRehedge     = true;          // Re-hedge when uni-trade in loss
input double   InpLossThreshPips  = 20;            // Loss threshold (pips) to trigger re-hedge

input group "=== Trailing Stop (Optional) ==="
input bool     InpUseTrailing     = false;         // Enable Trailing Stop
input double   InpTrailPips       = 30;            // Trail Distance (pips)
input double   InpTrailStartPips  = 20;            // Start Trail After (pips profit)
input bool     InpTrailByST       = false;         // Trail by SuperTrend Value

input group "=== Display ==="
input bool     InpPlotLevels      = true;          // Plot Fib Level Lines
input bool     InpShowDashboard   = true;          // Show Dashboard
input color    InpH22Color        = clrGold;       // 22H Level Color
input color    InpSession23Color  = clrOrange;     // 23:00 Level Color
input color    InpSession07Color  = clrCyan;       // 07:00 Level Color
input color    InpSession12Color  = clrMagenta;    // 12:00 Level Color
input color    InpOverlapColor    = clrWhite;      // Overlap Level Color

//+------------------------------------------------------------------+
//| Level structure                                                  |
//+------------------------------------------------------------------+
struct FibLevel
{
    double   price;
    string   source;     // "H22", "S23", "S07", "S12"
    datetime created;
    int      confidence; // 1=normal, 2+=overlapping
};

//+------------------------------------------------------------------+
//| GLOBAL STATE                                                     |
//+------------------------------------------------------------------+
CTrade   g_trade;
FibLevel g_levels[];
int      g_levelCount    = 0;
#define  MAX_LEVELS 200

//--- Indicator handles
int g_emaFastHandle, g_emaSlowHandle, g_atrHandle;

//--- SuperTrend state
double g_stUpperBand, g_stLowerBand, g_stValue;
bool   g_stBullish = true;

//--- Bar tracking
datetime g_lastBarTime   = 0;
datetime g_lastCalcTime  = 0;

//--- Dashboard tracking
double g_sessionPnL     = 0;
double g_cumulativePnL  = 0;
int    g_totalTrades     = 0;
int    g_buyTradeCount   = 0;
int    g_sellTradeCount  = 0;
int    g_rrBookings      = 0;  // count of RR profit bookings
int    g_lossRehedges    = 0;  // count of loss-triggered re-hedges

//--- Level caching
double g_nearestSupport  = 0;
double g_nearestResist   = 0;
int    g_nearSupConf     = 0;
int    g_nearResConf     = 0;

//--- Object prefix
string g_objPrefix = "GFH_EA_";

//+------------------------------------------------------------------+
int OnInit()
{
    g_trade.SetExpertMagicNumber(InpMagic);
    g_trade.SetDeviationInPoints((ulong)InpSlippage);
    g_trade.SetTypeFilling(ORDER_FILLING_IOC);

    g_emaFastHandle = iMA(_Symbol, PERIOD_M1, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
    g_emaSlowHandle = iMA(_Symbol, PERIOD_M1, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
    g_atrHandle     = iATR(_Symbol, PERIOD_M1, 14);

    if(g_emaFastHandle == INVALID_HANDLE || g_emaSlowHandle == INVALID_HANDLE || g_atrHandle == INVALID_HANDLE)
    {
        Print("Failed to create indicator handles");
        return INIT_FAILED;
    }

    ArrayResize(g_levels, MAX_LEVELS);
    g_levelCount = 0;

    Print("GoldFibHedge EA initialized. Magic=", InpMagic, " Lot=", InpLotSize);
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

    //--- Daily close check (every tick)
    if(IsDailyCloseTime())
    {
        CloseAllPositions("Daily close - swap avoidance");
        return;
    }

    //--- Trailing stop check (every tick)
    if(InpUseTrailing) ManageTrailingStop();

    //--- New bar logic
    datetime curBarTime = iTime(_Symbol, PERIOD_M1, 0);
    if(curBarTime == g_lastBarTime) return;
    g_lastBarTime = curBarTime;

    //--- Recalculate levels
    RecalculateLevels();
    DetectOverlaps();
    FindNearestLevels(bid);

    //--- Draw levels
    if(InpPlotLevels) DrawLevelLines();

    //--- Get EMA values
    double emaF[2], emaS[2];
    if(CopyBuffer(g_emaFastHandle, 0, 0, 2, emaF) < 2) return;
    if(CopyBuffer(g_emaSlowHandle, 0, 0, 2, emaS) < 2) return;

    double ema50  = emaF[0];
    double ema200 = emaS[0];

    //--- Calculate SuperTrend
    if(InpUseSuperTrend) CalculateSuperTrend();

    //--- Count current positions
    int buyPos = 0, sellPos = 0;
    double buyPnL = 0, sellPnL = 0;
    CountMyPositions(buyPos, sellPos, buyPnL, sellPnL);

    //--- HEDGE LOGIC ---
    int totalPos = buyPos + sellPos;

    //--- 1) If no positions, open full hedge at first level contact
    if(totalPos == 0)
    {
        if(IsPriceNearLevel(bid, 30))
        {
            OpenHedge(bid, ema200);
        }
    }
    //--- 2) If full hedge (2 positions), check losing leg exit + RR profit booking
    else if(totalPos == 2)
    {
        double rrTargetPoints = InpRRriskPips * InpRRratio * _Point * 10;

        // --- RR Profit Booking: close winner at 1:RR target, then re-hedge ---
        if(InpUseRR)
        {
            if(buyPnL > 0 && GetLegProfitPips(POSITION_TYPE_BUY) >= InpRRriskPips * InpRRratio)
            {
                CloseLeg(POSITION_TYPE_BUY, StringFormat("RR 1:%.0f profit booked on BUY (%.2f)", InpRRratio, buyPnL));
                g_rrBookings++;
                // Immediately re-hedge by adding BUY back
                OpenSingleLeg(true, "Re-hedge after RR BUY booking");
            }
            else if(sellPnL > 0 && GetLegProfitPips(POSITION_TYPE_SELL) >= InpRRriskPips * InpRRratio)
            {
                CloseLeg(POSITION_TYPE_SELL, StringFormat("RR 1:%.0f profit booked on SELL (%.2f)", InpRRratio, sellPnL));
                g_rrBookings++;
                // Immediately re-hedge by adding SELL back
                OpenSingleLeg(false, "Re-hedge after RR SELL booking");
            }
        }

        // --- Level-based exit: close losing leg at S/R ---
        // Recount after potential RR closure
        CountMyPositions(buyPos, sellPos, buyPnL, sellPnL);
        if(buyPos + sellPos == 2)
        {
            // Check if price hit a resistance → close losing BUY
            if(g_nearestResist > 0 && bid >= g_nearestResist - InpOverlapPips * _Point)
            {
                if(buyPnL < 0)
                    CloseLeg(POSITION_TYPE_BUY, "Hit resistance, closing losing BUY");
            }
            // Check if price hit a support → close losing SELL
            if(g_nearestSupport > 0 && bid <= g_nearestSupport + InpOverlapPips * _Point)
            {
                if(sellPnL < 0)
                    CloseLeg(POSITION_TYPE_SELL, "Hit support, closing losing SELL");
            }

            // SuperTrend exit (optional)
            if(InpUseSuperTrend)
            {
                if(!g_stBullish && buyPnL < 0)
                    CloseLeg(POSITION_TYPE_BUY, "SuperTrend bearish, closing BUY");
                else if(g_stBullish && sellPnL < 0)
                    CloseLeg(POSITION_TYPE_SELL, "SuperTrend bullish, closing SELL");
            }
        }
    }
    //--- 3) If only 1 position (uni-directional), check for loss re-hedge + RR booking + level re-hedge
    else if(totalPos == 1)
    {
        double uniPnL = buyPnL + sellPnL; // one will be 0

        // --- A) Loss re-hedge: if uni-trade in loss beyond threshold, re-hedge immediately ---
        if(InpLossRehedge)
        {
            double lossThreshold = InpLossThreshPips * _Point * 10;

            if(buyPos == 1 && sellPos == 0)
            {
                double buyProfitPips = GetLegProfitPips(POSITION_TYPE_BUY);
                if(buyProfitPips <= -InpLossThreshPips)
                {
                    OpenSingleLeg(false, "Loss re-hedge: BUY losing, adding SELL");
                    g_lossRehedges++;
                    if(InpShowDashboard) UpdateDashboard(bid, ema50, ema200);
                    return;
                }
            }
            else if(sellPos == 1 && buyPos == 0)
            {
                double sellProfitPips = GetLegProfitPips(POSITION_TYPE_SELL);
                if(sellProfitPips <= -InpLossThreshPips)
                {
                    OpenSingleLeg(true, "Loss re-hedge: SELL losing, adding BUY");
                    g_lossRehedges++;
                    if(InpShowDashboard) UpdateDashboard(bid, ema50, ema200);
                    return;
                }
            }
        }

        // --- B) RR Profit Booking on uni-directional winner: close + re-hedge ---
        if(InpUseRR)
        {
            if(buyPos == 1 && GetLegProfitPips(POSITION_TYPE_BUY) >= InpRRriskPips * InpRRratio)
            {
                CloseLeg(POSITION_TYPE_BUY, StringFormat("RR 1:%.0f uni-BUY profit booked", InpRRratio));
                g_rrBookings++;
                // Re-open full hedge
                OpenHedge(bid, ema200);
                if(InpShowDashboard) UpdateDashboard(bid, ema50, ema200);
                return;
            }
            else if(sellPos == 1 && GetLegProfitPips(POSITION_TYPE_SELL) >= InpRRriskPips * InpRRratio)
            {
                CloseLeg(POSITION_TYPE_SELL, StringFormat("RR 1:%.0f uni-SELL profit booked", InpRRratio));
                g_rrBookings++;
                // Re-open full hedge
                OpenHedge(bid, ema200);
                if(InpShowDashboard) UpdateDashboard(bid, ema50, ema200);
                return;
            }
        }

        // --- C) Level-based re-hedge (original logic) ---
        if(buyPos == 1 && sellPos == 0)
        {
            // Only BUY open - if price dropping below support, re-hedge
            if(g_nearestSupport > 0 && bid < g_nearestSupport)
            {
                OpenSingleLeg(false, "Re-hedge: price below support, adding SELL");
            }
            // Or if EMA bias changed
            else if(bid < ema200 && ema50 < ema200)
            {
                OpenSingleLeg(false, "Re-hedge: EMA bearish, adding SELL");
            }
        }
        else if(sellPos == 1 && buyPos == 0)
        {
            // Only SELL open - if price rising above resistance, re-hedge
            if(g_nearestResist > 0 && bid > g_nearestResist)
            {
                OpenSingleLeg(true, "Re-hedge: price above resistance, adding BUY");
            }
            // Or if EMA bias changed
            else if(bid > ema200 && ema50 > ema200)
            {
                OpenSingleLeg(true, "Re-hedge: EMA bullish, adding BUY");
            }
        }
    }

    //--- Update dashboard
    if(InpShowDashboard) UpdateDashboard(bid, ema50, ema200);
}

//+------------------------------------------------------------------+
//| BUILD 22H CANDLES FROM H1 DATA                                   |
//+------------------------------------------------------------------+
void Calculate22HLevels()
{
    MqlRates h1[];
    ArraySetAsSeries(h1, true);
    int barsNeeded = InpH22Lookback * 24 + 48;
    int copied = CopyRates(_Symbol, PERIOD_H1, 0, barsNeeded, h1);
    if(copied < 48) return;

    datetime cutoff = TimeCurrent() - InpH22Lookback * 86400;
    int candlesFound = 0;

    for(int i = 0; i < copied - 22 && candlesFound < InpH22Lookback; i++)
    {
        MqlDateTime dt;
        TimeToStruct(h1[i].time, dt);
        if(dt.hour != 20) continue;
        if(h1[i].time < cutoff) break;
        if(i + 21 >= copied) continue;

        double cHigh = -DBL_MAX;
        double cLow  = DBL_MAX;

        for(int j = i; j < i + 22 && j < copied; j++)
        {
            if(h1[j].high > cHigh) cHigh = h1[j].high;
            if(h1[j].low  < cLow)  cLow  = h1[j].low;
        }

        double range = cHigh - cLow;
        if(range < _Point) continue;

        AddLevel(cHigh - InpFibLevel1 * range, "H22", h1[i].time);
        AddLevel(cHigh - InpFibLevel2 * range, "H22", h1[i].time);
        candlesFound++;
    }
}

//+------------------------------------------------------------------+
//| CALCULATE SESSION LEVELS FROM M30                                |
//+------------------------------------------------------------------+
void CalculateSessionLevels()
{
    MqlRates m30[];
    ArraySetAsSeries(m30, true);
    int copied = CopyRates(_Symbol, PERIOD_M30, 0, 200, m30);
    if(copied < 10) return;

    datetime twoDaysAgo = TimeCurrent() - 2 * 86400;
    bool found23 = false, found07 = false, found12 = false;
    bool waitingForRed = false;
    datetime candle23Time = 0;

    for(int i = 0; i < copied; i++)
    {
        if(m30[i].time < twoDaysAgo) break;

        MqlDateTime dt;
        TimeToStruct(m30[i].time, dt);

        // 23:00 UTC - find first red candle after
        if(dt.hour == 23 && dt.min == 0 && !waitingForRed && !found23)
        {
            waitingForRed = true;
            candle23Time = m30[i].time;
            continue;
        }

        if(waitingForRed && !found23 && m30[i].time > candle23Time)
        {
            if(m30[i].close < m30[i].open)
            {
                double range = m30[i].high - m30[i].low;
                if(range > _Point)
                {
                    AddLevel(m30[i].high - InpFibLevel1 * range, "S23", m30[i].time);
                    AddLevel(m30[i].high - InpFibLevel2 * range, "S23", m30[i].time);
                    found23 = true;
                    waitingForRed = false;
                }
            }
        }

        // 07:00 UTC
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

        // 12:00 UTC
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
    {
        for(int j = i + 1; j < g_levelCount; j++)
        {
            if(MathAbs(g_levels[i].price - g_levels[j].price) <= threshold)
            {
                g_levels[i].confidence++;
                g_levels[j].confidence++;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| FIND NEAREST SUPPORT/RESISTANCE                                  |
//+------------------------------------------------------------------+
void FindNearestLevels(double price)
{
    g_nearestSupport = 0;
    g_nearestResist  = 0;
    g_nearSupConf    = 0;
    g_nearResConf    = 0;
    double minSD = DBL_MAX, minRD = DBL_MAX;

    for(int i = 0; i < g_levelCount; i++)
    {
        double diff = g_levels[i].price - price;
        double dist = MathAbs(diff);

        if(diff < 0 && dist < minSD)
        {
            minSD = dist;
            g_nearestSupport = g_levels[i].price;
            g_nearSupConf    = g_levels[i].confidence;
        }
        else if(diff >= 0 && dist < minRD)
        {
            minRD = dist;
            g_nearestResist = g_levels[i].price;
            g_nearResConf   = g_levels[i].confidence;
        }
    }
}

//+------------------------------------------------------------------+
//| CHECK IF PRICE IS NEAR ANY LEVEL                                 |
//+------------------------------------------------------------------+
bool IsPriceNearLevel(double price, double pipThreshold)
{
    double threshold = pipThreshold * _Point * 10;
    for(int i = 0; i < g_levelCount; i++)
    {
        if(MathAbs(price - g_levels[i].price) <= threshold)
            return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| SUPERTREND CALCULATION                                           |
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
    double upperBand = hl2 + InpSTmultiplier * atr[0];
    double lowerBand = hl2 - InpSTmultiplier * atr[0];

    static double prevUpper = 0, prevLower = 0;
    static bool   prevBull = true;

    if(prevLower > 0 && lowerBand < prevLower && rates[1].close > prevLower)
        lowerBand = prevLower;
    if(prevUpper > 0 && upperBand > prevUpper && rates[1].close < prevUpper)
        upperBand = prevUpper;

    if(rates[0].close > upperBand) g_stBullish = true;
    else if(rates[0].close < lowerBand) g_stBullish = false;
    else g_stBullish = prevBull;

    g_stValue = g_stBullish ? lowerBand : upperBand;
    prevUpper = upperBand;
    prevLower = lowerBand;
    prevBull  = g_stBullish;
}

//+------------------------------------------------------------------+
//| POSITION COUNTING                                                |
//+------------------------------------------------------------------+
void CountMyPositions(int &buyPos, int &sellPos, double &buyPnL, double &sellPnL)
{
    buyPos = 0; sellPos = 0;
    buyPnL = 0; sellPnL = 0;

    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

        double profit = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);

        if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
            buyPos++;
            buyPnL += profit;
        }
        else
        {
            sellPos++;
            sellPnL += profit;
        }
    }
}

//+------------------------------------------------------------------+
//| GET LEG PROFIT IN PIPS                                           |
//+------------------------------------------------------------------+
double GetLegProfitPips(ENUM_POSITION_TYPE type)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        if(PositionGetInteger(POSITION_TYPE) != type) continue;

        double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        double pipSize   = _Point * 10;

        if(type == POSITION_TYPE_BUY)
        {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            return (bid - openPrice) / pipSize;
        }
        else
        {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            return (openPrice - ask) / pipSize;
        }
    }
    return 0;
}

//+------------------------------------------------------------------+
//| OPEN FULL HEDGE                                                  |
//+------------------------------------------------------------------+
void OpenHedge(double price, double ema200)
{
    double sl_buy = 0, sl_sell = 0, tp_buy = 0, tp_sell = 0;

    // Use SuperTrend for SL/TP if enabled
    if(InpUseSuperTrend && g_stValue > 0)
    {
        sl_buy  = g_stBullish ? g_stValue : 0;
        sl_sell = !g_stBullish ? g_stValue : 0;
    }

    // Determine lot bias based on EMA 200
    double buyLot  = InpLotSize;
    double sellLot = InpLotSize;

    // Open BUY
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    if(g_trade.Buy(buyLot, _Symbol, ask, sl_buy, tp_buy, "GFH Hedge BUY"))
    {
        g_buyTradeCount++;
        g_totalTrades++;
        Print("Hedge BUY opened at ", ask);
    }

    // Open SELL
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    if(g_trade.Sell(sellLot, _Symbol, bid, sl_sell, tp_sell, "GFH Hedge SELL"))
    {
        g_sellTradeCount++;
        g_totalTrades++;
        Print("Hedge SELL opened at ", bid);
    }
}

//+------------------------------------------------------------------+
//| OPEN SINGLE LEG (for re-hedge)                                   |
//+------------------------------------------------------------------+
void OpenSingleLeg(bool isBuy, string reason)
{
    double sl = 0;
    if(InpUseSuperTrend && g_stValue > 0)
        sl = g_stValue;

    if(isBuy)
    {
        double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        if(g_trade.Buy(InpLotSize, _Symbol, ask, sl, 0, "GFH " + reason))
        {
            g_buyTradeCount++;
            g_totalTrades++;
            Print(reason, " at ", ask);
        }
    }
    else
    {
        double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        if(g_trade.Sell(InpLotSize, _Symbol, bid, sl, 0, "GFH " + reason))
        {
            g_sellTradeCount++;
            g_totalTrades++;
            Print(reason, " at ", bid);
        }
    }
}

//+------------------------------------------------------------------+
//| CLOSE LOSING LEG                                                 |
//+------------------------------------------------------------------+
void CloseLeg(ENUM_POSITION_TYPE type, string reason)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        if(PositionGetInteger(POSITION_TYPE) != type) continue;

        g_trade.PositionClose(ticket);
        Print(reason, " | Ticket: ", ticket);
    }
}

//+------------------------------------------------------------------+
//| CLOSE ALL POSITIONS                                              |
//+------------------------------------------------------------------+
void CloseAllPositions(string reason)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

        double profit = PositionGetDouble(POSITION_PROFIT);
        g_cumulativePnL += profit;
        g_trade.PositionClose(ticket);
    }
    Print(reason);
}

//+------------------------------------------------------------------+
//| DAILY CLOSE TIME CHECK                                           |
//+------------------------------------------------------------------+
bool IsDailyCloseTime()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    return (dt.hour == InpDailyCloseHr && dt.min >= InpDailyCloseMin && dt.min < InpDailyCloseMin + 2);
}

//+------------------------------------------------------------------+
//| TRAILING STOP MANAGEMENT                                         |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
    double trailPoints = InpTrailPips * _Point * 10;
    double startPoints = InpTrailStartPips * _Point * 10;

    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

        double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        double currentSL = PositionGetDouble(POSITION_SL);
        long   posType   = PositionGetInteger(POSITION_TYPE);

        if(posType == POSITION_TYPE_BUY)
        {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double profit = bid - openPrice;

            if(profit >= startPoints)
            {
                double newSL;
                if(InpTrailByST && InpUseSuperTrend && g_stBullish)
                    newSL = g_stValue;
                else
                    newSL = bid - trailPoints;

                newSL = NormalizeDouble(newSL, _Digits);
                if(newSL > currentSL + _Point)
                    g_trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
            }
        }
        else // SELL
        {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double profit = openPrice - ask;

            if(profit >= startPoints)
            {
                double newSL;
                if(InpTrailByST && InpUseSuperTrend && !g_stBullish)
                    newSL = g_stValue;
                else
                    newSL = ask + trailPoints;

                newSL = NormalizeDouble(newSL, _Digits);
                if(newSL < currentSL - _Point || currentSL == 0)
                    g_trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
            }
        }
    }
}

//+------------------------------------------------------------------+
//| DRAW LEVEL LINES                                                 |
//+------------------------------------------------------------------+
void DrawLevelLines()
{
    ObjectsDeleteAll(0, g_objPrefix + "LVL_");

    for(int i = 0; i < g_levelCount; i++)
    {
        string name = g_objPrefix + "LVL_" + IntegerToString(i);
        color  clr  = InpH22Color;
        int    width = 1;

        if(g_levels[i].source == "S23") clr = InpSession23Color;
        else if(g_levels[i].source == "S07") clr = InpSession07Color;
        else if(g_levels[i].source == "S12") clr = InpSession12Color;

        if(g_levels[i].confidence >= 2) { clr = InpOverlapColor; width = 2; }
        if(g_levels[i].confidence >= 3) width = 3;

        ObjectCreate(0, name, OBJ_HLINE, 0, 0, g_levels[i].price);
        ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
        ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
        ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
        ObjectSetInteger(0, name, OBJPROP_BACK, true);
        ObjectSetString(0, name, OBJPROP_TOOLTIP,
            StringFormat("%s %.2f [x%d]", g_levels[i].source, g_levels[i].price, g_levels[i].confidence));

        // Label
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
    int bp = 0, sp = 0;
    double bPnL = 0, sPnL = 0;
    CountMyPositions(bp, sp, bPnL, sPnL);
    g_sessionPnL = bPnL + sPnL;

    double buyLots = 0, sellLots = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
            buyLots += PositionGetDouble(POSITION_VOLUME);
        else
            sellLots += PositionGetDouble(POSITION_VOLUME);
    }

    string sep = "------------------------------------------------\n";
    string d = "";
    d += "    GOLD FIB HEDGE - STRATEGY DASHBOARD\n";
    d += sep;
    d += StringFormat("  Price:           %.2f\n", price);
    d += StringFormat("  Session P&L:     %.2f\n", g_sessionPnL);
    d += StringFormat("  Cumulative P&L:  %.2f\n", g_cumulativePnL + g_sessionPnL);
    d += sep;
    d += StringFormat("  BUY  Lots: %.2f | P&L: %.2f | Count: %d\n", buyLots, bPnL, g_buyTradeCount);
    d += StringFormat("  SELL Lots: %.2f | P&L: %.2f | Count: %d\n", sellLots, sPnL, g_sellTradeCount);
    d += StringFormat("  Total Trades:    %d\n", g_totalTrades);
    d += sep;
    if(InpUseRR)
        d += StringFormat("  RR Bookings:     %d  (1:%.0f ratio)\n", g_rrBookings, InpRRratio);
    if(InpLossRehedge)
        d += StringFormat("  Loss Re-hedges:  %d  (>%.0f pip loss)\n", g_lossRehedges, InpLossThreshPips);

    // Show current leg profit in pips
    if(bp > 0)
        d += StringFormat("  BUY Profit:      %.1f pips\n", GetLegProfitPips(POSITION_TYPE_BUY));
    if(sp > 0)
        d += StringFormat("  SELL Profit:     %.1f pips\n", GetLegProfitPips(POSITION_TYPE_SELL));
    d += sep;
    d += StringFormat("  Next Resistance: %.2f [Conf: %d]\n", g_nearestResist, g_nearResConf);
    d += StringFormat("  Next Support:    %.2f [Conf: %d]\n", g_nearestSupport, g_nearSupConf);
    d += sep;
    d += StringFormat("  EMA 50:  %.2f  |  EMA 200: %.2f\n", ema50, ema200);
    d += StringFormat("  Trend:   %s\n", ema50 > ema200 ? "BULLISH" : "BEARISH");
    if(InpUseSuperTrend)
        d += StringFormat("  ST:      %.2f (%s)\n", g_stValue, g_stBullish ? "BULL" : "BEAR");
    if(InpUseTrailing)
        d += StringFormat("  Trail:   %s (%.0f pips)\n", "ON", InpTrailPips);
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
