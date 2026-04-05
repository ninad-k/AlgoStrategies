//+------------------------------------------------------------------+
//|                                        SmartMoneyConcepts_EA.mq5 |
//|        Smart Money Concepts Strategy: BOS/CHoCH + OB + FVG       |
//|        Entry: OB retest with structure confirmation               |
//|        Targets: 1.5R (50%), 2.5R (25%), 3.5R (25%)               |
//|        Optimized for Forex M15                                    |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                  |
//+------------------------------------------------------------------+
input group "=== SMC Settings ==="
input int             InpSwingLength     = 10;           // Swing Length (bars)
input bool            InpRequireFVG      = false;        // Require FVG confluence
input bool            InpOnlyCHoCH       = false;        // Only trade CHoCH (reversals)
input int             InpMaxOB           = 5;            // Max active Order Blocks per side

input group "=== Risk Management ==="
input double          InpRiskPercent     = 1.5;          // Risk % per trade
input double          InpSLPaddingATR    = 0.5;          // SL padding (x ATR)
input double          InpTP1_R           = 1.5;          // TP1 R-multiple
input double          InpTP2_R           = 2.5;          // TP2 R-multiple
input double          InpTP3_R           = 3.5;          // TP3 R-multiple
input double          InpTP1_Pct         = 50;           // TP1 close %
input double          InpTP2_Pct         = 25;           // TP2 close %
input double          InpTP3_Pct         = 25;           // TP3 close %

input group "=== Filters ==="
input int             InpMaxSpreadPts    = 30;           // Max spread (points)
input int             InpMaxDailyTrades  = 3;            // Max trades per day
input double          InpMaxCandleATR    = 2.0;          // Max candle size (x ATR)
input int             InpMinBarsCooldown = 5;            // Min bars between trades
input bool            InpUseHTFFilter    = false;        // Use H1 trend filter

input group "=== Session (Server Time) ==="
input int             InpSessionStartHr  = 2;            // Session start hour
input int             InpSessionEndHr    = 20;           // Session end hour
input int             InpForceExitHr     = 23;           // Force exit hour
input int             InpForceExitMin    = 0;            // Force exit minute

input group "=== General ==="
input int             InpMagic           = 20250405;     // Magic Number
input double          InpSlippage        = 3;            // Max slippage (points)

//+------------------------------------------------------------------+
//| STRUCTURES                                                        |
//+------------------------------------------------------------------+
struct SOrderBlock
{
   double   top;
   double   bottom;
   int      barIndex;       // bar index when OB was created
   int      bias;           // 1=bullish, -1=bearish
   bool     active;
   bool     signalGiven;
   bool     isCHoCH;        // true if formed on CHoCH, false if BOS
};

struct SFVG
{
   double   top;
   double   bottom;
   int      barIndex;
   int      bias;
   bool     active;
};

//+------------------------------------------------------------------+
//| GLOBALS                                                           |
//+------------------------------------------------------------------+
CTrade   g_trade;

// Indicator handles
int      g_atrHandle     = INVALID_HANDLE;
int      g_htfAtrHandle  = INVALID_HANDLE;
int      g_htfEmaHandle  = INVALID_HANDLE;

// ATR value
double   g_atr = 0.0;

// Market structure tracking
double   g_phLevel = 0.0;        // Previous pivot high level
double   g_plLevel = 0.0;        // Previous pivot low level
int      g_phIdx   = -1;         // Previous pivot high bar index
int      g_plIdx   = -1;         // Previous pivot low bar index
int      g_trend   = 0;          // 1=bullish, -1=bearish, 0=undefined

// Order Blocks and FVGs
SOrderBlock g_bullOBs[];
SOrderBlock g_bearOBs[];
SFVG        g_fvgs[];

// Trade state
datetime g_lastBarTime      = 0;
int      g_dailyTradeCount  = 0;
datetime g_lastTradeDay     = 0;
int      g_lastTradeBar     = 0;  // bar index of last trade
bool     g_inTrade          = false;
int      g_tradeDirection   = 0;  // 1=long, -1=short
double   g_tradeSL          = 0;
double   g_tradeEntry       = 0;
double   g_tradeTP1         = 0;
double   g_tradeTP2         = 0;
double   g_tradeTP3         = 0;
bool     g_tp1Hit           = false;
bool     g_tp2Hit           = false;

// Structure analysis state
bool     g_structureReady   = false;

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpSlippage);

   if(InpSwingLength < 2)
   {
      Alert("SMC EA: SwingLength must be >= 2");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(g_atrHandle == INVALID_HANDLE)
   {
      Alert("SMC EA: Failed to create ATR handle");
      return INIT_FAILED;
   }

   if(InpUseHTFFilter)
   {
      g_htfAtrHandle = iATR(_Symbol, PERIOD_H1, 14);
      g_htfEmaHandle = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
      if(g_htfAtrHandle == INVALID_HANDLE || g_htfEmaHandle == INVALID_HANDLE)
      {
         Alert("SMC EA: Failed to create HTF indicator handles");
         return INIT_FAILED;
      }
   }

   ResetStructure();
   Print("SMC EA v1.0 initialized | ", _Symbol, " ", EnumToString(_Period),
         " | Magic: ", InpMagic, " | Risk: ", InpRiskPercent, "%");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_atrHandle != INVALID_HANDLE)    IndicatorRelease(g_atrHandle);
   if(g_htfAtrHandle != INVALID_HANDLE) IndicatorRelease(g_htfAtrHandle);
   if(g_htfEmaHandle != INVALID_HANDLE) IndicatorRelease(g_htfEmaHandle);
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   // --- Force exit check (every tick)
   if(IsForceExitTime() && HasPosition())
   {
      Print("SMC EA: Force exit at ", TimeToString(TimeCurrent(), TIME_MINUTES));
      CloseAllPositions();
      return;
   }

   // --- Manage existing position every tick
   if(g_inTrade && HasPosition())
      ManagePosition();

   // --- New bar detection (main logic runs once per bar)
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == g_lastBarTime)
      return;
   g_lastBarTime = currentBarTime;

   // --- Reset daily trade counter
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

   // --- Update ATR
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandle, 0, 0, 3, atrBuf) < 3) return;
   g_atr = atrBuf[1]; // use completed bar's ATR

   // --- Reset if position was closed externally
   if(g_inTrade && !HasPosition())
   {
      g_inTrade = false;
      g_tradeDirection = 0;
   }

   // --- Build market structure from history on first run
   if(!g_structureReady)
   {
      BuildStructure();
      g_structureReady = true;
      return; // skip trading on init bar
   }

   // --- Process the latest completed bar for structure updates
   int barsTotal = Bars(_Symbol, PERIOD_CURRENT);
   if(barsTotal < InpSwingLength * 2 + 5) return;

   // Analyze bar at index InpSwingLength (the bar that just got enough
   // right-side context to confirm as a pivot)
   int analyzeIdx = InpSwingLength;
   ProcessStructureBar(analyzeIdx, barsTotal);

   // --- Mitigate OBs and FVGs with current price
   double curHigh  = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double curLow   = iLow(_Symbol, PERIOD_CURRENT, 0);
   double curClose = iClose(_Symbol, PERIOD_CURRENT, 0);
   MitigateOBs(curHigh, curLow, curClose);
   MitigateFVGs(curHigh, curLow);

   // --- Check for new trade signals (on completed bar = index 1)
   if(!g_inTrade)
      CheckForEntry();
}

//+------------------------------------------------------------------+
//| BUILD STRUCTURE — Analyze history to initialize state             |
//+------------------------------------------------------------------+
void BuildStructure()
{
   int barsTotal = Bars(_Symbol, PERIOD_CURRENT);
   int startBar = barsTotal - 1 - InpSwingLength;
   if(startBar < InpSwingLength) return;

   // Process from oldest to newest (high bar indices = older)
   // We use iHigh/iLow with bar index (series-like, 0=current)
   // So we iterate from high index (old) to low index (new)
   for(int i = startBar; i >= InpSwingLength; i--)
      ProcessStructureBar(i, barsTotal);
}

//+------------------------------------------------------------------+
//| PROCESS A SINGLE BAR FOR STRUCTURE                                |
//+------------------------------------------------------------------+
void ProcessStructureBar(int barIdx, int barsTotal)
{
   bool ph = IsPivotHigh(barIdx, barsTotal);
   bool pl = IsPivotLow(barIdx, barsTotal);

   if(ph) HandlePivotHigh(barIdx, barsTotal);
   if(pl) HandlePivotLow(barIdx, barsTotal);

   CheckFVG(barIdx, barsTotal);
}

//+------------------------------------------------------------------+
//| PIVOT DETECTION (using bar indices — 0=current, higher=older)     |
//+------------------------------------------------------------------+
bool IsPivotHigh(int idx, int total)
{
   int len = InpSwingLength;
   if(idx - len < 0 || idx + len >= total) return false;
   double p = iHigh(_Symbol, PERIOD_CURRENT, idx);
   for(int k = 1; k <= len; k++)
   {
      if(iHigh(_Symbol, PERIOD_CURRENT, idx - k) >= p) return false;
      if(iHigh(_Symbol, PERIOD_CURRENT, idx + k) >= p) return false;
   }
   return true;
}

bool IsPivotLow(int idx, int total)
{
   int len = InpSwingLength;
   if(idx - len < 0 || idx + len >= total) return false;
   double p = iLow(_Symbol, PERIOD_CURRENT, idx);
   for(int k = 1; k <= len; k++)
   {
      if(iLow(_Symbol, PERIOD_CURRENT, idx - k) <= p) return false;
      if(iLow(_Symbol, PERIOD_CURRENT, idx + k) <= p) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| HANDLE PIVOT HIGH — Detect bullish structure breaks               |
//+------------------------------------------------------------------+
void HandlePivotHigh(int barIdx, int total)
{
   double pivPrice = iHigh(_Symbol, PERIOD_CURRENT, barIdx);

   if(g_phLevel > 0 && pivPrice > g_phLevel)
   {
      // Structure break upward: BOS (if already bullish) or CHoCH (if was bearish)
      bool isCHoCH = (g_trend == -1);
      g_trend = 1;

      // Create bullish Order Block
      AddOB(barIdx, 1, isCHoCH, total);
   }

   g_phLevel = pivPrice;
   g_phIdx   = barIdx;
}

//+------------------------------------------------------------------+
//| HANDLE PIVOT LOW — Detect bearish structure breaks                |
//+------------------------------------------------------------------+
void HandlePivotLow(int barIdx, int total)
{
   double pivPrice = iLow(_Symbol, PERIOD_CURRENT, barIdx);

   if(g_plLevel > 0 && pivPrice < g_plLevel)
   {
      // Structure break downward: BOS or CHoCH
      bool isCHoCH = (g_trend == 1);
      g_trend = -1;

      // Create bearish Order Block
      AddOB(barIdx, -1, isCHoCH, total);
   }

   g_plLevel = pivPrice;
   g_plIdx   = barIdx;
}

//+------------------------------------------------------------------+
//| ADD ORDER BLOCK                                                   |
//+------------------------------------------------------------------+
void AddOB(int pivIdx, int obBias, bool isCHoCH, int total)
{
   // Find the last opposing candle before the pivot
   int found = -1;
   for(int k = pivIdx - 1; k >= MathMax(0, pivIdx - InpSwingLength); k--)
   {
      double o = iOpen(_Symbol, PERIOD_CURRENT, k);
      double c = iClose(_Symbol, PERIOD_CURRENT, k);
      if(obBias == 1  && c < o) { found = k; break; } // last bearish candle before bullish break
      if(obBias == -1 && c > o) { found = k; break; } // last bullish candle before bearish break
   }
   if(found < 0) return;

   double o = iOpen(_Symbol, PERIOD_CURRENT, found);
   double c = iClose(_Symbol, PERIOD_CURRENT, found);
   double bodyTop = MathMax(o, c);
   double bodyBot = MathMin(o, c);
   double bodyMid = (bodyTop + bodyBot) / 2.0;

   double obTop, obBottom;
   if(obBias == 1)
   {
      obTop    = bodyMid;
      obBottom = bodyBot;
   }
   else
   {
      obTop    = bodyTop;
      obBottom = bodyMid;
   }

   if(obTop - obBottom < _Point) return;

   // Deduplicate — skip if too close to existing OB
   if(obBias == 1)
   {
      for(int j = 0; j < ArraySize(g_bullOBs); j++)
         if(g_bullOBs[j].active && MathAbs(g_bullOBs[j].top - obTop) < g_atr * 0.3) return;
   }
   else
   {
      for(int j = 0; j < ArraySize(g_bearOBs); j++)
         if(g_bearOBs[j].active && MathAbs(g_bearOBs[j].top - obTop) < g_atr * 0.3) return;
   }

   SOrderBlock ob;
   ob.top         = obTop;
   ob.bottom      = obBottom;
   ob.barIndex    = found;
   ob.bias        = obBias;
   ob.active      = true;
   ob.signalGiven = false;
   ob.isCHoCH     = isCHoCH;

   if(obBias == 1)
   {
      int n = ArraySize(g_bullOBs);
      if(n >= InpMaxOB) { ArrayRemoveOB(g_bullOBs, 0); n--; }
      ArrayResize(g_bullOBs, n + 1);
      g_bullOBs[n] = ob;
   }
   else
   {
      int n = ArraySize(g_bearOBs);
      if(n >= InpMaxOB) { ArrayRemoveOB(g_bearOBs, 0); n--; }
      ArrayResize(g_bearOBs, n + 1);
      g_bearOBs[n] = ob;
   }
}

//+------------------------------------------------------------------+
//| CHECK FOR FAIR VALUE GAPS                                         |
//+------------------------------------------------------------------+
void CheckFVG(int idx, int total)
{
   if(idx < 1 || idx + 1 >= total) return;

   double highPrev = iHigh(_Symbol, PERIOD_CURRENT, idx + 1);
   double lowPrev  = iLow(_Symbol, PERIOD_CURRENT, idx + 1);
   double highNext = iHigh(_Symbol, PERIOD_CURRENT, idx - 1);
   double lowNext  = iLow(_Symbol, PERIOD_CURRENT, idx - 1);

   bool bullFVG = (lowNext > highPrev);   // gap up
   bool bearFVG = (highNext < lowPrev);   // gap down
   if(!bullFVG && !bearFVG) return;

   double fTop, fBot;
   int    fBias;
   if(bullFVG) { fTop = lowNext;  fBot = highPrev; fBias =  1; }
   else        { fTop = lowPrev;  fBot = highNext;  fBias = -1; }

   if(fTop - fBot < g_atr * 0.15) return;

   // Deduplicate
   for(int j = 0; j < ArraySize(g_fvgs); j++)
      if(g_fvgs[j].active && MathAbs(g_fvgs[j].top - fTop) < g_atr * 0.2 && g_fvgs[j].bias == fBias)
         return;

   SFVG fvg;
   fvg.top      = fTop;
   fvg.bottom   = fBot;
   fvg.barIndex = idx;
   fvg.bias     = fBias;
   fvg.active   = true;

   int n = ArraySize(g_fvgs);
   ArrayResize(g_fvgs, n + 1);
   g_fvgs[n] = fvg;

   // Prune old FVGs (keep max 20)
   if(ArraySize(g_fvgs) > 20)
   {
      for(int i = 0; i < ArraySize(g_fvgs) - 1; i++)
         g_fvgs[i] = g_fvgs[i + 1];
      ArrayResize(g_fvgs, ArraySize(g_fvgs) - 1);
   }
}

//+------------------------------------------------------------------+
//| FVG CONFLUENCE CHECK                                              |
//+------------------------------------------------------------------+
bool FVGNearby(double obTop, double obBottom, int bias)
{
   for(int i = 0; i < ArraySize(g_fvgs); i++)
   {
      if(!g_fvgs[i].active)      continue;
      if(g_fvgs[i].bias != bias) continue;
      bool overlap = (g_fvgs[i].top >= obBottom - g_atr) &&
                     (g_fvgs[i].bottom <= obTop + g_atr);
      if(overlap) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| MITIGATE ORDER BLOCKS                                             |
//+------------------------------------------------------------------+
void MitigateOBs(double h, double l, double c)
{
   for(int i = 0; i < ArraySize(g_bullOBs); i++)
      if(g_bullOBs[i].active && c < g_bullOBs[i].bottom)
         g_bullOBs[i].active = false;

   for(int i = 0; i < ArraySize(g_bearOBs); i++)
      if(g_bearOBs[i].active && c > g_bearOBs[i].top)
         g_bearOBs[i].active = false;
}

//+------------------------------------------------------------------+
//| MITIGATE FAIR VALUE GAPS                                          |
//+------------------------------------------------------------------+
void MitigateFVGs(double h, double l)
{
   for(int i = 0; i < ArraySize(g_fvgs); i++)
   {
      if(!g_fvgs[i].active) continue;
      if((g_fvgs[i].bias == 1  && l <= g_fvgs[i].top    && l >= g_fvgs[i].bottom) ||
         (g_fvgs[i].bias == -1 && h >= g_fvgs[i].bottom && h <= g_fvgs[i].top))
         g_fvgs[i].active = false;
   }
}

//+------------------------------------------------------------------+
//| CHECK FOR ENTRY SIGNALS                                           |
//+------------------------------------------------------------------+
void CheckForEntry()
{
   // --- Pre-checks
   if(!IsSessionActive())       return;
   if(g_dailyTradeCount >= InpMaxDailyTrades) return;
   if(g_trend == 0)             return;

   // Cooldown check
   int currentBar = Bars(_Symbol, PERIOD_CURRENT);
   if(g_lastTradeBar > 0 && (currentBar - g_lastTradeBar) < InpMinBarsCooldown)
      return;

   // Spread filter
   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spreadPts > InpMaxSpreadPts) return;

   // HTF trend filter
   if(InpUseHTFFilter && !HTFTrendAligned()) return;

   // --- Analyze the last completed bar (index 1)
   double open1  = iOpen(_Symbol, PERIOD_CURRENT, 1);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double high1  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow(_Symbol, PERIOD_CURRENT, 1);

   double bodySize = MathAbs(close1 - open1);

   // Candle size filter
   if(bodySize > g_atr * InpMaxCandleATR) return;

   // Minimum body size (avoid dojis)
   if(bodySize < g_atr * 0.1) return;

   bool isBullCandle = (close1 > open1);
   bool isBearCandle = (close1 < open1);

   // --- BUY SIGNAL: Bullish trend, price touches bull OB, bullish candle confirms
   if(isBullCandle && g_trend == 1)
   {
      for(int j = 0; j < ArraySize(g_bullOBs); j++)
      {
         if(!g_bullOBs[j].active)     continue;
         if(g_bullOBs[j].signalGiven) continue;

         // CHoCH-only filter
         if(InpOnlyCHoCH && !g_bullOBs[j].isCHoCH) continue;

         // Price must have wicked into the OB zone
         bool inOB = (low1 <= g_bullOBs[j].top) &&
                     (low1 >= g_bullOBs[j].bottom - g_atr * 0.3);
         if(!inOB) continue;

         // FVG confluence
         if(InpRequireFVG && !FVGNearby(g_bullOBs[j].top, g_bullOBs[j].bottom, 1))
            continue;

         // Calculate SL and lots
         double sl = g_bullOBs[j].bottom - g_atr * InpSLPaddingATR;
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double riskDist = entry - sl;
         if(riskDist <= 0) continue;

         double lots = CalculateLotSize(riskDist);
         if(lots <= 0) continue;

         // Calculate TP levels
         double tp1 = entry + riskDist * InpTP1_R;
         double tp2 = entry + riskDist * InpTP2_R;
         double tp3 = entry + riskDist * InpTP3_R;

         // Execute
         if(g_trade.Buy(lots, _Symbol, entry, sl, tp3, "SMC BUY | OB Retest"))
         {
            g_bullOBs[j].signalGiven = true;
            g_inTrade        = true;
            g_tradeDirection = 1;
            g_tradeSL        = sl;
            g_tradeEntry     = entry;
            g_tradeTP1       = tp1;
            g_tradeTP2       = tp2;
            g_tradeTP3       = tp3;
            g_tp1Hit         = false;
            g_tp2Hit         = false;
            g_dailyTradeCount++;
            g_lastTradeBar   = currentBar;

            Print("SMC BUY | Entry: ", DoubleToString(entry, _Digits),
                  " | SL: ", DoubleToString(sl, _Digits),
                  " | TP1: ", DoubleToString(tp1, _Digits),
                  " | TP2: ", DoubleToString(tp2, _Digits),
                  " | TP3: ", DoubleToString(tp3, _Digits),
                  " | Lots: ", DoubleToString(lots, 2),
                  " | CHoCH: ", g_bullOBs[j].isCHoCH);
         }
         break; // one signal per bar
      }
   }

   // --- SELL SIGNAL: Bearish trend, price touches bear OB, bearish candle confirms
   if(isBearCandle && g_trend == -1 && !g_inTrade)
   {
      for(int j = 0; j < ArraySize(g_bearOBs); j++)
      {
         if(!g_bearOBs[j].active)     continue;
         if(g_bearOBs[j].signalGiven) continue;

         // CHoCH-only filter
         if(InpOnlyCHoCH && !g_bearOBs[j].isCHoCH) continue;

         // Price must have wicked into the OB zone
         bool inOB = (high1 >= g_bearOBs[j].bottom) &&
                     (high1 <= g_bearOBs[j].top + g_atr * 0.3);
         if(!inOB) continue;

         // FVG confluence
         if(InpRequireFVG && !FVGNearby(g_bearOBs[j].top, g_bearOBs[j].bottom, -1))
            continue;

         // Calculate SL and lots
         double sl = g_bearOBs[j].top + g_atr * InpSLPaddingATR;
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double riskDist = sl - entry;
         if(riskDist <= 0) continue;

         double lots = CalculateLotSize(riskDist);
         if(lots <= 0) continue;

         // Calculate TP levels
         double tp1 = entry - riskDist * InpTP1_R;
         double tp2 = entry - riskDist * InpTP2_R;
         double tp3 = entry - riskDist * InpTP3_R;

         // Execute
         if(g_trade.Sell(lots, _Symbol, entry, sl, tp3, "SMC SELL | OB Retest"))
         {
            g_bearOBs[j].signalGiven = true;
            g_inTrade        = true;
            g_tradeDirection = -1;
            g_tradeSL        = sl;
            g_tradeEntry     = entry;
            g_tradeTP1       = tp1;
            g_tradeTP2       = tp2;
            g_tradeTP3       = tp3;
            g_tp1Hit         = false;
            g_tp2Hit         = false;
            g_dailyTradeCount++;
            g_lastTradeBar   = currentBar;

            Print("SMC SELL | Entry: ", DoubleToString(entry, _Digits),
                  " | SL: ", DoubleToString(sl, _Digits),
                  " | TP1: ", DoubleToString(tp1, _Digits),
                  " | TP2: ", DoubleToString(tp2, _Digits),
                  " | TP3: ", DoubleToString(tp3, _Digits),
                  " | Lots: ", DoubleToString(lots, 2),
                  " | CHoCH: ", g_bearOBs[j].isCHoCH);
         }
         break;
      }
   }
}

//+------------------------------------------------------------------+
//| MANAGE OPEN POSITION — Partial TPs and trailing SL               |
//+------------------------------------------------------------------+
void ManagePosition()
{
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic) return;

   double currentPrice;
   double posLots = PositionGetDouble(POSITION_VOLUME);
   double posSL   = PositionGetDouble(POSITION_SL);

   if(g_tradeDirection == 1)
   {
      currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

      // TP1: Close 50%
      if(!g_tp1Hit && currentPrice >= g_tradeTP1)
      {
         double closeLots = NormalizeLots(posLots * InpTP1_Pct / 100.0);
         if(closeLots > 0)
         {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp1Hit = true;
            // Trail SL to breakeven
            if(g_tradeEntry > posSL)
               g_trade.PositionModify(_Symbol, g_tradeEntry, g_tradeTP3);
            Print("SMC: TP1 hit (LONG) — closed ", DoubleToString(closeLots, 2), " lots, SL to BE");
         }
      }

      // TP2: Close 25%
      if(g_tp1Hit && !g_tp2Hit && currentPrice >= g_tradeTP2)
      {
         posLots = PositionGetDouble(POSITION_VOLUME);
         double closeLots = NormalizeLots(posLots * (InpTP2_Pct / (InpTP2_Pct + InpTP3_Pct)));
         if(closeLots > 0)
         {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp2Hit = true;
            // Trail SL to TP1 level
            if(g_tradeTP1 > posSL)
               g_trade.PositionModify(_Symbol, g_tradeTP1, g_tradeTP3);
            Print("SMC: TP2 hit (LONG) — closed ", DoubleToString(closeLots, 2), " lots, SL to TP1");
         }
      }

      // ATR trailing after TP2
      if(g_tp2Hit)
      {
         double trailSL = currentPrice - g_atr * 1.5;
         if(trailSL > posSL)
            g_trade.PositionModify(_Symbol, trailSL, g_tradeTP3);
      }
   }
   else if(g_tradeDirection == -1)
   {
      currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      // TP1: Close 50%
      if(!g_tp1Hit && currentPrice <= g_tradeTP1)
      {
         double closeLots = NormalizeLots(posLots * InpTP1_Pct / 100.0);
         if(closeLots > 0)
         {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp1Hit = true;
            if(g_tradeEntry < posSL || posSL == 0)
               g_trade.PositionModify(_Symbol, g_tradeEntry, g_tradeTP3);
            Print("SMC: TP1 hit (SHORT) — closed ", DoubleToString(closeLots, 2), " lots, SL to BE");
         }
      }

      // TP2: Close 25%
      if(g_tp1Hit && !g_tp2Hit && currentPrice <= g_tradeTP2)
      {
         posLots = PositionGetDouble(POSITION_VOLUME);
         double closeLots = NormalizeLots(posLots * (InpTP2_Pct / (InpTP2_Pct + InpTP3_Pct)));
         if(closeLots > 0)
         {
            g_trade.PositionClosePartial(_Symbol, closeLots);
            g_tp2Hit = true;
            if(g_tradeTP1 < posSL || posSL == 0)
               g_trade.PositionModify(_Symbol, g_tradeTP1, g_tradeTP3);
            Print("SMC: TP2 hit (SHORT) — closed ", DoubleToString(closeLots, 2), " lots, SL to TP1");
         }
      }

      // ATR trailing after TP2
      if(g_tp2Hit)
      {
         double trailSL = currentPrice + g_atr * 1.5;
         if(trailSL < posSL || posSL == 0)
            g_trade.PositionModify(_Symbol, trailSL, g_tradeTP3);
      }
   }
}

//+------------------------------------------------------------------+
//| CALCULATE LOT SIZE based on risk %                                |
//+------------------------------------------------------------------+
double CalculateLotSize(double riskDistancePrice)
{
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount     = accountBalance * InpRiskPercent / 100.0;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tickValue <= 0 || tickSize <= 0 || riskDistancePrice <= 0)
      return 0;

   double riskInTicks = riskDistancePrice / tickSize;
   double lots = riskAmount / (riskInTicks * tickValue);

   return NormalizeLots(lots);
}

//+------------------------------------------------------------------+
//| NORMALIZE LOTS to broker constraints                              |
//+------------------------------------------------------------------+
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
//| HTF TREND FILTER — H1 EMA(50) direction                          |
//+------------------------------------------------------------------+
bool HTFTrendAligned()
{
   if(!InpUseHTFFilter) return true;

   double ema[];
   ArraySetAsSeries(ema, true);
   if(CopyBuffer(g_htfEmaHandle, 0, 0, 3, ema) < 3) return true; // allow if data unavailable

   double htfClose = iClose(_Symbol, PERIOD_H1, 1);

   if(g_trend == 1  && htfClose > ema[1]) return true;  // bullish aligned
   if(g_trend == -1 && htfClose < ema[1]) return true;  // bearish aligned
   return false;
}

//+------------------------------------------------------------------+
//| SESSION FILTER                                                    |
//+------------------------------------------------------------------+
bool IsSessionActive()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.hour >= InpSessionStartHr && dt.hour < InpSessionEndHr);
}

//+------------------------------------------------------------------+
//| FORCE EXIT TIME CHECK                                             |
//+------------------------------------------------------------------+
bool IsForceExitTime()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.hour > InpForceExitHr ||
           (dt.hour == InpForceExitHr && dt.min >= InpForceExitMin));
}

//+------------------------------------------------------------------+
//| CHECK IF POSITION EXISTS                                          |
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

//+------------------------------------------------------------------+
//| CLOSE ALL POSITIONS                                               |
//+------------------------------------------------------------------+
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
   g_tp1Hit = false;
   g_tp2Hit = false;
}

//+------------------------------------------------------------------+
//| RESET STRUCTURE STATE                                             |
//+------------------------------------------------------------------+
void ResetStructure()
{
   ArrayResize(g_bullOBs, 0);
   ArrayResize(g_bearOBs, 0);
   ArrayResize(g_fvgs, 0);
   g_phLevel = 0; g_plLevel = 0;
   g_phIdx   = -1; g_plIdx  = -1;
   g_trend   = 0;
   g_structureReady = false;
}

//+------------------------------------------------------------------+
//| ARRAY REMOVE HELPER                                               |
//+------------------------------------------------------------------+
void ArrayRemoveOB(SOrderBlock &arr[], int idx)
{
   int sz = ArraySize(arr);
   for(int i = idx; i < sz - 1; i++) arr[i] = arr[i + 1];
   ArrayResize(arr, sz - 1);
}
//+------------------------------------------------------------------+
