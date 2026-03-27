//+------------------------------------------------------------------+
//|                                             PivotVwapEma_EA.mq5  |
//|      Intraday Trading Strategy: Pivot + VWAP + 20 EMA            |
//|      Entry: All 3 indicators aligned + candle color confirmation |
//|      Targets: R1/S1 (50%), R2/S2 (25%), R3/S3 (25%)             |
//|      Force Exit: 15:20 IST                                       |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#include "../include/PivotPoints.mqh"
#include "../include/VWAP.mqh"
#include "../include/TradeManager.mqh"

//--- Input parameters
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

//--- Module instances
CPivotPoints pivotPoints;
CVWAP        vwap;
CTradeManager tradeManager;

//--- EMA handle
int emaHandle;
int atrHandle;

//--- State tracking
bool     g_inTrade = false;
datetime g_lastBarTime = 0;
int      g_tradeDirection = 0; // 1=long, -1=short, 0=none

//+------------------------------------------------------------------+
int OnInit()
{
    // Initialize modules
    vwap.SetSessionStart(InpSessionStartHr, InpSessionStartMin);
    tradeManager.Init(InpMagic, InpSlippage);
    tradeManager.SetPartialProfitPct(InpTP1Pct, InpTP2Pct, InpTP3Pct);
    tradeManager.SetForceExitTime(InpForceExitHr, InpForceExitMin);

    // Create indicator handles
    emaHandle = iMA(_Symbol, PERIOD_CURRENT, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
    atrHandle = iATR(_Symbol, PERIOD_CURRENT, 14);

    if(emaHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
    {
        Print("Failed to create indicator handles");
        return INIT_FAILED;
    }

    Print("PivotVwapEma EA initialized. Magic: ", InpMagic);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(emaHandle != INVALID_HANDLE) IndicatorRelease(emaHandle);
    if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
}

//+------------------------------------------------------------------+
void OnTick()
{
    //--- Force exit check (every tick)
    if(tradeManager.IsForceExitTime() && tradeManager.HasPosition(_Symbol))
    {
        Print("Force exit at ", TimeToString(TimeCurrent(), TIME_MINUTES));
        tradeManager.ForceExitAll(_Symbol);
        g_inTrade = false;
        g_tradeDirection = 0;
        return;
    }

    //--- New bar check (process logic once per bar)
    datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
    if(currentBarTime == g_lastBarTime)
    {
        // Same bar - only manage existing positions
        if(g_inTrade)
            ManagePosition();
        return;
    }
    g_lastBarTime = currentBarTime;

    //--- Update indicators
    if(!pivotPoints.Calculate(_Symbol, PERIOD_D1))
    {
        Print("Failed to calculate pivot points");
        return;
    }

    if(!vwap.Calculate(_Symbol, PERIOD_CURRENT))
    {
        Print("Failed to calculate VWAP");
        return;
    }

    double ema[], atr[];
    ArraySetAsSeries(ema, true);
    ArraySetAsSeries(atr, true);
    if(CopyBuffer(emaHandle, 0, 0, 3, ema) < 3) return;
    if(CopyBuffer(atrHandle, 0, 0, 3, atr) < 3) return;

    //--- Get price data (use bar index 1 = last closed bar)
    double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);
    double openPrice  = iOpen(_Symbol, PERIOD_CURRENT, 1);
    double highPrice  = iHigh(_Symbol, PERIOD_CURRENT, 1);
    double lowPrice   = iLow(_Symbol, PERIOD_CURRENT, 1);
    double prevClose  = iClose(_Symbol, PERIOD_CURRENT, 2);

    double emaValue  = ema[1];
    double atrValue  = atr[1];
    double vwapValue = vwap.Value();
    double pivotValue = pivotPoints.Pivot();

    //--- Manage existing position
    if(g_inTrade && tradeManager.HasPosition(_Symbol))
    {
        ManagePosition();
        return;
    }

    // Reset if position was closed externally
    if(g_inTrade && !tradeManager.HasPosition(_Symbol))
    {
        g_inTrade = false;
        g_tradeDirection = 0;
    }

    //--- No new trades check
    if(IsNoNewTradeTime())
        return;

    //--- Check if session is active
    if(!IsSessionActive())
        return;

    //--- Entry Logic
    bool isGreenCandle = closePrice > openPrice;
    bool isRedCandle   = closePrice < openPrice;
    double candleSize  = highPrice - lowPrice;

    // Filter: skip if candle is too large relative to ATR
    if(InpFilterBigCandle && atrValue > 0 && candleSize > atrValue * InpMaxCandleATRMult)
        return;

    // LONG ENTRY: Price > Pivot AND Price > EMA AND Price > VWAP AND green candle
    if(isGreenCandle &&
       closePrice > pivotValue &&
       closePrice > emaValue &&
       closePrice > vwapValue)
    {
        // Confirmation: previous bar was below at least one of the three
        if(prevClose <= pivotValue || prevClose <= emaValue || prevClose <= vwapValue)
        {
            double sl = CalculateStopLoss(true, lowPrice, vwapValue, pivotValue);

            // Risk/Reward check: make sure R1 target is at least 1:1
            double r1 = pivotPoints.R1();
            if(r1 > closePrice && (r1 - closePrice) >= (closePrice - sl))
            {
                if(tradeManager.OpenLong(_Symbol, InpLotSize, sl, "PVE Long"))
                {
                    g_inTrade = true;
                    g_tradeDirection = 1;
                    Print("LONG entry at ", closePrice, " SL: ", sl,
                          " | Pivot: ", pivotValue, " EMA: ", emaValue, " VWAP: ", vwapValue);
                }
            }
        }
    }

    // SHORT ENTRY: Price < Pivot AND Price < EMA AND Price < VWAP AND red candle
    if(!g_inTrade && isRedCandle &&
       closePrice < pivotValue &&
       closePrice < emaValue &&
       closePrice < vwapValue)
    {
        if(prevClose >= pivotValue || prevClose >= emaValue || prevClose >= vwapValue)
        {
            double sl = CalculateStopLoss(false, highPrice, vwapValue, pivotValue);

            double s1 = pivotPoints.S1();
            if(s1 < closePrice && (closePrice - s1) >= (sl - closePrice))
            {
                if(tradeManager.OpenShort(_Symbol, InpLotSize, sl, "PVE Short"))
                {
                    g_inTrade = true;
                    g_tradeDirection = -1;
                    Print("SHORT entry at ", closePrice, " SL: ", sl,
                          " | Pivot: ", pivotValue, " EMA: ", emaValue, " VWAP: ", vwapValue);
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Manage open position: partial profit + trailing                  |
//+------------------------------------------------------------------+
void ManagePosition()
{
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

    if(g_tradeDirection == 1) // Long
    {
        tradeManager.ManageLongTP(_Symbol, bid,
                                  pivotPoints.R1(),
                                  pivotPoints.R2(),
                                  pivotPoints.R3());

        // Trail SL to EMA after TP1 is hit
        double ema[];
        ArraySetAsSeries(ema, true);
        if(CopyBuffer(emaHandle, 0, 0, 2, ema) >= 2)
        {
            double trailLevel = ema[1]; // Use previous bar EMA
            tradeManager.TrailStopLoss(_Symbol, trailLevel);
        }
    }
    else if(g_tradeDirection == -1) // Short
    {
        tradeManager.ManageShortTP(_Symbol, ask,
                                   pivotPoints.S1(),
                                   pivotPoints.S2(),
                                   pivotPoints.S3());

        // Trail SL to EMA after TP1 is hit
        double ema[];
        ArraySetAsSeries(ema, true);
        if(CopyBuffer(emaHandle, 0, 0, 2, ema) >= 2)
        {
            double trailLevel = ema[1];
            tradeManager.TrailStopLoss(_Symbol, trailLevel);
        }
    }

    // Check if position was fully closed
    if(!tradeManager.HasPosition(_Symbol))
    {
        g_inTrade = false;
        g_tradeDirection = 0;
    }
}

//+------------------------------------------------------------------+
//| Calculate stop loss based on selected mode                       |
//+------------------------------------------------------------------+
double CalculateStopLoss(bool isLong, double candleExtreme, double vwapVal, double pivotVal)
{
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    double buffer = 5 * point; // Small buffer below/above SL level

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

    return candleExtreme; // Fallback
}

//+------------------------------------------------------------------+
//| Check if we're in the active trading session                     |
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

//+------------------------------------------------------------------+
//| No new trades after specified time                               |
//+------------------------------------------------------------------+
bool IsNoNewTradeTime()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);

    int currentMins = dt.hour * 60 + dt.min;
    int cutoff = InpNoNewTradeHr * 60 + InpNoNewTradeMin;

    return (currentMins >= cutoff);
}
//+------------------------------------------------------------------+
