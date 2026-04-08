//+------------------------------------------------------------------+
//|                                      GoldFibHedge_Indicator.mq5  |
//|      Gold Fibonacci Hedge - Level Indicator with Buy/Sell Calls  |
//|      22H Fib + Intraday Session Fib Levels + EMA + SuperTrend   |
//|      Dashboard: P&L, Lots, Levels, Trade Counts                  |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Gold Fib Hedge Indicator - Plots fib levels from 22H and session candles with buy/sell signals"
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   4

//--- Buy arrow
#property indicator_label1  "Buy Signal"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLime
#property indicator_width1  3

//--- Sell arrow
#property indicator_label2  "Sell Signal"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrRed
#property indicator_width2  3

//--- EMA 50
#property indicator_label3  "EMA 50"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrDodgerBlue
#property indicator_style3  STYLE_SOLID
#property indicator_width3  2

//--- EMA 200
#property indicator_label4  "EMA 200"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrGold
#property indicator_style4  STYLE_SOLID
#property indicator_width4  2

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
    bool     isResistance;
};

//--- Indicator buffers
double BuyBuffer[];
double SellBuffer[];
double EmaFastBuffer[];
double EmaSlowBuffer[];

//--- Handles
int g_emaFastHandle;
int g_emaSlowHandle;
int g_atrHandle;

//--- Level storage
FibLevel g_levels[];
int      g_levelCount = 0;
#define  MAX_LEVELS 200

//--- SuperTrend
double g_stUp[], g_stDn[], g_stValue;
bool   g_stBullish = true;

//--- Dashboard state
double g_totalPnL      = 0;
int    g_totalTrades    = 0;
int    g_buyCount       = 0;
int    g_sellCount      = 0;
double g_buyLots        = 0;
double g_sellLots       = 0;
double g_nearestSupport = 0;
double g_nearestResist  = 0;
int    g_nearestSupConf = 0;
int    g_nearestResConf = 0;

//--- State
datetime g_lastCalcTime  = 0;
datetime g_lastBarTime   = 0;
string   g_objPrefix     = "GFH_";

//+------------------------------------------------------------------+
int OnInit()
{
    //--- Set buffers
    SetIndexBuffer(0, BuyBuffer,    INDICATOR_DATA);
    SetIndexBuffer(1, SellBuffer,   INDICATOR_DATA);
    SetIndexBuffer(2, EmaFastBuffer,INDICATOR_DATA);
    SetIndexBuffer(3, EmaSlowBuffer,INDICATOR_DATA);

    PlotIndexSetInteger(0, PLOT_ARROW, 233); // up arrow
    PlotIndexSetInteger(1, PLOT_ARROW, 234); // down arrow
    PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0);
    PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, 0);
    PlotIndexSetDouble(2, PLOT_EMPTY_VALUE, 0);
    PlotIndexSetDouble(3, PLOT_EMPTY_VALUE, 0);

    //--- Create handles
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

    Print("GoldFibHedge Indicator initialized");
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(g_emaFastHandle != INVALID_HANDLE) IndicatorRelease(g_emaFastHandle);
    if(g_emaSlowHandle != INVALID_HANDLE) IndicatorRelease(g_emaSlowHandle);
    if(g_atrHandle     != INVALID_HANDLE) IndicatorRelease(g_atrHandle);

    //--- Remove objects
    ObjectsDeleteAll(0, g_objPrefix);
    Comment("");
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &close[],
                const double &high[],
                const double &low[],
                const double &tick_volume[],
                const long &volume[],
                const int &spread[])
{
    if(rates_total < InpEmaSlow) return 0;

    //--- Copy EMA data
    double emaF[], emaS[];
    ArraySetAsSeries(emaF, true);
    ArraySetAsSeries(emaS, true);

    int toCopy = rates_total - prev_calculated + 1;
    if(toCopy < 1) toCopy = 1;
    if(prev_calculated == 0) toCopy = rates_total;

    CopyBuffer(g_emaFastHandle, 0, 0, toCopy, emaF);
    CopyBuffer(g_emaSlowHandle, 0, 0, toCopy, emaS);

    //--- Fill EMA buffers
    int start = (prev_calculated == 0) ? InpEmaSlow : prev_calculated - 1;
    for(int i = start; i < rates_total; i++)
    {
        int idx = rates_total - 1 - i;
        if(idx >= 0 && idx < ArraySize(emaF)) EmaFastBuffer[i] = emaF[idx];
        if(idx >= 0 && idx < ArraySize(emaS)) EmaSlowBuffer[i] = emaS[idx];
        BuyBuffer[i]  = 0;
        SellBuffer[i] = 0;
    }

    //--- Recalculate levels periodically (every new M1 bar)
    datetime curBarTime = time[rates_total - 1];
    if(curBarTime != g_lastBarTime)
    {
        g_lastBarTime = curBarTime;
        RecalculateLevels();
        DetectOverlaps();
        if(InpPlotLevels) DrawLevelLines();
        FindNearestLevels(close[rates_total - 1]);
        GenerateSignals(rates_total, time, open, close, high, low);
        if(InpShowDashboard) UpdateDashboard(close[rates_total - 1]);
    }

    return rates_total;
}

//+------------------------------------------------------------------+
//| Build 22H candles from H1 data and extract fib levels            |
//+------------------------------------------------------------------+
void Calculate22HLevels()
{
    MqlRates h1[];
    ArraySetAsSeries(h1, true);
    int barsNeeded = InpH22Lookback * 24 + 48; // extra buffer
    int copied = CopyRates(_Symbol, PERIOD_H1, 0, barsNeeded, h1);
    if(copied < 48) return;

    datetime cutoff = TimeCurrent() - InpH22Lookback * 86400;
    int candlesFound = 0;

    //--- Walk through H1 bars, find 20:00 UTC starts
    for(int i = 0; i < copied - 22 && candlesFound < InpH22Lookback; i++)
    {
        MqlDateTime dt;
        TimeToStruct(h1[i].time, dt);

        // Look for the START of a 22H candle: a bar whose time is ~20:00 UTC
        // We scan backwards, so we look for the END of the 22H window
        // The 22H candle covers 20:00 to 18:00 next day
        // Find bars at 20:00
        if(dt.hour != 20) continue;
        if(h1[i].time < cutoff) break;

        // Aggregate 22 H1 bars starting from this point going forward (backwards in array since series)
        double cHigh = -DBL_MAX;
        double cLow  = DBL_MAX;
        int barStart = i;

        // Since array is series (0=latest), we need to go backwards from i
        // h1[i] is the most recent bar of this set, h1[i+21] would be 22 hours earlier
        if(i + 21 >= copied) continue;

        for(int j = i; j < i + 22 && j < copied; j++)
        {
            if(h1[j].high > cHigh) cHigh = h1[j].high;
            if(h1[j].low  < cLow)  cLow  = h1[j].low;
        }

        double range = cHigh - cLow;
        if(range < _Point) continue;

        // Fib levels
        double fib044 = cHigh - InpFibLevel1 * range;
        double fib050 = cHigh - InpFibLevel2 * range;

        AddLevel(fib044, "H22", h1[i].time, false);
        AddLevel(fib050, "H22", h1[i].time, false);

        candlesFound++;
    }
}

//+------------------------------------------------------------------+
//| Calculate session levels from M30 candles                        |
//+------------------------------------------------------------------+
void CalculateSessionLevels()
{
    MqlRates m30[];
    ArraySetAsSeries(m30, true);
    int copied = CopyRates(_Symbol, PERIOD_M30, 0, 200, m30);
    if(copied < 10) return;

    datetime twoDaysAgo = TimeCurrent() - 2 * 86400;

    //--- Process M30 bars
    bool found23 = false, found07 = false, found12 = false;
    bool waitingForRed23 = false;
    datetime candle23Time = 0;

    for(int i = 0; i < copied; i++)
    {
        if(m30[i].time < twoDaysAgo) break;

        MqlDateTime dt;
        TimeToStruct(m30[i].time, dt);
        int barHour = dt.hour;
        int barMin  = dt.min;

        //--- 23:00 UTC - wait for first red candle after
        if(barHour == 23 && barMin == 0 && !waitingForRed23)
        {
            waitingForRed23 = true;
            candle23Time = m30[i].time;
            continue;
        }

        if(waitingForRed23 && !found23 && m30[i].time > candle23Time)
        {
            // Check if this is a red (bearish) candle
            if(m30[i].close < m30[i].open)
            {
                double range = m30[i].high - m30[i].low;
                if(range > _Point)
                {
                    AddLevel(m30[i].high - InpFibLevel1 * range, "S23", m30[i].time, false);
                    AddLevel(m30[i].high - InpFibLevel2 * range, "S23", m30[i].time, false);
                    found23 = true;
                    waitingForRed23 = false;
                }
            }
        }

        //--- 07:00 UTC candle
        if(barHour == 7 && barMin == 0 && !found07)
        {
            double range = m30[i].high - m30[i].low;
            if(range > _Point)
            {
                AddLevel(m30[i].high - InpFibLevel1 * range, "S07", m30[i].time, false);
                AddLevel(m30[i].high - InpFibLevel2 * range, "S07", m30[i].time, false);
                found07 = true;
            }
        }

        //--- 12:00 UTC candle
        if(barHour == 12 && barMin == 0 && !found12)
        {
            double range = m30[i].high - m30[i].low;
            if(range > _Point)
            {
                AddLevel(m30[i].high - InpFibLevel1 * range, "S12", m30[i].time, false);
                AddLevel(m30[i].high - InpFibLevel2 * range, "S12", m30[i].time, false);
                found12 = true;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Add a level to the array                                         |
//+------------------------------------------------------------------+
void AddLevel(double price, string source, datetime created, bool isRes)
{
    if(g_levelCount >= MAX_LEVELS) return;

    g_levels[g_levelCount].price      = NormalizeDouble(price, _Digits);
    g_levels[g_levelCount].source     = source;
    g_levels[g_levelCount].created    = created;
    g_levels[g_levelCount].confidence = 1;
    g_levels[g_levelCount].isResistance = isRes;
    g_levelCount++;
}

//+------------------------------------------------------------------+
//| Recalculate all levels                                           |
//+------------------------------------------------------------------+
void RecalculateLevels()
{
    //--- Only recalculate every 60 seconds
    if(TimeCurrent() - g_lastCalcTime < 60) return;
    g_lastCalcTime = TimeCurrent();

    g_levelCount = 0;
    Calculate22HLevels();
    CalculateSessionLevels();
}

//+------------------------------------------------------------------+
//| Detect overlapping levels and boost confidence                   |
//+------------------------------------------------------------------+
void DetectOverlaps()
{
    double overlapThreshold = InpOverlapPips * _Point * 10; // pips to points

    // Reset confidence
    for(int i = 0; i < g_levelCount; i++)
        g_levels[i].confidence = 1;

    for(int i = 0; i < g_levelCount; i++)
    {
        for(int j = i + 1; j < g_levelCount; j++)
        {
            if(MathAbs(g_levels[i].price - g_levels[j].price) <= overlapThreshold)
            {
                g_levels[i].confidence++;
                g_levels[j].confidence++;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Find nearest support and resistance to current price             |
//+------------------------------------------------------------------+
void FindNearestLevels(double currentPrice)
{
    g_nearestSupport = 0;
    g_nearestResist  = 0;
    g_nearestSupConf = 0;
    g_nearestResConf = 0;
    double minSupDist = DBL_MAX;
    double minResDist = DBL_MAX;

    for(int i = 0; i < g_levelCount; i++)
    {
        double diff = g_levels[i].price - currentPrice;

        if(diff < 0) // below price = support
        {
            double dist = MathAbs(diff);
            if(dist < minSupDist)
            {
                minSupDist = dist;
                g_nearestSupport = g_levels[i].price;
                g_nearestSupConf = g_levels[i].confidence;
            }
        }
        else // above price = resistance
        {
            double dist = MathAbs(diff);
            if(dist < minResDist)
            {
                minResDist = dist;
                g_nearestResist  = g_levels[i].price;
                g_nearestResConf = g_levels[i].confidence;
            }
        }
    }

    // Set level direction
    for(int i = 0; i < g_levelCount; i++)
    {
        g_levels[i].isResistance = (g_levels[i].price >= currentPrice);
    }
}

//+------------------------------------------------------------------+
//| Draw level lines on chart                                        |
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

        // Overlapping levels get special treatment
        if(g_levels[i].confidence >= 2)
        {
            clr   = InpOverlapColor;
            width = 2;
        }
        if(g_levels[i].confidence >= 3) width = 3;

        ObjectCreate(0, name, OBJ_HLINE, 0, 0, g_levels[i].price);
        ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
        ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
        ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
        ObjectSetInteger(0, name, OBJPROP_BACK, true);
        ObjectSetString(0, name, OBJPROP_TOOLTIP,
            StringFormat("%s %.2f [Conf:%d]", g_levels[i].source, g_levels[i].price, g_levels[i].confidence));

        // Price label
        string lblName = g_objPrefix + "LBL_" + IntegerToString(i);
        ObjectCreate(0, lblName, OBJ_TEXT, 0, TimeCurrent(), g_levels[i].price);
        ObjectSetString(0, lblName, OBJPROP_TEXT,
            StringFormat("%.2f (%s x%d)", g_levels[i].price, g_levels[i].source, g_levels[i].confidence));
        ObjectSetInteger(0, lblName, OBJPROP_COLOR, clr);
        ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 8);
    }

    ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Optional SuperTrend calculation                                  |
//+------------------------------------------------------------------+
void CalculateSuperTrend(const double &close[], const double &high[],
                         const double &low[], int idx, int total)
{
    if(!InpUseSuperTrend || total < InpSTperiod + 1) return;

    double atr[];
    ArraySetAsSeries(atr, true);
    if(CopyBuffer(g_atrHandle, 0, 0, 2, atr) < 2) return;

    double atrVal = atr[0];
    double hl2 = (high[idx] + low[idx]) / 2.0;

    double upperBand = hl2 + InpSTmultiplier * atrVal;
    double lowerBand = hl2 - InpSTmultiplier * atrVal;

    static double prevUpper = 0, prevLower = 0;
    static bool   prevBullish = true;

    // Adjust bands
    if(prevLower > 0 && lowerBand < prevLower && close[idx - 1] > prevLower)
        lowerBand = prevLower;
    if(prevUpper > 0 && upperBand > prevUpper && close[idx - 1] < prevUpper)
        upperBand = prevUpper;

    // Determine direction
    if(close[idx] > upperBand)
        g_stBullish = true;
    else if(close[idx] < lowerBand)
        g_stBullish = false;
    else
        g_stBullish = prevBullish;

    g_stValue = g_stBullish ? lowerBand : upperBand;

    prevUpper   = upperBand;
    prevLower   = lowerBand;
    prevBullish = g_stBullish;
}

//+------------------------------------------------------------------+
//| Generate buy/sell signals                                        |
//+------------------------------------------------------------------+
void GenerateSignals(int total, const datetime &time[],
                     const double &open[], const double &close[],
                     const double &high[], const double &low[])
{
    if(total < 3) return;
    int idx = total - 2; // previous completed bar

    double emaF = EmaFastBuffer[idx];
    double emaS = EmaSlowBuffer[idx];
    double price = close[idx];

    if(emaF == 0 || emaS == 0) return;

    // Calculate SuperTrend
    CalculateSuperTrend(close, high, low, idx, total);

    bool priceAboveEma200 = (price > emaS);
    bool ema50AboveEma200 = (emaF > emaS);

    //--- Check if price crossed any level
    for(int i = 0; i < g_levelCount; i++)
    {
        double lvl = g_levels[i].price;
        double prevPrice = close[idx - 1];

        // Price crossed level upward → potential buy (if above EMA 200)
        if(prevPrice < lvl && price >= lvl && priceAboveEma200)
        {
            BuyBuffer[idx] = low[idx] - 10 * _Point;
            break;
        }

        // Price crossed level downward → potential sell (if below EMA 200)
        if(prevPrice > lvl && price <= lvl && !priceAboveEma200)
        {
            SellBuffer[idx] = high[idx] + 10 * _Point;
            break;
        }
    }
}

//+------------------------------------------------------------------+
//| Count open positions (reads from terminal)                       |
//+------------------------------------------------------------------+
void CountPositions()
{
    g_totalPnL   = 0;
    g_buyCount   = 0;
    g_sellCount  = 0;
    g_buyLots    = 0;
    g_sellLots   = 0;
    g_totalTrades = 0;

    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

        g_totalPnL += PositionGetDouble(POSITION_PROFIT);
        g_totalTrades++;

        if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
            g_buyCount++;
            g_buyLots += PositionGetDouble(POSITION_VOLUME);
        }
        else
        {
            g_sellCount++;
            g_sellLots += PositionGetDouble(POSITION_VOLUME);
        }
    }

    // Also count from history (today)
    datetime todayStart = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
    HistorySelect(todayStart, TimeCurrent());
    g_totalTrades += HistoryDealsTotal();
}

//+------------------------------------------------------------------+
//| Update dashboard display                                         |
//+------------------------------------------------------------------+
void UpdateDashboard(double currentPrice)
{
    CountPositions();

    string sep = "--------------------------------------------\n";
    string dash = "";
    dash += "  GOLD FIB HEDGE DASHBOARD\n";
    dash += sep;
    dash += StringFormat("  Price:         %.2f\n", currentPrice);
    dash += StringFormat("  P&L:           %.2f\n", g_totalPnL);
    dash += sep;
    dash += StringFormat("  Buy  Lots:     %.2f  (%d trades)\n", g_buyLots, g_buyCount);
    dash += StringFormat("  Sell Lots:     %.2f  (%d trades)\n", g_sellLots, g_sellCount);
    dash += StringFormat("  Total Trades:  %d (today)\n", g_totalTrades);
    dash += sep;
    dash += StringFormat("  Next Resist:   %.2f  [Conf: %d]\n", g_nearestResist, g_nearestResConf);
    dash += StringFormat("  Next Support:  %.2f  [Conf: %d]\n", g_nearestSupport, g_nearestSupConf);
    dash += sep;
    dash += StringFormat("  EMA 50:        %.2f\n", EmaFastBuffer[0] != 0 ? EmaFastBuffer[0] : 0);
    dash += StringFormat("  EMA 200:       %.2f\n", EmaSlowBuffer[0] != 0 ? EmaSlowBuffer[0] : 0);
    if(InpUseSuperTrend)
        dash += StringFormat("  SuperTrend:    %.2f (%s)\n", g_stValue, g_stBullish ? "BULL" : "BEAR");
    dash += sep;
    dash += StringFormat("  Active Levels: %d\n", g_levelCount);

    // Show level breakdown
    int h22cnt=0, s23cnt=0, s07cnt=0, s12cnt=0;
    for(int i=0; i<g_levelCount; i++)
    {
        if(g_levels[i].source == "H22") h22cnt++;
        else if(g_levels[i].source == "S23") s23cnt++;
        else if(g_levels[i].source == "S07") s07cnt++;
        else if(g_levels[i].source == "S12") s12cnt++;
    }
    dash += StringFormat("    22H: %d | 23:00: %d | 07:00: %d | 12:00: %d\n", h22cnt, s23cnt, s07cnt, s12cnt);
    dash += sep;

    Comment(dash);
}

//+------------------------------------------------------------------+
