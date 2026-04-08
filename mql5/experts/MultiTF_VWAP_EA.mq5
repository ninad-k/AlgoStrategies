//+------------------------------------------------------------------+
//|                                        MultiTF_VWAP_EA.mq5      |
//|                  Multi-Timeframe VWAP Strategy                   |
//|                                                                  |
//|  Concept: 4 VWAP periods plotted across timeframes               |
//|    Daily  VWAP  → best on 5-min  chart (intraday)                |
//|    Weekly VWAP  → best on 1-hour chart (swing)                   |
//|    Monthly VWAP → best on 4-hour chart (positional)              |
//|    Yearly VWAP  → best on Daily  chart (long-term positional)    |
//|                                                                  |
//|  Signal logic:                                                   |
//|    • Price above selected VWAPs → Bullish bias (Long only)       |
//|    • Price below selected VWAPs → Bearish bias (Short only)      |
//|    • Best entries: price pulls back near VWAP then bounces       |
//|    • Strongest signal: ALL active VWAPs aligned                  |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.10"
#property description "Multi-Timeframe VWAP Strategy (Daily/Weekly/Monthly/Yearly)\nv1.10: Added EMA/ATR/Candle/Slope/Session filters"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

CTrade        g_trade;
CPositionInfo g_pos;

//============================================================
//  ENUMERATIONS
//============================================================
enum ENUM_SIGNAL_TYPE
  {
   SIGNAL_VWAP_CROSS,        // Price crosses VWAP
   SIGNAL_VWAP_BOUNCE,       // Candle bounces near VWAP in trend direction
  };

enum ENUM_ALIGNMENT_MODE
  {
   ALIGN_ALL,                // ALL active VWAPs must be aligned
   ALIGN_MAJORITY,           // Majority of active VWAPs aligned
   ALIGN_ANY,                // At least one VWAP aligned
  };

//============================================================
//  INPUTS — DISPLAY
//============================================================
input group "━━━ VWAP Display ━━━"
input bool             InpPlotDaily      = false;            // Plot Daily VWAP
input bool             InpPlotWeekly     = true;             // Plot Weekly VWAP
input bool             InpPlotMonthly    = true;             // Plot Monthly VWAP
input bool             InpPlotYearly     = true;             // Plot Yearly VWAP
input color            InpColorDaily     = clrDeepSkyBlue;   // Daily VWAP Colour
input color            InpColorWeekly    = clrYellow;        // Weekly VWAP Colour
input color            InpColorMonthly   = clrOrange;        // Monthly VWAP Colour
input color            InpColorYearly    = clrMagenta;       // Yearly VWAP Colour
input int              InpLineWidth      = 2;                // Line Width (1–5)
input ENUM_LINE_STYLE  InpLineStyle      = STYLE_SOLID;      // Line Style

//============================================================
//  INPUTS — STRATEGY
//============================================================
input group "━━━ Strategy: VWAP Selection ━━━"
input bool             InpUseDaily       = false;  // Use Daily VWAP in signals
input bool             InpUseWeekly      = true;   // Use Weekly VWAP in signals
input bool             InpUseMonthly     = true;   // Use Monthly VWAP in signals
input bool             InpUseYearly      = true;   // Use Yearly VWAP in signals

input group "━━━ Strategy: Entry Logic ━━━"
input ENUM_SIGNAL_TYPE InpSignalType     = SIGNAL_VWAP_BOUNCE;  // Signal Type
input ENUM_ALIGNMENT_MODE InpAlignment   = ALIGN_ALL;           // VWAP Alignment Required
input double           InpProximityPct   = 0.5;   // Max % distance from VWAP for entry (0 = disabled)
input int              InpConfirmBars    = 1;      // Bars price must stay on same side of VWAP
input bool             InpAllowLong      = true;   // Allow Long Trades
input bool             InpAllowShort     = true;   // Allow Short Trades

input group "━━━ Filter: EMA Trend ━━━"
input bool             InpUseEMA         = true;   // Enable EMA Trend Filter
input int              InpEMAPeriod      = 50;     // EMA Period
input ENUM_TIMEFRAMES  InpEMATF          = PERIOD_CURRENT; // EMA Timeframe (CURRENT = chart TF)

input group "━━━ Filter: ATR Volatility ━━━"
input bool             InpUseATR         = true;   // Enable ATR Filter
input int              InpATRPeriod      = 14;     // ATR Period
input double           InpATRMinMult     = 0.3;    // Min ATR multiplier (skip dead market)
input double           InpATRMaxMult     = 2.5;    // Max ATR multiplier (skip chaos)

input group "━━━ Filter: Candle Strength ━━━"
input bool             InpUseCandleFilter = true;  // Enable Candle Body Filter
input double           InpMinBodyPct     = 40.0;   // Min candle body % of total range (0–100)

input group "━━━ Filter: VWAP Slope ━━━"
input bool             InpUseSlopeFilter = true;   // Enable VWAP Slope Filter
input int              InpSlopeLookback  = 3;      // Bars to measure VWAP direction

input group "━━━ Filter: Session Time ━━━"
input bool             InpUseSession     = false;  // Enable Session Filter
input int              InpSessionStartH  = 9;      // Session Start Hour (server time)
input int              InpSessionStartM  = 0;      // Session Start Minute
input int              InpSessionEndH    = 17;     // Session End Hour
input int              InpSessionEndM    = 0;      // Session End Minute

input group "━━━ Trade Management ━━━"
input double           InpLotSize        = 0.1;    // Lot Size
input int              InpSLPips         = 50;     // Stop Loss (pips)
input int              InpTPPips         = 150;    // Take Profit (pips, 0 = off)
input bool             InpTrailingStop   = false;  // Enable Trailing Stop
input int              InpTrailPips      = 30;     // Trailing Distance (pips)
input int              InpTrailStep      = 10;     // Trailing Step (pips)
input int              InpMaxPositions   = 1;      // Max Open Positions
input int              InpMagic          = 20240601; // Magic Number

//============================================================
//  GLOBALS
//============================================================
double   g_vwap[4];           // 0=Daily, 1=Weekly, 2=Monthly, 3=Yearly
double   g_prevVwap[4];      // previous-bar VWAP for slope calculation
string   g_objNames[4]    = {"MVWAP_Daily","MVWAP_Weekly","MVWAP_Monthly","MVWAP_Yearly"};
color    g_colors[4];
bool     g_plotFlags[4];
bool     g_useFlags[4];
string   g_labels[4]      = {"Daily","Weekly","Monthly","Yearly"};
datetime g_lastBar        = 0;
double   g_pipSize;

// Indicator handles for filters
int      g_emaHandle      = INVALID_HANDLE;
int      g_atrHandle      = INVALID_HANDLE;
double   g_atrAvg         = 0.0;  // running average ATR for baseline

//============================================================
//  INIT / DEINIT
//============================================================
int OnInit()
  {
   // Store per-index settings for easy array access
   g_plotFlags[0] = InpPlotDaily;    g_plotFlags[1] = InpPlotWeekly;
   g_plotFlags[2] = InpPlotMonthly;  g_plotFlags[3] = InpPlotYearly;
   g_useFlags[0]  = InpUseDaily;     g_useFlags[1]  = InpUseWeekly;
   g_useFlags[2]  = InpUseMonthly;   g_useFlags[3]  = InpUseYearly;
   g_colors[0]    = InpColorDaily;   g_colors[1]    = InpColorWeekly;
   g_colors[2]    = InpColorMonthly; g_colors[3]    = InpColorYearly;

   // Pip size: 10 points for 5-digit brokers, 1 point for 2-digit (JPY etc.)
   g_pipSize = (_Digits == 3 || _Digits == 5) ? _Point * 10.0 : _Point;

   // Initialize previous VWAP array
   ArrayInitialize(g_prevVwap, 0.0);

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);

   // Create indicator handles
   ENUM_TIMEFRAMES emaTF = (InpEMATF == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : InpEMATF;
   if(InpUseEMA)
     {
      g_emaHandle = iMA(_Symbol, emaTF, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(g_emaHandle == INVALID_HANDLE)
        { Print("EMA handle creation failed"); return INIT_FAILED; }
     }
   if(InpUseATR)
     {
      g_atrHandle = iATR(_Symbol, _Period, InpATRPeriod);
      if(g_atrHandle == INVALID_HANDLE)
        { Print("ATR handle creation failed"); return INIT_FAILED; }
     }

   DeleteLines();
   Print("MultiTF VWAP EA v1.10 — ", _Symbol, " ", EnumToString((ENUM_TIMEFRAMES)_Period));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_emaHandle != INVALID_HANDLE) IndicatorRelease(g_emaHandle);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   DeleteLines();
  }

//============================================================
//  TICK
//============================================================
void OnTick()
  {
   // Trailing stop management on every tick
   if(InpTrailingStop)
      ManageTrailing();

   // Process on new bar only
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == g_lastBar)
      return;
   g_lastBar = barTime;

   // Store previous VWAPs for slope calculation
   for(int i = 0; i < 4; i++)
      g_prevVwap[i] = g_vwap[i];

   // Recalculate all VWAPs
   CalcAllVWAPs();

   // Update chart lines
   DrawLines();

   // Trade signals
   if(CountPositions() < InpMaxPositions)
      CheckSignals();
  }

//============================================================
//  VWAP CALCULATION
//============================================================

// Returns the datetime for the start of the period containing 'now'
// periodType: 0=Daily, 1=Weekly, 2=Monthly, 3=Yearly
datetime PeriodStart(int periodType, datetime now)
  {
   MqlDateTime dt;
   TimeToStruct(now, dt);

   switch(periodType)
     {
      case 0: // Day starts at 00:00
        dt.hour = 0; dt.min = 0; dt.sec = 0;
        return StructToTime(dt);

      case 1: // Week starts on Monday
        {
         dt.hour = 0; dt.min = 0; dt.sec = 0;
         datetime dayStart = StructToTime(dt);
         int dow = dt.day_of_week; // 0=Sun
         if(dow == 0) dow = 7;    // treat Sunday as 7
         return dayStart - (datetime)(dow - 1) * 86400;
        }

      case 2: // Month starts on 1st
        dt.day = 1; dt.hour = 0; dt.min = 0; dt.sec = 0;
        return StructToTime(dt);

      case 3: // Year starts on Jan 1st
        dt.mon = 1; dt.day = 1; dt.hour = 0; dt.min = 0; dt.sec = 0;
        return StructToTime(dt);
     }
   return now;
  }

// Choose the data timeframe used for VWAP calculation
// Lower TF gives more granular VWAP; match to recommended pairing
ENUM_TIMEFRAMES CalcTF(int periodType)
  {
   // Daily  → M5  (or current TF if coarser)
   // Weekly → H1
   // Monthly→ H4
   // Yearly → D1
   static const ENUM_TIMEFRAMES tfs[4] = {PERIOD_M5, PERIOD_H1, PERIOD_H4, PERIOD_D1};
   ENUM_TIMEFRAMES desired = tfs[periodType];
   // Never use a TF finer than the chart's current TF
   if((int)desired < (int)_Period)
      return (ENUM_TIMEFRAMES)_Period;
   return desired;
  }

double CalcVWAP(int periodType)
  {
   datetime now   = TimeCurrent();
   datetime start = PeriodStart(periodType, now);
   ENUM_TIMEFRAMES tf = CalcTF(periodType);

   MqlRates rates[];
   int copied = CopyRates(_Symbol, tf, start, now, rates);
   if(copied < 1)
      return 0.0;

   double sumTPV = 0.0, sumVol = 0.0;
   for(int i = 0; i < copied; i++)
     {
      double tp  = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      double vol = (double)rates[i].tick_volume;
      if(vol < 1.0) vol = 1.0;
      sumTPV += tp * vol;
      sumVol += vol;
     }
   return (sumVol > 0) ? sumTPV / sumVol : 0.0;
  }

void CalcAllVWAPs()
  {
   for(int i = 0; i < 4; i++)
      g_vwap[i] = CalcVWAP(i);
  }

//============================================================
//  CHART LINES
//============================================================
void DrawLines()
  {
   for(int i = 0; i < 4; i++)
     {
      if(!g_plotFlags[i] || g_vwap[i] <= 0.0)
        {
         // Hide if disabled or not calculated
         if(ObjectFind(0, g_objNames[i]) >= 0)
            ObjectDelete(0, g_objNames[i]);
         continue;
        }

      string tooltip = g_labels[i] + " VWAP: " + DoubleToString(g_vwap[i], _Digits);

      if(ObjectFind(0, g_objNames[i]) < 0)
         ObjectCreate(0, g_objNames[i], OBJ_HLINE, 0, 0, g_vwap[i]);

      ObjectSetDouble(0,  g_objNames[i], OBJPROP_PRICE,     g_vwap[i]);
      ObjectSetInteger(0, g_objNames[i], OBJPROP_COLOR,     g_colors[i]);
      ObjectSetInteger(0, g_objNames[i], OBJPROP_WIDTH,     InpLineWidth);
      ObjectSetInteger(0, g_objNames[i], OBJPROP_STYLE,     InpLineStyle);
      ObjectSetString(0,  g_objNames[i], OBJPROP_TOOLTIP,   tooltip);
      ObjectSetInteger(0, g_objNames[i], OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0, g_objNames[i], OBJPROP_BACK,      true);
     }
   ChartRedraw(0);
  }

void DeleteLines()
  {
   for(int i = 0; i < 4; i++)
      ObjectDelete(0, g_objNames[i]);
  }

//============================================================
//  QUALITY FILTERS
//============================================================

// Filter 1: EMA Trend — price must be on correct side of EMA
bool PassEMAFilter(double price, bool isLong)
  {
   if(!InpUseEMA || g_emaHandle == INVALID_HANDLE)
      return true;

   double ema[];
   if(CopyBuffer(g_emaHandle, 0, 1, 1, ema) < 1)
      return true; // allow trade if data unavailable

   if(isLong  && price < ema[0]) return false; // price below EMA → no long
   if(!isLong && price > ema[0]) return false; // price above EMA → no short
   return true;
  }

// Filter 2: ATR Volatility — skip dead or chaotic markets
bool PassATRFilter()
  {
   if(!InpUseATR || g_atrHandle == INVALID_HANDLE)
      return true;

   double atr[];
   double atrHist[];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) < 1)
      return true;
   // Get longer ATR history for baseline average
   int histBars = 50;
   if(CopyBuffer(g_atrHandle, 0, 1, histBars, atrHist) < histBars)
      return true;

   double sum = 0;
   for(int i = 0; i < histBars; i++)
      sum += atrHist[i];
   double avgATR = sum / histBars;

   if(avgATR <= 0) return true;

   double ratio = atr[0] / avgATR;
   if(ratio < InpATRMinMult) return false; // too quiet
   if(ratio > InpATRMaxMult) return false; // too volatile
   return true;
  }

// Filter 3: Candle Strength — signal candle must have strong body
bool PassCandleFilter()
  {
   if(!InpUseCandleFilter)
      return true;

   double h = iHigh(_Symbol,  _Period, 1);
   double l = iLow(_Symbol,   _Period, 1);
   double o = iOpen(_Symbol,  _Period, 1);
   double c = iClose(_Symbol, _Period, 1);

   double range = h - l;
   if(range <= 0) return false;

   double bodyPct = MathAbs(c - o) / range * 100.0;
   return (bodyPct >= InpMinBodyPct);
  }

// Filter 4: VWAP Slope — active VWAPs should trend in trade direction
bool PassSlopeFilter(bool isLong)
  {
   if(!InpUseSlopeFilter)
      return true;

   // Check that at least one active VWAP is sloping in the right direction
   bool anyCorrectSlope = false;
   for(int i = 0; i < 4; i++)
     {
      if(!g_useFlags[i] || g_vwap[i] <= 0 || g_prevVwap[i] <= 0)
         continue;

      double slope = g_vwap[i] - g_prevVwap[i];
      if(isLong  && slope > 0) anyCorrectSlope = true;
      if(!isLong && slope < 0) anyCorrectSlope = true;
     }
   return anyCorrectSlope;
  }

// Filter 5: Session Time — only trade during active hours
bool PassSessionFilter()
  {
   if(!InpUseSession)
      return true;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int nowMinutes   = dt.hour * 60 + dt.min;
   int startMinutes = InpSessionStartH * 60 + InpSessionStartM;
   int endMinutes   = InpSessionEndH   * 60 + InpSessionEndM;

   if(startMinutes < endMinutes)
      return (nowMinutes >= startMinutes && nowMinutes < endMinutes);
   else // overnight session
      return (nowMinutes >= startMinutes || nowMinutes < endMinutes);
  }

//============================================================
//  SIGNAL LOGIC
//============================================================
void CheckSignals()
  {
   // ── Session filter first (cheapest check) ─────────────────
   if(!PassSessionFilter())
      return;

   // ── ATR filter (skip dead / chaotic market) ───────────────
   if(!PassATRFilter())
      return;

   // ── Collect active VWAP values ────────────────────────────
   double active[];
   for(int i = 0; i < 4; i++)
     {
      if(g_useFlags[i] && g_vwap[i] > 0.0)
        {
         int sz = ArraySize(active);
         ArrayResize(active, sz + 1);
         active[sz] = g_vwap[i];
        }
     }
   if(ArraySize(active) == 0)
      return;

   double close1 = iClose(_Symbol, _Period, 1); // last closed bar
   double close2 = iClose(_Symbol, _Period, 2);
   double open1  = iOpen(_Symbol,  _Period, 1);

   // Count VWAPs above / below price
   int aboveCnt = 0, belowCnt = 0;
   for(int i = 0; i < ArraySize(active); i++)
     {
      if(close1 > active[i]) aboveCnt++;
      else                   belowCnt++;
     }
   int total = ArraySize(active);

   // Determine bias according to alignment mode
   bool longBias  = false;
   bool shortBias = false;
   switch(InpAlignment)
     {
      case ALIGN_ALL:
         longBias  = (aboveCnt == total);
         shortBias = (belowCnt == total);
         break;
      case ALIGN_MAJORITY:
         longBias  = (aboveCnt > belowCnt);
         shortBias = (belowCnt > aboveCnt);
         break;
      case ALIGN_ANY:
         longBias  = (aboveCnt > 0);
         shortBias = (belowCnt > 0);
         break;
     }

   if(!longBias && !shortBias)
      return;

   // ── EMA trend filter ──────────────────────────────────────
   if(longBias  && !PassEMAFilter(close1, true))  longBias  = false;
   if(shortBias && !PassEMAFilter(close1, false)) shortBias = false;
   if(!longBias && !shortBias) return;

   // ── VWAP slope filter ─────────────────────────────────────
   if(longBias  && !PassSlopeFilter(true))  longBias  = false;
   if(shortBias && !PassSlopeFilter(false)) shortBias = false;
   if(!longBias && !shortBias) return;

   // ── Candle strength filter ────────────────────────────────
   if(!PassCandleFilter())
      return;

   // ── Proximity filter — skip if too far from nearest VWAP ─
   if(InpProximityPct > 0.0 && close1 > 0.0)
     {
      double minDistPct = DBL_MAX;
      for(int i = 0; i < ArraySize(active); i++)
        {
         double pct = MathAbs(close1 - active[i]) / active[i] * 100.0;
         if(pct < minDistPct) minDistPct = pct;
        }
      if(minDistPct > InpProximityPct)
         return;
     }

   // ── Confirmation bars ─────────────────────────────────────
   if(InpConfirmBars > 1)
     {
      bool confirmLong  = true;
      bool confirmShort = true;
      for(int b = 1; b <= InpConfirmBars; b++)
        {
         double c = iClose(_Symbol, _Period, b);
         for(int i = 0; i < ArraySize(active); i++)
           {
            if(c <= active[i]) confirmLong  = false;
            if(c >= active[i]) confirmShort = false;
           }
        }
      if(longBias  && !confirmLong)  return;
      if(shortBias && !confirmShort) return;
     }

   // ── Signal: Price Crossover ──────────────────────────────────
   if(InpSignalType == SIGNAL_VWAP_CROSS)
     {
      bool crossUp   = false;
      bool crossDown = false;
      for(int i = 0; i < ArraySize(active); i++)
        {
         if(close2 < active[i] && close1 > active[i]) crossUp   = true;
         if(close2 > active[i] && close1 < active[i]) crossDown = true;
        }
      if(InpAllowLong  && longBias  && crossUp)   OpenTrade(ORDER_TYPE_BUY);
      if(InpAllowShort && shortBias && crossDown)  OpenTrade(ORDER_TYPE_SELL);
     }
   // ── Signal: Bounce Near VWAP ─────────────────────────────────
   else if(InpSignalType == SIGNAL_VWAP_BOUNCE)
     {
      bool bullCandle = (close1 > open1);
      bool bearCandle = (close1 < open1);

      if(InpAllowLong  && longBias  && bullCandle) OpenTrade(ORDER_TYPE_BUY);
      if(InpAllowShort && shortBias && bearCandle) OpenTrade(ORDER_TYPE_SELL);
     }
  }

//============================================================
//  TRADE EXECUTION
//============================================================
void OpenTrade(ENUM_ORDER_TYPE type)
  {
   double slDist = InpSLPips * g_pipSize;
   double tpDist = InpTPPips * g_pipSize;

   double price, sl, tp;

   if(type == ORDER_TYPE_BUY)
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      sl    = NormalizeDouble(price - slDist, _Digits);
      tp    = (InpTPPips > 0) ? NormalizeDouble(price + tpDist, _Digits) : 0.0;
      if(!g_trade.Buy(InpLotSize, _Symbol, price, sl, tp, "VWAP Long"))
         Print("Buy failed: ", g_trade.ResultRetcodeDescription());
     }
   else
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl    = NormalizeDouble(price + slDist, _Digits);
      tp    = (InpTPPips > 0) ? NormalizeDouble(price - tpDist, _Digits) : 0.0;
      if(!g_trade.Sell(InpLotSize, _Symbol, price, sl, tp, "VWAP Short"))
         Print("Sell failed: ", g_trade.ResultRetcodeDescription());
     }
  }

//============================================================
//  TRAILING STOP
//============================================================
void ManageTrailing()
  {
   double trailDist = InpTrailPips * g_pipSize;
   double trailStep = InpTrailStep * g_pipSize;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol || g_pos.Magic() != InpMagic) continue;

      double curSL = g_pos.StopLoss();

      if(g_pos.PositionType() == POSITION_TYPE_BUY)
        {
         double bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double newSL = NormalizeDouble(bid - trailDist, _Digits);
         if(newSL > curSL + trailStep)
            g_trade.PositionModify(g_pos.Ticket(), newSL, g_pos.TakeProfit());
        }
      else
        {
         double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double newSL = NormalizeDouble(ask + trailDist, _Digits);
         if(curSL == 0.0 || newSL < curSL - trailStep)
            g_trade.PositionModify(g_pos.Ticket(), newSL, g_pos.TakeProfit());
        }
     }
  }

//============================================================
//  HELPERS
//============================================================
int CountPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(g_pos.SelectByIndex(i) &&
         g_pos.Symbol() == _Symbol &&
         g_pos.Magic()  == InpMagic)
         n++;
     }
   return n;
  }
//+------------------------------------------------------------------+
