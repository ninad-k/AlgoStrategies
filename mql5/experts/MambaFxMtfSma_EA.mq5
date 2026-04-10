//+------------------------------------------------------------------+
//| MambaFxMtfSma_EA.mq5                                             |
//| HTF pivot S/R + sequential SMA slow/fast breakout (see Pine      |
//| pinescript/strategies/MambaFxMtfSma_Strategy.pine). Intended M15. |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Mamba FX–style: HTF pivots + SMA sequence; SL near SMA slow; TP at HTF level or R:R fallback."
#property strict

#include <Trade\Trade.mqh>

CTrade trade;

input group "=== Timeframes ==="
input ENUM_TIMEFRAMES InpHTF = PERIOD_H4;          // Higher TF (S/R)

input group "=== SMAs (chart TF) ==="
input int InpSmaFast = 8;                        // SMA fast
input int InpSmaSlow = 50;                       // SMA slow

input group "=== HTF pivots ==="
input int InpPivotLeft = 5;                      // Pivot left bars
input int InpPivotRight = 5;                     // Pivot right bars
input int InpResLookback = 50;                   // HTF bars for hi/lo TP fallback

input group "=== Stops & targets ==="
input bool   InpSlUseAtr = true;                 // SL buffer: ATR (else fixed points)
input int    InpAtrLen = 14;                     // ATR length
input double InpAtrMult = 0.15;                  // SL: ATR ×
input double InpSlFixedPts = 50.0;               // SL: fixed buffer (points) if not ATR
input double InpTpFallbackRR = 2.0;              // TP R:R if no HTF level

input group "=== Trailing (optional) ==="
input bool   InpUseTrail = true;                 // Trail after profit (points)
input double InpTrailActivatePts = 100.0;        // Activate trail after profit (points)
input double InpTrailOffsetPts = 80.0;           // Trail distance (points)

input group "=== Trade ==="
input double InpLotSize = 0.1;                   // Lot size
input int    InpMagic = 20260410;                // Magic number
input double InpSlippage = 30;                   // Slippage (points)

//--- handles
int hSmaFast = INVALID_HANDLE;
int hSmaSlow = INVALID_HANDLE;
int hAtr     = INVALID_HANDLE;

datetime g_lastBarTime = 0;

bool     g_longSeqWait  = false;
bool     g_shortSeqWait = false;

double   g_longTpPrice  = 0.0;
double   g_shortTpPrice = 0.0;

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpSmaFast < 1 || InpSmaSlow < 2 || InpSmaFast >= InpSmaSlow)
   {
      Print("Invalid SMA periods");
      return INIT_PARAMETERS_INCORRECT;
   }

   hSmaFast = iMA(_Symbol, PERIOD_CURRENT, InpSmaFast, 0, MODE_SMA, PRICE_CLOSE);
   hSmaSlow = iMA(_Symbol, PERIOD_CURRENT, InpSmaSlow, 0, MODE_SMA, PRICE_CLOSE);
   hAtr     = iATR(_Symbol, PERIOD_CURRENT, InpAtrLen);

   if(hSmaFast == INVALID_HANDLE || hSmaSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE)
   {
      Print("Failed to create indicators");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints((int)InpSlippage);

   Print("MambaFxMtfSma_EA initialized | HTF=", EnumToString(InpHTF),
         " | Chart=", EnumToString(PERIOD_CURRENT));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hSmaFast != INVALID_HANDLE) IndicatorRelease(hSmaFast);
   if(hSmaSlow != INVALID_HANDLE) IndicatorRelease(hSmaSlow);
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(PositionByMagic())
      ManageOpenPosition();
   else
   {
      g_longTpPrice  = 0.0;
      g_shortTpPrice = 0.0;
   }

   datetime barOpen = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(barOpen == g_lastBarTime)
      return;
   g_lastBarTime = barOpen;

   ProcessNewBar();
}

//+------------------------------------------------------------------+
bool PositionByMagic()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool IsPivotLow(const double &low[], int s, int L, int R, int total)
{
   if(s < L || s + R >= total) return false;
   double v = low[s];
   for(int k = 1; k <= L; k++)
      if(v >= low[s - k]) return false;
   for(int k = 1; k <= R; k++)
      if(v >= low[s + k]) return false;
   return true;
}

//+------------------------------------------------------------------+
bool IsPivotHigh(const double &high[], int s, int L, int R, int total)
{
   if(s < L || s + R >= total) return false;
   double v = high[s];
   for(int k = 1; k <= L; k++)
      if(v < high[s - k]) return false;
   for(int k = 1; k <= R; k++)
      if(v <= high[s + k]) return false;
   return true;
}

//+------------------------------------------------------------------+
double GetNewestPivotLow(const double &low[], int L, int R, int total)
{
   for(int s = L + 1; s < total - R; s++)
   {
      if(IsPivotLow(low, s, L, R, total))
         return low[s];
   }
   return -1.0;
}

//+------------------------------------------------------------------+
double GetNewestPivotHigh(const double &high[], int L, int R, int total)
{
   for(int s = L + 1; s < total - R; s++)
   {
      if(IsPivotHigh(high, s, L, R, total))
         return high[s];
   }
   return -1.0;
}

//+------------------------------------------------------------------+
void HtfLevels(double &htfSup, double &htfRes, double &htfHiFb, double &htfLoFb,
               double &supLevel, double &resLevel)
{
   htfSup = htfRes = htfHiFb = htfLoFb = 0.0;
   supLevel = resLevel = 0.0;

   int need = InpResLookback + InpPivotLeft + InpPivotRight + 20;
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int n = CopyRates(_Symbol, InpHTF, 0, need, rates);
   if(n < InpPivotLeft + InpPivotRight + 5)
      return;

   double low[], high[];
   ArrayResize(low, n);
   ArrayResize(high, n);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(high, true);
   for(int i = 0; i < n; i++)
   {
      low[i]  = rates[i].low;
      high[i] = rates[i].high;
   }

   htfHiFb = high[ArrayMaximum(high, 0, InpResLookback)];
   htfLoFb = low[ArrayMinimum(low, 0, InpResLookback)];

   htfSup = GetNewestPivotLow(low, InpPivotLeft, InpPivotRight, n);
   htfRes = GetNewestPivotHigh(high, InpPivotLeft, InpPivotRight, n);

   supLevel = (htfSup > 0.0) ? htfSup : htfLoFb;
   resLevel = (htfRes > 0.0) ? htfRes : htfHiFb;
}

//+------------------------------------------------------------------+
double PointForRisk()
{
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(dg == 5 || dg == 3)
      return _Point * 10.0;
   return _Point;
}

//+------------------------------------------------------------------+
double SlBufferPrice()
{
   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(hAtr, 0, 0, 2, atr) < 2) return InpSlFixedPts * _Point;
   double atr1 = atr[1];
   if(InpSlUseAtr)
      return atr1 * InpAtrMult;
   return InpSlFixedPts * _Point;
}

//+------------------------------------------------------------------+
void ProcessNewBar()
{
   if(PositionByMagic()) return;

   double htfSup, htfRes, htfHiFb, htfLoFb, supLevel, resLevel;
   HtfLevels(htfSup, htfRes, htfHiFb, htfLoFb, supLevel, resLevel);

   double smaF[], smaS[];
   ArraySetAsSeries(smaF, true);
   ArraySetAsSeries(smaS, true);
   if(CopyBuffer(hSmaFast, 0, 0, 4, smaF) < 4) return;
   if(CopyBuffer(hSmaSlow, 0, 0, 4, smaS) < 4) return;

   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double c2 = iClose(_Symbol, PERIOD_CURRENT, 2);

   double sf1 = smaF[1], sf2 = smaF[2];
   double ss1 = smaS[1], ss2 = smaS[2];

   bool crossSlowUp   = (c1 > ss1 && c2 <= ss2);
   bool crossSlowDown = (c1 < ss1 && c2 >= ss2);
   bool crossFastUp   = (c1 > sf1 && c2 <= sf2);
   bool crossFastDown = (c1 < sf1 && c2 >= sf2);

   if(crossSlowUp)  g_longSeqWait = true;
   if(crossSlowDown) g_longSeqWait = false;

   if(crossSlowDown) g_shortSeqWait = true;
   if(crossSlowUp)   g_shortSeqWait = false;

   double slBuf = SlBufferPrice();
   double riskLong  = MathMax(c1 - (ss1 - slBuf), PointForRisk());
   double riskShort = MathMax((ss1 + slBuf) - c1, PointForRisk());

   double tpLong = 0.0, tpShort = 0.0;
   if(htfRes > 0.0 && htfRes > c1)
      tpLong = htfRes;
   else if(htfHiFb > c1)
      tpLong = htfHiFb;
   else
      tpLong = c1 + riskLong * InpTpFallbackRR;

   if(htfSup > 0.0 && htfSup < c1)
      tpShort = htfSup;
   else if(htfLoFb < c1)
      tpShort = htfLoFb;
   else
      tpShort = c1 - riskShort * InpTpFallbackRR;

   double slLong  = ss1 - slBuf;
   double slShort = ss1 + slBuf;

   bool longSignal = g_longSeqWait && crossFastUp && (c1 > supLevel);
   if(longSignal) g_longSeqWait = false;

   bool shortSignal = g_shortSeqWait && crossFastDown && (c1 < resLevel);
   if(shortSignal) g_shortSeqWait = false;

   bool longOk = longSignal && (slLong < c1) && (tpLong > c1);
   bool shortOk = shortSignal && (slShort > c1) && (tpShort < c1);

   if(!longOk && !shortOk) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(longOk)
   {
      g_longTpPrice = tpLong;
      g_shortTpPrice = 0.0;
      double sl = NormalizeDouble(slLong, _Digits);
      double tp = NormalizeDouble(tpLong, _Digits);
      StopsNormalize(ORDER_TYPE_BUY, ask, sl, tp);
      if(trade.Buy(InpLotSize, _Symbol, 0.0, sl, tp, "Mamba long"))
         Print("Buy SL=", sl, " TP=", tp);
   }
   else if(shortOk)
   {
      g_shortTpPrice = tpShort;
      g_longTpPrice = 0.0;
      double sl = NormalizeDouble(slShort, _Digits);
      double tp = NormalizeDouble(tpShort, _Digits);
      StopsNormalize(ORDER_TYPE_SELL, bid, sl, tp);
      if(trade.Sell(InpLotSize, _Symbol, 0.0, sl, tp, "Mamba short"))
         Print("Sell SL=", sl, " TP=", tp);
   }
}

//+------------------------------------------------------------------+
void StopsNormalize(const ENUM_ORDER_TYPE type, double price, double &sl, double &tp)
{
   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = (stopLevel > 0) ? stopLevel * _Point : _Point * 10.0;

   if(type == ORDER_TYPE_BUY)
   {
      if(price - sl < minDist) sl = NormalizeDouble(price - minDist, _Digits);
      if(tp - price < minDist) tp = NormalizeDouble(price + minDist, _Digits);
   }
   else
   {
      if(sl - price < minDist) sl = NormalizeDouble(price + minDist, _Digits);
      if(price - tp < minDist) tp = NormalizeDouble(price - minDist, _Digits);
   }
}

//+------------------------------------------------------------------+
ulong GetPositionTicketByMagic()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      return ticket;
   }
   return 0;
}

//+------------------------------------------------------------------+
void ManageOpenPosition()
{
   ulong ticket = GetPositionTicketByMagic();
   if(ticket == 0 || !PositionSelectByTicket(ticket)) return;

   double atrLive[];
   ArraySetAsSeries(atrLive, true);
   double slBuf = InpSlFixedPts * _Point;
   if(InpSlUseAtr && CopyBuffer(hAtr, 0, 0, 1, atrLive) > 0)
      slBuf = atrLive[0] * InpAtrMult;

   ENUM_POSITION_TYPE ptype = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double smaS[];
   ArraySetAsSeries(smaS, true);
   if(CopyBuffer(hSmaSlow, 0, 0, 2, smaS) < 2) return;
   double ss0 = smaS[0];

   double curSl = PositionGetDouble(POSITION_SL);
   double curTp = PositionGetDouble(POSITION_TP);

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   if(ptype == POSITION_TYPE_BUY)
   {
      double dynSl = NormalizeDouble(ss0 - slBuf, _Digits);
      double openPx = PositionGetDouble(POSITION_PRICE_OPEN);
      if(InpUseTrail)
      {
         double profitPts = (bid - openPx) / _Point;
         if(profitPts >= InpTrailActivatePts)
         {
            double trailSl = NormalizeDouble(bid - InpTrailOffsetPts * _Point, _Digits);
            if(trailSl > dynSl) dynSl = trailSl;
         }
      }
      bool better = (curSl == 0.0) || (dynSl > curSl);
      if(better && dynSl < bid)
      {
         double tp = (g_longTpPrice > 0.0) ? NormalizeDouble(g_longTpPrice, _Digits) : curTp;
         trade.PositionModify(ticket, dynSl, tp);
      }
   }
   else
   {
      double dynSl = NormalizeDouble(ss0 + slBuf, _Digits);
      double openPx = PositionGetDouble(POSITION_PRICE_OPEN);
      if(InpUseTrail)
      {
         double profitPts = (openPx - ask) / _Point;
         if(profitPts >= InpTrailActivatePts)
         {
            double trailSl = NormalizeDouble(ask + InpTrailOffsetPts * _Point, _Digits);
            if(trailSl < dynSl) dynSl = trailSl;
         }
      }
      bool better = (curSl == 0.0) || (dynSl < curSl);
      if(better && dynSl > ask)
      {
         double tp = (g_shortTpPrice > 0.0) ? NormalizeDouble(g_shortTpPrice, _Digits) : curTp;
         trade.PositionModify(ticket, dynSl, tp);
      }
   }
}

//+------------------------------------------------------------------+
