//+------------------------------------------------------------------+
//|                                    Structure_FVG_Execution_EA.mq5 |
//| "Range → Change → Execution" style framework (video transcript):   |
//| 1) RANGE (HTF): who is in control — swing / break-of-structure bias |
//| 2) CHANGE: align with fresh displacement + FVG on execution TF   |
//| 3) EXECUTION: enter from FVG pullback (midpoint zone), SL beyond   |
//|    zone/structure, TP at fixed R-multiple (default 1:4).          |
//|                                                                   |
//| Uses same 3-candle FVG geometry as FVG_Zones / FairValueGap EA.   |
//| No profitability guarantee — test thoroughly and tune symbols/TFs.   |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "HTF structure bias + LTF FVG pullback execution, R-multiple exits, optional NY-style session"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- Step 1 — Higher timeframe "range / control"
input group "=== Step 1: HTF bias (range / control) ==="
input ENUM_TIMEFRAMES InpHTF = PERIOD_M15; // Bias timeframe (e.g. 15m) for structure break

//--- Step 2 — Execution timeframe FVG
input group "=== Step 2–3: Execution TF & FVG ==="
input int    InpMinGapPoints   = 15;    // Min FVG height (points)
input int    InpFvgLookback    = 120;   // Bars to scan for FVG on execution chart
input double InpEntryZoneFrac  = 0.45;  // Enter when price in lower/upper 45% of FVG (midpoint area)
input bool   InpRequireTouch   = true;  // Require bar to touch FVG zone before entry

//--- Filters
input group "=== Filters ==="
input bool   InpUseSession     = false;
input int    InpSessStartHour  = 13;    // e.g. NY cash ~ 14:30 server — adjust to broker
input int    InpSessStartMin   = 30;
input int    InpSessEndHour    = 21;
input int    InpSessEndMin     = 0;
input int    InpMaxSpreadPts   = 60;    // 0 = off

//--- Risk
input group "=== Risk & management ==="
input double InpFixedLot       = 0.10;
input double InpRiskRR         = 4.0;   // Target R (video: 1:4 baseline)
input int    InpSLBufferPts    = 15;    // Beyond FVG edge + buffer
input int    InpMagic          = 20260411;
input int    InpDeviationPts   = 20;
input bool   InpOneTrade       = true;

//--- Handles / state
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
double PtsToPrice(const int pts) { return pts * _Point; }

double GetTickSize()
{
   double t = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (t > 0) ? t : _Point;
}

double NormPrice(const double p)
{
   double ts = GetTickSize();
   return NormalizeDouble(MathRound(p / ts) * ts, (int)_Digits);
}

double NormLot(const double lots)
{
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st <= 0) st = 0.01;
   double l = MathMax(mn, MathMin(mx, lots));
   l = MathFloor(l / st) * st;
   return MathMax(l, mn);
}

bool MinStopOK(const bool buy, const double entry, double &sl, double &tp)
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double md = (lv > 0) ? lv * _Point : 0;
   if(md <= 0) return true;
   if(buy)
   {
      if(entry - sl < md) sl = entry - md;
      if(tp - entry < md) tp = entry + md;
   }
   else
   {
      if(sl - entry < md) sl = entry + md;
      if(entry - tp < md) tp = entry - md;
   }
   sl = NormPrice(sl);
   tp = NormPrice(tp);
   return true;
}

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_lastBar) { g_lastBar = t; return true; }
   return false;
}

bool InSession()
{
   if(!InpUseSession) return true;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int c = dt.hour * 60 + dt.min;
   int a = InpSessStartHour * 60 + InpSessStartMin;
   int b = InpSessEndHour * 60 + InpSessEndMin;
   if(a <= b) return (c >= a && c <= b);
   return (c >= a || c <= b);
}

bool SpreadOK()
{
   if(InpMaxSpreadPts <= 0) return true;
   return ((long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= InpMaxSpreadPts);
}

// HTF bias: break of recent swing range (BOS-style) on InpHTF — matches "who's in control"
int GetHTFBiasStructureBreak()
{
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, InpHTF, 0, 40, r) < 20) return 0;
   double hh = r[5].high;
   double ll = r[5].low;
   for(int i = 6; i < 25; i++)
   {
      hh = MathMax(hh, r[i].high);
      ll = MathMin(ll, r[i].low);
   }
   if(r[1].close > hh) return 1;
   if(r[1].close < ll) return -1;
   return 0;
}

int GetBias() { return GetHTFBiasStructureBreak(); }

struct FvgZone
{
   double lo;
   double hi;
   bool   bearish; // bearish FVG = supply above
   bool   valid;
};

// Find most recent FVG on execution TF aligned with bias (bearish FVG for bias -1)
bool FindRecentFvg(const int bias, FvgZone &z)
{
   z.valid = false;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpFvgLookback + 5, rates);
   if(n < 5) return false;

   double minGap = InpMinGapPoints * _Point;
   double zf = MathMax(0.1, MathMin(0.49, InpEntryZoneFrac));

   // i = last bar of 3-candle pattern (bars i-2, i-1, i). Newest pattern: i = n-1 first.
   for(int i = n - 1; i >= 2; i--)
   {
      if(bias == 1)
      {
         double gLo = rates[i - 2].high;
         double gHi = rates[i].low;
         if(gHi > gLo && (gHi - gLo) >= minGap)
         {
            z.lo = gLo;
            z.hi = gHi;
            z.bearish = false;
            z.valid = true;
            return true;
         }
      }
      if(bias == -1)
      {
         double top = rates[i - 2].low;
         double bot = rates[i].high;
         if(top > bot && (top - bot) >= minGap)
         {
            z.hi = top;
            z.lo = bot;
            z.bearish = true;
            z.valid = true;
            return true;
         }
      }
   }
   return false;
}

bool PriceInEntryZone(const FvgZone &z, const double price, const bool isShort)
{
   double w = z.hi - z.lo;
   if(w <= 0) return false;
   double frac = MathMax(0.05, MathMin(0.49, InpEntryZoneFrac));
   if(isShort)
   {
      // Upper portion of supply FVG (sell zone)
      double thr = z.hi - w * frac;
      return (price <= z.hi && price >= thr);
   }
   // Long: lower portion of demand FVG
   double thr2 = z.lo + w * frac;
   return (price >= z.lo && price <= thr2);
}

ulong FindPos(const ENUM_POSITION_TYPE t)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == t) return tk;
   }
   return 0;
}

bool HasPos() { return FindPos(POSITION_TYPE_BUY) > 0 || FindPos(POSITION_TYPE_SELL) > 0; }

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPts);
   Print("Structure_FVG_Execution_EA | HTF=", EnumToString(InpHTF), " RR=1:", InpRiskRR);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(!InSession() || !SpreadOK()) return;
   if(InpOneTrade && HasPos()) return;

   int bias = GetBias();
   if(bias == 0) return;

   FvgZone z;
   if(!FindRecentFvg(bias, z) || !z.valid) return;

   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double h1 = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double l1 = iLow(_Symbol, PERIOD_CURRENT, 1);

   double lots = NormLot(InpFixedLot);
   double buf = PtsToPrice(InpSLBufferPts);

   if(bias == -1 && z.bearish)
   {
      bool touch = !InpRequireTouch || (h1 >= z.lo && l1 <= z.hi);
      if(!touch) return;
      if(!PriceInEntryZone(z, c1, true)) return;

      double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormPrice(z.hi + buf);
      double risk = sl - entry;
      if(risk <= 0) return;
      double tp = NormPrice(entry - risk * InpRiskRR);
      MinStopOK(false, entry, sl, tp);
      if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "StructFVG sell"))
         Print("SELL FVG supply RR=", InpRiskRR, " sl=", sl, " tp=", tp);
   }
   else if(bias == 1 && !z.bearish)
   {
      bool touch = !InpRequireTouch || (l1 <= z.hi && h1 >= z.lo);
      if(!touch) return;
      if(!PriceInEntryZone(z, c1, false)) return;

      double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormPrice(z.lo - buf);
      double risk = entry - sl;
      if(risk <= 0) return;
      double tp = NormPrice(entry + risk * InpRiskRR);
      MinStopOK(true, entry, sl, tp);
      if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "StructFVG buy"))
         Print("BUY FVG demand RR=", InpRiskRR, " sl=", sl, " tp=", tp);
   }
}
//+------------------------------------------------------------------+
