//+------------------------------------------------------------------+
//|                                   BoxStrategy_PDRange_Pro_EA.mq5  |
//| "Box strategy" from PDH/PDL — structured rules + quality filters   |
//|                                                                   |
//| Framework (video): box = previous day high/low. Trade edges, not  |
//| the middle. Inside range: fade stretched moves to PDH/PDL. Outside|
//| broken box: continuation on retest/hold. Confirmation: close vs   |
//| prior candle high/low. Stops beyond local structure + buffer.      |
//|                                                                   |
//| No profitability guarantee; use filters + tester + forward demo.   |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "PDH/PDL box strategy with mid-zone avoidance, ATR/spread filters, optional PDD levels, session LOD/HOD targets"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- Expert
input group "=== Expert ==="
input double InpLotSize       = 0.10;
input int    InpMagicNumber     = 20260410;
input int    InpDeviationPts    = 20;
input bool   InpOneTradeAtTime  = true;
input bool   InpCloseOnOpp      = false;

//--- Session (server time) — e.g. US RTH 9:30–16:00 NY ≈ set to your broker
input group "=== Session ==="
input bool InpUseSession   = true;
input int  InpStartHour    = 8;
input int  InpStartMinute  = 30;
input int  InpEndHour      = 17;
input int  InpEndMinute    = 0;

//--- Box: previous day range (D1[1])
input group "=== PD box ==="
input int InpProximityPoints       = 80;   // Near PDH/PDL (points)
input int InpBreakoutConfirmPoints = 25;   // Close beyond box for "outside" (points)

//--- "Don't trade the middle" — only edges of PD range (video rule)
input group "=== Mid-zone avoidance (inside box) ==="
input bool InpUseMidZoneFilter = true;
input double InpEdgeFraction = 0.35;   // Trade only if in lower/upper 35% of [PDL,PDH]; middle = skip

//--- Optional: day-before-yesterday high/low as extra context (multi-box idea)
input group "=== Optional PDD confluence (D1[2]) ==="
input bool InpUsePDD = false;
input bool InpRequirePDDConfluence = false; // If true, edge must align with PDD level within proximity

//--- Quality filters
input group "=== Quality filters ==="
input int    InpATRLen            = 14;
input double InpMinBoxATRMult     = 0.8;  // Min (PDH-PDL) >= this * ATR(14) on signal TF
input int    InpMaxSpreadPoints   = 50;   // Skip if spread > points (0 = off)

//--- Strategy mode
input group "=== Mode ==="
enum ProTradeMode { PRO_BOTH=0, PRO_INSIDE_ONLY=1, PRO_OUTSIDE_ONLY=2 };
input ProTradeMode InpMode = PRO_BOTH;

input group "=== Confirmation candle ==="
input bool InpUseConfirmCandle = true;

input group "=== Risk / TP / SL ==="
enum ProTpMode
{
   PRO_TP_OPP_BOX = 0,   // Target opposite PD edge (inside fade)
   PRO_TP_SESSION = 1,   // Target session LOD (shorts) / HOD (longs) — video "low of day"
   PRO_TP_RR      = 2
};
input ProTpMode InpTpMode = PRO_TP_SESSION;
input double InpRR        = 2.0;
input int    InpSLBufferPoints = 25;
input int    InpSwingLookback  = 5;
input double InpMinRR          = 1.2;  // Skip entry if RR below this (0 = off)

//--- Handles
int hATR = INVALID_HANDLE;
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
double GetTickSize()
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0) ? ts : _Point;
}

double NormalizePrice(const double p)
{
   double t = GetTickSize();
   return NormalizeDouble(MathRound(p / t) * t, (int)_Digits);
}

double NormalizeLot(const double lots)
{
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;
   double l = MathMax(minL, MathMin(maxL, lots));
   l = MathFloor(l / step) * step;
   return MathMax(l, minL);
}

double MinStopDist()
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (lv > 0) ? lv * _Point : 0.0;
}

void ApplyMinStops(const bool buy, const double entry, double &sl, double &tp)
{
   double md = MinStopDist();
   if(md <= 0) { sl = NormalizePrice(sl); tp = NormalizePrice(tp); return; }
   if(buy)
   {
      if(sl > 0 && entry - sl < md) sl = entry - md;
      if(tp > 0 && tp - entry < md) tp = entry + md;
   }
   else
   {
      if(sl > 0 && sl - entry < md) sl = entry + md;
      if(tp > 0 && entry - tp < md) tp = entry - md;
   }
   sl = (sl > 0) ? NormalizePrice(sl) : 0;
   tp = (tp > 0) ? NormalizePrice(tp) : 0;
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
   int s = InpStartHour * 60 + InpStartMinute;
   int e = InpEndHour * 60 + InpEndMinute;
   if(s <= e) return (c >= s && c <= e);
   return (c >= s || c <= e);
}

bool SpreadOK()
{
   if(InpMaxSpreadPoints <= 0) return true;
   long sp = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return (sp <= InpMaxSpreadPoints);
}

bool GetPDLevels(double &pdh, double &pdl, double &pddh, double &pddl)
{
   MqlRates d1[];
   ArraySetAsSeries(d1, true);
   if(CopyRates(_Symbol, PERIOD_D1, 0, 4, d1) < 3) return false;
   pdh  = d1[1].high;
   pdl  = d1[1].low;
   pddh = d1[2].high;
   pddl = d1[2].low;
   return (pdh > pdl && pdh > 0);
}

double ATR1()
{
   double a[]; ArraySetAsSeries(a, true);
   if(CopyBuffer(hATR, 0, 1, 1, a) < 1) return 0;
   return a[0];
}

// Position in PD range: 0 = at PDL, 1 = at PDH
double RangePosition(const double price, const double lo, const double hi)
{
   if(hi <= lo) return 0.5;
   return (price - lo) / (hi - lo);
}

// Inside box and in "edge" zone only (not middle)
bool InEdgeZone(const double close1, const double pdh, const double pdl, const bool wantUpperEdge)
{
   if(!InpUseMidZoneFilter) return true;
   double rp = RangePosition(close1, pdl, pdh);
   double e = MathMax(0.05, MathMin(0.45, InpEdgeFraction));
   if(wantUpperEdge) return (rp >= 1.0 - e); // top edge
   return (rp <= e); // bottom edge
}

bool BoxWideEnough(const double pdh, const double pdl)
{
   double atr = ATR1();
   if(atr <= 0) return true;
   double w = pdh - pdl;
   return (w >= atr * InpMinBoxATRMult);
}

bool ConfirmShort() { return !InpUseConfirmCandle || (iClose(_Symbol, PERIOD_CURRENT, 1) < iLow(_Symbol, PERIOD_CURRENT, 2)); }
bool ConfirmLong()  { return !InpUseConfirmCandle || (iClose(_Symbol, PERIOD_CURRENT, 1) > iHigh(_Symbol, PERIOD_CURRENT, 2)); }

double SwingHigh(const int sh, const int lb)
{
   double m = iHigh(_Symbol, PERIOD_CURRENT, sh);
   for(int k = 1; k <= lb; k++) m = MathMax(m, iHigh(_Symbol, PERIOD_CURRENT, sh + k));
   return m;
}

double SwingLow(const int sh, const int lb)
{
   double m = iLow(_Symbol, PERIOD_CURRENT, sh);
   for(int k = 1; k <= lb; k++) m = MathMin(m, iLow(_Symbol, PERIOD_CURRENT, sh + k));
   return m;
}

// Session HOD / LOD from bar 1 back to session start (approximate)
bool SessionHighLow(double &hod, double &lod)
{
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   MqlDateTime dt; TimeToStruct(t1, dt);
   dt.hour = InpStartHour; dt.min = InpStartMinute; dt.sec = 0;
   datetime dayStart = StructToTime(dt);
   if(t1 < dayStart) dayStart -= 86400;

   hod = iHigh(_Symbol, PERIOD_CURRENT, 1);
   lod = iLow(_Symbol, PERIOD_CURRENT, 1);
   int i = 1;
   while(i < 500 && iTime(_Symbol, PERIOD_CURRENT, i) >= dayStart)
   {
      hod = MathMax(hod, iHigh(_Symbol, PERIOD_CURRENT, i));
      lod = MathMin(lod, iLow(_Symbol, PERIOD_CURRENT, i));
      i++;
   }
   return true;
}

ulong FindTk(const ENUM_POSITION_TYPE t)
{
   for(int k = PositionsTotal() - 1; k >= 0; k--)
   {
      ulong tk = PositionGetTicket(k);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == t) return tk;
   }
   return 0;
}

bool HasPos() { return FindTk(POSITION_TYPE_BUY) > 0 || FindTk(POSITION_TYPE_SELL) > 0; }

bool RR_OK(const bool buy, const double entry, const double sl, const double tp)
{
   if(InpMinRR <= 0) return true;
   if(sl <= 0 || tp <= 0) return true;
   double risk = buy ? (entry - sl) : (sl - entry);
   double rew  = buy ? (tp - entry) : (entry - tp);
   if(risk <= 0) return false;
   return (rew / risk >= InpMinRR);
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpDeviationPts);
   hATR = iATR(_Symbol, PERIOD_CURRENT, InpATRLen);
   if(hATR == INVALID_HANDLE)
   {
      Print("BoxStrategy_PDRange_Pro: ATR failed err=", GetLastError());
      return INIT_FAILED;
   }
   Print("BoxStrategy_PDRange_Pro_EA started. Magic=", InpMagicNumber,
         " | MidFilter=", InpUseMidZoneFilter, " edge=", InpEdgeFraction);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsNewBar()) return;
   if(!InSession() || !SpreadOK()) return;
   if(InpOneTradeAtTime && HasPos() && !InpCloseOnOpp) return;

   double pdh, pdl, pddh, pddl;
   if(!GetPDLevels(pdh, pdl, pddh, pddl)) return;
   if(!BoxWideEnough(pdh, pdl)) return;

   double prox = InpProximityPoints * _Point;
   double brk  = InpBreakoutConfirmPoints * _Point;
   double slBuf = InpSLBufferPoints * _Point;

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double high1  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow(_Symbol, PERIOD_CURRENT, 1);
   if(close1 <= 0) return;

   bool inside = (close1 <= pdh && close1 >= pdl);
   bool above  = (close1 > pdh + brk);
   bool below  = (close1 < pdl - brk);

   double hod, lod;
   SessionHighLow(hod, lod);

   double lots = NormalizeLot(InpLotSize);

   // -------- INSIDE: fade at edges only --------
   if((InpMode == PRO_BOTH || InpMode == PRO_INSIDE_ONLY) && inside)
   {
      // Short near PDH — must be upper edge zone (not middle)
      bool nearTop = (MathAbs(high1 - pdh) <= prox) || (MathAbs(close1 - pdh) <= prox);
      if(nearTop && InEdgeZone(close1, pdh, pdl, true) && ConfirmShort())
      {
         if(InpUsePDD && InpRequirePDDConfluence)
         {
            bool alignTop = (MathAbs(pdh - pddh) <= prox * 3) || (MathAbs(pdh - pddl) <= prox * 3);
            if(!alignTop) return;
         }
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = NormalizePrice(SwingHigh(1, InpSwingLookback) + slBuf);
         double tp = 0;
         if(InpTpMode == PRO_TP_OPP_BOX) tp = NormalizePrice(pdl);
         else if(InpTpMode == PRO_TP_SESSION) tp = NormalizePrice(lod);
         else tp = NormalizePrice(entry - (sl - entry) * InpRR);
         ApplyMinStops(false, entry, sl, tp);
         if(!RR_OK(false, entry, sl, tp)) return;
         if(InpCloseOnOpp && FindTk(POSITION_TYPE_BUY) > 0) trade.PositionClose(FindTk(POSITION_TYPE_BUY));
         if(InpOneTradeAtTime && HasPos()) return;
         if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "BoxPro fade PDH"))
            Print("BoxPro SELL fade @PDH tp=", tp);
         return;
      }

      // Long near PDL — lower edge zone
      bool nearBot = (MathAbs(low1 - pdl) <= prox) || (MathAbs(close1 - pdl) <= prox);
      if(nearBot && InEdgeZone(close1, pdh, pdl, false) && ConfirmLong())
      {
         if(InpUsePDD && InpRequirePDDConfluence)
         {
            bool alignBot = (MathAbs(pdl - pddl) <= prox * 3) || (MathAbs(pdl - pddh) <= prox * 3);
            if(!alignBot) return;
         }
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = NormalizePrice(SwingLow(1, InpSwingLookback) - slBuf);
         double tp = 0;
         if(InpTpMode == PRO_TP_OPP_BOX) tp = NormalizePrice(pdh);
         else if(InpTpMode == PRO_TP_SESSION) tp = NormalizePrice(hod);
         else tp = NormalizePrice(entry + (entry - sl) * InpRR);
         ApplyMinStops(true, entry, sl, tp);
         if(!RR_OK(true, entry, sl, tp)) return;
         if(InpCloseOnOpp && FindTk(POSITION_TYPE_SELL) > 0) trade.PositionClose(FindTk(POSITION_TYPE_SELL));
         if(InpOneTradeAtTime && HasPos()) return;
         if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "BoxPro fade PDL"))
            Print("BoxPro BUY fade @PDL tp=", tp);
         return;
      }
   }

   // -------- OUTSIDE: continuation on retest --------
   if(InpMode == PRO_BOTH || InpMode == PRO_OUTSIDE_ONLY)
   {
      if(above)
      {
         bool retest = (low1 <= pdh + prox) && (close1 >= pdh);
         if(retest && ConfirmLong())
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = NormalizePrice(MathMin(pdh, SwingLow(1, InpSwingLookback)) - slBuf);
            double tp = NormalizePrice(entry + (entry - sl) * InpRR);
            if(InpTpMode == PRO_TP_SESSION) tp = NormalizePrice(hod);
            ApplyMinStops(true, entry, sl, tp);
            if(!RR_OK(true, entry, sl, tp)) return;
            if(InpCloseOnOpp && FindTk(POSITION_TYPE_SELL) > 0) trade.PositionClose(FindTk(POSITION_TYPE_SELL));
            if(InpOneTradeAtTime && HasPos()) return;
            if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "BoxPro cont above"))
               Print("BoxPro BUY continuation");
            return;
         }
      }
      else if(below)
      {
         bool retest = (high1 >= pdl - prox) && (close1 <= pdl);
         if(retest && ConfirmShort())
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = NormalizePrice(MathMax(pdl, SwingHigh(1, InpSwingLookback)) + slBuf);
            double tp = NormalizePrice(entry - (sl - entry) * InpRR);
            if(InpTpMode == PRO_TP_SESSION) tp = NormalizePrice(lod);
            ApplyMinStops(false, entry, sl, tp);
            if(!RR_OK(false, entry, sl, tp)) return;
            if(InpCloseOnOpp && FindTk(POSITION_TYPE_BUY) > 0) trade.PositionClose(FindTk(POSITION_TYPE_BUY));
            if(InpOneTradeAtTime && HasPos()) return;
            if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "BoxPro cont below"))
               Print("BoxPro SELL continuation");
            return;
         }
      }
   }
}
//+------------------------------------------------------------------+
