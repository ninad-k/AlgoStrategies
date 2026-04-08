//+------------------------------------------------------------------+
//|                                  SmartRenko_BoxStrategy_Bundled.mq5 |
//| BUNDLED: Smart Renko-like (EMA30 + brick SL/TP) + Box PDH/PDL      |
//| Single file — no #include project deps; only Trade.mqh              |
//| Modes: Renko only | Box only | Combined AND | Combined OR          |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Bundled Renko-like + Previous-Day Box strategy — single EA, no separate indicators required"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- Bundled mode
enum ENUM_BUNDLED_MODE
{
   BUNDLED_RENKO_ONLY = 0,   // Smart Renko-like only
   BUNDLED_BOX_ONLY   = 1,   // Box PDH/PDL only
   BUNDLED_COMBINED_AND = 2, // Both strategies must agree (same direction)
   BUNDLED_COMBINED_OR  = 3  // Renko first, else Box
};

input group "=== Bundled mode ==="
input ENUM_BUNDLED_MODE InpBundledMode = BUNDLED_COMBINED_OR;
input int    InpMagicNumber   = 20260409;
input double InpFixedLot      = 0.10;
input int    InpDeviationPts  = 20;

//--- Renko block (matches SmartRenkoLikeEA + SmartRenkoLikeStep)
input group "=== Renko: signal ==="
input int    InpRenkoEMAPeriod = 30;

input group "=== Renko: brick ==="
enum BrickCalcMode { RENKO_ATR = 0, RENKO_PERCENT = 1, RENKO_FIXED = 2 };
input BrickCalcMode InpBrickCalc      = RENKO_ATR;
input int           InpATRLen         = 14;
input double        InpATRMult        = 1.0;
input double        InpCustomPct      = 1.0;
input double        InpFixedBoxPoints = 50.0;
input double        InpRoundingStep   = 0.0;
input bool          InpAllowMultiBrick = true;
input bool          InpInitRoundFirst  = false;
input int           InpRenkoReplayBars = 5000; // bars to replay for dir[1]/dir[2]

//--- Box block (matches BoxStrategy_PDRange_EA)
input group "=== Box: session ==="
input bool InpBoxUseSession  = false;
input int  InpBoxStartHour   = 0;
input int  InpBoxStartMinute = 0;
input int  InpBoxEndHour     = 23;
input int  InpBoxEndMinute   = 59;

input group "=== Box: levels ==="
input int InpProximityPoints       = 50;
input int InpBreakoutConfirmPoints = 20;

input group "=== Box: mode ==="
enum BoxTradeMode { BOX_MODE_BOTH = 0, BOX_INSIDE_ONLY = 1, BOX_OUTSIDE_ONLY = 2 };
input BoxTradeMode InpBoxMode = BOX_MODE_BOTH;

input bool InpBoxUseConfirmCandle = true;

input group "=== Box: risk ==="
enum BoxTpMode { BOX_TP_OPPOSITE = 0, BOX_TP_RR = 1 };
input BoxTpMode InpBoxTpMode = BOX_TP_OPPOSITE;
input double InpBoxRR            = 2.0;
input int    InpBoxSLBufferPts   = 20;
input int    InpBoxSwingLookback = 5;
input bool   InpBoxOneTrade      = true;
input bool   InpBoxCloseOpp      = false;

//--- Handles (Renko replay uses ATR + EMA only)
int hATR = INVALID_HANDLE;
int hEMA = INVALID_HANDLE;

datetime g_lastBar = 0;

//+------------------------------------------------------------------+
double GetTickSize()
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0) ? ts : _Point;
}

double RoundToStep(const double value, const double step)
{
   if(step <= 0.0) return value;
   return MathRound(value / step) * step;
}

double NormalizePrice(const double price)
{
   double tick = GetTickSize();
   return NormalizeDouble(RoundToStep(price, tick), (int)_Digits);
}

double NormalizeLot(const double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   double l = MathMax(minLot, MathMin(maxLot, lots));
   l = MathFloor(l / stepLot) * stepLot;
   return MathMax(l, minLot);
}

double MinStopDistance()
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (lv > 0) ? lv * _Point : 0.0;
}

void ApplyMinStops(const bool isBuy, const double entry, double &sl, double &tp)
{
   double md = MinStopDistance();
   if(md <= 0.0) return;
   if(isBuy)
   {
      if(sl > 0 && (entry - sl) < md) sl = entry - md;
      if(tp > 0 && (tp - entry) < md) tp = entry + md;
   }
   else
   {
      if(sl > 0 && (sl - entry) < md) sl = entry + md;
      if(tp > 0 && (entry - tp) < md) tp = entry - md;
   }
   sl = (sl > 0) ? NormalizePrice(sl) : 0.0;
   tp = (tp > 0) ? NormalizePrice(tp) : 0.0;
}

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_lastBar) { g_lastBar = t; return true; }
   return false;
}

ulong FindTicket(const int magic, const ENUM_POSITION_TYPE t)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((int)PositionGetInteger(POSITION_MAGIC) != magic) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == t) return tk;
   }
   return 0;
}

bool HasPos(const int magic)
{
   return FindTicket(magic, POSITION_TYPE_BUY) > 0 || FindTicket(magic, POSITION_TYPE_SELL) > 0;
}

//+------------------------------------------------------------------+
bool GetPDRange(double &pdh, double &pdl)
{
   MqlRates d1[];
   ArraySetAsSeries(d1, true);
   if(CopyRates(_Symbol, PERIOD_D1, 0, 3, d1) < 2) return false;
   pdh = d1[1].high;
   pdl = d1[1].low;
   return (pdh > pdl && pdh > 0 && pdl > 0);
}

// Replay Renko series — returns dir at series index 1 and 2, brick at 1
bool ComputeRenkoDir(int &dir1, int &dir2, double &brick1)
{
   int need = InpRenkoReplayBars;
   if(need < 100) need = 100;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int n = CopyRates(_Symbol, PERIOD_CURRENT, 0, need, rates);
   if(n < 3) return false;

   double close[];
   ArrayResize(close, n);
   ArraySetAsSeries(close, true);
   for(int j = 0; j < n; j++)
      close[j] = rates[j].close;

   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(hATR, 0, 0, n, atr) < n) return false;

   double tickSize = GetTickSize();
   double step = (InpRoundingStep > 0.0) ? InpRoundingStep : tickSize;

   double RenkoBuffer[];
   double DirBuffer[];
   double BrickBuffer[];
   ArrayResize(RenkoBuffer, n);
   ArrayResize(DirBuffer, n);
   ArrayResize(BrickBuffer, n);
   ArraySetAsSeries(RenkoBuffer, true);
   ArraySetAsSeries(DirBuffer, true);
   ArraySetAsSeries(BrickBuffer, true);

   for(int i = n - 1; i >= 0; i--)
   {
      double brickRaw = 0.0;
      if(InpBrickCalc == RENKO_ATR) brickRaw = atr[i] * InpATRMult;
      else if(InpBrickCalc == RENKO_PERCENT) brickRaw = close[i] * (InpCustomPct / 100.0);
      else brickRaw = InpFixedBoxPoints;

      double brick = RoundToStep(brickRaw, step);
      if(brick < tickSize) brick = tickSize;
      BrickBuffer[i] = brick;

      if(i == n - 1)
      {
         double ir = close[i];
         if(InpInitRoundFirst) ir = RoundToStep(ir, brick);
         RenkoBuffer[i] = ir;
         DirBuffer[i] = 0.0;
         continue;
      }

      double prevRenko = RenkoBuffer[i + 1];
      double prevDir   = DirBuffer[i + 1];
      double upMove = close[i] - prevRenko;
      double dnMove = prevRenko - close[i];
      double renko = prevRenko;
      double dirv  = prevDir;

      if(upMove >= brick)
      {
         int br = InpAllowMultiBrick ? (int)MathFloor(upMove / brick) : 1;
         renko = prevRenko + br * brick;
         dirv = 1.0;
      }
      else if(dnMove >= brick)
      {
         int br = InpAllowMultiBrick ? (int)MathFloor(dnMove / brick) : 1;
         renko = prevRenko - br * brick;
         dirv = -1.0;
      }
      RenkoBuffer[i] = renko;
      DirBuffer[i] = dirv;
   }

   dir1 = (int)MathRound(DirBuffer[1]);
   dir2 = (int)MathRound(DirBuffer[2]);
   brick1 = BrickBuffer[1];
   return (brick1 > 0);
}

bool RenkoSignals(bool &flipUp, bool &flipDn)
{
   int d1, d2;
   double br;
   if(!ComputeRenkoDir(d1, d2, br)) return false;
   flipUp = (d2 != 1 && d1 == 1);
   flipDn = (d2 != -1 && d1 == -1);
   return true;
}

bool BoxConfirmLong()  { return !InpBoxUseConfirmCandle || (iClose(_Symbol, PERIOD_CURRENT, 1) > iHigh(_Symbol, PERIOD_CURRENT, 2)); }
bool BoxConfirmShort() { return !InpBoxUseConfirmCandle || (iClose(_Symbol, PERIOD_CURRENT, 1) < iLow(_Symbol, PERIOD_CURRENT, 2)); }

double SwingHigh(const int shift, const int lookback)
{
   double maxH = iHigh(_Symbol, PERIOD_CURRENT, shift);
   for(int k = 1; k <= lookback; k++) maxH = MathMax(maxH, iHigh(_Symbol, PERIOD_CURRENT, shift + k));
   return maxH;
}

double SwingLow(const int shift, const int lookback)
{
   double minL = iLow(_Symbol, PERIOD_CURRENT, shift);
   for(int k = 1; k <= lookback; k++) minL = MathMin(minL, iLow(_Symbol, PERIOD_CURRENT, shift + k));
   return minL;
}

bool BoxInSession()
{
   if(!InpBoxUseSession) return true;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int cur = dt.hour * 60 + dt.min;
   int s = InpBoxStartHour * 60 + InpBoxStartMinute;
   int e = InpBoxEndHour * 60 + InpBoxEndMinute;
   if(s <= e) return (cur >= s && cur <= e);
   return (cur >= s || cur <= e);
}

// Returns: 0 none, 1 buy, -1 sell; fills sl,tp for market entry
int BoxSignal(const double pdh, const double pdl, double &sl, double &tp)
{
   double prox  = InpProximityPoints * _Point;
   double brk   = InpBreakoutConfirmPoints * _Point;
   double slBuf = InpBoxSLBufferPts * _Point;

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double high1  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow(_Symbol, PERIOD_CURRENT, 1);
   if(close1 <= 0) return 0;

   bool inside = (close1 <= pdh && close1 >= pdl);
   bool above  = (close1 > pdh + brk);
   bool below  = (close1 < pdl - brk);

   // Inside fade
   if((InpBoxMode == BOX_MODE_BOTH || InpBoxMode == BOX_INSIDE_ONLY) && inside)
   {
      bool nearTop = (MathAbs(high1 - pdh) <= prox) || (MathAbs(close1 - pdh) <= prox);
      if(nearTop && BoxConfirmShort())
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         sl = NormalizePrice(SwingHigh(1, InpBoxSwingLookback) + slBuf);
         if(InpBoxTpMode == BOX_TP_OPPOSITE) tp = NormalizePrice(pdl);
         else tp = NormalizePrice(entry - (sl - entry) * InpBoxRR);
         ApplyMinStops(false, entry, sl, tp);
         return -1;
      }
      bool nearBot = (MathAbs(low1 - pdl) <= prox) || (MathAbs(close1 - pdl) <= prox);
      if(nearBot && BoxConfirmLong())
      {
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         sl = NormalizePrice(SwingLow(1, InpBoxSwingLookback) - slBuf);
         if(InpBoxTpMode == BOX_TP_OPPOSITE) tp = NormalizePrice(pdh);
         else tp = NormalizePrice(entry + (entry - sl) * InpBoxRR);
         ApplyMinStops(true, entry, sl, tp);
         return 1;
      }
   }

   if(InpBoxMode == BOX_MODE_BOTH || InpBoxMode == BOX_OUTSIDE_ONLY)
   {
      if(above)
      {
         bool retest = (low1 <= pdh + prox) && (close1 >= pdh);
         if(retest && BoxConfirmLong())
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            sl = NormalizePrice(MathMin(pdh, SwingLow(1, InpBoxSwingLookback)) - slBuf);
            tp = NormalizePrice(entry + (entry - sl) * InpBoxRR);
            ApplyMinStops(true, entry, sl, tp);
            return 1;
         }
      }
      else if(below)
      {
         bool retest = (high1 >= pdl - prox) && (close1 <= pdl);
         if(retest && BoxConfirmShort())
         {
            double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            sl = NormalizePrice(MathMax(pdl, SwingHigh(1, InpBoxSwingLookback)) + slBuf);
            tp = NormalizePrice(entry - (sl - entry) * InpBoxRR);
            ApplyMinStops(false, entry, sl, tp);
            return -1;
         }
      }
   }
   return 0;
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpDeviationPts);

   hATR = iATR(_Symbol, PERIOD_CURRENT, InpATRLen);
   hEMA = iMA(_Symbol, PERIOD_CURRENT, InpRenkoEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || hEMA == INVALID_HANDLE)
   {
      Print("Bundled EA: failed ATR/EMA handles err=", GetLastError());
      return INIT_FAILED;
   }

   Print("SmartRenko_BoxStrategy_Bundled initialized. Mode=", EnumToString(InpBundledMode),
         " Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hEMA != INVALID_HANDLE) IndicatorRelease(hEMA);
}

//+------------------------------------------------------------------+
void TryRenkoTrade()
{
   int dir1, dir2;
   double brick;
   if(!ComputeRenkoDir(dir1, dir2, brick)) return;

   double ema[];
   ArraySetAsSeries(ema, true);
   if(CopyBuffer(hEMA, 0, 0, 3, ema) < 3) return;

   bool flipUp = (dir2 != 1 && dir1 == 1);
   bool flipDn = (dir2 != -1 && dir1 == -1);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   bool buyF = close1 > ema[1];
   bool sellF = close1 < ema[1];

   ulong b = FindTicket(InpMagicNumber, POSITION_TYPE_BUY);
   ulong s = FindTicket(InpMagicNumber, POSITION_TYPE_SELL);
   double lots = NormalizeLot(InpFixedLot);

   if(flipUp && buyF)
   {
      if(s > 0) trade.PositionClose(s);
      if(b == 0)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = NormalizePrice(ask - brick);
         double tp = NormalizePrice(ask + 2.0 * brick);
         ApplyMinStops(true, ask, sl, tp);
         if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "Bundled Renko BUY"))
            Print("Bundled Renko BUY brick=", brick);
      }
   }
   else if(flipDn && sellF)
   {
      if(b > 0) trade.PositionClose(b);
      if(s == 0)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = NormalizePrice(bid + brick);
         double tp = NormalizePrice(bid - 2.0 * brick);
         ApplyMinStops(false, bid, sl, tp);
         if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "Bundled Renko SELL"))
            Print("Bundled Renko SELL brick=", brick);
      }
   }
}

void TryBoxTrade()
{
   if(!BoxInSession()) return;
   if(InpBoxOneTrade && HasPos(InpMagicNumber) && !InpBoxCloseOpp) return;

   double pdh, pdl;
   if(!GetPDRange(pdh, pdl)) return;

   double sl = 0, tp = 0;
   int sig = BoxSignal(pdh, pdl, sl, tp);
   if(sig == 0) return;

   double lots = NormalizeLot(InpFixedLot);
   ulong b = FindTicket(InpMagicNumber, POSITION_TYPE_BUY);
   ulong s = FindTicket(InpMagicNumber, POSITION_TYPE_SELL);

   if(sig == 1)
   {
      if(InpBoxCloseOpp && s > 0) trade.PositionClose(s);
      if(InpBoxOneTrade && HasPos(InpMagicNumber)) return;
      if(trade.Buy(lots, _Symbol, 0.0, sl, tp, "Bundled Box BUY"))
         Print("Bundled Box BUY");
   }
   else if(sig == -1)
   {
      if(InpBoxCloseOpp && b > 0) trade.PositionClose(b);
      if(InpBoxOneTrade && HasPos(InpMagicNumber)) return;
      if(trade.Sell(lots, _Symbol, 0.0, sl, tp, "Bundled Box SELL"))
         Print("Bundled Box SELL");
   }
}

// Combined AND: Renko direction must match Box direction on same bar
void TryCombinedAnd()
{
   if(!BoxInSession()) return;

   int dir1, dir2;
   double brick;
   if(!ComputeRenkoDir(dir1, dir2, brick)) return;

   double ema[];
   ArraySetAsSeries(ema, true);
   if(CopyBuffer(hEMA, 0, 0, 3, ema) < 3) return;

   bool flipUp = (dir2 != 1 && dir1 == 1);
   bool flipDn = (dir2 != -1 && dir1 == -1);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   bool renkoBuy = flipUp && (close1 > ema[1]);
   bool renkoSell = flipDn && (close1 < ema[1]);

   double pdh, pdl;
   if(!GetPDRange(pdh, pdl)) return;

   double slb = 0, tpb = 0;
   int boxSig = BoxSignal(pdh, pdl, slb, tpb);

   if(renkoBuy && boxSig == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizePrice(ask - brick);
      double tp = NormalizePrice(ask + 2.0 * brick);
      ApplyMinStops(true, ask, sl, tp);
      ulong s = FindTicket(InpMagicNumber, POSITION_TYPE_SELL);
      if(s > 0) trade.PositionClose(s);
      if(FindTicket(InpMagicNumber, POSITION_TYPE_BUY) == 0)
         trade.Buy(NormalizeLot(InpFixedLot), _Symbol, 0.0, sl, tp, "Bundled AND BUY");
   }
   else if(renkoSell && boxSig == -1)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizePrice(bid + brick);
      double tp = NormalizePrice(bid - 2.0 * brick);
      ApplyMinStops(false, bid, sl, tp);
      ulong b = FindTicket(InpMagicNumber, POSITION_TYPE_BUY);
      if(b > 0) trade.PositionClose(b);
      if(FindTicket(InpMagicNumber, POSITION_TYPE_SELL) == 0)
         trade.Sell(NormalizeLot(InpFixedLot), _Symbol, 0.0, sl, tp, "Bundled AND SELL");
   }
}

void OnTick()
{
   if(!IsNewBar()) return;

   switch(InpBundledMode)
   {
      case BUNDLED_RENKO_ONLY:
         TryRenkoTrade();
         break;
      case BUNDLED_BOX_ONLY:
         TryBoxTrade();
         break;
      case BUNDLED_COMBINED_AND:
         TryCombinedAnd();
         break;
      case BUNDLED_COMBINED_OR:
      default:
         TryRenkoTrade();
         if(!HasPos(InpMagicNumber))
            TryBoxTrade();
         break;
   }
}
//+------------------------------------------------------------------+
