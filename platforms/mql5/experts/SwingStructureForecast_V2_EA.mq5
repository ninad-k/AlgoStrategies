//+------------------------------------------------------------------+
//|  SwingStructureForecast_V2_EA.mq5                                 |
//|  Author: Ninad Kulkarni                                           |
//|                                                                   |
//|  Strategy v2: trade swing-flip forecast with SMC confluence:      |
//|    1. Internal trend (BOS/CHoCH) must align with the flip dir.   |
//|    2. (optional) Premium/Discount zone filter.                    |
//|    3. (optional) Unmitigated order-block confluence.              |
//|    4. (optional) Use nearest EQH/EQL as TP override.              |
//|  Stop = opposing pivot ± ATR buffer; TP = projected target.       |
//+------------------------------------------------------------------+
#property copyright "Ninad Kulkarni"
#property version   "2.00"

#include <Trade/Trade.mqh>

enum ENUM_FCAST_METHOD { METHOD_WEIGHTED=0, METHOD_AVERAGE=1, METHOD_MEDIAN=2 };
enum ENUM_OB_FILTER    { OB_FILT_ATR=0, OB_FILT_RANGE=1 };
enum ENUM_OB_MITIG     { OB_MITIG_CLOSE=0, OB_MITIG_HIGHLOW=1 };

#define BULLISH  +1
#define BEARISH  -1
#define BULL_LEG  1
#define BEAR_LEG  0

//--- Inputs ---------------------------------------------------------
input group "Forecast Core"
input int    InpSwingLen   = 16;
input int    InpSamples    = 20;
input ENUM_FCAST_METHOD InpMethod = METHOD_WEIGHTED;
input int    InpMinSamples = 3;

input group "SMC Confluence"
input bool   InpUseTrendFilter = true;   // Internal trend must align with flip
input bool   InpUseZoneFilter  = true;   // Long in discount, short in premium
input bool   InpUseOBFilter    = false;  // Need unmitigated same-side OB
input bool   InpUseEQTP        = false;  // Use EQH/EQL as TP override

input group "SMC Structure / OB"
input int    InpInternalLen = 5;
input int    InpEQLen       = 3;
input double InpEQThr       = 0.10;
input ENUM_OB_FILTER InpOBFilter = OB_FILT_ATR;
input ENUM_OB_MITIG  InpOBMitig  = OB_MITIG_HIGHLOW;

input group "Risk / Exits"
input double InpRiskPct       = 1.0;
input double InpSLAtrMult     = 1.0;
input bool   InpUseFibTP      = false;
input double InpFibTPLevel    = 1.000;
input int    InpMaxBarsInTrade= 0;
input bool   InpReverseOnFlip = true;

input group "Direction Toggles"
input bool   InpAllowLong  = true;
input bool   InpAllowShort = true;

input group "Execution"
input long   InpMagic    = 920502;
input ulong  InpSlippage = 10;
input string InpComment  = "SSF_V2";

//--- Globals --------------------------------------------------------
CTrade   trade;
int      g_atrHandle = INVALID_HANDLE;
int      g_lastBars  = 0;
datetime g_entryBar  = 0;

struct PivotF { double price; int idx; datetime time; };
PivotF g_hi = {0.0, -1, 0};
PivotF g_lo = {0.0, -1, 0};
bool   g_dir = false;
bool   g_dirInit = false;

double g_pcts[];
double g_durs[];

struct SmcPivot
  {
   double   curLevel;
   double   lastLevel;
   bool     crossed;
   datetime barTime;
   int      barIndex;
  };
SmcPivot g_intHi = {0,0,false,0,-1};
SmcPivot g_intLo = {0,0,false,0,-1};
SmcPivot g_eqHi  = {0,0,false,0,-1};
SmcPivot g_eqLo  = {0,0,false,0,-1};
int g_intTrend = 0;
int g_intLeg = 0, g_eqLeg = 0;
int g_lastIntLeg = 0, g_lastEqLeg = 0;

double g_trailTop = -DBL_MAX;
double g_trailBot =  DBL_MAX;

double g_lastEQH = 0.0;
double g_lastEQL = 0.0;

struct OrderBlock { double barHigh; double barLow; datetime barTime; int bias; };
OrderBlock g_intOBs[];

//+------------------------------------------------------------------+
double ArrAvg(const double &a[])      { int n=ArraySize(a); if(n==0) return 0; double s=0; for(int i=0;i<n;i++) s+=a[i]; return s/n; }
double ArrMedian(const double &a[])
  {
   int n=ArraySize(a); if(n==0) return 0;
   double t[]; ArrayResize(t,n);
   for(int i=0;i<n;i++) t[i]=a[i];
   ArraySort(t);
   return (n%2==1) ? t[n/2] : 0.5*(t[n/2-1]+t[n/2]);
  }
double ArrWeighted(const double &a[]) { int n=ArraySize(a); if(n==0) return 0; double tw=0,ws=0; for(int i=0;i<n;i++){double w=i+1.0; ws+=a[i]*w; tw+=w;} return ws/tw; }
void   PushCapped(double &a[], const double v, const int cap)
  {
   int n=ArraySize(a); ArrayResize(a,n+1); a[n]=v;
   if(ArraySize(a)>cap){ int s=ArraySize(a); for(int i=0;i<s-1;i++) a[i]=a[i+1]; ArrayResize(a,s-1); }
  }

double HighestN(const double &h[], int barIdx, int len)
  {
   double m=-DBL_MAX;
   int from=barIdx-len+1; if(from<0) from=0;
   for(int i=from;i<=barIdx;i++) if(h[i]>m) m=h[i];
   return m;
  }
double LowestN(const double &l[], int barIdx, int len)
  {
   double m=DBL_MAX;
   int from=barIdx-len+1; if(from<0) from=0;
   for(int i=from;i<=barIdx;i++) if(l[i]<m) m=l[i];
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
int OnInit()
  {
   trade.SetExpertMagicNumber((ulong)InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_atrHandle = iATR(_Symbol, _Period, 200);
   if(g_atrHandle == INVALID_HANDLE) return INIT_FAILED;
   g_lastBars = 0;
   g_dirInit  = false;
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
//|  SMC: leg detection                                              |
//+------------------------------------------------------------------+
int LegState(const double &h[], const double &l[], int barIdx, int size, int &lastState)
  {
   if(barIdx < size + 1) return lastState;
   int pivBar = barIdx - size;
   if(pivBar < 0) return lastState;
   double maxAfter = -DBL_MAX, minAfter = DBL_MAX;
   for(int k = pivBar + 1; k <= barIdx; k++)
     {
      if(h[k] > maxAfter) maxAfter = h[k];
      if(l[k] < minAfter) minAfter = l[k];
     }
   if(h[pivBar] > maxAfter)      lastState = BEAR_LEG;
   else if(l[pivBar] < minAfter) lastState = BULL_LEG;
   return lastState;
  }

//+------------------------------------------------------------------+
//|  SMC: capture pivots                                             |
//+------------------------------------------------------------------+
void CaptureSmcStructure(const int barIdx, const int size, const bool equalMode, const bool internal,
                         const double &h[], const double &l[], const datetime &tm[], const double atrV)
  {
   int prev = equalMode ? g_lastEqLeg : g_lastIntLeg;
   int newCur = equalMode ? LegState(h,l,barIdx,size,g_eqLeg) : LegState(h,l,barIdx,size,g_intLeg);
   bool isNew = (newCur != prev);
   if(equalMode) g_lastEqLeg = newCur;
   else          g_lastIntLeg = newCur;
   if(!isNew) return;
   bool isLow = (newCur == BULL_LEG);
   int pivBar = barIdx - size;
   if(pivBar < 0) return;
   if(isLow)
     {
      if(equalMode)
        {
         if(MathAbs(g_eqLo.curLevel - l[pivBar]) < InpEQThr * atrV && g_eqLo.barIndex >= 0)
            g_lastEQL = l[pivBar];
         g_eqLo.lastLevel = g_eqLo.curLevel;
         g_eqLo.curLevel  = l[pivBar];
         g_eqLo.crossed   = false;
         g_eqLo.barTime   = tm[pivBar];
         g_eqLo.barIndex  = pivBar;
        }
      else
        {
         g_intLo.lastLevel = g_intLo.curLevel;
         g_intLo.curLevel  = l[pivBar];
         g_intLo.crossed   = false;
         g_intLo.barTime   = tm[pivBar];
         g_intLo.barIndex  = pivBar;
        }
     }
   else
     {
      if(equalMode)
        {
         if(MathAbs(g_eqHi.curLevel - h[pivBar]) < InpEQThr * atrV && g_eqHi.barIndex >= 0)
            g_lastEQH = h[pivBar];
         g_eqHi.lastLevel = g_eqHi.curLevel;
         g_eqHi.curLevel  = h[pivBar];
         g_eqHi.crossed   = false;
         g_eqHi.barTime   = tm[pivBar];
         g_eqHi.barIndex  = pivBar;
        }
      else
        {
         g_intHi.lastLevel = g_intHi.curLevel;
         g_intHi.curLevel  = h[pivBar];
         g_intHi.crossed   = false;
         g_intHi.barTime   = tm[pivBar];
         g_intHi.barIndex  = pivBar;
        }
     }
  }

//+------------------------------------------------------------------+
//|  SMC: BOS/CHoCH detection — updates internal trend + OBs         |
//+------------------------------------------------------------------+
void StoreOB(const int bias, const double &h[], const double &l[], const datetime &tm[])
  {
   SmcPivot p = (bias==BULLISH) ? g_intHi : g_intLo;
   if(p.barIndex < 0) return;
   int from = p.barIndex, to = ArraySize(h) - 1;
   if(from >= to) return;
   int pickIdx = from;
   if(bias == BEARISH)
     {
      double mx = -DBL_MAX;
      for(int i = from; i <= to; i++) if(h[i] > mx) { mx = h[i]; pickIdx = i; }
     }
   else
     {
      double mn = DBL_MAX;
      for(int i = from; i <= to; i++) if(l[i] < mn) { mn = l[i]; pickIdx = i; }
     }
   OrderBlock ob;
   ob.barHigh = h[pickIdx];
   ob.barLow  = l[pickIdx];
   ob.barTime = tm[pickIdx];
   ob.bias    = bias;
   int n = ArraySize(g_intOBs);
   ArrayResize(g_intOBs, n + 1);
   for(int i = n; i > 0; i--) g_intOBs[i] = g_intOBs[i-1];
   g_intOBs[0] = ob;
   if(ArraySize(g_intOBs) > 100) ArrayResize(g_intOBs, 100);
  }

void DeleteMitigatedOBs(const double curClose, const double curHigh, const double curLow)
  {
   double bearSrc = (InpOBMitig == OB_MITIG_CLOSE) ? curClose : curHigh;
   double bullSrc = (InpOBMitig == OB_MITIG_CLOSE) ? curClose : curLow;
   for(int i = ArraySize(g_intOBs) - 1; i >= 0; i--)
     {
      bool kill = false;
      if(g_intOBs[i].bias == BEARISH && bearSrc > g_intOBs[i].barHigh) kill = true;
      if(g_intOBs[i].bias == BULLISH && bullSrc < g_intOBs[i].barLow ) kill = true;
      if(kill)
        {
         int s = ArraySize(g_intOBs);
         for(int k = i; k < s-1; k++) g_intOBs[k] = g_intOBs[k+1];
         ArrayResize(g_intOBs, s-1);
        }
     }
  }

void DetectInternalStructure(const int barIdx, const double curClose,
                             const double &h[], const double &l[], const datetime &tm[])
  {
   if(!g_intHi.crossed && curClose > g_intHi.curLevel && g_intHi.curLevel > 0)
     {
      g_intHi.crossed = true;
      g_intTrend = BULLISH;
      StoreOB(BULLISH, h, l, tm);
     }
   if(!g_intLo.crossed && curClose < g_intLo.curLevel && g_intLo.curLevel > 0)
     {
      g_intLo.crossed = true;
      g_intTrend = BEARISH;
      StoreOB(BEARISH, h, l, tm);
     }
  }

//+------------------------------------------------------------------+
//|  Forecast pivot detection + trade decision                       |
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

   // Record swing leg
   double pct  = (!g_dir)
               ? (g_hi.price - g_lo.price) / g_lo.price * 100.0
               : (g_lo.price - g_hi.price) / g_hi.price * 100.0;
   double bars = (double)MathAbs(g_hi.idx - g_lo.idx);
   PushCapped(g_pcts, MathAbs(pct), InpSamples);
   PushCapped(g_durs, bars,         InpSamples);

   if(ArraySize(g_pcts) < InpMinSamples) return;

   double fPct = (InpMethod == METHOD_WEIGHTED) ? ArrWeighted(g_pcts) :
                 (InpMethod == METHOD_MEDIAN)   ? ArrMedian(g_pcts)   : ArrAvg(g_pcts);
   if(fPct <= 0.0) return;

   bool wantLong  = ( g_dir) && InpAllowLong;
   bool wantShort = (!g_dir) && InpAllowShort;
   if(!wantLong && !wantShort) return;

   double curClose = c[i];

   //--- Confluence filters ---
   bool trendOK = !InpUseTrendFilter ||
                  (wantLong  && g_intTrend == BULLISH) ||
                  (wantShort && g_intTrend == BEARISH);
   if(!trendOK) return;

   bool zoneOK = true;
   if(InpUseZoneFilter && g_trailTop > -DBL_MAX/2 && g_trailBot < DBL_MAX/2)
     {
      double mid = (g_trailTop + g_trailBot) / 2.0;
      zoneOK = wantLong ? (curClose <= mid) : (curClose >= mid);
     }
   if(!zoneOK) return;

   bool obOK = true;
   if(InpUseOBFilter)
     {
      bool found = false;
      for(int k = 0; k < ArraySize(g_intOBs); k++)
        {
         if(wantLong  && g_intOBs[k].bias == BULLISH && g_intOBs[k].barHigh < curClose) { found = true; break; }
         if(wantShort && g_intOBs[k].bias == BEARISH && g_intOBs[k].barLow  > curClose) { found = true; break; }
        }
      obOK = found;
     }
   if(!obOK) return;

   //--- Compute trade levels ---
   double origin   = wantLong ? g_lo.price : g_hi.price;
   double rawTgt   = wantLong ? origin * (1.0 + fPct/100.0)
                              : origin * (1.0 - fPct/100.0);
   double fcastTP  = InpUseFibTP
                   ? origin + (rawTgt - origin) * InpFibTPLevel
                   : rawTgt;

   double tpPrice = fcastTP;
   if(InpUseEQTP)
     {
      if(wantLong  && g_lastEQH > 0 && g_lastEQH > curClose && g_lastEQH < fcastTP) tpPrice = g_lastEQH;
      if(wantShort && g_lastEQL > 0 && g_lastEQL < curClose && g_lastEQL > fcastTP) tpPrice = g_lastEQL;
     }

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

   ENUM_POSITION_TYPE openType;
   bool hasPos = HasOpenPosition(openType);
   if(hasPos)
     {
      bool oppositeDirection = (wantLong  && openType == POSITION_TYPE_SELL) ||
                               (wantShort && openType == POSITION_TYPE_BUY);
      if(oppositeDirection && InpReverseOnFlip) CloseOurPositions();
      else                                      return;
     }

   if(wantLong  && (tpPrice <= entry || slPrice >= entry)) return;
   if(wantShort && (tpPrice >= entry || slPrice <= entry)) return;

   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   bool ok = false;
   if(wantLong)  ok = trade.Buy (lots, _Symbol, 0.0, slPrice, tpPrice, InpComment);
   if(wantShort) ok = trade.Sell(lots, _Symbol, 0.0, slPrice, tpPrice, InpComment);

   if(ok) g_entryBar = TimeCurrent();
   else   PrintFormat("Order failed: ret=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//|  Per-bar processor                                               |
//+------------------------------------------------------------------+
void OnNewBar()
  {
   int bars = iBars(_Symbol, _Period);
   if(bars < InpSwingLen + 50) return;

   double h[], l[], c[]; datetime tm[];
   if(CopyHigh (_Symbol, _Period, 0, bars, h)  <= 0) return;
   if(CopyLow  (_Symbol, _Period, 0, bars, l)  <= 0) return;
   if(CopyClose(_Symbol, _Period, 0, bars, c)  <= 0) return;
   if(CopyTime (_Symbol, _Period, 0, bars, tm) <= 0) return;
   ArraySetAsSeries(h, false);
   ArraySetAsSeries(l, false);
   ArraySetAsSeries(c, false);
   ArraySetAsSeries(tm, false);

   double atrBuf[];
   if(CopyBuffer(g_atrHandle, 0, 0, bars, atrBuf) <= 0) return;
   ArraySetAsSeries(atrBuf, false);

   int from = (g_lastBars == 0) ? InpInternalLen + 5 : MathMax(g_lastBars - 1, InpInternalLen + 5);
   int to   = bars - 2;
   for(int i = from; i <= to; i++)
     {
      double atrV = (atrBuf[i] > 0) ? atrBuf[i] : 0.0;
      // Update SMC state (internal pivots + EQ + trend)
      CaptureSmcStructure(i, InpInternalLen, false, true, h, l, tm, atrV);
      CaptureSmcStructure(i, InpEQLen, true, false, h, l, tm, atrV);
      DetectInternalStructure(i, c[i], h, l, tm);
      DeleteMitigatedOBs(c[i], h[i], l[i]);
      // Trailing extremes for premium/discount filter
      if(h[i] > g_trailTop) g_trailTop = h[i];
      if(l[i] < g_trailBot) g_trailBot = l[i];
      // Forecast flip + maybe trade
      ProcessAndMaybeTrade(i, h, l, c, tm, atrV);
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
void OnTick()
  {
   int bars = iBars(_Symbol, _Period);
   if(bars == g_lastBars) return;
   OnNewBar();
  }
//+------------------------------------------------------------------+
