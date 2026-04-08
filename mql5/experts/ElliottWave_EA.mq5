//+------------------------------------------------------------------+
//|                                           ElliottWave_EA.mq5     |
//|      Elliott Wave Strategy with RSI Divergence + MACD + ATR      |
//|      Targets Profit Factor >= 2 via Wave 3/5 entries + Fib TP    |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Elliott Wave EA - swing-based wave counting with multi-indicator confirmation"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| ENUMS                                                            |
//+------------------------------------------------------------------+
enum ENUM_WAVE_ENTRY
{
    ENTRY_WAVE3,       // Enter on Wave 3 start (after Wave 2 retracement)
    ENTRY_WAVE5,       // Enter on Wave 5 start (after Wave 4 retracement)
    ENTRY_BOTH         // Enter on both Wave 3 and Wave 5
};

enum ENUM_LOT_MODE
{
    LOT_FIXED,         // Fixed Lot
    LOT_RISK_PCT       // Risk % of Balance
};

enum ENUM_TP_MODE
{
    TP_FIB_EXTENSION,  // Fibonacci Extension
    TP_FIXED_RR,       // Fixed Risk:Reward Ratio
    TP_ATR_MULTIPLE    // ATR Multiple
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "=== Elliott Wave Settings ==="
input ENUM_TIMEFRAMES InpWaveTF        = PERIOD_H1;       // Wave Detection Timeframe
input int           InpZigZagDepth     = 12;              // ZigZag Depth (swing sensitivity)
input int           InpZigZagDeviation = 5;               // ZigZag Deviation
input int           InpZigZagBackstep  = 3;               // ZigZag Backstep
input double        InpWave2MinRet     = 0.382;           // Wave 2 Min Retracement (of Wave 1)
input double        InpWave2MaxRet     = 0.786;           // Wave 2 Max Retracement (of Wave 1)
input double        InpWave4MinRet     = 0.236;           // Wave 4 Min Retracement (of Wave 3)
input double        InpWave4MaxRet     = 0.50;            // Wave 4 Max Retracement (of Wave 3)
input ENUM_WAVE_ENTRY InpEntryWave     = ENTRY_BOTH;      // Which Wave to Enter

input group "=== RSI Divergence Filter ==="
input bool          InpUseRSI          = true;            // Enable RSI Divergence Filter
input int           InpRSIPeriod       = 14;              // RSI Period
input double        InpRSIOverbought   = 70;              // RSI Overbought Level
input double        InpRSIOversold     = 30;              // RSI Oversold Level

input group "=== MACD Confirmation ==="
input bool          InpUseMACD         = true;            // Enable MACD Confirmation
input int           InpMACDFast        = 12;              // MACD Fast EMA
input int           InpMACDSlow        = 26;              // MACD Slow EMA
input int           InpMACDSignal      = 9;               // MACD Signal Period

input group "=== EMA Trend Filter ==="
input bool          InpUseEMA          = true;            // Enable EMA Trend Filter
input int           InpEMAPeriod       = 200;             // EMA Period

input group "=== Trade Management ==="
input ENUM_LOT_MODE InpLotMode         = LOT_RISK_PCT;    // Lot Mode
input double        InpFixedLot        = 0.1;             // Fixed Lot Size
input double        InpRiskPct         = 1.0;             // Risk % of Balance
input ENUM_TP_MODE  InpTPMode          = TP_FIB_EXTENSION;// Take Profit Mode
input double        InpFibTPLevel      = 1.618;           // Fib Extension TP Level (1.272, 1.618, 2.618)
input double        InpRRRatio         = 2.5;             // Risk:Reward Ratio (if TP_FIXED_RR)
input double        InpATRTPMult       = 3.0;             // ATR Multiple for TP (if TP_ATR_MULTIPLE)
input double        InpSLPaddingPips   = 10;              // SL Padding Beyond Swing (pips)
input int           InpATRPeriod       = 14;              // ATR Period (for SL/TP)

input group "=== Trailing Stop ==="
input bool          InpUseTrailing     = true;            // Enable Trailing Stop
input double        InpTrailATRMult    = 1.5;             // Trail Distance (ATR multiplier)
input double        InpTrailStartRR    = 1.0;             // Start Trailing at R:R reached

input group "=== Risk Management ==="
input int           InpMaxDailyTrades  = 3;               // Max Trades Per Day
input int           InpMaxOpenTrades   = 1;               // Max Simultaneous Open Trades
input double        InpMaxDailyLossPct = 3.0;             // Max Daily Loss % (pause trading)
input int           InpCooldownBars    = 5;               // Cooldown Bars After Exit

input group "=== General ==="
input long          InpMagic           = 20260330;        // Magic Number
input double        InpSlippage        = 5;               // Max Slippage (points)

input group "=== Display ==="
input bool          InpShowDashboard   = true;            // Show Dashboard
input bool          InpShowWaveLabels  = true;            // Draw Wave Labels on Chart

//+------------------------------------------------------------------+
//| STRUCTURES                                                       |
//+------------------------------------------------------------------+
struct SwingPoint
{
    double   price;
    datetime time;
    int      barIndex;
    bool     isHigh;     // true = swing high, false = swing low
};

struct WaveCount
{
    SwingPoint points[6]; // Wave 0 (origin), 1, 2, 3, 4, 5
    int        count;     // how many waves identified (0-5)
    bool       bullish;   // true = bullish impulse, false = bearish
    bool       valid;     // passes Elliott rules
};

//+------------------------------------------------------------------+
//| GLOBALS                                                          |
//+------------------------------------------------------------------+
CTrade      g_trade;
WaveCount   g_wave;
SwingPoint  g_swings[];
int         g_swingCount = 0;

// Indicator handles
int g_rsiHandle, g_macdHandle, g_emaHandle, g_atrHandle;

// Bar tracking
datetime g_lastBarTime = 0;
int      g_barsSinceExit = 999;

// Daily stats
int      g_dailyTrades  = 0;
double   g_dailyPnL     = 0;
datetime g_lastTradeDay  = 0;

// Dashboard stats
int      g_totalTrades   = 0;
int      g_winCount      = 0;
double   g_totalProfit   = 0;
double   g_totalLoss     = 0;
double   g_entryPrice    = 0;
double   g_entrySL       = 0;

string g_objPrefix = "EW_";

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
    g_trade.SetExpertMagicNumber(InpMagic);
    g_trade.SetDeviationInPoints((ulong)InpSlippage);
    g_trade.SetTypeFilling(ORDER_FILLING_IOC);

    // Create indicator handles
    if(InpUseRSI)
        g_rsiHandle = iRSI(_Symbol, InpWaveTF, InpRSIPeriod, PRICE_CLOSE);
    else
        g_rsiHandle = INVALID_HANDLE;

    if(InpUseMACD)
        g_macdHandle = iMACD(_Symbol, InpWaveTF, InpMACDFast, InpMACDSlow, InpMACDSignal, PRICE_CLOSE);
    else
        g_macdHandle = INVALID_HANDLE;

    if(InpUseEMA)
        g_emaHandle = iMA(_Symbol, InpWaveTF, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
    else
        g_emaHandle = INVALID_HANDLE;

    g_atrHandle = iATR(_Symbol, InpWaveTF, InpATRPeriod);

    if(g_atrHandle == INVALID_HANDLE)
    {
        Print("Failed to create ATR handle");
        return INIT_FAILED;
    }
    if(InpUseRSI && g_rsiHandle == INVALID_HANDLE)
    {
        Print("Failed to create RSI handle");
        return INIT_FAILED;
    }
    if(InpUseMACD && g_macdHandle == INVALID_HANDLE)
    {
        Print("Failed to create MACD handle");
        return INIT_FAILED;
    }
    if(InpUseEMA && g_emaHandle == INVALID_HANDLE)
    {
        Print("Failed to create EMA handle");
        return INIT_FAILED;
    }

    ArrayResize(g_swings, 0);
    g_swingCount = 0;
    ResetWaveCount();

    Print("ElliottWave EA initialized. Magic=", InpMagic, " TF=", EnumToString(InpWaveTF));
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(g_rsiHandle  != INVALID_HANDLE) IndicatorRelease(g_rsiHandle);
    if(g_macdHandle != INVALID_HANDLE) IndicatorRelease(g_macdHandle);
    if(g_emaHandle  != INVALID_HANDLE) IndicatorRelease(g_emaHandle);
    if(g_atrHandle  != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
    ObjectsDeleteAll(0, g_objPrefix);
    Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

    // Trailing stop management every tick
    if(InpUseTrailing && HasPosition())
        ManageTrailingStop();

    // New bar check on wave timeframe
    datetime curBarTime = iTime(_Symbol, InpWaveTF, 0);
    if(curBarTime == g_lastBarTime) return;
    g_lastBarTime = curBarTime;
    g_barsSinceExit++;

    // Reset daily counters
    ResetDailyStats();

    // Check daily loss limit
    if(InpMaxDailyLossPct > 0 && g_dailyPnL < 0)
    {
        double maxLoss = AccountInfoDouble(ACCOUNT_BALANCE) * InpMaxDailyLossPct / 100.0;
        if(MathAbs(g_dailyPnL) >= maxLoss)
        {
            if(InpShowDashboard) UpdateDashboard("PAUSED - Daily loss limit reached");
            return;
        }
    }

    // Detect swing points and count waves
    DetectSwingPoints();
    CountWaves();

    // Draw wave labels
    if(InpShowWaveLabels) DrawWaveLabels();

    // Manage existing position exits
    if(HasPosition())
    {
        CheckWaveInvalidation();
    }

    // Entry logic
    if(!HasPosition() && g_barsSinceExit >= InpCooldownBars)
    {
        if(CountOpenTrades() >= InpMaxOpenTrades) return;
        if(g_dailyTrades >= InpMaxDailyTrades) return;

        int signal = GetEntrySignal(bid);
        if(signal != 0)
            ExecuteEntry(signal, bid);
    }

    if(InpShowDashboard) UpdateDashboard("");
}

//+------------------------------------------------------------------+
//| Trade transaction handler - track closed trades                  |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
    if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
    {
        if(HistoryDealSelect(trans.deal))
        {
            long dealMagic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
            if(dealMagic == InpMagic)
            {
                ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
                if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
                {
                    double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                                  + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
                                  + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
                    g_dailyPnL += profit;
                    g_totalTrades++;

                    if(profit > 0)
                    {
                        g_winCount++;
                        g_totalProfit += profit;
                    }
                    else
                    {
                        g_totalLoss += MathAbs(profit);
                    }

                    g_barsSinceExit = 0;
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Detect swing highs and lows using ZigZag logic                   |
//+------------------------------------------------------------------+
void DetectSwingPoints()
{
    int barsNeeded = 200;
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(_Symbol, InpWaveTF, 0, barsNeeded, rates);
    if(copied < barsNeeded) return;

    ArrayResize(g_swings, 0);
    g_swingCount = 0;

    int depth    = InpZigZagDepth;
    int dev      = InpZigZagDeviation;
    int backstep = InpZigZagBackstep;

    double highs[], lows[];
    ArrayResize(highs, copied);
    ArrayResize(lows, copied);
    ArrayInitialize(highs, 0);
    ArrayInitialize(lows, 0);

    // Find local highs
    for(int i = depth; i < copied - depth; i++)
    {
        double highVal = rates[i].high;
        bool isHigh = true;
        for(int j = 1; j <= depth; j++)
        {
            if(rates[i - j].high > highVal || rates[i + j].high > highVal)
            {
                isHigh = false;
                break;
            }
        }
        if(isHigh)
        {
            // Check backstep - no other high within backstep bars
            bool tooClose = false;
            for(int k = 1; k <= backstep && k <= i; k++)
            {
                if(highs[i - k] > 0 && highs[i - k] >= highVal)
                {
                    tooClose = true;
                    break;
                }
            }
            if(!tooClose)
                highs[i] = highVal;
        }
    }

    // Find local lows
    for(int i = depth; i < copied - depth; i++)
    {
        double lowVal = rates[i].low;
        bool isLow = true;
        for(int j = 1; j <= depth; j++)
        {
            if(rates[i - j].low < lowVal || rates[i + j].low < lowVal)
            {
                isLow = false;
                break;
            }
        }
        if(isLow)
        {
            bool tooClose = false;
            for(int k = 1; k <= backstep && k <= i; k++)
            {
                if(lows[i - k] > 0 && lows[i - k] <= lowVal)
                {
                    tooClose = true;
                    break;
                }
            }
            if(!tooClose)
                lows[i] = lowVal;
        }
    }

    // Build alternating swing sequence (must alternate high/low)
    // Collect all swings first
    SwingPoint allSwings[];
    int allCount = 0;

    for(int i = copied - 1; i >= depth; i--)
    {
        if(highs[i] > 0)
        {
            int size = ArrayResize(allSwings, allCount + 1);
            allSwings[allCount].price    = highs[i];
            allSwings[allCount].time     = rates[i].time;
            allSwings[allCount].barIndex = i;
            allSwings[allCount].isHigh   = true;
            allCount++;
        }
        if(lows[i] > 0)
        {
            int size = ArrayResize(allSwings, allCount + 1);
            allSwings[allCount].price    = lows[i];
            allSwings[allCount].time     = rates[i].time;
            allSwings[allCount].barIndex = i;
            allSwings[allCount].isHigh   = false;
            allCount++;
        }
    }

    // Sort by time (oldest first) - already in order from loop above
    // Filter to alternating sequence
    if(allCount < 2) return;

    ArrayResize(g_swings, allCount);
    g_swings[0] = allSwings[0];
    g_swingCount = 1;

    for(int i = 1; i < allCount; i++)
    {
        if(allSwings[i].isHigh != g_swings[g_swingCount - 1].isHigh)
        {
            g_swings[g_swingCount] = allSwings[i];
            g_swingCount++;
        }
        else
        {
            // Same type - keep the more extreme one
            if(allSwings[i].isHigh && allSwings[i].price > g_swings[g_swingCount - 1].price)
                g_swings[g_swingCount - 1] = allSwings[i];
            else if(!allSwings[i].isHigh && allSwings[i].price < g_swings[g_swingCount - 1].price)
                g_swings[g_swingCount - 1] = allSwings[i];
        }
    }

    ArrayResize(g_swings, g_swingCount);
}

//+------------------------------------------------------------------+
//| Count Elliott Waves from swing points                            |
//+------------------------------------------------------------------+
void CountWaves()
{
    ResetWaveCount();
    if(g_swingCount < 5) return;

    // Try to find a valid 5-wave impulse from the most recent swings
    // Work backwards from the latest swing points
    // We need at least 6 points for waves 0-5

    // Try bullish impulse (low-high-low-high-low-high pattern)
    if(TryCountBullishWave())
        return;

    // Try bearish impulse (high-low-high-low-high-low pattern)
    TryCountBearishWave();
}

//+------------------------------------------------------------------+
//| Try to identify a bullish 5-wave impulse                         |
//+------------------------------------------------------------------+
bool TryCountBullishWave()
{
    // Look for: Low(0) -> High(1) -> Low(2) -> High(3) -> Low(4) -> [pending High(5)]
    // Starting from recent swings, find the pattern
    for(int start = g_swingCount - 5; start >= MathMax(0, g_swingCount - 20); start--)
    {
        // Wave 0 must be a low
        if(g_swings[start].isHigh) continue;

        // Check we have alternating H/L pattern for 5 points after origin
        bool patternOk = true;
        for(int k = 1; k <= 4 && (start + k) < g_swingCount; k++)
        {
            bool expectHigh = (k % 2 == 1);
            if(g_swings[start + k].isHigh != expectHigh)
            {
                patternOk = false;
                break;
            }
        }
        if(!patternOk || start + 4 >= g_swingCount) continue;

        double p0 = g_swings[start].price;     // Wave origin (low)
        double p1 = g_swings[start + 1].price;  // Wave 1 end (high)
        double p2 = g_swings[start + 2].price;  // Wave 2 end (low)
        double p3 = g_swings[start + 3].price;  // Wave 3 end (high)
        double p4 = g_swings[start + 4].price;  // Wave 4 end (low)

        // Elliott Wave Rules for bullish impulse:
        // 1. Wave 2 cannot retrace beyond Wave 0 (p2 > p0)
        if(p2 <= p0) continue;

        // 2. Wave 3 must exceed Wave 1 end (p3 > p1)
        if(p3 <= p1) continue;

        // 3. Wave 4 cannot overlap Wave 1 territory (p4 > p1)
        if(p4 <= p1) continue;

        // 4. Wave 3 cannot be the shortest impulse wave
        double wave1Len = p1 - p0;
        double wave3Len = p3 - p2;
        double wave5Est = (p3 - p0) * 0.382; // estimate wave 5
        if(wave3Len < wave1Len && wave3Len < wave5Est) continue;

        // Check Wave 2 retracement of Wave 1
        double wave2Ret = (p1 - p2) / (p1 - p0);
        if(wave2Ret < InpWave2MinRet || wave2Ret > InpWave2MaxRet) continue;

        // Check Wave 4 retracement of Wave 3
        double wave4Ret = (p3 - p4) / (p3 - p2);
        if(wave4Ret < InpWave4MinRet || wave4Ret > InpWave4MaxRet) continue;

        // Valid bullish wave found
        g_wave.bullish = true;
        g_wave.valid = true;

        // Determine wave count based on how many points we have
        for(int w = 0; w <= 4 && (start + w) < g_swingCount; w++)
        {
            g_wave.points[w] = g_swings[start + w];
            g_wave.count = w + 1;
        }

        // Check if wave 5 is also present
        if(start + 5 < g_swingCount && g_swings[start + 5].isHigh)
        {
            double p5 = g_swings[start + 5].price;
            if(p5 > p3) // Wave 5 should exceed Wave 3 (no truncation for now)
            {
                g_wave.points[5] = g_swings[start + 5];
                g_wave.count = 6;
            }
        }

        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Try to identify a bearish 5-wave impulse                         |
//+------------------------------------------------------------------+
bool TryCountBearishWave()
{
    for(int start = g_swingCount - 5; start >= MathMax(0, g_swingCount - 20); start--)
    {
        // Wave 0 must be a high
        if(!g_swings[start].isHigh) continue;

        bool patternOk = true;
        for(int k = 1; k <= 4 && (start + k) < g_swingCount; k++)
        {
            bool expectLow = (k % 2 == 1);
            if(g_swings[start + k].isHigh == expectLow)
            {
                patternOk = false;
                break;
            }
        }
        if(!patternOk || start + 4 >= g_swingCount) continue;

        double p0 = g_swings[start].price;      // Wave origin (high)
        double p1 = g_swings[start + 1].price;   // Wave 1 end (low)
        double p2 = g_swings[start + 2].price;   // Wave 2 end (high)
        double p3 = g_swings[start + 3].price;   // Wave 3 end (low)
        double p4 = g_swings[start + 4].price;   // Wave 4 end (high)

        // Bearish rules (mirrored):
        if(p2 >= p0) continue;       // Wave 2 can't retrace beyond origin
        if(p3 >= p1) continue;       // Wave 3 must go beyond Wave 1
        if(p4 >= p1) continue;       // Wave 4 can't overlap Wave 1

        double wave1Len = p0 - p1;
        double wave3Len = p2 - p3;
        double wave5Est = (p0 - p3) * 0.382;
        if(wave3Len < wave1Len && wave3Len < wave5Est) continue;

        double wave2Ret = (p2 - p1) / (p0 - p1);
        if(wave2Ret < InpWave2MinRet || wave2Ret > InpWave2MaxRet) continue;

        double wave4Ret = (p4 - p3) / (p2 - p3);
        if(wave4Ret < InpWave4MinRet || wave4Ret > InpWave4MaxRet) continue;

        g_wave.bullish = false;
        g_wave.valid = true;

        for(int w = 0; w <= 4 && (start + w) < g_swingCount; w++)
        {
            g_wave.points[w] = g_swings[start + w];
            g_wave.count = w + 1;
        }

        if(start + 5 < g_swingCount && !g_swings[start + 5].isHigh)
        {
            double p5 = g_swings[start + 5].price;
            if(p5 < p3)
            {
                g_wave.points[5] = g_swings[start + 5];
                g_wave.count = 6;
            }
        }

        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Get entry signal: +1 = buy, -1 = sell, 0 = no signal            |
//+------------------------------------------------------------------+
int GetEntrySignal(double bid)
{
    if(!g_wave.valid) return 0;

    int signal = 0;

    // Wave 3 entry: we have waves 0,1,2 identified (count >= 3, wave not yet 3)
    // Enter in direction of the impulse after Wave 2 retracement completes
    if((InpEntryWave == ENTRY_WAVE3 || InpEntryWave == ENTRY_BOTH) && g_wave.count == 5)
    {
        // 5 points = waves 0-4 identified. But for Wave 3 entry,
        // we want count==3 (waves 0,1,2 done). Since we detect post-facto,
        // check if Wave 3 is still developing (price in Wave 3 zone)
        // Actually: count==5 means we have through Wave 4 end.
        // Wave 3 entry is missed. We use count to determine which phase we're in.
    }

    // Wave 3 entry: count == 3 means waves 0,1,2 are identified
    if((InpEntryWave == ENTRY_WAVE3 || InpEntryWave == ENTRY_BOTH) && g_wave.count >= 3 && g_wave.count < 5)
    {
        if(g_wave.bullish)
        {
            // Wave 2 has retraced, expect Wave 3 up
            // Confirm price is above Wave 2 low and starting to move up
            double wave2Low = g_wave.points[2].price;
            if(bid > wave2Low && bid < g_wave.points[1].price)
                signal = 1;
        }
        else
        {
            double wave2High = g_wave.points[2].price;
            if(bid < wave2High && bid > g_wave.points[1].price)
                signal = -1;
        }
    }

    // Wave 5 entry: count == 5 means waves 0-4 identified
    if((InpEntryWave == ENTRY_WAVE5 || InpEntryWave == ENTRY_BOTH) && g_wave.count == 5)
    {
        if(g_wave.bullish)
        {
            double wave4Low = g_wave.points[4].price;
            double wave3High = g_wave.points[3].price;
            if(bid > wave4Low && bid < wave3High)
                signal = 1;
        }
        else
        {
            double wave4High = g_wave.points[4].price;
            double wave3Low = g_wave.points[3].price;
            if(bid < wave4High && bid > wave3Low)
                signal = -1;
        }
    }

    if(signal == 0) return 0;

    // Apply filters
    if(!CheckEMAFilter(signal)) return 0;
    if(!CheckRSIFilter(signal)) return 0;
    if(!CheckMACDFilter(signal)) return 0;

    return signal;
}

//+------------------------------------------------------------------+
//| Check EMA trend filter                                           |
//+------------------------------------------------------------------+
bool CheckEMAFilter(int signal)
{
    if(!InpUseEMA) return true;

    double ema[1];
    if(CopyBuffer(g_emaHandle, 0, 0, 1, ema) < 1) return false;

    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

    if(signal > 0 && bid < ema[0]) return false;  // Buy only above EMA
    if(signal < 0 && bid > ema[0]) return false;  // Sell only below EMA

    return true;
}

//+------------------------------------------------------------------+
//| Check RSI divergence / zone filter                               |
//+------------------------------------------------------------------+
bool CheckRSIFilter(int signal)
{
    if(!InpUseRSI) return true;

    double rsi[3];
    if(CopyBuffer(g_rsiHandle, 0, 0, 3, rsi) < 3) return false;

    // For Wave 3 entries: look for RSI confirming momentum
    // For buy: RSI should be rising and not overbought
    // For sell: RSI should be falling and not oversold
    if(signal > 0)
    {
        if(rsi[0] > InpRSIOverbought) return false;  // Already overbought
        if(rsi[0] < rsi[2] - 5) return false;        // RSI declining significantly
    }
    else
    {
        if(rsi[0] < InpRSIOversold) return false;     // Already oversold
        if(rsi[0] > rsi[2] + 5) return false;         // RSI rising significantly
    }

    // Check for RSI divergence at wave completion points (stronger confirmation)
    // Bullish divergence: price makes lower low but RSI makes higher low
    // Bearish divergence: price makes higher high but RSI makes lower high
    if(g_wave.count >= 5)
    {
        double rsiAtWave2Bar[1], rsiAtWave4Bar[1];
        int wave2Shift = g_wave.points[2].barIndex;
        int wave4Shift = g_wave.points[4].barIndex;

        if(CopyBuffer(g_rsiHandle, 0, wave2Shift, 1, rsiAtWave2Bar) >= 1 &&
           CopyBuffer(g_rsiHandle, 0, wave4Shift, 1, rsiAtWave4Bar) >= 1)
        {
            if(signal > 0)
            {
                // Bullish: Wave 4 low > Wave 2 low (already ensured), RSI divergence is bonus
                // If RSI at wave 4 > RSI at wave 2, extra confirmation
                if(rsiAtWave4Bar[0] > rsiAtWave2Bar[0])
                    return true; // Strong divergence confirmation
            }
            else
            {
                if(rsiAtWave4Bar[0] < rsiAtWave2Bar[0])
                    return true;
            }
        }
    }

    return true;
}

//+------------------------------------------------------------------+
//| Check MACD momentum confirmation                                 |
//+------------------------------------------------------------------+
bool CheckMACDFilter(int signal)
{
    if(!InpUseMACD) return true;

    double macdMain[2], macdSignal[2];
    if(CopyBuffer(g_macdHandle, 0, 0, 2, macdMain) < 2) return false;
    if(CopyBuffer(g_macdHandle, 1, 0, 2, macdSignal) < 2) return false;

    // MACD should confirm direction
    if(signal > 0)
    {
        // Buy: MACD above signal line or crossing above
        if(macdMain[0] < macdSignal[0] && macdMain[1] < macdSignal[1])
            return false; // MACD bearish, no buy
    }
    else
    {
        // Sell: MACD below signal line or crossing below
        if(macdMain[0] > macdSignal[0] && macdMain[1] > macdSignal[1])
            return false; // MACD bullish, no sell
    }

    return true;
}

//+------------------------------------------------------------------+
//| Execute trade entry                                              |
//+------------------------------------------------------------------+
void ExecuteEntry(int signal, double bid)
{
    double atr[1];
    if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) < 1) return;

    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    double pip   = point * 10;
    double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

    double sl = 0, tp = 0;
    double slDistance = 0;

    if(signal > 0) // BUY
    {
        // SL below the wave origin or wave 2/4 low + padding
        double swingLow;
        if(g_wave.count == 5)
            swingLow = g_wave.points[4].price; // Below wave 4 for wave 5 entry
        else
            swingLow = g_wave.points[2].price; // Below wave 2 for wave 3 entry

        sl = swingLow - InpSLPaddingPips * pip;
        slDistance = ask - sl;

        if(slDistance <= 0) return;

        // Take Profit
        if(InpTPMode == TP_FIB_EXTENSION)
        {
            // Fibonacci extension of the relevant wave
            double wave1Len = g_wave.points[1].price - g_wave.points[0].price;
            if(g_wave.count == 5)
            {
                // Wave 5 TP: extension from Wave 4
                tp = g_wave.points[4].price + wave1Len * InpFibTPLevel;
            }
            else
            {
                // Wave 3 TP: 1.618 extension from Wave 2
                tp = g_wave.points[2].price + wave1Len * InpFibTPLevel;
            }
        }
        else if(InpTPMode == TP_FIXED_RR)
        {
            tp = ask + slDistance * InpRRRatio;
        }
        else // TP_ATR_MULTIPLE
        {
            tp = ask + atr[0] * InpATRTPMult;
        }

        // Calculate lot size
        double lots = CalculateLotSize(slDistance);
        if(lots <= 0) return;

        // Normalize prices
        int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
        sl = NormalizeDouble(sl, digits);
        tp = NormalizeDouble(tp, digits);

        string comment = StringFormat("EW_%s_W%d", g_wave.bullish ? "Bull" : "Bear",
                                       g_wave.count >= 5 ? 5 : 3);

        if(g_trade.Buy(lots, _Symbol, ask, sl, tp, comment))
        {
            g_dailyTrades++;
            g_entryPrice = ask;
            g_entrySL = sl;
            Print("BUY opened: ", comment, " Lots=", lots, " SL=", sl, " TP=", tp);
        }
    }
    else // SELL
    {
        double swingHigh;
        if(g_wave.count == 5)
            swingHigh = g_wave.points[4].price;
        else
            swingHigh = g_wave.points[2].price;

        sl = swingHigh + InpSLPaddingPips * pip;
        slDistance = sl - bid;

        if(slDistance <= 0) return;

        if(InpTPMode == TP_FIB_EXTENSION)
        {
            double wave1Len = g_wave.points[0].price - g_wave.points[1].price;
            if(g_wave.count == 5)
                tp = g_wave.points[4].price - wave1Len * InpFibTPLevel;
            else
                tp = g_wave.points[2].price - wave1Len * InpFibTPLevel;
        }
        else if(InpTPMode == TP_FIXED_RR)
        {
            tp = bid - slDistance * InpRRRatio;
        }
        else
        {
            tp = bid - atr[0] * InpATRTPMult;
        }

        double lots = CalculateLotSize(slDistance);
        if(lots <= 0) return;

        int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
        sl = NormalizeDouble(sl, digits);
        tp = NormalizeDouble(tp, digits);

        string comment = StringFormat("EW_%s_W%d", g_wave.bullish ? "Bull" : "Bear",
                                       g_wave.count >= 5 ? 5 : 3);

        if(g_trade.Sell(lots, _Symbol, bid, sl, tp, comment))
        {
            g_dailyTrades++;
            g_entryPrice = bid;
            g_entrySL = sl;
            Print("SELL opened: ", comment, " Lots=", lots, " SL=", sl, " TP=", tp);
        }
    }
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk                                 |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistancePrice)
{
    if(InpLotMode == LOT_FIXED) return InpFixedLot;

    double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskAmount = balance * InpRiskPct / 100.0;
    double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);

    if(tickSize == 0 || tickValue == 0) return InpFixedLot;

    double slTicks = slDistancePrice / tickSize;
    double lots    = riskAmount / (slTicks * tickValue);

    double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

    lots = MathFloor(lots / lotStep) * lotStep;
    lots = MathMax(minLot, MathMin(maxLot, lots));

    return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Manage trailing stop                                             |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
    double atr[1];
    if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) < 1) return;

    double trailDist = atr[0] * InpTrailATRMult;

    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

        double posOpen = PositionGetDouble(POSITION_PRICE_OPEN);
        double posSL   = PositionGetDouble(POSITION_SL);
        double posTP   = PositionGetDouble(POSITION_TP);
        long   posType = PositionGetInteger(POSITION_TYPE);
        int    digits  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

        double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

        // Check if minimum profit reached to start trailing
        double slDist = MathAbs(posOpen - posSL);
        double minProfit = slDist * InpTrailStartRR;

        if(posType == POSITION_TYPE_BUY)
        {
            double profit = bid - posOpen;
            if(profit < minProfit) continue;

            double newSL = NormalizeDouble(bid - trailDist, digits);
            if(newSL > posSL && newSL < bid)
            {
                g_trade.PositionModify(ticket, newSL, posTP);
            }
        }
        else if(posType == POSITION_TYPE_SELL)
        {
            double profit = posOpen - ask;
            if(profit < minProfit) continue;

            double newSL = NormalizeDouble(ask + trailDist, digits);
            if(newSL < posSL && newSL > ask)
            {
                g_trade.PositionModify(ticket, newSL, posTP);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Check if wave pattern is invalidated - close position            |
//+------------------------------------------------------------------+
void CheckWaveInvalidation()
{
    if(!g_wave.valid) return;

    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

    // If wave structure breaks (e.g., Wave 4 overlaps Wave 1 territory)
    // the SL should handle this, but we can add extra safety
    // The SL placed at the swing low/high already handles invalidation
}

//+------------------------------------------------------------------+
//| Helper: check if we have an open position                        |
//+------------------------------------------------------------------+
bool HasPosition()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
           PositionGetString(POSITION_SYMBOL) == _Symbol)
            return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Count open trades for this EA                                    |
//+------------------------------------------------------------------+
int CountOpenTrades()
{
    int count = 0;
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
           PositionGetString(POSITION_SYMBOL) == _Symbol)
            count++;
    }
    return count;
}

//+------------------------------------------------------------------+
//| Reset wave count                                                 |
//+------------------------------------------------------------------+
void ResetWaveCount()
{
    g_wave.count   = 0;
    g_wave.bullish = false;
    g_wave.valid   = false;
}

//+------------------------------------------------------------------+
//| Reset daily statistics                                           |
//+------------------------------------------------------------------+
void ResetDailyStats()
{
    MqlDateTime dt;
    TimeCurrent(dt);
    datetime today = StringToTime(StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day));

    if(today != g_lastTradeDay)
    {
        g_lastTradeDay = today;
        g_dailyTrades  = 0;
        g_dailyPnL     = 0;
    }
}

//+------------------------------------------------------------------+
//| Draw wave labels on chart                                        |
//+------------------------------------------------------------------+
void DrawWaveLabels()
{
    // Clean previous labels
    ObjectsDeleteAll(0, g_objPrefix + "WL_");

    if(!g_wave.valid) return;

    string waveNames[] = {"0", "1", "2", "3", "4", "5"};
    color  waveColors[] = {clrWhite, clrDodgerBlue, clrOrange, clrLime, clrYellow, clrMagenta};

    for(int i = 0; i < g_wave.count && i < 6; i++)
    {
        string name = g_objPrefix + "WL_" + IntegerToString(i);
        double price = g_wave.points[i].price;
        datetime time = g_wave.points[i].time;

        if(ObjectFind(0, name) >= 0)
            ObjectDelete(0, name);

        ObjectCreate(0, name, OBJ_TEXT, 0, time, price);
        ObjectSetString(0, name, OBJPROP_TEXT, waveNames[i]);
        ObjectSetInteger(0, name, OBJPROP_COLOR, waveColors[i]);
        ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 12);
        ObjectSetString(0, name, OBJPROP_FONT, "Arial Bold");
        ObjectSetInteger(0, name, OBJPROP_ANCHOR,
                          g_wave.points[i].isHigh ? ANCHOR_LOWER : ANCHOR_UPPER);
    }
}

//+------------------------------------------------------------------+
//| Update dashboard                                                 |
//+------------------------------------------------------------------+
void UpdateDashboard(string status)
{
    double profitFactor = (g_totalLoss > 0) ? g_totalProfit / g_totalLoss : 0;
    double winRate = (g_totalTrades > 0) ? (double)g_winCount / g_totalTrades * 100 : 0;

    string waveStatus = "No wave detected";
    if(g_wave.valid)
    {
        waveStatus = StringFormat("%s Impulse - %d points identified",
                                   g_wave.bullish ? "Bullish" : "Bearish", g_wave.count);
    }

    string txt = "";
    txt += "=== Elliott Wave EA ===\n";
    txt += StringFormat("Symbol: %s | TF: %s\n", _Symbol, EnumToString(InpWaveTF));
    txt += StringFormat("Wave: %s\n", waveStatus);
    txt += StringFormat("Swings found: %d\n", g_swingCount);
    txt += "---\n";
    txt += StringFormat("Total Trades: %d | Wins: %d (%.1f%%)\n", g_totalTrades, g_winCount, winRate);
    txt += StringFormat("Profit Factor: %.2f\n", profitFactor);
    txt += StringFormat("Gross Profit: %.2f | Gross Loss: %.2f\n", g_totalProfit, g_totalLoss);
    txt += StringFormat("Daily PnL: %.2f | Daily Trades: %d/%d\n", g_dailyPnL, g_dailyTrades, InpMaxDailyTrades);
    txt += "---\n";
    txt += StringFormat("Entry: %s | RSI: %s | MACD: %s | EMA: %s\n",
                         EnumToString(InpEntryWave),
                         InpUseRSI ? "ON" : "OFF",
                         InpUseMACD ? "ON" : "OFF",
                         InpUseEMA ? "ON" : "OFF");

    if(status != "")
        txt += StringFormat("Status: %s\n", status);

    Comment(txt);
}

//+------------------------------------------------------------------+
