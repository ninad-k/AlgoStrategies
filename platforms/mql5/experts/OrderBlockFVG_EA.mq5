//+------------------------------------------------------------------+
//|                                           OrderBlockFVG_EA.mq5   |
//|  Order Block + FVG Strategy: Detect 3-candle FVG pattern, mark   |
//|  the pre-move candle as Order Block, enter on 50% OB retest.     |
//|  Best for Gold (XAUUSD) and Forex pairs on M5/M15.              |
//|  Author: Ninad K                                                 |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Order Block + FVG pullback EA. Detects explosive 3-candle FVG, marks Order Block, enters at 50% OB retest."
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//+------------------------------------------------------------------+
//| ENUMS                                                             |
//+------------------------------------------------------------------+
enum ENUM_ENTRY_MODE
  {
   ENTRY_OB_50PCT  = 0,   // Order Block 50% (Recommended)
   ENTRY_FVG_ZONE  = 1,   // FVG Zone
   ENTRY_BOTH      = 2    // Both (OB 50% preferred, FVG fallback)
  };

enum ENUM_SL_TP_MODE
  {
   MODE_ATR    = 0,   // ATR-based
   MODE_POINTS = 1    // Fixed Points
  };

enum ENUM_LOT_MODE
  {
   LOT_FIXED = 0,   // Fixed Lot
   LOT_RISK  = 1    // Risk % of Balance
  };

//+------------------------------------------------------------------+
//| STRUCTURES                                                        |
//+------------------------------------------------------------------+
struct SOrderBlock
  {
   double   top;           // High of the OB candle
   double   bottom;        // Low of the OB candle
   double   mid50;         // 50% level
   int      barIndex;      // Bar shift when created
   datetime timeCreated;   // Time of OB candle
   int      bias;          // 1=bullish, -1=bearish
   bool     active;        // Still valid
   bool     traded;        // Already traded once
  };

struct SFVG
  {
   double   upper;         // Top of gap
   double   lower;         // Bottom of gap
   int      barIndex;
   datetime timeCreated;
   int      bias;          // 1=bullish, -1=bearish
   bool     active;
  };

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                  |
//+------------------------------------------------------------------+
input group "=== Order Block Detection ==="
input double          InpMinBodyRatio    = 0.6;          // Min Body/Range ratio for explosive candle
input double          InpMinMoveATR      = 1.5;          // Min candle 2 size (x ATR)
input int             InpMaxOBs          = 10;           // Max Order Blocks per side
input int             InpLookback        = 200;          // Lookback bars for initial scan

input group "=== Entry Settings ==="
input ENUM_ENTRY_MODE InpEntryMode       = ENTRY_OB_50PCT;  // Entry Mode
input double          InpOBEntryLevel    = 0.50;         // OB Entry Level (0.5 = 50%)
input bool            InpRequireClose    = true;         // Require candle close confirmation

input group "=== Risk Management ==="
input ENUM_LOT_MODE   InpLotMode         = LOT_RISK;     // Lot Mode
input double          InpFixedLots       = 0.1;          // Fixed Lot Size
input double          InpRiskPercent     = 1.5;          // Risk % per trade
input ENUM_SL_TP_MODE InpSLMode          = MODE_ATR;     // SL Mode
input double          InpSLATRMult       = 0.5;          // SL ATR padding multiplier
input int             InpSLPoints        = 150;          // SL Fixed Points (if Points mode)
input int             InpATRPeriod       = 14;           // ATR Period

input group "=== Take Profit ==="
input double          InpTP_RR           = 2.0;          // TP Risk:Reward ratio
input bool            InpUsePartials     = true;         // Enable partial profit booking
input double          InpTP1_Pct         = 50;           // TP1 close % (at 1R)
input double          InpTP2_Pct         = 25;           // TP2 close % (at 2R)
input double          InpTP3_Pct         = 25;           // TP3 close % (at target R)

input group "=== Filters ==="
input int             InpMaxSpreadPts    = 40;           // Max spread (points)
input int             InpMaxDailyTrades  = 3;            // Max trades per day
input int             InpMinBarsCooldown = 3;            // Min bars between trades
input bool            InpUseHTFFilter    = false;        // Use HTF EMA trend filter
input ENUM_TIMEFRAMES InpHTF             = PERIOD_H1;    // HTF for trend filter
input int             InpHTFEMA          = 50;           // HTF EMA period

input group "=== Session (Server Time) ==="
input int             InpSessionStartHr  = 2;            // Session start hour
input int             InpSessionEndHr    = 20;           // Session end hour
input int             InpForceExitHr     = 23;           // Force exit hour
input int             InpForceExitMin    = 0;            // Force exit minute

input group "=== General ==="
input int             InpMagic           = 20250410;     // Magic Number
input double          InpSlippage        = 3;            // Max slippage (points)

//+------------------------------------------------------------------+
//| GLOBALS                                                           |
//+------------------------------------------------------------------+
CTrade         g_trade;
CPositionInfo  g_posInfo;

int            g_atrHandle      = INVALID_HANDLE;
int            g_htfEmaHandle   = INVALID_HANDLE;

double         g_atr            = 0.0;

SOrderBlock    g_bullOBs[];
SOrderBlock    g_bearOBs[];
SFVG           g_bullFVGs[];
SFVG           g_bearFVGs[];

datetime       g_lastBarTime    = 0;
int            g_dailyTradeCount= 0;
datetime       g_lastTradeDay   = 0;
int            g_lastTradeBar   = 0;
bool           g_inTrade        = false;
int            g_tradeDirection = 0;    // 1=long, -1=short
double         g_tradeSL        = 0;
double         g_tradeEntry     = 0;
double         g_tradeTP1       = 0;
double         g_tradeTP2       = 0;
double         g_tradeTP3       = 0;
bool           g_tp1Hit         = false;
bool           g_tp2Hit         = false;
bool           g_initDone       = false;

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpSlippage);

   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Alert("OB-FVG EA: Failed to create ATR handle");
      return INIT_FAILED;
     }

   if(InpUseHTFFilter)
     {
      g_htfEmaHandle = iMA(_Symbol, InpHTF, InpHTFEMA, 0, MODE_EMA, PRICE_CLOSE);
      if(g_htfEmaHandle == INVALID_HANDLE)
        {
         Alert("OB-FVG EA: Failed to create HTF EMA handle");
         return INIT_FAILED;
        }
     }

   ArrayResize(g_bullOBs, 0);
   ArrayResize(g_bearOBs, 0);
   ArrayResize(g_bullFVGs, 0);
   ArrayResize(g_bearFVGs, 0);

   Print("OB-FVG EA v1.0 initialized | ", _Symbol, " ", EnumToString(_Period),
         " | Magic: ", InpMagic, " | Entry: ", EnumToString(InpEntryMode));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)    IndicatorRelease(g_atrHandle);
   if(g_htfEmaHandle != INVALID_HANDLE) IndicatorRelease(g_htfEmaHandle);
   ObjectsDeleteAll(0, "OB_");
   ObjectsDeleteAll(0, "FVG_");
  }

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Force exit check every tick
   if(IsForceExitTime() && HasPosition())
     {
      Print("OB-FVG EA: Force exit at ", TimeToString(TimeCurrent(), TIME_MINUTES));
      CloseAllPositions();
      return;
     }

   // Manage existing position every tick
   if(g_inTrade && HasPosition())
      ManagePosition();

   // New bar detection
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == g_lastBarTime)
      return;
   g_lastBarTime = currentBarTime;

   // Reset daily trade counter
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime today = StringToTime(IntegerToString(dt.year) + "." +
                                 IntegerToString(dt.mon)  + "." +
                                 IntegerToString(dt.day));
   if(today != g_lastTradeDay)
     {
      g_dailyTradeCount = 0;
      g_lastTradeDay = today;
     }

   // Update ATR
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandle, 0, 0, 3, atrBuf) < 3) return;
   g_atr = atrBuf[1];

   // Reset if position was closed externally
   if(g_inTrade && !HasPosition())
     {
      g_inTrade = false;
      g_tradeDirection = 0;
     }

   // Initial scan on first bar
   if(!g_initDone)
     {
      ScanHistoryForOBs();
      g_initDone = true;
      return;
     }

   // Detect new FVGs and Order Blocks on completed bars
   DetectFVGAndOB();

   // Mitigate OBs (invalidate if price closed through)
   MitigateOBs();

   // Check for entry signals
   if(!g_inTrade && IsSessionActive())
      CheckForEntry();
  }

//+------------------------------------------------------------------+
//| SCAN HISTORY — Build initial OB list from recent bars             |
//+------------------------------------------------------------------+
void ScanHistoryForOBs()
  {
   int barsAvail = Bars(_Symbol, PERIOD_CURRENT);
   int scanBars  = MathMin(InpLookback, barsAvail - 5);
   if(scanBars < 5) return;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandle, 0, 0, scanBars + 3, atrBuf) < scanBars + 3)
      return;

   for(int i = scanBars; i >= 3; i--)
     {
      double atrVal = atrBuf[i];
      if(atrVal <= 0) continue;
      CheckFVGAtBar(i, atrVal);
     }
  }

//+------------------------------------------------------------------+
//| DETECT FVG AND ORDER BLOCK on latest completed bars               |
//+------------------------------------------------------------------+
void DetectFVGAndOB()
  {
   // Check the 3-candle pattern at bars 3,2,1 (all completed)
   if(Bars(_Symbol, PERIOD_CURRENT) < 5) return;
   CheckFVGAtBar(3, g_atr);
  }

//+------------------------------------------------------------------+
//| CHECK FVG AT A SPECIFIC BAR INDEX (candle 1 of 3-candle pattern)  |
//| Pattern: bar[idx] = candle 1, bar[idx-1] = candle 2 (explosive), |
//|          bar[idx-2] = candle 3                                     |
//+------------------------------------------------------------------+
void CheckFVGAtBar(int idx, double atrVal)
  {
   if(idx < 2 || atrVal <= 0) return;

   int c1 = idx;       // Pre-move candle (becomes Order Block)
   int c2 = idx - 1;   // Explosive candle
   int c3 = idx - 2;   // Post-move candle

   double c1High  = iHigh(_Symbol, PERIOD_CURRENT, c1);
   double c1Low   = iLow(_Symbol, PERIOD_CURRENT, c1);
   double c2High  = iHigh(_Symbol, PERIOD_CURRENT, c2);
   double c2Low   = iLow(_Symbol, PERIOD_CURRENT, c2);
   double c2Open  = iOpen(_Symbol, PERIOD_CURRENT, c2);
   double c2Close = iClose(_Symbol, PERIOD_CURRENT, c2);
   double c3High  = iHigh(_Symbol, PERIOD_CURRENT, c3);
   double c3Low   = iLow(_Symbol, PERIOD_CURRENT, c3);

   double c2Body  = MathAbs(c2Close - c2Open);
   double c2Range = c2High - c2Low;
   if(c2Range <= 0) return;

   double bodyRatio = c2Body / c2Range;

   // Explosive candle checks
   if(bodyRatio < InpMinBodyRatio) return;
   if(c2Range < InpMinMoveATR * atrVal) return;

   // --- Bullish FVG: gap between candle 1 high and candle 3 low ---
   if(c3Low > c1High && c2Close > c2Open)
     {
      // Check for duplicate
      datetime obTime = iTime(_Symbol, PERIOD_CURRENT, c1);
      if(IsDuplicateOB(g_bullOBs, obTime)) return;

      // Create FVG
      SFVG fvg;
      fvg.upper       = c3Low;
      fvg.lower       = c1High;
      fvg.barIndex    = c2;
      fvg.timeCreated = iTime(_Symbol, PERIOD_CURRENT, c2);
      fvg.bias        = 1;
      fvg.active      = true;
      AddFVG(g_bullFVGs, fvg);

      // Create Order Block from candle 1
      SOrderBlock ob;
      ob.top          = c1High;
      ob.bottom       = c1Low;
      ob.mid50        = c1Low + (c1High - c1Low) * InpOBEntryLevel;
      ob.barIndex     = c1;
      ob.timeCreated  = obTime;
      ob.bias         = 1;
      ob.active       = true;
      ob.traded       = false;
      AddOB(g_bullOBs, ob);

      DrawOBZone(ob);
     }

   // --- Bearish FVG: gap between candle 3 high and candle 1 low ---
   if(c1Low > c3High && c2Close < c2Open)
     {
      datetime obTime = iTime(_Symbol, PERIOD_CURRENT, c1);
      if(IsDuplicateOB(g_bearOBs, obTime)) return;

      SFVG fvg;
      fvg.upper       = c1Low;
      fvg.lower       = c3High;
      fvg.barIndex    = c2;
      fvg.timeCreated = iTime(_Symbol, PERIOD_CURRENT, c2);
      fvg.bias        = -1;
      fvg.active      = true;
      AddFVG(g_bearFVGs, fvg);

      SOrderBlock ob;
      ob.top          = c1High;
      ob.bottom       = c1Low;
      ob.mid50        = c1High - (c1High - c1Low) * InpOBEntryLevel;
      ob.barIndex     = c1;
      ob.timeCreated  = obTime;
      ob.bias         = -1;
      ob.active       = true;
      ob.traded       = false;
      AddOB(g_bearOBs, ob);

      DrawOBZone(ob);
     }
  }

//+------------------------------------------------------------------+
//| ADD ORDER BLOCK to array (with max cap)                           |
//+------------------------------------------------------------------+
void AddOB(SOrderBlock &arr[], SOrderBlock &ob)
  {
   int size = ArraySize(arr);
   if(size >= InpMaxOBs)
     {
      // Remove oldest (index 0)
      for(int i = 0; i < size - 1; i++)
         arr[i] = arr[i + 1];
      ArrayResize(arr, size);
      arr[size - 1] = ob;
     }
   else
     {
      ArrayResize(arr, size + 1);
      arr[size] = ob;
     }
  }

//+------------------------------------------------------------------+
//| ADD FVG to array                                                  |
//+------------------------------------------------------------------+
void AddFVG(SFVG &arr[], SFVG &fvg)
  {
   int size = ArraySize(arr);
   if(size >= InpMaxOBs * 2)
     {
      for(int i = 0; i < size - 1; i++)
         arr[i] = arr[i + 1];
      ArrayResize(arr, size);
      arr[size - 1] = fvg;
     }
   else
     {
      ArrayResize(arr, size + 1);
      arr[size] = fvg;
     }
  }

//+------------------------------------------------------------------+
//| CHECK FOR DUPLICATE OB                                            |
//+------------------------------------------------------------------+
bool IsDuplicateOB(SOrderBlock &arr[], datetime t)
  {
   for(int i = ArraySize(arr) - 1; i >= 0; i--)
      if(arr[i].timeCreated == t) return true;
   return false;
  }

//+------------------------------------------------------------------+
//| MITIGATE OBs — invalidate if price closed through the zone       |
//+------------------------------------------------------------------+
void MitigateOBs()
  {
   double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);

   // Bullish OBs: invalidate if price closed below bottom
   for(int i = ArraySize(g_bullOBs) - 1; i >= 0; i--)
     {
      if(!g_bullOBs[i].active) continue;
      if(closePrice < g_bullOBs[i].bottom)
         g_bullOBs[i].active = false;
     }

   // Bearish OBs: invalidate if price closed above top
   for(int i = ArraySize(g_bearOBs) - 1; i >= 0; i--)
     {
      if(!g_bearOBs[i].active) continue;
      if(closePrice > g_bearOBs[i].top)
         g_bearOBs[i].active = false;
     }
  }

//+------------------------------------------------------------------+
//| CHECK FOR ENTRY SIGNAL                                            |
//+------------------------------------------------------------------+
void CheckForEntry()
  {
   // Pre-checks
   if(g_dailyTradeCount >= InpMaxDailyTrades) return;

   int currentBar = Bars(_Symbol, PERIOD_CURRENT);
   if(currentBar - g_lastTradeBar < InpMinBarsCooldown && g_lastTradeBar > 0) return;

   // Spread filter
   double spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts) return;

   // HTF trend filter
   int htfBias = 0;
   if(InpUseHTFFilter)
     {
      htfBias = GetHTFBias();
      if(htfBias == 0) return;
     }

   double lastClose = iClose(_Symbol, PERIOD_CURRENT, 1);
   double lastLow   = iLow(_Symbol, PERIOD_CURRENT, 1);
   double lastHigh  = iHigh(_Symbol, PERIOD_CURRENT, 1);

   // --- Check Bullish OBs for long entry ---
   if(!InpUseHTFFilter || htfBias == 1)
     {
      for(int i = ArraySize(g_bullOBs) - 1; i >= 0; i--)
        {
         if(!g_bullOBs[i].active || g_bullOBs[i].traded) continue;

         bool entrySignal = false;

         if(InpEntryMode == ENTRY_OB_50PCT || InpEntryMode == ENTRY_BOTH)
           {
            // Price dipped to 50% level and closed above it
            if(lastLow <= g_bullOBs[i].mid50 && lastClose > g_bullOBs[i].mid50)
               entrySignal = true;
            // Or if not requiring close, just touching the zone
            if(!InpRequireClose && lastLow <= g_bullOBs[i].mid50)
               entrySignal = true;
           }

         if(!entrySignal && (InpEntryMode == ENTRY_FVG_ZONE || InpEntryMode == ENTRY_BOTH))
           {
            // Check if price entered the FVG zone above the OB
            if(lastLow <= g_bullOBs[i].top && lastClose > g_bullOBs[i].top)
               entrySignal = true;
           }

         if(entrySignal)
           {
            ExecuteLong(g_bullOBs[i]);
            g_bullOBs[i].traded = true;
            return;
           }
        }
     }

   // --- Check Bearish OBs for short entry ---
   if(!InpUseHTFFilter || htfBias == -1)
     {
      for(int i = ArraySize(g_bearOBs) - 1; i >= 0; i--)
        {
         if(!g_bearOBs[i].active || g_bearOBs[i].traded) continue;

         bool entrySignal = false;

         if(InpEntryMode == ENTRY_OB_50PCT || InpEntryMode == ENTRY_BOTH)
           {
            if(lastHigh >= g_bearOBs[i].mid50 && lastClose < g_bearOBs[i].mid50)
               entrySignal = true;
            if(!InpRequireClose && lastHigh >= g_bearOBs[i].mid50)
               entrySignal = true;
           }

         if(!entrySignal && (InpEntryMode == ENTRY_FVG_ZONE || InpEntryMode == ENTRY_BOTH))
           {
            if(lastHigh >= g_bearOBs[i].bottom && lastClose < g_bearOBs[i].bottom)
               entrySignal = true;
           }

         if(entrySignal)
           {
            ExecuteShort(g_bearOBs[i]);
            g_bearOBs[i].traded = true;
            return;
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| EXECUTE LONG                                                      |
//+------------------------------------------------------------------+
void ExecuteLong(SOrderBlock &ob)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = CalculateSL(ob, 1);
   double slDist = ask - sl;
   if(slDist <= 0) return;

   double lots = CalculateLots(slDist);
   if(lots <= 0) return;

   // TP levels based on R:R
   g_tradeEntry = ask;
   g_tradeSL    = sl;
   g_tradeTP1   = ask + slDist * 1.0;
   g_tradeTP2   = ask + slDist * 2.0;
   g_tradeTP3   = ask + slDist * InpTP_RR;

   double tp = g_tradeTP3;

   if(g_trade.Buy(lots, _Symbol, ask, sl, tp, "OB-FVG Long"))
     {
      g_inTrade        = true;
      g_tradeDirection = 1;
      g_tp1Hit         = false;
      g_tp2Hit         = false;
      g_dailyTradeCount++;
      g_lastTradeBar   = Bars(_Symbol, PERIOD_CURRENT);
      Print("OB-FVG: LONG @ ", ask, " SL=", sl, " TP=", tp,
            " OB[", ob.bottom, "-", ob.top, "] 50%=", ob.mid50);
     }
  }

//+------------------------------------------------------------------+
//| EXECUTE SHORT                                                     |
//+------------------------------------------------------------------+
void ExecuteShort(SOrderBlock &ob)
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl  = CalculateSL(ob, -1);
   double slDist = sl - bid;
   if(slDist <= 0) return;

   double lots = CalculateLots(slDist);
   if(lots <= 0) return;

   g_tradeEntry = bid;
   g_tradeSL    = sl;
   g_tradeTP1   = bid - slDist * 1.0;
   g_tradeTP2   = bid - slDist * 2.0;
   g_tradeTP3   = bid - slDist * InpTP_RR;

   double tp = g_tradeTP3;

   if(g_trade.Sell(lots, _Symbol, bid, sl, tp, "OB-FVG Short"))
     {
      g_inTrade        = true;
      g_tradeDirection = -1;
      g_tp1Hit         = false;
      g_tp2Hit         = false;
      g_dailyTradeCount++;
      g_lastTradeBar   = Bars(_Symbol, PERIOD_CURRENT);
      Print("OB-FVG: SHORT @ ", bid, " SL=", sl, " TP=", tp,
            " OB[", ob.bottom, "-", ob.top, "] 50%=", ob.mid50);
     }
  }

//+------------------------------------------------------------------+
//| CALCULATE STOP LOSS                                               |
//+------------------------------------------------------------------+
double CalculateSL(SOrderBlock &ob, int direction)
  {
   double padding = 0;
   if(InpSLMode == MODE_ATR)
      padding = g_atr * InpSLATRMult;
   else
      padding = InpSLPoints * _Point;

   if(direction == 1)
      return NormalizeDouble(ob.bottom - padding, _Digits);
   else
      return NormalizeDouble(ob.top + padding, _Digits);
  }

//+------------------------------------------------------------------+
//| CALCULATE LOT SIZE                                                |
//+------------------------------------------------------------------+
double CalculateLots(double slDistance)
  {
   if(InpLotMode == LOT_FIXED)
      return InpFixedLots;

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tickValue <= 0 || tickSize <= 0 || slDistance <= 0)
      return InpFixedLots;

   double lots = riskMoney / (slDistance / tickSize * tickValue);

   // Normalize
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   lots = MathFloor(lots / stepLot) * stepLot;
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;

   return lots;
  }

//+------------------------------------------------------------------+
//| MANAGE POSITION — partial profits                                 |
//+------------------------------------------------------------------+
void ManagePosition()
  {
   if(!InpUsePartials) return;
   if(!HasPosition()) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   if(g_tradeDirection == 1)
     {
      double currentPrice = bid;
      ManagePartials(currentPrice, g_tradeTP1, g_tradeTP2, g_tradeTP3, true);
     }
   else if(g_tradeDirection == -1)
     {
      double currentPrice = ask;
      ManagePartials(currentPrice, g_tradeTP1, g_tradeTP2, g_tradeTP3, false);
     }
  }

//+------------------------------------------------------------------+
//| PARTIAL PROFIT MANAGEMENT                                         |
//+------------------------------------------------------------------+
void ManagePartials(double price, double tp1, double tp2, double tp3, bool isLong)
  {
   double totalLots = GetPositionLots();
   if(totalLots <= 0) return;

   bool tp1Cond = isLong ? (price >= tp1) : (price <= tp1);
   bool tp2Cond = isLong ? (price >= tp2) : (price <= tp2);

   // TP1: close portion
   if(!g_tp1Hit && tp1Cond)
     {
      double closeLots = NormalizeLots(totalLots * InpTP1_Pct / 100.0);
      if(closeLots > 0)
        {
         g_trade.PositionClosePartial(_Symbol, closeLots);
         g_tp1Hit = true;

         // Move SL to breakeven
         if(HasPosition())
           {
            double tp = 0;
            if(PositionSelect(_Symbol))
               tp = PositionGetDouble(POSITION_TP);
            g_trade.PositionModify(_Symbol, g_tradeEntry, tp);
           }
        }
     }

   // TP2: close another portion
   if(g_tp1Hit && !g_tp2Hit && tp2Cond)
     {
      totalLots = GetPositionLots();
      double remaining = InpTP2_Pct + InpTP3_Pct;
      double closeLots = NormalizeLots(totalLots * (InpTP2_Pct / remaining));
      if(closeLots > 0)
        {
         g_trade.PositionClosePartial(_Symbol, closeLots);
         g_tp2Hit = true;
        }
     }
  }

//+------------------------------------------------------------------+
//| GET HTF TREND BIAS                                                |
//+------------------------------------------------------------------+
int GetHTFBias()
  {
   if(g_htfEmaHandle == INVALID_HANDLE) return 0;

   double emaBuf[];
   ArraySetAsSeries(emaBuf, true);
   if(CopyBuffer(g_htfEmaHandle, 0, 0, 2, emaBuf) < 2) return 0;

   double htfClose[];
   ArraySetAsSeries(htfClose, true);
   if(CopyClose(_Symbol, InpHTF, 0, 2, htfClose) < 2) return 0;

   if(htfClose[0] > emaBuf[0]) return 1;
   if(htfClose[0] < emaBuf[0]) return -1;
   return 0;
  }

//+------------------------------------------------------------------+
//| SESSION & TIME HELPERS                                            |
//+------------------------------------------------------------------+
bool IsSessionActive()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.hour >= InpSessionStartHr && dt.hour < InpSessionEndHr);
  }

bool IsForceExitTime()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.hour > InpForceExitHr ||
           (dt.hour == InpForceExitHr && dt.min >= InpForceExitMin));
  }

//+------------------------------------------------------------------+
//| POSITION HELPERS                                                  |
//+------------------------------------------------------------------+
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

void CloseAllPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) == _Symbol)
        {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagic)
            g_trade.PositionClose(_Symbol);
        }
     }
   g_inTrade = false;
   g_tradeDirection = 0;
  }

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

//+------------------------------------------------------------------+
//| DRAW ORDER BLOCK ZONE on chart                                    |
//+------------------------------------------------------------------+
void DrawOBZone(SOrderBlock &ob)
  {
   string prefix = (ob.bias == 1) ? "OB_Bull_" : "OB_Bear_";
   string name   = prefix + TimeToString(ob.timeCreated, TIME_DATE | TIME_MINUTES);
   color  clr    = (ob.bias == 1) ? clrDodgerBlue : clrCrimson;

   datetime t1 = ob.timeCreated;
   datetime t2 = t1 + PeriodSeconds() * 20;

   // OB zone rectangle
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, ob.top, t2, ob.bottom);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
     }

   // 50% line
   string midName = name + "_50";
   if(ObjectFind(0, midName) < 0)
     {
      ObjectCreate(0, midName, OBJ_TREND, 0, t1, ob.mid50, t2, ob.mid50);
      ObjectSetInteger(0, midName, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, midName, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, midName, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, midName, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, midName, OBJPROP_BACK, false);
      ObjectSetInteger(0, midName, OBJPROP_SELECTABLE, false);
     }
  }
//+------------------------------------------------------------------+
