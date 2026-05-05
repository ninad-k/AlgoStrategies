//+------------------------------------------------------------------+
//|  SwingStructureForecast_V2.mq5                                    |
//|  Author: Ninad Kulkarni                                           |
//|                                                                   |
//|  v2 = forecast core + Smart Money Concepts confluence:            |
//|    - swing pivots (rolling highest/lowest over swingLen)          |
//|    - S/R zones, projection beam, target box, fib extensions       |
//|    - internal & swing BOS / CHoCH structure                       |
//|    - internal & swing order blocks                                |
//|    - equal high / equal low (EQH / EQL)                           |
//|    - fair value gaps (current TF)                                 |
//|    - trailing strong/weak high & low                              |
//|    - premium / discount zones                                     |
//|    - daily / weekly / monthly MTF levels                          |
//+------------------------------------------------------------------+
#property copyright "Ninad Kulkarni"
#property version   "2.00"
#property indicator_chart_window
#property indicator_plots 0

#define PFX "SSF2_"

enum ENUM_FCAST_METHOD { METHOD_WEIGHTED=0, METHOD_AVERAGE=1, METHOD_MEDIAN=2 };
enum ENUM_OB_FILTER    { OB_FILT_ATR=0, OB_FILT_RANGE=1 };
enum ENUM_OB_MITIG     { OB_MITIG_CLOSE=0, OB_MITIG_HIGHLOW=1 };

//--- Forecast core --------------------------------------------------
input group "Forecast Core"
input int    InpSwingLen = 16;
input int    InpSamples  = 20;
input ENUM_FCAST_METHOD InpMethod = METHOD_WEIGHTED;
input int    InpFwdBars  = 5;
input bool   InpShowBeam   = true;
input bool   InpShowTarget = true;
input bool   InpShowDots   = true;
input bool   InpShowFibs   = true;
input bool   InpFib1On = true;  input double InpFib1V = 1.000;
input bool   InpFib2On = true;  input double InpFib2V = 1.272;
input bool   InpFib3On = true;  input double InpFib3V = 1.618;
input bool   InpFib4On = false; input double InpFib4V = 2.000;
input bool   InpFib5On = false; input double InpFib5V = 2.618;

input group "S/R Zones"
input bool   InpShowLevels = true;
input double InpZoneATR    = 0.30;
input int    InpMaxAge     = 300;

input group "SMC — Internal/Swing"
input int    InpInternalLen = 5;
input int    InpSwingSmcLen = 50;
input bool   InpShowIntStr  = true;
input bool   InpShowSwStr   = true;
input bool   InpShowIntOB   = true;
input bool   InpShowSwOB    = false;
input int    InpIntOBSize   = 5;
input int    InpSwOBSize    = 5;
input ENUM_OB_FILTER InpOBFilter = OB_FILT_ATR;
input ENUM_OB_MITIG  InpOBMitig  = OB_MITIG_HIGHLOW;

input group "SMC — EQH/EQL"
input bool   InpShowEQ = true;
input int    InpEQLen  = 3;
input double InpEQThr  = 0.10;

input group "SMC — FVG"
input bool   InpShowFVG = false;
input bool   InpFVGAuto = true;
input int    InpFVGExt  = 1;

input group "SMC — Strong/Weak + PD"
input bool   InpShowStrongWeak = true;
input bool   InpShowPD         = false;

input group "SMC — MTF Levels"
input bool   InpShowDaily   = false;
input bool   InpShowWeekly  = false;
input bool   InpShowMonthly = false;

input group "Colors"
input color  InpBullClr = clrLime;
input color  InpBearClr = clrRed;
input color  InpProjClr = clrDodgerBlue;
input color  InpFibClr  = clrGold;
input color  InpSwBullClr = clrSeaGreen;
input color  InpSwBearClr = clrCrimson;
input color  InpIntBullClr = clrDarkGreen;
input color  InpIntBearClr = clrDarkRed;
input color  InpBullOBClr  = clrRoyalBlue;
input color  InpBearOBClr  = clrLightCoral;
input color  InpFVGBullClr = clrLimeGreen;
input color  InpFVGBearClr = clrTomato;
input color  InpPremClr    = clrCrimson;
input color  InpDiscClr    = clrSeaGreen;
input color  InpEQuilClr   = clrGray;
input color  InpMTFClr     = clrDodgerBlue;

//--- Constants ------------------------------------------------------
#define BULLISH  +1
#define BEARISH  -1
#define BULL_LEG  1
#define BEAR_LEG  0

//--- Pivot tracker (forecast core) ---------------------------------
struct PivotF { double price; int idx; datetime time; };
PivotF g_hi = {0.0, -1, 0};
PivotF g_lo = {0.0, -1, 0};
bool   g_dir = false;
bool   g_dirInit = false;

//--- S/R zones ------------------------------------------------------
struct SRZone
  {
   double   price;
   int      startIdx;
   datetime startTime;
   bool     isResistance;
   bool     broken;
   string   nameOuter;
   string   nameInner;
   string   nameLine;
  };
SRZone g_zones[];
int    g_zoneSeq = 0;

//--- Swing history --------------------------------------------------
double g_pcts[];
double g_durs[];

//--- SMC pivot trackers --------------------------------------------
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
SmcPivot g_swHi  = {0,0,false,0,-1};
SmcPivot g_swLo  = {0,0,false,0,-1};
SmcPivot g_eqHi  = {0,0,false,0,-1};
SmcPivot g_eqLo  = {0,0,false,0,-1};
int g_intTrend = 0;
int g_swTrend  = 0;
int g_intLeg = 0, g_swLeg = 0, g_eqLeg = 0;
int g_lastIntLeg = 0, g_lastSwLeg = 0, g_lastEqLeg = 0;

//--- Order blocks ---------------------------------------------------
struct OrderBlock
  {
   double   barHigh;
   double   barLow;
   datetime barTime;
   int      bias;
   string   nameBox;
  };
OrderBlock g_intOBs[];
OrderBlock g_swOBs[];
int g_obSeq = 0;

//--- FVGs -----------------------------------------------------------
struct FVG
  {
   double   top;
   double   bot;
   int      bias;
   string   nameTop;
   string   nameBot;
  };
FVG g_fvgs[];
int g_fvgSeq = 0;

//--- Trailing extremes ---------------------------------------------
struct Trailing
  {
   double top;
   double bot;
   datetime barTime;
   int barIndex;
   datetime lastTopTime;
   datetime lastBotTime;
  };
Trailing g_trail = {-DBL_MAX, DBL_MAX, 0, -1, 0, 0};

//--- ATR handle -----------------------------------------------------
int g_atrHandle = INVALID_HANDLE;
int g_lastBars = 0;

//+------------------------------------------------------------------+
//|  Color blend (transparency emulation)                            |
//+------------------------------------------------------------------+
color BlendAlpha(const color base, const int transparency)
  {
   long bgL = ChartGetInteger(0, CHART_COLOR_BACKGROUND, 0);
   color bg = (color)bgL;
   double t = MathMax(0.0, MathMin(100.0, (double)transparency)) / 100.0;
   int br = (base       & 0xFF);
   int bgn= (base >> 8) & 0xFF;
   int bb = (base >>16) & 0xFF;
   int gr = (bg         & 0xFF);
   int gg = (bg  >> 8 ) & 0xFF;
   int gB = (bg  >> 16) & 0xFF;
   int rr = (int)MathRound(br + (gr - br) * t);
   int gG = (int)MathRound(bgn + (gg - bgn) * t);
   int rB = (int)MathRound(bb + (gB - bb) * t);
   return (color)((rB << 16) | (gG << 8) | rr);
  }

//+------------------------------------------------------------------+
datetime BarTime(const int shiftFromCurrent)
  {
   datetime t0 = iTime(_Symbol, _Period, 0);
   return t0 + (datetime)(shiftFromCurrent * PeriodSeconds());
  }

//+------------------------------------------------------------------+
bool CreateRect(const string name, datetime t1, double p1, datetime t2, double p2, color c, bool back=true)
  {
   ObjectDelete(0, name);
   if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2)) return false;
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, back);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   return true;
  }

bool CreateTrend(const string name, datetime t1, double p1, datetime t2, double p2,
                 color c, ENUM_LINE_STYLE st=STYLE_SOLID, int width=1, bool back=false)
  {
   ObjectDelete(0, name);
   if(!ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2)) return false;
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_STYLE, st);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, back);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   return true;
  }

bool CreateText(const string name, datetime t, double p, const string txt, color c, int fontsize=9,
                ENUM_ANCHOR_POINT anchor=ANCHOR_LEFT)
  {
   ObjectDelete(0, name);
   if(!ObjectCreate(0, name, OBJ_TEXT, 0, t, p)) return false;
   ObjectSetString (0, name, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontsize);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   return true;
  }

void DeleteByPrefix(const string prefix)
  {
   int total = ObjectsTotal(0, -1, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, -1, -1);
      if(StringFind(nm, prefix) == 0) ObjectDelete(0, nm);
     }
  }

//+------------------------------------------------------------------+
//|  Init / Deinit                                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   ArrayResize(g_zones, 0);
   ArrayResize(g_pcts, 0);
   ArrayResize(g_durs, 0);
   ArrayResize(g_intOBs, 0);
   ArrayResize(g_swOBs, 0);
   ArrayResize(g_fvgs, 0);
   g_atrHandle = iATR(_Symbol, _Period, 200);
   if(g_atrHandle == INVALID_HANDLE) return INIT_FAILED;
   DeleteByPrefix(PFX);
   g_lastBars = 0;
   g_dirInit  = false;
   g_intTrend = 0; g_swTrend = 0;
   ChartRedraw(0);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   DeleteByPrefix(PFX);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//|  Stat / array helpers                                            |
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
//|  S/R zones — manage / age / fade                                 |
//+------------------------------------------------------------------+
void UpdateSRZones(const int curBarIdx, const datetime curTime, const double curClose)
  {
   datetime rightT = BarTime(5);
   for(int i = ArraySize(g_zones) - 1; i >= 0; i--)
     {
      int age = curBarIdx - g_zones[i].startIdx;
      color cBase = g_zones[i].isResistance ? InpBearClr : InpBullClr;
      if(!g_zones[i].broken)
        {
         bool brokeUp   =  g_zones[i].isResistance && curClose > g_zones[i].price;
         bool brokeDown = !g_zones[i].isResistance && curClose < g_zones[i].price;
         if(brokeUp || brokeDown)
           {
            g_zones[i].broken = true;
            ObjectSetInteger(0, g_zones[i].nameLine,  OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, g_zones[i].nameLine,  OBJPROP_COLOR, BlendAlpha(cBase, 80));
            ObjectSetInteger(0, g_zones[i].nameOuter, OBJPROP_COLOR, BlendAlpha(cBase, 96));
            ObjectSetInteger(0, g_zones[i].nameInner, OBJPROP_COLOR, BlendAlpha(cBase, 94));
           }
        }
      if(age > InpMaxAge || (g_zones[i].broken && age > 30))
        {
         ObjectDelete(0, g_zones[i].nameOuter);
         ObjectDelete(0, g_zones[i].nameInner);
         ObjectDelete(0, g_zones[i].nameLine);
         int s = ArraySize(g_zones);
         for(int k = i; k < s - 1; k++) g_zones[k] = g_zones[k+1];
         ArrayResize(g_zones, s - 1);
         continue;
        }
      if(!g_zones[i].broken)
        {
         double fade  = MathMin((double)age / (double)InpMaxAge, 1.0);
         int outerT   = (int)(90.0 + 10.0 * fade);
         int innerT   = (int)(82.0 + 18.0 * fade);
         int lineT    = (int)(45.0 + 55.0 * fade);
         ObjectSetInteger(0, g_zones[i].nameOuter, OBJPROP_TIME, 1, rightT);
         ObjectSetInteger(0, g_zones[i].nameInner, OBJPROP_TIME, 1, rightT);
         ObjectSetInteger(0, g_zones[i].nameLine,  OBJPROP_TIME, 1, rightT);
         ObjectSetInteger(0, g_zones[i].nameOuter, OBJPROP_COLOR, BlendAlpha(cBase, outerT));
         ObjectSetInteger(0, g_zones[i].nameInner, OBJPROP_COLOR, BlendAlpha(cBase, innerT));
         ObjectSetInteger(0, g_zones[i].nameLine,  OBJPROP_COLOR, BlendAlpha(cBase, lineT));
        }
     }
  }

//+------------------------------------------------------------------+
//|  Forecast renderer                                               |
//+------------------------------------------------------------------+
void DrawForecast(const double atrV)
  {
   DeleteByPrefix(PFX "fcast_");
   int n = ArraySize(g_pcts);
   if(n < 2) return;

   double fPct = (InpMethod == METHOD_WEIGHTED) ? ArrWeighted(g_pcts) :
                 (InpMethod == METHOD_MEDIAN)   ? ArrMedian(g_pcts)   : ArrAvg(g_pcts);
   double variance = 0.0;
   for(int i=0;i<n;i++){double d=g_pcts[i]-fPct; variance+=d*d;}
   double stdDev = MathSqrt(variance / n);

   bool isBear     = !g_dir;
   double origin   = isBear ? g_hi.price : g_lo.price;
   datetime originT= isBear ? g_hi.time  : g_lo.time;
   double target   = isBear ? origin*(1.0 - fPct/100.0) : origin*(1.0 + fPct/100.0);
   datetime targetT= BarTime(InpFwdBars);
   double bandHalf = MathMax(origin*stdDev/100.0, atrV*0.1);

   if(InpShowBeam)
     {
      const int steps = 12;
      double mults[3] = {1.5, 1.0, 0.5};
      int    tr_[3]   = {93, 87, 78};
      for(int layer=0; layer<3; layer++)
        {
         color cl = BlendAlpha(InpProjClr, tr_[layer]);
         for(int s=0; s<steps; s++)
           {
            double t1=(double)s/steps, t2=(double)(s+1)/steps;
            double e1=t1*t1*(3.0-2.0*t1), e2=t2*t2*(3.0-2.0*t2);
            datetime x1 = originT + (datetime)((targetT-originT)*t1);
            datetime x2 = originT + (datetime)((targetT-originT)*t2);
            double yc1=origin+(target-origin)*e1, yc2=origin+(target-origin)*e2;
            double sp1=bandHalf*mults[layer]*e1, sp2=bandHalf*mults[layer]*e2;
            CreateTrend(StringFormat("%sfcast_b_%d_%d_u",PFX,layer,s), x1,yc1+sp1, x2,yc2+sp2, cl, STYLE_SOLID, 1, true);
            CreateTrend(StringFormat("%sfcast_b_%d_%d_d",PFX,layer,s), x1,yc1-sp1, x2,yc2-sp2, cl, STYLE_SOLID, 1, true);
           }
        }
     }
   CreateTrend(PFX "fcast_center", originT, origin, targetT, target, BlendAlpha(InpProjClr, 30), STYLE_DASH, 1, false);
   if(InpShowDots)
     {
      for(int s=1;s<=4;s++)
        {
         double t=s/5.0, e=t*t*(3.0-2.0*t);
         datetime xt = originT + (datetime)((targetT-originT)*t);
         double y = origin + (target-origin)*e;
         int tr = (int)(25.0 + 45.0*(1.0-t));
         CreateText(StringFormat("%sfcast_d_%d",PFX,s), xt, y, "●", BlendAlpha(InpProjClr, tr), 8, ANCHOR_CENTER);
        }
     }
   if(InpShowTarget)
     {
      double tgtTop = target + bandHalf*0.6;
      double tgtBot = target - bandHalf*0.6;
      datetime t1o = targetT - (datetime)(3*PeriodSeconds());
      datetime t2o = targetT + (datetime)(6*PeriodSeconds());
      datetime t1i = targetT - (datetime)(2*PeriodSeconds());
      datetime t2i = targetT + (datetime)(5*PeriodSeconds());
      CreateRect(PFX "fcast_tgt_o", t1o, tgtTop+bandHalf*0.3, t2o, tgtBot-bandHalf*0.3, BlendAlpha(InpProjClr, 90));
      CreateRect(PFX "fcast_tgt_i", t1i, tgtTop, t2i, tgtBot, BlendAlpha(InpProjClr, 80));
      string sign = isBear ? "▼ " : "▲ ";
      string txt  = sign + DoubleToString(fPct, 2) + "%  " + DoubleToString(target, _Digits);
      CreateText(PFX "fcast_tgt_l", BarTime(InpFwdBars+6), target, txt, BlendAlpha(clrWhite, 0), 10, ANCHOR_LEFT);
     }
   if(InpShowFibs)
     {
      bool   actA[5] = {InpFib1On, InpFib2On, InpFib3On, InpFib4On, InpFib5On};
      double valA[5] = {InpFib1V,  InpFib2V,  InpFib3V,  InpFib4V,  InpFib5V};
      int    al[5]   = {30,45,30,55,65};
      double full = target - origin;
      for(int i=0;i<5;i++)
        {
         if(!actA[i]) continue;
         double r = valA[i], fp = origin + full*r;
         CreateTrend(StringFormat("%sfcast_f_%d_l",PFX,i), iTime(_Symbol,_Period,0), fp, BarTime(InpFwdBars+20), fp,
                     BlendAlpha(InpFibClr, al[i]), (r==1.0)?STYLE_SOLID:STYLE_DASH, 1, false);
         CreateText(StringFormat("%sfcast_f_%d_t",PFX,i), BarTime(InpFwdBars+22), fp,
                    DoubleToString(r,3) + "  " + DoubleToString(fp,_Digits), BlendAlpha(InpFibClr, 10), 9, ANCHOR_LEFT);
        }
     }
  }

//+------------------------------------------------------------------+
//|  Forecast pivot detection (drives swing flips)                   |
//+------------------------------------------------------------------+
void ProcessBarForecast(const int i, const double &h[], const double &l[], const double &c[],
                        const datetime &tm[], const double atrV)
  {
   if(i < InpSwingLen) return;
   double H_i  = HighestN(h, i, InpSwingLen);
   double L_i  = LowestN (l, i, InpSwingLen);
   double H_im = (i>=1) ? HighestN(h, i-1, InpSwingLen) : H_i;
   double L_im = (i>=1) ? LowestN (l, i-1, InpSwingLen) : L_i;
   bool prevDir = g_dir;
   if(h[i] >= H_i - 1e-12) g_dir = true;
   if(l[i] <= L_i + 1e-12) g_dir = false;
   if(i >= 1)
     {
      if(MathAbs(h[i-1] - H_im) < 1e-12 && h[i] < H_im) { g_hi.idx=i-1; g_hi.price=h[i-1]; g_hi.time=tm[i-1]; }
      if(MathAbs(l[i-1] - L_im) < 1e-12 && l[i] > L_im) { g_lo.idx=i-1; g_lo.price=l[i-1]; g_lo.time=tm[i-1]; }
     }
   if(!g_dirInit) { g_dirInit = true; return; }
   if(g_dir != prevDir && g_hi.idx >= 0 && g_lo.idx >= 0)
     {
      double pct = (!g_dir) ? (g_hi.price-g_lo.price)/g_lo.price*100.0 : (g_lo.price-g_hi.price)/g_hi.price*100.0;
      double bars = (double)MathAbs(g_hi.idx - g_lo.idx);
      PushCapped(g_pcts, MathAbs(pct), InpSamples);
      PushCapped(g_durs, bars,         InpSamples);
      if(InpShowLevels)
        {
         double zw = atrV * InpZoneATR;
         g_zoneSeq++;
         SRZone z;
         z.broken = false;
         z.nameOuter = StringFormat("%szone_%d_o", PFX, g_zoneSeq);
         z.nameInner = StringFormat("%szone_%d_i", PFX, g_zoneSeq);
         z.nameLine  = StringFormat("%szone_%d_l", PFX, g_zoneSeq);
         if(g_dir)
           {
            z.price = g_hi.price; z.startIdx = g_hi.idx; z.startTime = g_hi.time; z.isResistance = true;
            datetime t2 = BarTime(5);
            CreateRect(z.nameOuter, z.startTime, z.price+zw,      t2, z.price, BlendAlpha(InpBearClr, 90));
            CreateRect(z.nameInner, z.startTime, z.price+zw*0.35, t2, z.price, BlendAlpha(InpBearClr, 82));
            CreateTrend(z.nameLine, z.startTime, z.price, t2, z.price, BlendAlpha(InpBearClr, 45), STYLE_SOLID, 1, false);
           }
         else
           {
            z.price = g_lo.price; z.startIdx = g_lo.idx; z.startTime = g_lo.time; z.isResistance = false;
            datetime t2 = BarTime(5);
            CreateRect(z.nameOuter, z.startTime, z.price, t2, z.price-zw,      BlendAlpha(InpBullClr, 90));
            CreateRect(z.nameInner, z.startTime, z.price, t2, z.price-zw*0.35, BlendAlpha(InpBullClr, 82));
            CreateTrend(z.nameLine, z.startTime, z.price, t2, z.price, BlendAlpha(InpBullClr, 45), STYLE_SOLID, 1, false);
           }
         int sz = ArraySize(g_zones); ArrayResize(g_zones, sz+1); g_zones[sz] = z;
        }
     }
  }

//+------------------------------------------------------------------+
//|  SMC: leg detection equivalent                                   |
//|  Returns 1 (bullish leg start), 0 (bearish leg start), or prev. |
//+------------------------------------------------------------------+
int LegState(const double &h[], const double &l[], int barIdx, int size, int &lastState)
  {
   if(barIdx < size + 1) return lastState;
   // ta.highest(size) excludes current bar in Pine; matches len ending at barIdx-1
   // newLegHigh: high[size] > ta.highest(size) → high at (barIdx-size) > max(high[barIdx-size+1..barIdx])
   int pivBar = barIdx - size;
   if(pivBar < 0) return lastState;
   double maxAfter = -DBL_MAX, minAfter = DBL_MAX;
   for(int k = pivBar + 1; k <= barIdx; k++)
     {
      if(h[k] > maxAfter) maxAfter = h[k];
      if(l[k] < minAfter) minAfter = l[k];
     }
   bool newHi = h[pivBar] > maxAfter;
   bool newLo = l[pivBar] < minAfter;
   if(newHi)      lastState = BEAR_LEG;
   else if(newLo) lastState = BULL_LEG;
   return lastState;
  }

//+------------------------------------------------------------------+
//|  SMC: capture pivots, draw EQ levels                             |
//+------------------------------------------------------------------+
void CaptureSmcStructure(const int barIdx, const int size, const bool equalMode, const bool internal,
                         const double &h[], const double &l[], const datetime &tm[], const double atrV)
  {
   int prev = equalMode ? g_lastEqLeg : (internal ? g_lastIntLeg : g_lastSwLeg);
   int cur  = equalMode ? g_eqLeg     : (internal ? g_intLeg     : g_swLeg);
   int newCur;
   if(equalMode)      { newCur = LegState(h, l, barIdx, size, g_eqLeg);  }
   else if(internal)  { newCur = LegState(h, l, barIdx, size, g_intLeg); }
   else               { newCur = LegState(h, l, barIdx, size, g_swLeg);  }
   bool isNew = (newCur != prev);
   if(equalMode) g_lastEqLeg = newCur;
   else if(internal) g_lastIntLeg = newCur;
   else g_lastSwLeg = newCur;
   if(!isNew) return;

   bool isLow  = (newCur == BULL_LEG);
   int pivBar = barIdx - size;
   if(pivBar < 0) return;

   if(isLow)
     {
      if(equalMode)
        {
         if(MathAbs(g_eqLo.curLevel - l[pivBar]) < InpEQThr * atrV && g_eqLo.barIndex >= 0)
           {
            string nm = StringFormat("%seq_lo_%d", PFX, barIdx);
            CreateTrend(nm, g_eqLo.barTime, g_eqLo.curLevel, tm[pivBar], l[pivBar], BlendAlpha(InpSwBullClr, 30), STYLE_DOT, 1, false);
           }
         g_eqLo.lastLevel = g_eqLo.curLevel;
         g_eqLo.curLevel  = l[pivBar];
         g_eqLo.crossed   = false;
         g_eqLo.barTime   = tm[pivBar];
         g_eqLo.barIndex  = pivBar;
        }
      else if(internal)
        {
         g_intLo.lastLevel = g_intLo.curLevel;
         g_intLo.curLevel  = l[pivBar];
         g_intLo.crossed   = false;
         g_intLo.barTime   = tm[pivBar];
         g_intLo.barIndex  = pivBar;
        }
      else
        {
         g_swLo.lastLevel = g_swLo.curLevel;
         g_swLo.curLevel  = l[pivBar];
         g_swLo.crossed   = false;
         g_swLo.barTime   = tm[pivBar];
         g_swLo.barIndex  = pivBar;
         g_trail.bot     = g_swLo.curLevel;
         g_trail.barTime = g_swLo.barTime;
         g_trail.barIndex= g_swLo.barIndex;
         g_trail.lastBotTime = g_swLo.barTime;
        }
     }
   else
     {
      if(equalMode)
        {
         if(MathAbs(g_eqHi.curLevel - h[pivBar]) < InpEQThr * atrV && g_eqHi.barIndex >= 0)
           {
            string nm = StringFormat("%seq_hi_%d", PFX, barIdx);
            CreateTrend(nm, g_eqHi.barTime, g_eqHi.curLevel, tm[pivBar], h[pivBar], BlendAlpha(InpSwBearClr, 30), STYLE_DOT, 1, false);
           }
         g_eqHi.lastLevel = g_eqHi.curLevel;
         g_eqHi.curLevel  = h[pivBar];
         g_eqHi.crossed   = false;
         g_eqHi.barTime   = tm[pivBar];
         g_eqHi.barIndex  = pivBar;
        }
      else if(internal)
        {
         g_intHi.lastLevel = g_intHi.curLevel;
         g_intHi.curLevel  = h[pivBar];
         g_intHi.crossed   = false;
         g_intHi.barTime   = tm[pivBar];
         g_intHi.barIndex  = pivBar;
        }
      else
        {
         g_swHi.lastLevel = g_swHi.curLevel;
         g_swHi.curLevel  = h[pivBar];
         g_swHi.crossed   = false;
         g_swHi.barTime   = tm[pivBar];
         g_swHi.barIndex  = pivBar;
         g_trail.top     = g_swHi.curLevel;
         g_trail.barTime = g_swHi.barTime;
         g_trail.barIndex= g_swHi.barIndex;
         g_trail.lastTopTime = g_swHi.barTime;
        }
     }
  }

//+------------------------------------------------------------------+
//|  SMC: draw a BOS/CHoCH structure line                             |
//+------------------------------------------------------------------+
void DrawSmcStructure(const SmcPivot &piv, const string tag, const color c, const ENUM_LINE_STYLE lst,
                      const datetime nowT, const string ns, const int seq)
  {
   string lineName = StringFormat("%s%s_l_%d", PFX, ns, seq);
   string txtName  = StringFormat("%s%s_t_%d", PFX, ns, seq);
   CreateTrend(lineName, piv.barTime, piv.curLevel, nowT, piv.curLevel, c, lst, 1, false);
   datetime mid = piv.barTime + (datetime)((nowT - piv.barTime) / 2);
   CreateText(txtName, mid, piv.curLevel, tag, c, 8, ANCHOR_CENTER);
  }

//+------------------------------------------------------------------+
//|  SMC: BOS/CHoCH detection on close cross                          |
//+------------------------------------------------------------------+
int g_intStrSeq = 0, g_swStrSeq = 0;

void DetectSmcStructure(const int barIdx, const double curClose, const datetime curTime,
                        const bool internal, const double &h[], const double &l[],
                        const datetime &tm[], const double atrV)
  {
   bool show = internal ? InpShowIntStr : InpShowSwStr;
   bool showOB = internal ? InpShowIntOB : InpShowSwOB;
   color cBull = internal ? InpIntBullClr : InpSwBullClr;
   color cBear = internal ? InpIntBearClr : InpSwBearClr;
   ENUM_LINE_STYLE lst = internal ? STYLE_DASH : STYLE_SOLID;

   // bullish break
   double prevHi  = internal ? g_intHi.curLevel : g_swHi.curLevel;
   bool   crossedHi = internal ? g_intHi.crossed : g_swHi.crossed;
   if(!crossedHi && curClose > prevHi && prevHi > 0)
     {
      string tag = ((internal ? g_intTrend : g_swTrend) == BEARISH) ? "CHoCH" : "BOS";
      if(internal) { g_intHi.crossed = true; g_intTrend = BULLISH; }
      else         { g_swHi.crossed  = true; g_swTrend  = BULLISH; }
      if(show)
        {
         g_intStrSeq++; g_swStrSeq++;
         SmcPivot p = internal ? g_intHi : g_swHi;
         DrawSmcStructure(p, tag, cBull, lst, curTime, internal?"intStr":"swStr", internal?g_intStrSeq:g_swStrSeq);
        }
      if(showOB) StoreOB(internal, BULLISH, h, l, tm);
     }
   // bearish break
   double prevLo  = internal ? g_intLo.curLevel : g_swLo.curLevel;
   bool   crossedLo = internal ? g_intLo.crossed : g_swLo.crossed;
   if(!crossedLo && curClose < prevLo && prevLo > 0)
     {
      string tag = ((internal ? g_intTrend : g_swTrend) == BULLISH) ? "CHoCH" : "BOS";
      if(internal) { g_intLo.crossed = true; g_intTrend = BEARISH; }
      else         { g_swLo.crossed  = true; g_swTrend  = BEARISH; }
      if(show)
        {
         g_intStrSeq++; g_swStrSeq++;
         SmcPivot p = internal ? g_intLo : g_swLo;
         DrawSmcStructure(p, tag, cBear, lst, curTime, internal?"intStr":"swStr", internal?g_intStrSeq:g_swStrSeq);
        }
      if(showOB) StoreOB(internal, BEARISH, h, l, tm);
     }
  }

//+------------------------------------------------------------------+
//|  SMC: order block storage / mitigation / draw                    |
//+------------------------------------------------------------------+
void StoreOB(const bool internal, const int bias, const double &h[], const double &l[], const datetime &tm[])
  {
   SmcPivot p = internal ? (bias==BULLISH?g_intHi:g_intLo) : (bias==BULLISH?g_swHi:g_swLo);
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
   g_obSeq++;
   ob.nameBox = StringFormat("%s%s_ob_%d", PFX, internal?"int":"sw", g_obSeq);
   if(internal)
     {
      int n = ArraySize(g_intOBs);
      ArrayResize(g_intOBs, n + 1);
      // insert at front
      for(int i = n; i > 0; i--) g_intOBs[i] = g_intOBs[i-1];
      g_intOBs[0] = ob;
      if(ArraySize(g_intOBs) > 100) ArrayResize(g_intOBs, 100);
     }
   else
     {
      int n = ArraySize(g_swOBs);
      ArrayResize(g_swOBs, n + 1);
      for(int i = n; i > 0; i--) g_swOBs[i] = g_swOBs[i-1];
      g_swOBs[0] = ob;
      if(ArraySize(g_swOBs) > 100) ArrayResize(g_swOBs, 100);
     }
  }

void DeleteMitigatedOBs(const double curClose, const double curHigh, const double curLow, const bool internal)
  {
   double bearSrc = (InpOBMitig == OB_MITIG_CLOSE) ? curClose : curHigh;
   double bullSrc = (InpOBMitig == OB_MITIG_CLOSE) ? curClose : curLow;
   if(internal)
     {
      for(int i = ArraySize(g_intOBs) - 1; i >= 0; i--)
        {
         bool kill = false;
         if(g_intOBs[i].bias == BEARISH && bearSrc > g_intOBs[i].barHigh) kill = true;
         if(g_intOBs[i].bias == BULLISH && bullSrc < g_intOBs[i].barLow ) kill = true;
         if(kill)
           {
            ObjectDelete(0, g_intOBs[i].nameBox);
            int s = ArraySize(g_intOBs);
            for(int k = i; k < s-1; k++) g_intOBs[k] = g_intOBs[k+1];
            ArrayResize(g_intOBs, s-1);
           }
        }
     }
   else
     {
      for(int i = ArraySize(g_swOBs) - 1; i >= 0; i--)
        {
         bool kill = false;
         if(g_swOBs[i].bias == BEARISH && bearSrc > g_swOBs[i].barHigh) kill = true;
         if(g_swOBs[i].bias == BULLISH && bullSrc < g_swOBs[i].barLow ) kill = true;
         if(kill)
           {
            ObjectDelete(0, g_swOBs[i].nameBox);
            int s = ArraySize(g_swOBs);
            for(int k = i; k < s-1; k++) g_swOBs[k] = g_swOBs[k+1];
            ArrayResize(g_swOBs, s-1);
           }
        }
     }
  }

void DrawOBs(const bool internal, const datetime nowT)
  {
   int n = internal ? ArraySize(g_intOBs) : ArraySize(g_swOBs);
   int maxOB = internal ? InpIntOBSize : InpSwOBSize;
   int draw = MathMin(n, maxOB);
   for(int i = 0; i < draw; i++)
     {
      OrderBlock ob = internal ? g_intOBs[i] : g_swOBs[i];
      color c = (ob.bias == BULLISH) ? InpBullOBClr : InpBearOBClr;
      CreateRect(ob.nameBox, ob.barTime, ob.barHigh, nowT, ob.barLow, BlendAlpha(c, 70), true);
     }
  }

//+------------------------------------------------------------------+
//|  SMC: FVG detection / draw                                        |
//+------------------------------------------------------------------+
double g_fvgThrAcc = 0.0;
int    g_fvgBarCount = 0;

void DetectFVG(const int i, const double &h[], const double &l[], const double &c[], const double &o[],
               const datetime &tm[])
  {
   if(i < 2) return;
   double bdp = (c[i-1] - o[i-1]) / (o[i-1] * 100.0);
   g_fvgThrAcc += MathAbs(bdp);
   g_fvgBarCount++;
   double thr = InpFVGAuto && g_fvgBarCount > 0 ? (g_fvgThrAcc / g_fvgBarCount) * 2.0 : 0.0;
   bool bullFVG = l[i] > h[i-2] && c[i-1] > h[i-2] && bdp > thr;
   bool bearFVG = h[i] < l[i-2] && c[i-1] < l[i-2] && -bdp > thr;
   if(bullFVG)
     {
      g_fvgSeq++;
      FVG g;
      g.top = l[i]; g.bot = h[i-2]; g.bias = BULLISH;
      g.nameTop = StringFormat("%sfvg_bu_%d_t", PFX, g_fvgSeq);
      g.nameBot = StringFormat("%sfvg_bu_%d_b", PFX, g_fvgSeq);
      datetime rt = tm[i] + (datetime)(InpFVGExt * PeriodSeconds());
      double mid = (g.top + g.bot) / 2.0;
      CreateRect(g.nameTop, tm[i-1], g.top, rt, mid, BlendAlpha(InpFVGBullClr, 70));
      CreateRect(g.nameBot, tm[i-1], mid,  rt, g.bot, BlendAlpha(InpFVGBullClr, 70));
      int n = ArraySize(g_fvgs); ArrayResize(g_fvgs, n+1); g_fvgs[n] = g;
     }
   if(bearFVG)
     {
      g_fvgSeq++;
      FVG g;
      g.top = l[i-2]; g.bot = h[i]; g.bias = BEARISH;
      g.nameTop = StringFormat("%sfvg_be_%d_t", PFX, g_fvgSeq);
      g.nameBot = StringFormat("%sfvg_be_%d_b", PFX, g_fvgSeq);
      datetime rt = tm[i] + (datetime)(InpFVGExt * PeriodSeconds());
      double mid = (g.top + g.bot) / 2.0;
      CreateRect(g.nameTop, tm[i-1], g.top, rt, mid, BlendAlpha(InpFVGBearClr, 70));
      CreateRect(g.nameBot, tm[i-1], mid,  rt, g.bot, BlendAlpha(InpFVGBearClr, 70));
      int n = ArraySize(g_fvgs); ArrayResize(g_fvgs, n+1); g_fvgs[n] = g;
     }
  }

void CleanupFVGs(const double curHigh, const double curLow)
  {
   for(int i = ArraySize(g_fvgs) - 1; i >= 0; i--)
     {
      bool kill = false;
      if(g_fvgs[i].bias == BULLISH && curLow  < g_fvgs[i].bot) kill = true;
      if(g_fvgs[i].bias == BEARISH && curHigh > g_fvgs[i].top) kill = true;
      if(kill)
        {
         ObjectDelete(0, g_fvgs[i].nameTop);
         ObjectDelete(0, g_fvgs[i].nameBot);
         int s = ArraySize(g_fvgs);
         for(int k = i; k < s-1; k++) g_fvgs[k] = g_fvgs[k+1];
         ArrayResize(g_fvgs, s-1);
        }
     }
  }

//+------------------------------------------------------------------+
//|  SMC: trailing strong/weak high & low + premium/discount zones   |
//+------------------------------------------------------------------+
void DrawStrongWeak(const datetime nowT)
  {
   if(g_trail.top == -DBL_MAX || g_trail.bot == DBL_MAX) return;
   datetime rt = nowT + (datetime)(20 * PeriodSeconds());
   string nT = PFX "trail_top", nB = PFX "trail_bot", nTl = PFX "trail_topL", nBl = PFX "trail_botL";
   CreateTrend(nT, g_trail.lastTopTime, g_trail.top, rt, g_trail.top, InpSwBearClr, STYLE_SOLID, 1, false);
   CreateTrend(nB, g_trail.lastBotTime, g_trail.bot, rt, g_trail.bot, InpSwBullClr, STYLE_SOLID, 1, false);
   string tT = (g_swTrend == BEARISH) ? "Strong High" : "Weak High";
   string tB = (g_swTrend == BULLISH) ? "Strong Low"  : "Weak Low";
   CreateText(nTl, rt, g_trail.top, tT, InpSwBearClr, 9, ANCHOR_LEFT);
   CreateText(nBl, rt, g_trail.bot, tB, InpSwBullClr, 9, ANCHOR_LEFT);
  }

void DrawPDZones(const datetime nowT)
  {
   if(g_trail.top == -DBL_MAX || g_trail.bot == DBL_MAX) return;
   double mid = (g_trail.top + g_trail.bot) / 2.0;
   double premTop = g_trail.top, premBot = 0.95*g_trail.top + 0.05*g_trail.bot;
   double discTop = 0.95*g_trail.bot + 0.05*g_trail.top, discBot = g_trail.bot;
   double eqTop   = 0.525*g_trail.top + 0.475*g_trail.bot;
   double eqBot   = 0.525*g_trail.bot + 0.475*g_trail.top;
   CreateRect(PFX "pd_prem", g_trail.barTime, premTop, nowT, premBot, BlendAlpha(InpPremClr, 80));
   CreateRect(PFX "pd_eq",   g_trail.barTime, eqTop,   nowT, eqBot,   BlendAlpha(InpEQuilClr, 80));
   CreateRect(PFX "pd_disc", g_trail.barTime, discTop, nowT, discBot, BlendAlpha(InpDiscClr, 80));
   CreateText(PFX "pd_premL", nowT, (premTop+premBot)/2, "Premium",     InpPremClr, 9, ANCHOR_LEFT);
   CreateText(PFX "pd_eqL",   nowT, mid,                 "Equilibrium", InpEQuilClr,9, ANCHOR_LEFT);
   CreateText(PFX "pd_discL", nowT, (discTop+discBot)/2, "Discount",    InpDiscClr, 9, ANCHOR_LEFT);
  }

//+------------------------------------------------------------------+
//|  MTF levels (Daily / Weekly / Monthly)                           |
//+------------------------------------------------------------------+
void DrawMTFLevel(const ENUM_TIMEFRAMES tf, const string tag, const datetime nowT)
  {
   double hh[]; double ll[];
   if(CopyHigh(_Symbol, tf, 1, 1, hh) <= 0) return;
   if(CopyLow (_Symbol, tf, 1, 1, ll) <= 0) return;
   datetime t1[]; if(CopyTime(_Symbol, tf, 1, 1, t1) <= 0) return;
   datetime rt = nowT + (datetime)(20 * PeriodSeconds());
   string nH = StringFormat("%smtf_%s_h", PFX, tag), nL = StringFormat("%smtf_%s_l", PFX, tag);
   string lbH = StringFormat("%smtf_%s_hL", PFX, tag), lbL = StringFormat("%smtf_%s_lL", PFX, tag);
   CreateTrend(nH, t1[0], hh[0], rt, hh[0], InpMTFClr, STYLE_SOLID, 1, false);
   CreateTrend(nL, t1[0], ll[0], rt, ll[0], InpMTFClr, STYLE_SOLID, 1, false);
   CreateText(lbH, rt, hh[0], "P" + tag + "H", InpMTFClr, 9, ANCHOR_LEFT);
   CreateText(lbL, rt, ll[0], "P" + tag + "L", InpMTFClr, 9, ANCHOR_LEFT);
  }

//+------------------------------------------------------------------+
//|  Trailing extremes update                                        |
//+------------------------------------------------------------------+
void UpdateTrailing(const double curHigh, const double curLow, const datetime curTime)
  {
   if(curHigh > g_trail.top) { g_trail.top = curHigh; g_trail.lastTopTime = curTime; }
   if(curLow  < g_trail.bot) { g_trail.bot = curLow;  g_trail.lastBotTime = curTime; }
  }

//+------------------------------------------------------------------+
//|  OnCalculate                                                     |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < InpSwingLen + InpSwingSmcLen + 5) return 0;
   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   if(CopyBuffer(g_atrHandle, 0, 0, rates_total, atrBuf) <= 0) return 0;
   int start = (prev_calculated <= 0) ? 0 : prev_calculated - 1;
   if(start < InpSwingSmcLen + 2) start = InpSwingSmcLen + 2;
   for(int i = start; i < rates_total; i++)
     {
      double atrV = (atrBuf[i] > 0) ? atrBuf[i] : 0.0;
      // Forecast pivot detection + S/R
      ProcessBarForecast(i, high, low, close, time, atrV);
      UpdateSRZones(i, time[i], close[i]);
      // SMC structure capture (internal + swing + EQ)
      CaptureSmcStructure(i, InpInternalLen, false, true,  high, low, time, atrV);
      CaptureSmcStructure(i, InpSwingSmcLen, false, false, high, low, time, atrV);
      if(InpShowEQ) CaptureSmcStructure(i, InpEQLen, true, false, high, low, time, atrV);
      // BOS / CHoCH detection
      DetectSmcStructure(i, close[i], time[i], true,  high, low, time, atrV);
      DetectSmcStructure(i, close[i], time[i], false, high, low, time, atrV);
      // OB mitigation
      DeleteMitigatedOBs(close[i], high[i], low[i], true);
      DeleteMitigatedOBs(close[i], high[i], low[i], false);
      // FVG detection + cleanup
      if(InpShowFVG) DetectFVG(i, high, low, close, open, time);
      if(InpShowFVG) CleanupFVGs(high[i], low[i]);
      // Trailing extremes
      if(InpShowStrongWeak || InpShowPD) UpdateTrailing(high[i], low[i], time[i]);
     }
   // Refresh forecast + SMC overlays on latest bar
   double atrLast = (atrBuf[rates_total-1] > 0) ? atrBuf[rates_total-1] : 0.0;
   DrawForecast(atrLast);
   datetime nowT = time[rates_total-1];
   if(InpShowIntOB) DrawOBs(true,  nowT);
   if(InpShowSwOB)  DrawOBs(false, nowT);
   if(InpShowStrongWeak) DrawStrongWeak(nowT);
   if(InpShowPD)         DrawPDZones(nowT);
   if(InpShowDaily   && PeriodSeconds() < PeriodSeconds(PERIOD_D1)) DrawMTFLevel(PERIOD_D1, "D", nowT);
   if(InpShowWeekly  && PeriodSeconds() < PeriodSeconds(PERIOD_W1)) DrawMTFLevel(PERIOD_W1, "W", nowT);
   if(InpShowMonthly && PeriodSeconds() < PeriodSeconds(PERIOD_MN1)) DrawMTFLevel(PERIOD_MN1, "M", nowT);
   ChartRedraw(0);
   return rates_total;
  }
//+------------------------------------------------------------------+
