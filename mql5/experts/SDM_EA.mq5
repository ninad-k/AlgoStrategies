//+------------------------------------------------------------------+
//| SDM_EA.mq5                                                       |
//| SuperTrend + MACD + ADX (Same-Bar Entries, Close-Only Exits)     |
//| Port of the Pine Script "SDM" indicator/strategy.                |
//|                                                                  |
//| Logic (evaluated only on confirmed bar close):                   |
//|   - SuperTrend (TV-style: Wilder ATR + sticky final bands,       |
//|     direction flips when close crosses opposite final band).    |
//|   - MACD(12, 26, 9) crossover of macdLine vs signalLine.         |
//|   - ADX(14, 14) value within [20, 35].                           |
//| Entry: flat AND ST flips AND MACD crosses in same direction      |
//|        AND ADX in range, all on the same just-closed bar.        |
//| Exit : only when SuperTrend flips against the open position      |
//|        (close-only).                                             |
//| Author: Ninad K                                                  |
//+------------------------------------------------------------------+
#property copyright "Ninad K"
#property version   "1.00"
#property description "SDM: SuperTrend(7,2) + MACD(12,26,9) + ADX(14) in 20..35. Entries on a confirmed bar close when ST flips and MACD crosses the same direction. Exits only on ST flip."

#include <Trade\Trade.mqh>
CTrade trade;

//--- SuperTrend
input group "=== SuperTrend ==="
input int    InpAtrPeriod = 7;     // SuperTrend ATR period
input double InpFactor    = 2.0;   // SuperTrend factor

//--- MACD
input group "=== MACD ==="
input int InpMacdFast   = 12;      // MACD fast length
input int InpMacdSlow   = 26;      // MACD slow length
input int InpMacdSignal = 9;       // MACD signal length

//--- ADX
input group "=== ADX ==="
input int    InpAdxLen = 14;       // ADX length / smoothing
input double InpAdxMin = 20.0;     // ADX minimum (inclusive)
input double InpAdxMax = 35.0;     // ADX maximum (inclusive)

//--- Trading
input group "=== Trading ==="
input double InpLots        = 0.10;   // Order size (lots)
input double InpStopLossPts = 0.0;    // SL distance in points (0 = none)
input double InpTakePts     = 0.0;    // TP distance in points (0 = none)
input int    InpMagic       = 770077; // Magic number
input int    InpSlippage    = 20;     // Slippage in points

//--- Runtime
int      hMacd = INVALID_HANDLE;
int      hAdx  = INVALID_HANDLE;
datetime lastBarTime = 0;
double   gPoint = 0.0;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpAtrPeriod < 1 || InpFactor <= 0.0)
   {
      Alert("SDM: invalid SuperTrend parameters");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpMacdFast < 1 || InpMacdSlow <= InpMacdFast || InpMacdSignal < 1)
   {
      Alert("SDM: invalid MACD parameters");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpAdxLen < 1 || InpAdxMin > InpAdxMax)
   {
      Alert("SDM: invalid ADX parameters");
      return INIT_PARAMETERS_INCORRECT;
   }

   hMacd = iMACD(_Symbol, PERIOD_CURRENT, InpMacdFast, InpMacdSlow, InpMacdSignal, PRICE_CLOSE);
   hAdx  = iADX (_Symbol, PERIOD_CURRENT, InpAdxLen);
   if(hMacd == INVALID_HANDLE || hAdx == INVALID_HANDLE)
   {
      Alert("SDM: failed to create indicator handles");
      return INIT_FAILED;
   }

   gPoint = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints((ulong)InpSlippage);
   trade.SetTypeFilling(ORDER_FILLING_FOK);

   lastBarTime = 0;
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hMacd != INVALID_HANDLE) IndicatorRelease(hMacd);
   if(hAdx  != INVALID_HANDLE) IndicatorRelease(hAdx);
}

//+------------------------------------------------------------------+
//| Compute Wilder/RMA ATR over the requested history (ascending).   |
//| Returns false if history is insufficient.                        |
//+------------------------------------------------------------------+
bool WilderATR(int total, const double &high[], const double &low[], const double &close[], double &atr[])
{
   if(total < InpAtrPeriod + 2) return false;
   ArrayResize(atr, total);
   ArrayInitialize(atr, 0.0);

   double trsum = 0.0;
   for(int i = 1; i < total; i++)
   {
      double tr = MathMax(high[i] - low[i],
                          MathMax(MathAbs(high[i] - close[i-1]),
                                  MathAbs(low[i]  - close[i-1])));
      if(i < InpAtrPeriod)
         trsum += tr;
      else if(i == InpAtrPeriod)
      {
         trsum += tr;
         atr[i] = trsum / InpAtrPeriod;
      }
      else
         atr[i] = (atr[i-1] * (InpAtrPeriod - 1) + tr) / InpAtrPeriod;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Compute TV-style SuperTrend series in ascending order.           |
//|   trend[i] : the SuperTrend line value                          |
//|   dir[i]   : +1 (uptrend) or -1 (downtrend)                     |
//|   fu[i]    : final upper band                                    |
//|   fl[i]    : final lower band                                    |
//+------------------------------------------------------------------+
bool ComputeSuperTrend(int needBars,
                       double &trend[], int &dir[],
                       double &fu[],    double &fl[],
                       int &outTotal)
{
   int total = needBars + InpAtrPeriod + 50;
   double high[], low[], close[];
   if(CopyHigh (_Symbol, PERIOD_CURRENT, 0, total, high)  < total) return false;
   if(CopyLow  (_Symbol, PERIOD_CURRENT, 0, total, low)   < total) return false;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 0, total, close) < total) return false;
   ArraySetAsSeries(high,  false);
   ArraySetAsSeries(low,   false);
   ArraySetAsSeries(close, false);

   double atr[];
   if(!WilderATR(total, high, low, close, atr)) return false;

   ArrayResize(trend, total);
   ArrayResize(dir,   total);
   ArrayResize(fu,    total);
   ArrayResize(fl,    total);
   for(int i = 0; i < total; i++)
   {
      trend[i] = 0.0;
      dir[i]   = -1;
      fu[i]    = 0.0;
      fl[i]    = 0.0;
   }

   for(int i = InpAtrPeriod; i < total; i++)
   {
      double m  = (high[i] + low[i]) * 0.5;
      double bu = m + InpFactor * atr[i];
      double bl = m - InpFactor * atr[i];

      double prevFU    = fu[i-1];
      double prevFL    = fl[i-1];
      double prevClose = close[i-1];

      // Sticky final bands (TV behaviour)
      fu[i] = (prevFU == 0.0) ? bu : ((bu < prevFU || prevClose > prevFU) ? bu : prevFU);
      fl[i] = (prevFL == 0.0) ? bl : ((bl > prevFL || prevClose < prevFL) ? bl : prevFL);

      int prevDir = (i > InpAtrPeriod) ? dir[i-1] : -1;
      int d = prevDir;
      if(close[i] > fu[i-1]) d =  1;
      else if(close[i] < fl[i-1]) d = -1;
      dir[i] = d;
      trend[i] = (d == 1) ? fl[i] : fu[i];
   }

   outTotal = total;
   return true;
}

//+------------------------------------------------------------------+
//| Position helpers                                                 |
//+------------------------------------------------------------------+
bool GetOurPosition(ENUM_POSITION_TYPE &ptype, ulong &ticket)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ptype  = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      ticket = tk;
      return true;
   }
   return false;
}

void CloseOurPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      trade.PositionClose(tk);
   }
}

//+------------------------------------------------------------------+
//| Open a market position with optional SL/TP in points             |
//+------------------------------------------------------------------+
void OpenPosition(bool isBuy)
{
   double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                        : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = 0.0, tp = 0.0;
   if(InpStopLossPts > 0.0)
      sl = isBuy ? price - InpStopLossPts * gPoint
                 : price + InpStopLossPts * gPoint;
   if(InpTakePts > 0.0)
      tp = isBuy ? price + InpTakePts * gPoint
                 : price - InpTakePts * gPoint;

   if(isBuy)
      trade.Buy(InpLots, _Symbol, price, sl, tp, "SDM Buy");
   else
      trade.Sell(InpLots, _Symbol, price, sl, tp, "SDM Sell");
}

//+------------------------------------------------------------------+
//| OnTick: bar-close evaluation                                     |
//+------------------------------------------------------------------+
void OnTick()
{
   // Trigger only on a new bar (i.e. previous bar just closed)
   datetime t0 = (datetime)SeriesInfoInteger(_Symbol, PERIOD_CURRENT, SERIES_LASTBAR_DATE);
   if(t0 == lastBarTime) return;
   if(lastBarTime == 0) { lastBarTime = t0; return; }
   lastBarTime = t0;

   // Need MACD + ADX history; recompute SuperTrend over history
   int needBars = MathMax(InpMacdSlow + InpMacdSignal, InpAdxLen * 3) + 50;

   double stTrend[], stFU[], stFL[];
   int    stDir[];
   int    total = 0;
   if(!ComputeSuperTrend(needBars, stTrend, stDir, stFU, stFL, total))
      return;
   if(total < 4) return;

   // Indices: total-1 is the just-opened (current) bar; the just-closed bar is total-2.
   int iCur  = total - 2;   // last closed bar
   int iPrev = total - 3;   // bar before that
   if(iPrev < InpAtrPeriod + 1) return;

   bool flipUpClose   = (stDir[iCur] ==  1 && stDir[iPrev] == -1);
   bool flipDownClose = (stDir[iCur] == -1 && stDir[iPrev] ==  1);

   // MACD: shift=0 is current (forming) bar, shift=1 is last closed bar
   double macdMain[2], macdSig[2];
   if(CopyBuffer(hMacd, MAIN_LINE,   1, 2, macdMain) < 2) return;
   if(CopyBuffer(hMacd, SIGNAL_LINE, 1, 2, macdSig)  < 2) return;
   // CopyBuffer gives ascending: index 0 = older (iPrev equiv), index 1 = newer (iCur equiv)
   bool macdCrossUp   = (macdMain[0] <= macdSig[0]) && (macdMain[1] >  macdSig[1]);
   bool macdCrossDown = (macdMain[0] >= macdSig[0]) && (macdMain[1] <  macdSig[1]);

   // ADX value at the just-closed bar
   double adxBuf[1];
   if(CopyBuffer(hAdx, MAIN_LINE, 1, 1, adxBuf) < 1) return;
   double adx = adxBuf[0];
   bool adxInRange = (adx >= InpAdxMin && adx <= InpAdxMax);

   // Position state
   ENUM_POSITION_TYPE curType;
   ulong curTicket;
   bool hasPos = GetOurPosition(curType, curTicket);
   bool inLong  = hasPos && curType == POSITION_TYPE_BUY;
   bool inShort = hasPos && curType == POSITION_TYPE_SELL;

   // Exits: only on ST flip against position (close-only)
   if(inLong && flipDownClose)
   {
      CloseOurPositions();
      hasPos = false; inLong = false;
   }
   else if(inShort && flipUpClose)
   {
      CloseOurPositions();
      hasPos = false; inShort = false;
   }

   bool flat = !inLong && !inShort && !hasPos;

   // Entries: same bar requires ST flip + MACD cross + ADX in range
   bool buyEntry  = flat && flipUpClose   && macdCrossUp   && adxInRange;
   bool sellEntry = flat && flipDownClose && macdCrossDown && adxInRange;

   if(buyEntry)
      OpenPosition(true);
   else if(sellEntry)
      OpenPosition(false);
}
//+------------------------------------------------------------------+
