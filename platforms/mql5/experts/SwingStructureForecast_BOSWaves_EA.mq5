//+------------------------------------------------------------------+
//|        SwingStructureForecast_BOSWaves_EA.mq5                     |
//|  EA driven by the BOSWaves Swing Structure Forecast core logic    |
//|  Enters on confirmed swing flip in the forecast direction;        |
//|  TP = projected target (or fib extension), SL = opposing pivot.   |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies — port of BOSWaves Swing Structure Forecast"
#property version   "1.00"

#include <Trade/Trade.mqh>

enum ENUM_FCAST_METHOD { METHOD_WEIGHTED=0, METHOD_AVERAGE=1, METHOD_MEDIAN=2 };

//--- Inputs ---------------------------------------------------------
input group "Detection"
input int    InpSwingLen   = 16;

input group "Forecast"
input int               InpSamples = 20;
input ENUM_FCAST_METHOD InpMethod  = METHOD_WEIGHTED;
input int               InpMinSamples = 3;     // min completed swings before trading

input group "Risk"
input double InpRiskPct       = 1.0;     // % of equity risked per trade
input double InpSLAtrMult     = 1.0;     // ATR(200) buffer added beyond opposing pivot
input bool   InpUseFibTP      = false;   // use fib multiple instead of raw target
input double InpFibTPLevel    = 1.000;   // 1.0 = projected target; 1.272/1.618 also valid
input int    InpMaxBarsInTrade= 0;       // 0 = off; else close after N bars
input bool   InpReverseOnFlip = true;    // close opposite trade on flip

input group "Direction toggles"
input bool   InpAllowLong  = true;
input bool   InpAllowShort = true;

input group "Execution"
input long   InpMagic    = 920501;
input ulong  InpSlippage = 10;           // points
input string InpComment  = "BOSWaves_SSF";

//--- Globals --------------------------------------------------------
CTrade       trade;
int          g_atrHandle = INVALID_HANDLE;
int          g_lastBars  = 0;
datetime     g_entryBar  = 0;

struct Pivot { double price; int idx; datetime time; };
Pivot   g_hi = {0.0, -1, 0};
Pivot   g_lo = {0.0, -1, 0};
bool    g_dir = false;
bool    g_dirInit = false;

double g_pcts[];
double g_durs[];

//+------------------------------------------------------------------+
double ArrAvg(const double &a[])
  {
   int n = ArraySize(a); if(n == 0) return 0.0;
   double s = 0.0; for(int i = 0; i < n; i++) s += a[i];
   return s / n;
  }
double ArrMedian(const double &a[])
  {
   int n = ArraySize(a); if(n == 0) return 0.0;
   double tmp[]; ArrayResize(tmp, n);
   for(int i = 0; i < n; i++) tmp[i] = a[i];
   ArraySort(tmp);
   return (n % 2 == 1) ? tmp[n/2] : 0.5 * (tmp[n/2 - 1] + tmp[n/2]);
  }
double ArrWeighted(const double &a[])
  {
   int n = ArraySize(a); if(n == 0) return 0.0;
   double tw = 0.0, ws = 0.0;
   for(int i = 0; i < n; i++) { double w = i + 1.0; ws += a[i]*w; tw += w; }
   return ws / tw;
  }
void PushCapped(double &arr[], const double v, const int cap)
  {
   int n = ArraySize(arr);
   ArrayResize(arr, n + 1);
   arr[n] = v;
   if(ArraySize(arr) > cap)
     {
      int s = ArraySize(arr);
      for(int i = 0; i < s - 1; i++) arr[i] = arr[i+1];
      ArrayResize(arr, s - 1);
     }
  }

double HighestN(const double &h[], int barIdx, int len)
  {
   double m = -DBL_MAX;
   int from = barIdx - len + 1; if(from < 0) from = 0;
   for(int i = from; i <= barIdx; i++) if(h[i] > m) m = h[i];
   return m;
  }
double LowestN(const double &l[], int barIdx, int len)
  {
   double m = DBL_MAX;
   int from = barIdx - len + 1; if(from < 0) from = 0;
   for(int i = from; i <= barIdx; i++) if(l[i] < m) m = l[i];
   return m;
  }

//+------------------------------------------------------------------+
//|  Position helpers                                                 |
//+------------------------------------------------------------------+
bool HasOpenPosition(ENUM_POSITION_TYPE &outType)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      if((string)PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      outType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
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
      if((string)PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      trade.PositionClose(tk);
     }
  }

double NormalizeLots(double lots)
  {
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   lots = MathFloor(lots / stepLot) * stepLot;
   return NormalizeDouble(lots, 2);
  }

double CalcLotsByRisk(double slDistPrice)
  {
   if(slDistPrice <= 0) return 0.0;
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney  = equity * (InpRiskPct / 100.0);
   double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0) return 0.0;
   double lossPerLot = (slDistPrice / tickSize) * tickValue;
   if(lossPerLot <= 0) return 0.0;
   return NormalizeLots(riskMoney / lossPerLot);
  }

//+------------------------------------------------------------------+
//|  Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber((ulong)InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_atrHandle = iATR(_Symbol, _Period, 200);
   if(g_atrHandle == INVALID_HANDLE) { Print("ATR handle failed"); return INIT_FAILED; }
   g_lastBars = 0;
   g_dirInit  = false;
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
//|  Signal handler invoked once per *new closed* bar                 |
//+------------------------------------------------------------------+
void OnNewBar()
  {
   int bars = iBars(_Symbol, _Period);
   if(bars < InpSwingLen + 5) return;

   //--- pull latest bar series ---
   double h[], l[], c[]; datetime tm[];
   if(CopyHigh (_Symbol, _Period, 0, bars, h)  <= 0) return;
   if(CopyLow  (_Symbol, _Period, 0, bars, l)  <= 0) return;
   if(CopyClose(_Symbol, _Period, 0, bars, c)  <= 0) return;
   if(CopyTime (_Symbol, _Period, 0, bars, tm) <= 0) return;
   ArraySetAsSeries(h,  false);
   ArraySetAsSeries(l,  false);
   ArraySetAsSeries(c,  false);
   ArraySetAsSeries(tm, false);

   double atrBuf[];
   if(CopyBuffer(g_atrHandle, 0, 0, bars, atrBuf) <= 0) return;
   ArraySetAsSeries(atrBuf, false);

   // Process the just-closed bar (index bars-2; bar bars-1 is the live forming bar).
   // To keep behavior bar-close based, scan from g_lastBars to bars-2 inclusive.
   int from = (g_lastBars == 0) ? InpSwingLen : MathMax(g_lastBars - 1, InpSwingLen);
   int to   = bars - 2;
   for(int i = from; i <= to; i++)
     {
      ProcessAndMaybeTrade(i, h, l, c, tm, atrBuf[i]);
     }
   g_lastBars = bars;

   // Time-stop exit
   if(InpMaxBarsInTrade > 0 && g_entryBar > 0)
     {
      ENUM_POSITION_TYPE pt;
      if(HasOpenPosition(pt))
        {
         int barsHeld = iBarShift(_Symbol, _Period, g_entryBar, false);
         if(barsHeld >= InpMaxBarsInTrade)
           {
            CloseOurPositions();
            g_entryBar = 0;
           }
        }
      else g_entryBar = 0;
     }
  }

//+------------------------------------------------------------------+
void ProcessAndMaybeTrade(const int i,
                          const double &h[], const double &l[], const double &c[],
                          const datetime &tm[], const double atrV)
  {
   if(i < InpSwingLen) return;

   double H_i  = HighestN(h, i, InpSwingLen);
   double L_i  = LowestN (l, i, InpSwingLen);
   double H_im = (i >= 1) ? HighestN(h, i-1, InpSwingLen) : H_i;
   double L_im = (i >= 1) ? LowestN (l, i-1, InpSwingLen) : L_i;

   bool prevDir = g_dir;
   if(h[i] >= H_i - 1e-12) g_dir = true;
   if(l[i] <= L_i + 1e-12) g_dir = false;

   if(i >= 1)
     {
      if(MathAbs(h[i-1] - H_im) < 1e-12 && h[i] < H_im)
        { g_hi.idx = i-1; g_hi.price = h[i-1]; g_hi.time = tm[i-1]; }
      if(MathAbs(l[i-1] - L_im) < 1e-12 && l[i] > L_im)
        { g_lo.idx = i-1; g_lo.price = l[i-1]; g_lo.time = tm[i-1]; }
     }

   if(!g_dirInit) { g_dirInit = true; return; }

   if(g_dir == prevDir) return;
   if(g_hi.idx < 0 || g_lo.idx < 0) return;

   //--- Record swing leg ---
   double pct  = (!g_dir)
               ? (g_hi.price - g_lo.price) / g_lo.price * 100.0
               : (g_lo.price - g_hi.price) / g_hi.price * 100.0;
   double bars = (double)MathAbs(g_hi.idx - g_lo.idx);
   PushCapped(g_pcts, MathAbs(pct), InpSamples);
   PushCapped(g_durs, bars,         InpSamples);

   if(ArraySize(g_pcts) < InpMinSamples) return;

   double fPct = 0.0;
   if(InpMethod == METHOD_WEIGHTED)      fPct = ArrWeighted(g_pcts);
   else if(InpMethod == METHOD_MEDIAN)   fPct = ArrMedian(g_pcts);
   else                                  fPct = ArrAvg(g_pcts);
   if(fPct <= 0.0) return;

   //--- Determine trade params ---
   bool wantLong  = ( g_dir) && InpAllowLong;   // flipped to bull
   bool wantShort = (!g_dir) && InpAllowShort;  // flipped to bear
   if(!wantLong && !wantShort) return;

   double origin   = wantLong ? g_lo.price : g_hi.price;
   double rawTgt   = wantLong ? origin * (1.0 + fPct/100.0)
                              : origin * (1.0 - fPct/100.0);
   double tpPrice  = InpUseFibTP
                   ? origin + (rawTgt - origin) * InpFibTPLevel
                   : rawTgt;

   double opposing = wantLong ? g_lo.price : g_hi.price;
   double atrBuf   = (atrV > 0) ? atrV : 0.0;
   double slPrice  = wantLong ? opposing - atrBuf * InpSLAtrMult
                              : opposing + atrBuf * InpSLAtrMult;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry  = wantLong ? ask : bid;
   double slDist = MathAbs(entry - slPrice);
   if(slDist <= _Point * 5) return;

   double lots = CalcLotsByRisk(slDist);
   if(lots <= 0.0) return;

   //--- Manage existing position ---
   ENUM_POSITION_TYPE openType;
   bool hasPos = HasOpenPosition(openType);
   if(hasPos)
     {
      bool oppositeDirection = (wantLong  && openType == POSITION_TYPE_SELL) ||
                               (wantShort && openType == POSITION_TYPE_BUY);
      if(oppositeDirection && InpReverseOnFlip)
        {
         CloseOurPositions();
        }
      else
        {
         return; // skip — same-side position already open, or reverse disabled
        }
     }

   //--- Sanity-check TP relative to entry & SL ---
   if(wantLong  && (tpPrice <= entry || slPrice >= entry)) return;
   if(wantShort && (tpPrice >= entry || slPrice <= entry)) return;

   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   bool ok = false;
   if(wantLong)  ok = trade.Buy (lots, _Symbol, 0.0, slPrice, tpPrice, InpComment);
   if(wantShort) ok = trade.Sell(lots, _Symbol, 0.0, slPrice, tpPrice, InpComment);

   if(ok)
     {
      g_entryBar = TimeCurrent();
     }
   else
     {
      PrintFormat("Order failed: ret=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//|  OnTick — bar-close gated                                         |
//+------------------------------------------------------------------+
void OnTick()
  {
   int bars = iBars(_Symbol, _Period);
   if(bars == g_lastBars) return;
   OnNewBar();
  }
//+------------------------------------------------------------------+
