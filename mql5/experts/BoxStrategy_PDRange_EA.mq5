//+------------------------------------------------------------------+
//|                                       BoxStrategy_PDRange_EA.mq5  |
//| Box Strategy (PDH/PDL):                                           |
//|  - Inside box: fade extremes (sell near PDH, buy near PDL)        |
//|  - Outside box: breakout-retest continuation                      |
//| Confirmation (from transcript examples):                          |
//|  - Short: close[1] < low[2]                                       |
//|  - Long : close[1] > high[2]                                      |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- Inputs
input group "=== Expert ==="
input double InpLotSize        = 0.10;     // Fixed lot size
input int    InpMagicNumber    = 20260408; // Magic number
input int    InpDeviationPts   = 20;       // Deviation (points)
input bool   InpOneTradeAtTime = true;     // One position at a time

input group "=== Session Filter (server time) ==="
input bool InpUseSession  = false; // Enable session filter
input int  InpStartHour   = 0;
input int  InpStartMinute = 0;
input int  InpEndHour     = 23;
input int  InpEndMinute   = 59;

input group "=== Box Levels ==="
input int InpProximityPoints        = 50; // Proximity to PDH/PDL (points)
input int InpBreakoutConfirmPoints  = 20; // Breakout threshold beyond PDH/PDL (points)

input group "=== Strategy Mode ==="
enum TradeMode { MODE_BOTH=0, MODE_INSIDE_ONLY=1, MODE_OUTSIDE_ONLY=2 };
input TradeMode InpMode = MODE_BOTH;

input group "=== Confirmation Candle ==="
input bool InpUseConfirmCandle = true; // Require confirmation candle pattern

input group "=== Risk/TP/SL ==="
enum TpMode { TP_OPPOSITE_BOX=0, TP_RR=1 };
input TpMode InpTpMode = TP_OPPOSITE_BOX;
input double InpRR     = 2.0;   // RR if TP_RR (also used for outside continuation TP)
input int    InpSLBufferPoints = 20; // SL buffer (points)
input int    InpSwingLookback  = 5;  // Swing lookback bars for SL
input bool   InpCloseOnOppSignal = false; // Close open trade if opposite signal appears

//--- Handles
int hBox = INVALID_HANDLE; // iCustom BoxStrategy_PDRange (PDH/PDL)

//--- State
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_lastBarTime)
   {
      g_lastBarTime = t;
      return true;
   }
   return false;
}

bool InSession()
{
   if(!InpUseSession) return true;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int cur = dt.hour * 60 + dt.min;
   int start = InpStartHour * 60 + InpStartMinute;
   int end = InpEndHour * 60 + InpEndMinute;
   if(start <= end) return (cur >= start && cur <= end);
   return (cur >= start || cur <= end); // spans midnight
}

double GetTickSize()
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0) ? ts : _Point;
}

double NormalizePrice(const double price)
{
   double tick = GetTickSize();
   double p = MathRound(price / tick) * tick;
   return NormalizeDouble(p, (int)_Digits);
}

double NormalizeLot(const double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   double l = lots;
   l = MathMax(l, minLot);
   l = MathMin(l, maxLot);
   l = MathFloor(l / stepLot) * stepLot;
   l = MathMax(l, minLot);
   return l;
}

double MinStopDistance()
{
   long stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (stopLevelPts > 0) ? stopLevelPts * _Point : 0.0;
}

void ApplyMinStops(const bool isBuy, const double entry, double &sl, double &tp)
{
   double minDist = MinStopDistance();
   if(minDist <= 0.0) return;

   if(isBuy)
   {
      if(sl > 0 && (entry - sl) < minDist) sl = entry - minDist;
      if(tp > 0 && (tp - entry) < minDist) tp = entry + minDist;
   }
   else
   {
      if(sl > 0 && (sl - entry) < minDist) sl = entry + minDist;
      if(tp > 0 && (entry - tp) < minDist) tp = entry - minDist;
   }

   sl = (sl > 0) ? NormalizePrice(sl) : 0.0;
   tp = (tp > 0) ? NormalizePrice(tp) : 0.0;
}

ulong FindPositionTicket(const ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            (int)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
            return ticket;
      }
   }
   return 0;
}

bool HasAnyPosition()
{
   return (FindPositionTicket(POSITION_TYPE_BUY) > 0 || FindPositionTicket(POSITION_TYPE_SELL) > 0);
}

bool CloseIfOppositeSignal(const bool wantBuy, const bool wantSell)
{
   if(!InpCloseOnOppSignal) return false;
   ulong buyTicket  = FindPositionTicket(POSITION_TYPE_BUY);
   ulong sellTicket = FindPositionTicket(POSITION_TYPE_SELL);
   if(wantSell && buyTicket > 0)
   {
      trade.PositionClose(buyTicket);
      return true;
   }
   if(wantBuy && sellTicket > 0)
   {
      trade.PositionClose(sellTicket);
      return true;
   }
   return false;
}

double SwingHigh(const int shift, const int lookback)
{
   double maxH = iHigh(_Symbol, PERIOD_CURRENT, shift);
   for(int k = 1; k <= lookback; k++)
      maxH = MathMax(maxH, iHigh(_Symbol, PERIOD_CURRENT, shift + k));
   return maxH;
}

double SwingLow(const int shift, const int lookback)
{
   double minL = iLow(_Symbol, PERIOD_CURRENT, shift);
   for(int k = 1; k <= lookback; k++)
      minL = MathMin(minL, iLow(_Symbol, PERIOD_CURRENT, shift + k));
   return minL;
}

bool ConfirmShort()
{
   if(!InpUseConfirmCandle) return true;
   return (iClose(_Symbol, PERIOD_CURRENT, 1) < iLow(_Symbol, PERIOD_CURRENT, 2));
}

bool ConfirmLong()
{
   if(!InpUseConfirmCandle) return true;
   return (iClose(_Symbol, PERIOD_CURRENT, 1) > iHigh(_Symbol, PERIOD_CURRENT, 2));
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpDeviationPts);

   // Use indicator only as a PDH/PDL source; drawing is harmless.
   hBox = iCustom(_Symbol, PERIOD_CURRENT, "BoxStrategy_PDRange",
                  true, clrSlateGray, 85, 500);
   if(hBox == INVALID_HANDLE)
   {
      Print("BoxStrategy EA: failed to create iCustom handle. err=", GetLastError());
      return INIT_FAILED;
   }

   Print("BoxStrategy_PDRange_EA initialized. Magic=", InpMagicNumber,
         " | Symbol=", _Symbol, " | TF=", EnumToString(PERIOD_CURRENT),
         " | TickSize=", DoubleToString(GetTickSize(), _Digits),
         " | StopsLevelPts=", (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hBox != INVALID_HANDLE) IndicatorRelease(hBox);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsNewBar()) return;
   if(!InSession()) return;
   // If we allow only one trade at a time, we still optionally allow closing on opposite signals.

   // PDH/PDL from indicator buffers (bar 1 = last closed)
   double pdhBuf[3], pdlBuf[3];
   ArraySetAsSeries(pdhBuf, true);
   ArraySetAsSeries(pdlBuf, true);
   if(CopyBuffer(hBox, 0, 0, 3, pdhBuf) < 3) { Print("CopyBuffer PDH failed err=", GetLastError()); return; }
   if(CopyBuffer(hBox, 1, 0, 3, pdlBuf) < 3) { Print("CopyBuffer PDL failed err=", GetLastError()); return; }

   double pdh = pdhBuf[1];
   double pdl = pdlBuf[1];
   if(pdh <= 0 || pdl <= 0 || pdh <= pdl)
   {
      Print("Invalid PD range. pdh=", pdh, " pdl=", pdl, " err=", GetLastError());
      return;
   }

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double high1  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow(_Symbol, PERIOD_CURRENT, 1);

   if(close1 <= 0 || high1 <= 0 || low1 <= 0)
      return;

   double prox  = InpProximityPoints * _Point;
   double brk   = InpBreakoutConfirmPoints * _Point;
   double slBuf = InpSLBufferPoints * _Point;

   bool inside = (close1 <= pdh && close1 >= pdl);
   bool above  = (close1 > pdh + brk);
   bool below  = (close1 < pdl - brk);

   double lots = NormalizeLot(InpLotSize);
   bool hasPos = HasAnyPosition();
   if(InpOneTradeAtTime && hasPos && !InpCloseOnOppSignal) return;

   // ================================================================
   // INSIDE BOX: fade extremes (sell PDH, buy PDL)
   // ================================================================
   if((InpMode == MODE_BOTH || InpMode == MODE_INSIDE_ONLY) && inside)
   {
      bool nearTop = (MathAbs(high1 - pdh) <= prox) || (MathAbs(close1 - pdh) <= prox);
      if(nearTop && ConfirmShort())
      {
         CloseIfOppositeSignal(false, true);
         if(InpOneTradeAtTime && HasAnyPosition()) return;
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = NormalizePrice(SwingHigh(1, InpSwingLookback) + slBuf);
         double tp = 0.0;

         if(InpTpMode == TP_OPPOSITE_BOX)
            tp = NormalizePrice(pdl);
         else
            tp = NormalizePrice(entry - (sl - entry) * InpRR);

         ApplyMinStops(false, entry, sl, tp);
         if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "BoxFade SELL"))
            Print("BoxFade SELL pdh=", pdh, " pdl=", pdl, " sl=", sl, " tp=", tp);
         else
            Print("SELL failed. err=", GetLastError());
         return;
      }

      bool nearBot = (MathAbs(low1 - pdl) <= prox) || (MathAbs(close1 - pdl) <= prox);
      if(nearBot && ConfirmLong())
      {
         CloseIfOppositeSignal(true, false);
         if(InpOneTradeAtTime && HasAnyPosition()) return;
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = NormalizePrice(SwingLow(1, InpSwingLookback) - slBuf);
         double tp = 0.0;

         if(InpTpMode == TP_OPPOSITE_BOX)
            tp = NormalizePrice(pdh);
         else
            tp = NormalizePrice(entry + (entry - sl) * InpRR);

         ApplyMinStops(true, entry, sl, tp);
         if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "BoxFade BUY"))
            Print("BoxFade BUY pdh=", pdh, " pdl=", pdl, " sl=", sl, " tp=", tp);
         else
            Print("BUY failed. err=", GetLastError());
         return;
      }
   }

   // ================================================================
   // OUTSIDE BOX: breakout-retest continuation
   // - Above: retest PDH as support (low tags PDH area, close back above PDH)
   // - Below: retest PDL as resistance (high tags PDL area, close back below PDL)
   // ================================================================
   if(InpMode == MODE_BOTH || InpMode == MODE_OUTSIDE_ONLY)
   {
      if(above)
      {
         bool retestHold = (low1 <= pdh + prox) && (close1 >= pdh);
         if(retestHold && ConfirmLong())
         {
            CloseIfOppositeSignal(true, false);
            if(InpOneTradeAtTime && HasAnyPosition()) return;
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl = NormalizePrice(MathMin(pdh, SwingLow(1, InpSwingLookback)) - slBuf);
            double tp = NormalizePrice(entry + (entry - sl) * InpRR);
            ApplyMinStops(true, entry, sl, tp);
            if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "BoxCont BUY"))
               Print("BoxCont BUY pdh=", pdh, " sl=", sl, " tp=", tp);
            else
               Print("BUY failed. err=", GetLastError());
            return;
         }
      }
      else if(below)
      {
         bool retestReject = (high1 >= pdl - prox) && (close1 <= pdl);
         if(retestReject && ConfirmShort())
         {
            CloseIfOppositeSignal(false, true);
            if(InpOneTradeAtTime && HasAnyPosition()) return;
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl = NormalizePrice(MathMax(pdl, SwingHigh(1, InpSwingLookback)) + slBuf);
            double tp = NormalizePrice(entry - (sl - entry) * InpRR);
            ApplyMinStops(false, entry, sl, tp);
            if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "BoxCont SELL"))
               Print("BoxCont SELL pdl=", pdl, " sl=", sl, " tp=", tp);
            else
               Print("SELL failed. err=", GetLastError());
            return;
         }
      }
   }
}
//+------------------------------------------------------------------+

