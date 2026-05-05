//+------------------------------------------------------------------+
//|              SwingStructureForecast_BOSWaves.mq5                  |
//|  MQL5 port of "Swing Structure Forecast [BOSWaves]" Pine v6       |
//|  Original: BOSWaves (MPL 2.0). Port: AlgoStrategies repo          |
//+------------------------------------------------------------------+
#property copyright "Port of BOSWaves Swing Structure Forecast (MPL 2.0)"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

//--- Inputs ---------------------------------------------------------
enum ENUM_FCAST_METHOD { METHOD_WEIGHTED=0, METHOD_AVERAGE=1, METHOD_MEDIAN=2 };

input group "Detection"
input int    InpSwingLen   = 16;        // Swing Length

input group "Support / Resistance"
input bool   InpShowLevels = true;      // Show S/R Levels
input double InpZoneATR    = 0.30;      // Zone Width (ATR mult)
input int    InpMaxAge     = 300;       // Max Level Age (bars)

input group "Forecast"
input int               InpSamples    = 20;
input ENUM_FCAST_METHOD InpMethod     = METHOD_WEIGHTED;
input int               InpFwdBars    = 5;
input bool              InpShowBeam   = true;
input bool              InpShowTarget = true;
input bool              InpShowDots   = true;
input bool              InpShowFibs   = true;
input bool              InpFib1Active = true;   input double InpFib1Val = 1.000;
input bool              InpFib2Active = true;   input double InpFib2Val = 1.272;
input bool              InpFib3Active = true;   input double InpFib3Val = 1.618;
input bool              InpFib4Active = false;  input double InpFib4Val = 2.000;
input bool              InpFib5Active = false;  input double InpFib5Val = 2.618;

input group "Colors"
input color  InpBullClr = clrLime;
input color  InpBearClr = clrRed;
input color  InpProjClr = clrDodgerBlue;
input color  InpFibClr  = clrGold;

//--- Object name prefix --------------------------------------------
#define PFX "SSF_"

//--- Pivot tracker --------------------------------------------------
struct Pivot { double price; int idx; datetime time; };
Pivot   g_hi = {0.0, -1, 0};
Pivot   g_lo = {0.0, -1, 0};
bool    g_dir = false;
bool    g_dirInit = false;

//--- S/R zone records ----------------------------------------------
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

//--- ATR handle -----------------------------------------------------
int g_atrHandle = INVALID_HANDLE;

//--- Last processed bar --------------------------------------------
int g_lastBars = 0;

//+------------------------------------------------------------------+
//|  Color helpers — emulate Pine color.new(c, transp 0..100)        |
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
   // shiftFromCurrent==0 -> current bar; positive -> future bars
   datetime t0 = iTime(_Symbol, _Period, 0);
   return t0 + (datetime)(shiftFromCurrent * PeriodSeconds());
  }

//+------------------------------------------------------------------+
//|  Object factories                                                |
//+------------------------------------------------------------------+
bool CreateRect(const string name, datetime t1, double p1, datetime t2, double p2, color c)
  {
   ObjectDelete(0, name);
   if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2)) return false;
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
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

//+------------------------------------------------------------------+
//|  Delete every object whose name starts with prefix                |
//+------------------------------------------------------------------+
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
   g_atrHandle = iATR(_Symbol, _Period, 200);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("Failed to create ATR(200) handle");
      return INIT_FAILED;
     }
   DeleteByPrefix(PFX);
   g_lastBars = 0;
   g_dirInit = false;
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
//|  Stat helpers                                                    |
//+------------------------------------------------------------------+
double ArrAvg(const double &a[])
  {
   int n = ArraySize(a);
   if(n == 0) return 0.0;
   double s = 0.0;
   for(int i = 0; i < n; i++) s += a[i];
   return s / n;
  }
double ArrMedian(const double &a[])
  {
   int n = ArraySize(a);
   if(n == 0) return 0.0;
   double tmp[];
   ArrayResize(tmp, n);
   for(int i = 0; i < n; i++) tmp[i] = a[i];
   ArraySort(tmp);
   return (n % 2 == 1) ? tmp[n/2] : 0.5 * (tmp[n/2 - 1] + tmp[n/2]);
  }
double ArrWeighted(const double &a[])
  {
   int n = ArraySize(a);
   if(n == 0) return 0.0;
   double tw = 0.0, ws = 0.0;
   for(int i = 0; i < n; i++)
     {
      double w = i + 1.0;
      ws += a[i] * w;
      tw += w;
     }
   return ws / tw;
  }

//+------------------------------------------------------------------+
//|  Push with cap (Pine .push + .shift)                             |
//+------------------------------------------------------------------+
void PushCapped(double &arr[], const double v, const int cap)
  {
   int n = ArraySize(arr);
   ArrayResize(arr, n + 1);
   arr[n] = v;
   if(ArraySize(arr) > cap)
     {
      // shift left by 1
      int s = ArraySize(arr);
      for(int i = 0; i < s - 1; i++) arr[i] = arr[i+1];
      ArrayResize(arr, s - 1);
     }
  }

//+------------------------------------------------------------------+
//|  Highest/Lowest over `len` bars ending at shift `endShift`        |
//|  (shift uses MQL5 series convention: 0 = current)                 |
//+------------------------------------------------------------------+
double HighestN(const double &h[], int rates_total, int barIdx, int len)
  {
   double m = -DBL_MAX;
   int from = barIdx - len + 1;
   if(from < 0) from = 0;
   for(int i = from; i <= barIdx; i++) if(h[i] > m) m = h[i];
   return m;
  }
double LowestN(const double &l[], int rates_total, int barIdx, int len)
  {
   double m = DBL_MAX;
   int from = barIdx - len + 1;
   if(from < 0) from = 0;
   for(int i = from; i <= barIdx; i++) if(l[i] < m) m = l[i];
   return m;
  }

//+------------------------------------------------------------------+
//|  S/R management                                                  |
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
            ObjectSetInteger(0, g_zones[i].nameLine, OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, g_zones[i].nameLine, OBJPROP_COLOR, BlendAlpha(cBase, 80));
            ObjectSetInteger(0, g_zones[i].nameOuter, OBJPROP_COLOR, BlendAlpha(cBase, 96));
            ObjectSetInteger(0, g_zones[i].nameInner, OBJPROP_COLOR, BlendAlpha(cBase, 94));
           }
        }

      if(age > InpMaxAge || (g_zones[i].broken && age > 30))
        {
         ObjectDelete(0, g_zones[i].nameOuter);
         ObjectDelete(0, g_zones[i].nameInner);
         ObjectDelete(0, g_zones[i].nameLine);
         // remove element i
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
//|  Forecast renderer (called once on the latest bar)                |
//+------------------------------------------------------------------+
void ClearForecast()
  {
   DeleteByPrefix(PFX "fcast_");
  }

void DrawForecast(const double atrV)
  {
   ClearForecast();
   int n = ArraySize(g_pcts);
   if(n < 2) return;

   double fPct = 0.0;
   double fBars = 0.0;
   if(InpMethod == METHOD_WEIGHTED) { fPct = ArrWeighted(g_pcts); fBars = ArrWeighted(g_durs); }
   else if(InpMethod == METHOD_MEDIAN) { fPct = ArrMedian(g_pcts); fBars = ArrMedian(g_durs); }
   else { fPct = ArrAvg(g_pcts); fBars = ArrAvg(g_durs); }

   double variance = 0.0;
   for(int i = 0; i < n; i++) { double d = g_pcts[i] - fPct; variance += d*d; }
   double stdDev = MathSqrt(variance / n);

   bool   isBear     = !g_dir;
   double origin     = isBear ? g_hi.price : g_lo.price;
   datetime originT  = isBear ? g_hi.time  : g_lo.time;
   double target     = isBear ? origin * (1.0 - fPct/100.0) : origin * (1.0 + fPct/100.0);
   datetime targetT  = BarTime(InpFwdBars);
   double bandHalf   = MathMax(origin * stdDev / 100.0, atrV * 0.1);

   //--- Beam (3 layers, smoothstep eased, segmented as OBJ_TREND) -----
   if(InpShowBeam)
     {
      const int steps = 12;
      double mults[3] = {1.5, 1.0, 0.5};
      int    transp[3]= {93, 87, 78};
      for(int layer = 0; layer < 3; layer++)
        {
         color cl = BlendAlpha(InpProjClr, transp[layer]);
         for(int s = 0; s < steps; s++)
           {
            double t1 = (double)s / steps;
            double t2 = (double)(s+1) / steps;
            double e1 = t1*t1*(3.0-2.0*t1);
            double e2 = t2*t2*(3.0-2.0*t2);
            datetime x1 = originT + (datetime)((targetT - originT) * t1);
            datetime x2 = originT + (datetime)((targetT - originT) * t2);
            double yc1 = origin + (target - origin) * e1;
            double yc2 = origin + (target - origin) * e2;
            double sp1 = bandHalf * mults[layer] * e1;
            double sp2 = bandHalf * mults[layer] * e2;
            string nUp = StringFormat("%sfcast_beam_%d_%d_u", PFX, layer, s);
            string nDn = StringFormat("%sfcast_beam_%d_%d_d", PFX, layer, s);
            CreateTrend(nUp, x1, yc1+sp1, x2, yc2+sp2, cl, STYLE_SOLID, 1, true);
            CreateTrend(nDn, x1, yc1-sp1, x2, yc2-sp2, cl, STYLE_SOLID, 1, true);
           }
        }
     }

   //--- Center trajectory ---------------------------------------------
   CreateTrend(PFX "fcast_center", originT, origin, targetT, target,
               BlendAlpha(InpProjClr, 30), STYLE_DASH, 1, false);

   //--- Path markers ---------------------------------------------------
   if(InpShowDots)
     {
      for(int s = 1; s <= 4; s++)
        {
         double t = s / 5.0;
         double e = t*t*(3.0-2.0*t);
         datetime xt = originT + (datetime)((targetT - originT) * t);
         double y    = origin + (target - origin) * e;
         int tr      = (int)(25.0 + 45.0 * (1.0 - t));
         CreateText(StringFormat("%sfcast_dot_%d", PFX, s), xt, y, "●",
                    BlendAlpha(InpProjClr, tr), 8, ANCHOR_CENTER);
        }
     }

   //--- Target zone ----------------------------------------------------
   if(InpShowTarget)
     {
      double tgtTop = target + bandHalf * 0.6;
      double tgtBot = target - bandHalf * 0.6;
      datetime t1o = targetT - (datetime)(3 * PeriodSeconds());
      datetime t2o = targetT + (datetime)(6 * PeriodSeconds());
      datetime t1i = targetT - (datetime)(2 * PeriodSeconds());
      datetime t2i = targetT + (datetime)(5 * PeriodSeconds());
      CreateRect(PFX "fcast_tgt_outer", t1o, tgtTop + bandHalf*0.3, t2o, tgtBot - bandHalf*0.3,
                 BlendAlpha(InpProjClr, 90));
      CreateRect(PFX "fcast_tgt_inner", t1i, tgtTop, t2i, tgtBot,
                 BlendAlpha(InpProjClr, 80));
      string sign = isBear ? "▼ " : "▲ ";
      string txt  = sign + DoubleToString(fPct, 2) + "%  " + DoubleToString(target, _Digits);
      CreateText(PFX "fcast_tgt_label", BarTime(InpFwdBars + 6), target, txt,
                 BlendAlpha(clrWhite, 0), 10, ANCHOR_LEFT);
     }

   //--- Fib extensions -------------------------------------------------
   if(InpShowFibs)
     {
      bool   actA[5] = {InpFib1Active, InpFib2Active, InpFib3Active, InpFib4Active, InpFib5Active};
      double valA[5] = {InpFib1Val,    InpFib2Val,    InpFib3Val,    InpFib4Val,    InpFib5Val};
      int    alpha[5]= {30, 45, 30, 55, 65};
      double fullMove = target - origin;
      for(int i = 0; i < 5; i++)
        {
         if(!actA[i]) continue;
         double ratio = valA[i];
         double fp    = origin + fullMove * ratio;
         CreateTrend(StringFormat("%sfcast_fib_%d_l", PFX, i),
                     iTime(_Symbol, _Period, 0), fp,
                     BarTime(InpFwdBars + 20), fp,
                     BlendAlpha(InpFibClr, alpha[i]), (ratio == 1.0) ? STYLE_SOLID : STYLE_DASH, 1, false);
         CreateText(StringFormat("%sfcast_fib_%d_t", PFX, i),
                    BarTime(InpFwdBars + 22), fp,
                    DoubleToString(ratio, 3) + "  " + DoubleToString(fp, _Digits),
                    BlendAlpha(InpFibClr, 10), 9, ANCHOR_LEFT);
        }
     }
  }

//+------------------------------------------------------------------+
//|  Confirm a swing on bar i (closed); update direction              |
//+------------------------------------------------------------------+
void ProcessBar(const int i, const int rates_total,
                const double &h[], const double &l[], const double &c[],
                const datetime &tm[], const double atrV)
  {
   if(i < InpSwingLen) return;

   // Pine: H = ta.highest(high, swingLen); evaluated at bar i
   double H_i  = HighestN(h, rates_total, i, InpSwingLen);
   double L_i  = LowestN (l, rates_total, i, InpSwingLen);
   double H_im = (i >= 1) ? HighestN(h, rates_total, i-1, InpSwingLen) : H_i;
   double L_im = (i >= 1) ? LowestN (l, rates_total, i-1, InpSwingLen) : L_i;

   bool prevDir = g_dir;

   if(h[i] >= H_i - 1e-12) g_dir = true;
   if(l[i] <= L_i + 1e-12) g_dir = false;

   // Confirm pivots: high[1]==H[1] && high < H -> swing high at i-1
   if(i >= 1)
     {
      if(MathAbs(h[i-1] - H_im) < 1e-12 && h[i] < H_im)
        {
         g_hi.idx   = i - 1;
         g_hi.price = h[i-1];
         g_hi.time  = tm[i-1];
        }
      if(MathAbs(l[i-1] - L_im) < 1e-12 && l[i] > L_im)
        {
         g_lo.idx   = i - 1;
         g_lo.price = l[i-1];
         g_lo.time  = tm[i-1];
        }
     }

   if(!g_dirInit) { g_dirInit = true; return; }

   // Direction flip: record swing leg + create S/R zone
   if(g_dir != prevDir && g_hi.idx >= 0 && g_lo.idx >= 0)
     {
      double pct  = (!g_dir)
                  ? (g_hi.price - g_lo.price) / g_lo.price * 100.0
                  : (g_lo.price - g_hi.price) / g_hi.price * 100.0;
      double bars = (double)MathAbs(g_hi.idx - g_lo.idx);

      PushCapped(g_pcts, MathAbs(pct), InpSamples);
      PushCapped(g_durs, bars,         InpSamples);

      if(InpShowLevels)
        {
         double zWidth = atrV * InpZoneATR;
         g_zoneSeq++;
         SRZone z;
         z.broken = false;
         z.nameOuter = StringFormat("%szone_%d_o", PFX, g_zoneSeq);
         z.nameInner = StringFormat("%szone_%d_i", PFX, g_zoneSeq);
         z.nameLine  = StringFormat("%szone_%d_l", PFX, g_zoneSeq);

         if(g_dir)  // flipped to bull -> prior pivot was a swing high (resistance)
           {
            z.price = g_hi.price; z.startIdx = g_hi.idx; z.startTime = g_hi.time;
            z.isResistance = true;
            datetime t2 = BarTime(5);
            CreateRect(z.nameOuter, z.startTime, z.price + zWidth,         t2, z.price,
                       BlendAlpha(InpBearClr, 90));
            CreateRect(z.nameInner, z.startTime, z.price + zWidth*0.35,    t2, z.price,
                       BlendAlpha(InpBearClr, 82));
            CreateTrend(z.nameLine, z.startTime, z.price, t2, z.price,
                        BlendAlpha(InpBearClr, 45), STYLE_SOLID, 1, false);
           }
         else        // flipped to bear -> prior pivot was a swing low (support)
           {
            z.price = g_lo.price; z.startIdx = g_lo.idx; z.startTime = g_lo.time;
            z.isResistance = false;
            datetime t2 = BarTime(5);
            CreateRect(z.nameOuter, z.startTime, z.price,                 t2, z.price - zWidth,
                       BlendAlpha(InpBullClr, 90));
            CreateRect(z.nameInner, z.startTime, z.price,                 t2, z.price - zWidth*0.35,
                       BlendAlpha(InpBullClr, 82));
            CreateTrend(z.nameLine, z.startTime, z.price, t2, z.price,
                        BlendAlpha(InpBullClr, 45), STYLE_SOLID, 1, false);
           }
         int sz = ArraySize(g_zones);
         ArrayResize(g_zones, sz + 1);
         g_zones[sz] = z;
        }
     }
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
   if(rates_total < InpSwingLen + 2) return 0;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   if(CopyBuffer(g_atrHandle, 0, 0, rates_total, atrBuf) <= 0) return 0;

   // Series-as-series=false from MQL5: arrays are oldest->newest like Pine's bar_index ascending
   int start = (prev_calculated <= 0) ? 0 : prev_calculated - 1;
   if(start < InpSwingLen) start = InpSwingLen;

   for(int i = start; i < rates_total; i++)
     {
      double atrV = (atrBuf[i] > 0) ? atrBuf[i] : 0.0;
      ProcessBar(i, rates_total, high, low, close, time, atrV);
      UpdateSRZones(i, time[i], close[i]);
     }

   // Forecast layer — only on latest bar
   double atrLast = (atrBuf[rates_total-1] > 0) ? atrBuf[rates_total-1] : 0.0;
   DrawForecast(atrLast);

   ChartRedraw(0);
   return rates_total;
  }
//+------------------------------------------------------------------+
