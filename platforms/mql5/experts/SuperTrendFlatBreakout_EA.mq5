//+------------------------------------------------------------------+
//|                                  SuperTrendFlatBreakout_EA.mq5   |
//|                                         AlgoStrategies           |
//|  SuperTrend Flat Breakout + 23 EMA swing strategy: detect        |
//|  flat consolidation, enter on swing high breakout, trail with    |
//|  23 EMA, partial TP, re-entry after SL hit, on-chart dashboard   |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property link      ""
#property version   "1.00"
#property description "SuperTrend Flat Breakout: RED->GREEN shift, flat detection, swing high breakout, 23 EMA momentum trailing, partial TP, re-entry"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_EXIT_MODE {                                                 //--- Exit mode
   EXIT_TARGET,                                                       // Target-Based (TP1/TP2)
   EXIT_MOMENTUM,                                                     // Momentum (23 EMA Trail)
   EXIT_COMBINED                                                      // Combined (TP1 partial + EMA trail)
};

enum ENUM_LOT_MODE {                                                  //--- Lot sizing mode
   LOT_FIXED,                                                         // Fixed Lot
   LOT_RISK_PCT                                                       // Risk % of Balance
};

enum ENUM_SL_MODE {                                                   //--- Initial SL mode
   SL_SWING_LOW,                                                      // Swing Low
   SL_FIXED_PCT                                                       // Fixed %
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
sinput string sep0 = "=== SuperTrend Settings ===";
input int              InpSTPeriod      = 10;                         // ATR Period
input double           InpSTMultiplier  = 3.0;                        // Multiplier

sinput string sep1 = "=== Flat Detection ===";
input int              InpMinFlatBars   = 5;                          // Min Flat Days
input double           InpFlatTolPct    = 0.1;                        // Flat Tolerance %

sinput string sep2 = "=== Entry Settings ===";
input double           InpRetestZonePct = 3.0;                        // Retest Zone %
input double           InpDualResBuf    = 3.0;                        // Dual Resistance Buffer %

sinput string sep3 = "=== EMA Settings ===";
input int              InpEMALen        = 23;                         // EMA Length (23 = ~1 month trading)

sinput string sep4 = "=== Exit Mode ===";
input ENUM_EXIT_MODE   InpExitMode      = EXIT_MOMENTUM;             // Exit Strategy
input double           InpTP1Pct        = 10.0;                       // TP1 %
input double           InpTP2Pct        = 20.0;                       // TP2 %
input double           InpTP1QtyPct     = 50.0;                       // TP1 Close Qty %

sinput string sep5 = "=== Stop Loss ===";
input ENUM_SL_MODE     InpSLMode        = SL_SWING_LOW;              // Initial SL Mode
input double           InpFixedSLPct    = 5.0;                        // Fixed SL %
input int              InpSLLookback    = 10;                         // Swing Low Lookback Bars
input double           InpTrailActPct   = 10.0;                       // Trail Activation % (shift SL to EMA)

sinput string sep6 = "=== Re-entry ===";
input bool             InpEnableReentry = true;                       // Enable Re-entry After SL Hit

sinput string sep7 = "=== Lot Settings ===";
input ENUM_LOT_MODE    InpLotMode       = LOT_FIXED;                 // Lot Mode
input double           InpFixedLot      = 0.1;                        // Fixed Lot Size
input double           InpRiskPct       = 1.0;                        // Risk % of Balance

sinput string sep8 = "=== Display ===";
input bool             InpShowEMA       = true;                       // Plot 23 EMA Line
input bool             InpShowST        = true;                       // Plot SuperTrend Line
input bool             InpShowSignals   = true;                       // Plot Entry/Exit Arrows
input bool             InpShowDashboard = true;                       // Show P&L Dashboard

sinput string sep9 = "=== General ===";
input long             InpMagic         = 230523;                     // Magic Number
input string           InpComment       = "STFlatBO";                 // Order Comment

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CTrade g_Trade;                                                       //--- Trade object

// Manual EMA (23-period)
double g_EMA           = 0;                                           //--- EMA current value
bool   g_EMAInit       = false;                                       //--- EMA warmup done
double g_PrevEMA       = 0;                                           //--- Previous bar EMA
datetime g_PrevBarTime = 0;                                           //--- Previous bar time
int    g_LineCount     = 0;                                           //--- Line segment counter

// SuperTrend (manual ATR)
double g_STUpperBand   = 0;
double g_STLowerBand   = 0;
double g_SuperTrend    = 0;
int    g_STDir         = 0;                                           //--- 1=bullish, -1=bearish
double g_PrevSTUpper   = 0;
double g_PrevSTLower   = 0;
int    g_PrevSTDir     = 0;
bool   g_STInit        = false;
double g_ATR           = 0;
double g_SmoothedATR   = 0;
int    g_ATRBarCount   = 0;

// Previous bar data
double g_PrevClose     = 0;
double g_PrevHigh      = 0;
double g_PrevLow       = 0;
double g_PrevSTValue   = 0;                                           //--- Previous ST value for flat detect

// Flat detection state
bool   g_InWatchlist   = false;                                       //--- RED->GREEN shift occurred
int    g_FlatCount     = 0;                                           //--- Consecutive flat bars
double g_SwingHigh     = 0;                                           //--- Swing high during flat zone
double g_PrevSwingHigh = 0;                                           //--- Previous swing high for dual-res check
double g_BreakoutLevel = 0;                                           //--- Final breakout level

// Trade state
int    g_TradeState    = 0;                                           //--- 0=flat, 1=long
double g_EntryPrice    = 0;
double g_StopLoss      = 0;
double g_OriginalLots  = 0;
bool   g_TP1Hit        = false;
bool   g_SLTrailing    = false;                                       //--- SL shifted to 23 EMA
bool   g_ReentryMode   = false;                                       //--- Waiting for re-entry
double g_ReentryLevel  = 0;                                           //--- Wave high for re-entry

// Dashboard
#define DASH_PREFIX "STFBO_"
#define DASH_ROWS   16
#define DASH_COLS   2

// Stats
int    g_TotalTrades   = 0;
int    g_WinTrades     = 0;
int    g_LossTrades    = 0;
double g_GrossProfit   = 0;
double g_GrossLoss     = 0;
double g_TotalWinAmt   = 0;
double g_TotalLossAmt  = 0;
double g_MaxEquity     = 0;
double g_MaxDrawdown   = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpSTPeriod <= 0 || InpEMALen <= 0)
   {
      Print("Invalid parameters: STPeriod and EMALen must be > 0");
      return INIT_FAILED;
   }

   // Reset all state
   g_EMA = 0; g_PrevEMA = 0; g_EMAInit = false;
   g_PrevBarTime = 0; g_LineCount = 0;
   g_STInit = false; g_ATRBarCount = 0; g_SmoothedATR = 0;
   g_PrevClose = 0; g_PrevHigh = 0; g_PrevLow = 0; g_PrevSTValue = 0;
   g_InWatchlist = false; g_FlatCount = 0;
   g_SwingHigh = 0; g_PrevSwingHigh = 0; g_BreakoutLevel = 0;
   g_TradeState = 0; g_EntryPrice = 0; g_StopLoss = 0;
   g_TP1Hit = false; g_SLTrailing = false;
   g_ReentryMode = false; g_ReentryLevel = 0;

   g_Trade.SetExpertMagicNumber(InpMagic);
   g_Trade.SetDeviationInPoints(10);
   g_Trade.SetTypeFilling(ORDER_FILLING_FOK);

   g_MaxEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   LoadHistoricalStats();

   if(InpShowDashboard)
      CreateDashboard();

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, DASH_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Intra-bar SL check (every tick)
   if(g_TradeState == 1 && g_StopLoss > 0)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(bid <= g_StopLoss)
      {
         Print("SL HIT: bid=", bid, " SL=", g_StopLoss,
               g_SLTrailing ? " (trailing)" : " (initial)");

         // Setup re-entry if initial SL (not trailing EMA exit)
         double liveHigh = iHigh(_Symbol, PERIOD_CURRENT, 0);
         if(!g_SLTrailing && InpEnableReentry)
         {
            g_ReentryMode  = true;
            g_ReentryLevel = liveHigh;
         }
         CloseAllPositions("SL Hit");
      }
   }

   //--- Intra-bar TP check (every tick)
   if(g_TradeState == 1 && g_EntryPrice > 0)
   {
      double liveHigh = iHigh(_Symbol, PERIOD_CURRENT, 0);
      ProcessPartialTP(liveHigh);
   }

   //--- New bar logic only
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime) return;
   lastBarTime = currentBarTime;

   //--- Bar 1 = last closed candle
   double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);
   double highPrice  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double lowPrice   = iLow(_Symbol, PERIOD_CURRENT, 1);
   datetime barTime  = iTime(_Symbol, PERIOD_CURRENT, 1);

   //--- EMA warmup
   if(!g_EMAInit)
   {
      g_EMA     = closePrice;
      g_EMAInit = true;
      g_PrevClose = closePrice;
      g_PrevHigh  = highPrice;
      g_PrevLow   = lowPrice;
      return;
   }

   //--- Update 23 EMA
   double k = 2.0 / (InpEMALen + 1);
   g_EMA = closePrice * k + g_EMA * (1.0 - k);

   //--- Calculate SuperTrend
   CalcSuperTrend(highPrice, lowPrice, closePrice);

   //--- Sync trade state with broker
   SyncTradeState();

   //--- SuperTrend flat detection logic
   if(g_STInit)
   {
      // Detect RED -> GREEN color shift
      bool colorShift = (g_PrevSTDir == -1 && g_STDir == 1);

      if(colorShift)
      {
         g_InWatchlist   = true;
         g_FlatCount     = 0;
         g_SwingHigh     = 0;
         g_PrevSwingHigh = 0;
         g_BreakoutLevel = 0;
         Print("SuperTrend RED->GREEN shift: added to watchlist");
      }

      if(g_STDir == -1)  // went back to red
      {
         g_InWatchlist   = false;
         g_FlatCount     = 0;
         g_SwingHigh     = 0;
         g_PrevSwingHigh = 0;
         g_BreakoutLevel = 0;
      }

      // Detect flat: ST value barely changes
      if(g_InWatchlist && g_STDir == 1 && g_PrevSTValue > 0)
      {
         double changePct = MathAbs(g_SuperTrend - g_PrevSTValue) / g_PrevSTValue * 100.0;
         if(changePct < InpFlatTolPct)
         {
            g_FlatCount++;
            // Track swing high during flat period
            if(g_FlatCount == 1)
            {
               g_PrevSwingHigh = g_SwingHigh;
               g_SwingHigh     = highPrice;
            }
            else
            {
               if(highPrice > g_SwingHigh)
                  g_SwingHigh = highPrice;
            }
         }
         else
         {
            g_FlatCount = 0;
         }
      }

      // Determine breakout level (dual-resistance check)
      if(g_SwingHigh > 0)
      {
         g_BreakoutLevel = g_SwingHigh;
         if(g_PrevSwingHigh > 0)
         {
            double gapPct = MathAbs(g_PrevSwingHigh - g_SwingHigh) / g_SwingHigh * 100.0;
            if(gapPct <= InpDualResBuf)
               g_BreakoutLevel = MathMax(g_SwingHigh, g_PrevSwingHigh);
         }
      }

      g_PrevSTValue = g_SuperTrend;
   }

   //--- Entry conditions
   bool flatReady = g_InWatchlist && g_FlatCount >= InpMinFlatBars && g_BreakoutLevel > 0;
   bool buySignal = false;

   if(g_TradeState == 0 && !g_ReentryMode && flatReady)
   {
      // Breakout: close above swing high
      if(closePrice > g_BreakoutLevel && g_PrevClose <= g_BreakoutLevel)
      {
         double gapFromBO = (closePrice - g_BreakoutLevel) / g_BreakoutLevel * 100.0;
         if(gapFromBO <= InpRetestZonePct)
            buySignal = true;
      }
      // Retest entry: was too far above, now pulled back into zone
      else if(g_PrevClose > g_BreakoutLevel)
      {
         double prevGap = (g_PrevClose - g_BreakoutLevel) / g_BreakoutLevel * 100.0;
         double nowGap  = (closePrice - g_BreakoutLevel) / g_BreakoutLevel * 100.0;
         if(prevGap > InpRetestZonePct && nowGap >= 0 && nowGap <= InpRetestZonePct && closePrice > iOpen(_Symbol, PERIOD_CURRENT, 1))
            buySignal = true;
      }
   }

   // Re-entry signal after SL hit
   if(g_TradeState == 0 && g_ReentryMode && InpEnableReentry && g_ReentryLevel > 0)
   {
      if(closePrice > g_ReentryLevel && g_PrevClose <= g_ReentryLevel)
      {
         buySignal = true;
         Print("Re-entry signal: close=", closePrice, " > reentry level=", g_ReentryLevel);
      }
   }

   //--- Exit conditions (bar-close based)
   bool emaExit = false;
   if(g_TradeState == 1)
   {
      // 23 EMA break: red candle closes below EMA
      if(closePrice < g_EMA && g_PrevClose >= g_PrevEMA)
         emaExit = true;
   }

   //--- Execute exits
   // Target TP2 full close (checked on bar close for daily chart consistency)
   if(g_TradeState == 1 && g_EntryPrice > 0 && InpExitMode != EXIT_MOMENTUM)
   {
      double tp2Price = g_EntryPrice * (1.0 + InpTP2Pct / 100.0);
      if(highPrice >= tp2Price)
      {
         CloseAllPositions("TP2");
         if(InpShowSignals)
            DrawArrow(barTime, highPrice, false, clrAqua, "TP2");
         Print("TP2 hit: ", tp2Price);
      }
   }

   // EMA momentum exit
   if(emaExit && g_TradeState == 1 && (InpExitMode == EXIT_MOMENTUM || InpExitMode == EXIT_COMBINED))
   {
      CloseAllPositions("EMA Exit");
      if(InpShowSignals)
         DrawArrow(barTime, highPrice, false, clrMagenta, "EMA_EXIT");
      Print("23 EMA exit at ", closePrice);
   }

   //--- Execute entry
   if(buySignal && g_TradeState == 0)
   {
      OpenEntry(barTime, highPrice, lowPrice, closePrice);
   }

   //--- Trail SL activation: after X% gain, shift SL to 23 EMA
   if(g_TradeState == 1 && g_EntryPrice > 0 && !g_SLTrailing)
   {
      double gainPct = (closePrice - g_EntryPrice) / g_EntryPrice * 100.0;
      if(gainPct >= InpTrailActPct)
      {
         g_SLTrailing = true;
         g_StopLoss   = g_EMA;
         Print("SL shifted to 23 EMA trailing: new SL=", g_StopLoss);
      }
   }

   // Update trailing SL (EMA moves up)
   if(g_TradeState == 1 && g_SLTrailing && g_EMA > g_StopLoss)
      g_StopLoss = g_EMA;

   //--- Store previous bar data
   g_PrevClose = closePrice;
   g_PrevHigh  = highPrice;
   g_PrevLow   = lowPrice;
   g_PrevEMA   = g_EMA;

   //--- Draw EMA line
   if(InpShowEMA && g_PrevBarTime > 0)
   {
      string segName = DASH_PREFIX + "EMA_" + IntegerToString(g_LineCount);
      ObjectCreate(0, segName, OBJ_TREND, 0, g_PrevBarTime, g_PrevEMA, barTime, g_EMA);
      ObjectSetInteger(0, segName, OBJPROP_COLOR, clrOrange);
      ObjectSetInteger(0, segName, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, segName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, segName, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, segName, OBJPROP_BACK, true);
      g_LineCount++;
   }

   //--- Draw SuperTrend dots
   if(InpShowST && g_STInit)
   {
      string stName = DASH_PREFIX + "ST_" + IntegerToString(g_LineCount + 100000);
      color stColor = g_STDir == 1 ? clrLime : clrRed;
      ObjectCreate(0, stName, OBJ_ARROW, 0, barTime, g_SuperTrend);
      ObjectSetInteger(0, stName, OBJPROP_ARROWCODE, 159);
      ObjectSetInteger(0, stName, OBJPROP_COLOR, stColor);
      ObjectSetInteger(0, stName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, stName, OBJPROP_BACK, true);
   }

   //--- Draw breakout level line
   if(flatReady && g_BreakoutLevel > 0)
   {
      DrawHLine(DASH_PREFIX + "BO_LINE", g_BreakoutLevel, clrWhite, STYLE_DOT, 1);
   }
   else
   {
      ObjectDelete(0, DASH_PREFIX + "BO_LINE");
   }

   //--- Draw SL line
   if(g_TradeState == 1 && g_StopLoss > 0)
   {
      color slClr = g_SLTrailing ? clrOrange : clrRed;
      DrawHLine(DASH_PREFIX + "SL_LINE", g_StopLoss, slClr, STYLE_DASH, 1);
   }
   else
   {
      ObjectDelete(0, DASH_PREFIX + "SL_LINE");
   }

   //--- Draw TP lines
   if(g_TradeState == 1 && g_EntryPrice > 0 && InpExitMode != EXIT_MOMENTUM)
   {
      if(!g_TP1Hit)
         DrawHLine(DASH_PREFIX + "TP1_LINE", g_EntryPrice * (1.0 + InpTP1Pct / 100.0), clrLime, STYLE_DASH, 1);
      else
         ObjectDelete(0, DASH_PREFIX + "TP1_LINE");

      DrawHLine(DASH_PREFIX + "TP2_LINE", g_EntryPrice * (1.0 + InpTP2Pct / 100.0), clrAqua, STYLE_DASH, 1);
   }
   else
   {
      ObjectDelete(0, DASH_PREFIX + "TP1_LINE");
      ObjectDelete(0, DASH_PREFIX + "TP2_LINE");
   }

   g_PrevBarTime = barTime;

   //--- Update dashboard
   if(InpShowDashboard)
      UpdateDashboard();

   //--- Track equity / drawdown
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_MaxEquity) g_MaxEquity = equity;
   double dd = g_MaxEquity - equity;
   if(dd > g_MaxDrawdown) g_MaxDrawdown = dd;
}

//+------------------------------------------------------------------+
//| OnTrade - track completed trades                                 |
//+------------------------------------------------------------------+
void OnTrade()
{
   LoadHistoricalStats();
   if(InpShowDashboard)
      UpdateDashboard();
}

//+------------------------------------------------------------------+
//| Open a new long entry                                            |
//+------------------------------------------------------------------+
void OpenEntry(datetime barTime, double highPrice, double lowPrice, double closePrice)
{
   double lots = CalcLotSize();
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   if(g_Trade.Buy(lots, _Symbol, ask, 0, 0, InpComment + " Buy"))
   {
      g_TradeState   = 1;
      g_EntryPrice   = ask;
      g_OriginalLots = lots;
      g_TP1Hit       = false;
      g_SLTrailing   = false;
      g_ReentryMode  = false;
      g_ReentryLevel = 0;

      // Set initial SL
      if(InpSLMode == SL_SWING_LOW)
      {
         double swLow = lowPrice;
         for(int i = 2; i <= InpSLLookback; i++)
         {
            double lo = iLow(_Symbol, PERIOD_CURRENT, i);
            if(lo < swLow) swLow = lo;
         }
         g_StopLoss = swLow;
      }
      else
      {
         g_StopLoss = ask * (1.0 - InpFixedSLPct / 100.0);
      }

      Print("BUY opened @ ", ask, " SL=", g_StopLoss,
            " breakout level=", g_BreakoutLevel);

      if(InpShowSignals)
         DrawArrow(barTime, lowPrice, true, clrGreen, "BUY");
   }
   else
   {
      Print("BUY FAILED: retcode=", g_Trade.ResultRetcode(), " ", g_Trade.ResultComment());
   }
}

//+------------------------------------------------------------------+
//| Process Partial Take Profit (TP1 only — TP2 is full close)       |
//+------------------------------------------------------------------+
void ProcessPartialTP(double highPrice)
{
   if(g_TradeState != 1 || g_EntryPrice == 0) return;
   if(InpExitMode == EXIT_MOMENTUM) return;  // no targets in momentum mode

   double tp1Price = g_EntryPrice * (1.0 + InpTP1Pct / 100.0);

   if(!g_TP1Hit && highPrice >= tp1Price)
   {
      double closeLots = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0);
      if(closeLots > 0 && PartialClose(closeLots, "TP1"))
      {
         g_TP1Hit = true;
         Print("TP1 hit @ ", tp1Price, " closed ", closeLots, " lots");
      }
   }
}

//+------------------------------------------------------------------+
//| Sync trade state with actual open position                       |
//+------------------------------------------------------------------+
void SyncTradeState()
{
   bool hasPosition = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      hasPosition = true;
      break;
   }
   if(!hasPosition && g_TradeState != 0)
   {
      g_TradeState = 0;
      g_EntryPrice = 0;
      g_StopLoss   = 0;
      g_TP1Hit     = false;
      g_SLTrailing = false;
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size                                               |
//+------------------------------------------------------------------+
double CalcLotSize()
{
   if(InpLotMode == LOT_FIXED)
      return InpFixedLot;

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPct / 100.0;

   // Estimate SL in points for risk calc
   double slPoints = 0;
   if(InpSLMode == SL_FIXED_PCT)
      slPoints = SymbolInfoDouble(_Symbol, SYMBOL_ASK) * InpFixedSLPct / 100.0 / _Point;
   else
      slPoints = SymbolInfoDouble(_Symbol, SYMBOL_ASK) * 0.05 / _Point;  // ~5% estimate

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue == 0 || tickSize == 0) return InpFixedLot;

   double slMoney = (slPoints * _Point / tickSize) * tickValue;
   if(slMoney == 0) return InpFixedLot;

   double lot     = NormalizeDouble(riskMoney / slMoney, 2);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   lot = MathFloor(lot / stepLot) * stepLot;
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Partial close of position                                        |
//+------------------------------------------------------------------+
bool PartialClose(double lots, string comment)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      ulong ticket = PositionGetInteger(POSITION_TICKET);
      double posVol = PositionGetDouble(POSITION_VOLUME);

      if(lots >= posVol) lots = posVol;
      lots = NormalizeLots(lots);
      if(lots <= 0) return false;

      Print("Partial close [", comment, "] lots=", lots, " of ", posVol);
      return g_Trade.PositionClosePartial(ticket, lots, ULONG_MAX);
   }
   return false;
}

//+------------------------------------------------------------------+
//| Close all positions for this EA                                  |
//+------------------------------------------------------------------+
void CloseAllPositions(string comment)
{
   for(int attempt = 1; attempt <= 5; attempt++)
   {
      bool anyOpen = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
         anyOpen = true;
         ulong ticket = PositionGetInteger(POSITION_TICKET);
         double vol   = PositionGetDouble(POSITION_VOLUME);
         Print("CloseAll [", comment, "] attempt=", attempt,
               " ticket=", ticket, " vol=", vol);
         if(!g_Trade.PositionClose(ticket, ULONG_MAX))
            Print("  Close FAILED retcode=", g_Trade.ResultRetcode(),
                  " ", g_Trade.ResultComment());
         break;
      }
      if(!anyOpen) break;
   }
   g_TradeState = 0;
   g_EntryPrice = 0;
   g_StopLoss   = 0;
   g_SLTrailing = false;
}

//+------------------------------------------------------------------+
//| Normalize lots to valid volume                                   |
//+------------------------------------------------------------------+
double NormalizeLots(double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot == 0) return minLot;
   lots = MathFloor(lots / stepLot) * stepLot;
   if(lots < minLot) lots = 0;
   if(lots > maxLot) lots = maxLot;
   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Calculate SuperTrend (manual ATR-based)                          |
//+------------------------------------------------------------------+
void CalcSuperTrend(double highPrice, double lowPrice, double closePrice)
{
   g_ATRBarCount++;

   // True Range
   double tr;
   if(g_ATRBarCount == 1)
      tr = highPrice - lowPrice;
   else
      tr = MathMax(highPrice - lowPrice,
           MathMax(MathAbs(highPrice - g_PrevClose), MathAbs(lowPrice - g_PrevClose)));

   // ATR (RMA / Wilder smoothing)
   if(g_ATRBarCount <= InpSTPeriod)
   {
      g_SmoothedATR += tr;
      if(g_ATRBarCount == InpSTPeriod)
         g_ATR = g_SmoothedATR / InpSTPeriod;
      return;
   }
   else
   {
      g_ATR = (g_ATR * (InpSTPeriod - 1) + tr) / InpSTPeriod;
   }

   // SuperTrend bands
   double midPrice  = (highPrice + lowPrice) / 2.0;
   double upperBand = midPrice + InpSTMultiplier * g_ATR;
   double lowerBand = midPrice - InpSTMultiplier * g_ATR;

   // Carry forward bands
   if(!g_STInit)
   {
      g_STUpperBand = upperBand;
      g_STLowerBand = lowerBand;
      g_STDir       = closePrice > g_STUpperBand ? 1 : -1;
      g_SuperTrend  = g_STDir == 1 ? g_STLowerBand : g_STUpperBand;
      g_PrevSTValue = g_SuperTrend;
      g_STInit      = true;
   }
   else
   {
      // Lower band: only move up
      if(lowerBand > g_PrevSTLower || g_PrevClose < g_PrevSTLower)
         g_STLowerBand = lowerBand;
      else
         g_STLowerBand = g_PrevSTLower;

      // Upper band: only move down
      if(upperBand < g_PrevSTUpper || g_PrevClose > g_PrevSTUpper)
         g_STUpperBand = upperBand;
      else
         g_STUpperBand = g_PrevSTUpper;

      // Direction
      g_PrevSTDir = g_STDir;
      if(g_STDir == 1)
         g_STDir = closePrice < g_STLowerBand ? -1 : 1;
      else
         g_STDir = closePrice > g_STUpperBand ? 1 : -1;

      g_SuperTrend = g_STDir == 1 ? g_STLowerBand : g_STUpperBand;
   }

   g_PrevSTUpper = g_STUpperBand;
   g_PrevSTLower = g_STLowerBand;
}

//+------------------------------------------------------------------+
//| Load historical stats from account deal history                  |
//+------------------------------------------------------------------+
void LoadHistoricalStats()
{
   g_TotalTrades = 0; g_WinTrades = 0; g_LossTrades = 0;
   g_GrossProfit = 0; g_GrossLoss = 0;
   g_TotalWinAmt = 0; g_TotalLossAmt = 0;

   HistorySelect(0, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT &&
         HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT_BY) continue;

      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                    + HistoryDealGetDouble(ticket, DEAL_SWAP)
                    + HistoryDealGetDouble(ticket, DEAL_COMMISSION);

      g_TotalTrades++;
      if(profit >= 0)
      {
         g_WinTrades++;
         g_GrossProfit += profit;
         g_TotalWinAmt += profit;
      }
      else
      {
         g_LossTrades++;
         g_GrossLoss += profit;
         g_TotalLossAmt += MathAbs(profit);
      }
   }
}

//+------------------------------------------------------------------+
//| Draw entry/exit arrow on chart                                   |
//+------------------------------------------------------------------+
void DrawArrow(datetime time, double price, bool isUp, color clr, string label)
{
   string name = DASH_PREFIX + "ARR_" + TimeToString(time) + "_" + label;
   int code = isUp ? 233 : 234;
   ObjectCreate(0, name, OBJ_ARROW, 0, time, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, label + " @ " + DoubleToString(price, _Digits));
}

//+------------------------------------------------------------------+
//| Draw horizontal line                                             |
//+------------------------------------------------------------------+
void DrawHLine(string name, double price, color clr, ENUM_LINE_STYLE style, int width)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

//+------------------------------------------------------------------+
//| Create Dashboard Table                                           |
//+------------------------------------------------------------------+
void CreateDashboard()
{
   int x = 10, y = 30;
   int cellW = 140, cellH = 20;
   int fontSize = 8;

   string bgName = DASH_PREFIX + "BG";
   ObjectCreate(0, bgName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bgName, OBJPROP_XDISTANCE, x - 5);
   ObjectSetInteger(0, bgName, OBJPROP_YDISTANCE, y - 5);
   ObjectSetInteger(0, bgName, OBJPROP_XSIZE, cellW * 2 + 15);
   ObjectSetInteger(0, bgName, OBJPROP_YSIZE, cellH * DASH_ROWS + 15);
   ObjectSetInteger(0, bgName, OBJPROP_BGCOLOR, C'20,20,30');
   ObjectSetInteger(0, bgName, OBJPROP_BORDER_COLOR, clrDimGray);
   ObjectSetInteger(0, bgName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, bgName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bgName, OBJPROP_BACK, false);

   CreateLabel(DASH_PREFIX + "TITLE", x + cellW / 2, y, "ST Flat Breakout", 10, clrDodgerBlue);

   string labels[] = {"", "Net Profit", "Open P&L", "Gross Profit", "Gross Loss",
                       "Total Trades", "Win / Loss", "Win Rate", "Profit Factor",
                       "Avg Win", "Avg Loss", "Avg R:R", "Max Drawdown",
                       "Flat Days", "BO Level", "Status"};

   for(int r = 1; r < DASH_ROWS; r++)
   {
      string lblName = DASH_PREFIX + "LBL_" + IntegerToString(r);
      CreateLabel(lblName, x, y + r * cellH, labels[r], fontSize, clrSilver);

      string valName = DASH_PREFIX + "VAL_" + IntegerToString(r);
      CreateLabel(valName, x + cellW + 10, y + r * cellH, "-", fontSize, clrWhite);
   }
}

//+------------------------------------------------------------------+
//| Create text label object                                         |
//+------------------------------------------------------------------+
void CreateLabel(string name, int x, int y, string text, int fontSize, color clr)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
}

//+------------------------------------------------------------------+
//| Update Dashboard Values                                          |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   double netProfit    = g_GrossProfit + g_GrossLoss;
   double winRate      = g_TotalTrades > 0 ? (double)g_WinTrades / g_TotalTrades * 100.0 : 0;
   double profitFactor = g_TotalLossAmt > 0 ? g_GrossProfit / g_TotalLossAmt : 0;
   double avgWin       = g_WinTrades > 0 ? g_TotalWinAmt / g_WinTrades : 0;
   double avgLoss      = g_LossTrades > 0 ? g_TotalLossAmt / g_LossTrades : 0;
   double avgRR        = avgLoss > 0 ? avgWin / avgLoss : 0;
   double initBal      = AccountInfoDouble(ACCOUNT_BALANCE) - netProfit;
   double netProfitPct = initBal > 0 ? netProfit / initBal * 100.0 : 0;

   double openPnL = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      openPnL += PositionGetDouble(POSITION_PROFIT)
               + PositionGetDouble(POSITION_SWAP);
   }

   double maxDDPct = initBal > 0 ? g_MaxDrawdown / initBal * 100.0 : 0;

   color netClr  = netProfit >= 0 ? clrLime : clrRed;
   color openClr = openPnL >= 0 ? clrLime : clrRed;
   color wrClr   = winRate >= 50 ? clrLime : clrRed;
   color pfClr   = profitFactor >= 1.5 ? clrLime : (profitFactor >= 1.0 ? clrYellow : clrRed);
   color ddClr   = maxDDPct <= 10 ? clrLime : (maxDDPct <= 20 ? clrYellow : clrRed);
   color rrClr   = avgRR >= 2 ? clrLime : (avgRR >= 1 ? clrYellow : clrRed);

   SetDashValue(1,  DoubleToString(netProfit, 2) + " (" + DoubleToString(netProfitPct, 1) + "%)", netClr);
   SetDashValue(2,  DoubleToString(openPnL, 2), openClr);
   SetDashValue(3,  DoubleToString(g_GrossProfit, 2), clrLime);
   SetDashValue(4,  DoubleToString(MathAbs(g_GrossLoss), 2), clrRed);
   SetDashValue(5,  IntegerToString(g_TotalTrades), clrWhite);
   SetDashValue(6,  IntegerToString(g_WinTrades) + " / " + IntegerToString(g_LossTrades), clrWhite);
   SetDashValue(7,  DoubleToString(winRate, 1) + "%", wrClr);
   SetDashValue(8,  DoubleToString(profitFactor, 2), pfClr);
   SetDashValue(9,  DoubleToString(avgWin, 2), clrLime);
   SetDashValue(10, DoubleToString(avgLoss, 2), clrRed);
   SetDashValue(11, DoubleToString(avgRR, 2), rrClr);
   SetDashValue(12, DoubleToString(g_MaxDrawdown, 2) + " (" + DoubleToString(maxDDPct, 1) + "%)", ddClr);
   SetDashValue(13, IntegerToString(g_FlatCount), g_FlatCount >= InpMinFlatBars ? clrLime : clrYellow);
   SetDashValue(14, g_BreakoutLevel > 0 ? DoubleToString(g_BreakoutLevel, _Digits) : "-", clrWhite);

   // Status line
   string status;
   color  stClr;
   if(g_TradeState == 1)
   { status = "LONG"; stClr = clrLime; }
   else if(g_ReentryMode)
   { status = "RE-ENTRY WAIT"; stClr = clrAqua; }
   else if(g_FlatCount >= InpMinFlatBars && g_BreakoutLevel > 0)
   { status = "READY"; stClr = clrYellow; }
   else if(g_InWatchlist)
   { status = "WATCHING"; stClr = clrSilver; }
   else
   { status = "SCANNING"; stClr = clrGray; }

   SetDashValue(15, status, stClr);

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Set dashboard value cell                                         |
//+------------------------------------------------------------------+
void SetDashValue(int row, string text, color clr)
{
   string name = DASH_PREFIX + "VAL_" + IntegerToString(row);
   if(ObjectFind(0, name) >= 0)
   {
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   }
}
//+------------------------------------------------------------------+
