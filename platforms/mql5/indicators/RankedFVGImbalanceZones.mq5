//+------------------------------------------------------------------+
//| RankedFVGImbalanceZones.mq5                                       |
//| MT5 port of "Ranked FVG Imbalance Zones (Zeiierman)" Pine v6.     |
//| Detects 3-candle FVGs, scores them (size, volume, trend, age,     |
//| mitigation), keeps top-N visible, draws bull/bear strength bars   |
//| inside each zone with smart labels, fires Alert() on key events.  |
//+------------------------------------------------------------------+
#property copyright "Ninad K (port of Zeiierman, CC BY-NC-SA 4.0)"
#property version   "1.00"
#property description "Ranked FVG Imbalance Zones — top-N quality-scored 3-bar FVGs with strength bars."
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   0

//--- Font size selector (mirrors Pine text.size_*)
enum ENUM_FVG_FONT
  {
   FVG_FONT_TINY   = 6,
   FVG_FONT_SMALL  = 8,
   FVG_FONT_NORMAL = 10,
   FVG_FONT_LARGE  = 12,
   FVG_FONT_HUGE   = 16
  };

//--- Inputs : Ranking
input int    InpMaxZones      = 10;          // Show Top Zones (1..20)
input int    InpMaxStored     = 50;          // Max Stored FVGs (10..200)
//--- Inputs : Strength Engine
input int    InpVolLength     = 20;          // Volume MA Length
input int    InpTrendLength   = 50;          // Trend EMA Length
//--- Inputs : Display
input bool          InpShowBars       = true;          // Show Strength Bars
input bool          InpShowBlockText  = true;          // Show FVG Block Text
input ENUM_FVG_FONT InpStrengthSize   = FVG_FONT_SMALL;// Strength Text Size
input ENUM_FVG_FONT InpBlockSize      = FVG_FONT_SMALL;// Block Text Size
//--- Inputs : Colors
input color  InpBullColor     = clrTeal;     // Bullish
input color  InpBearColor     = clrCrimson;  // Bearish
input uchar  InpBodyAlpha     = 70;          // Body fill lightness (0..255)
//--- Inputs : Alerts
input bool   InpAlertNewBull        = true;
input bool   InpAlertNewBear        = true;
input bool   InpAlertTopRank        = true;
input bool   InpAlertBullTouch      = true;
input bool   InpAlertBearTouch      = true;
input bool   InpAlertFullyMitigated = true;
input bool   InpPushNotify          = false; // Also send push (SendNotification)

//--- Internal
#define FVG_PREFIX "RFVG_"
#define EXTEND_BARS 25

double g_dummy[];

int    h_volMA = INVALID_HANDLE;
int    h_emaCl = INVALID_HANDLE;
int    h_atr14 = INVALID_HANDLE;

datetime g_lastBarTime = 0;
string   g_topKey      = "";

//--- FVG record
struct SFvg
  {
   double   qualityScore;
   double   top;
   double   bottom;
   int      direction;       // +1 bull, -1 bear
   int      bornBar;
   datetime leftTime;
   double   size;
   double   mitigation;
   double   volumeScore;
   double   trendScore;
   int      bullStrength;
   int      bearStrength;
   string   nBody;
   string   nBull;
   string   nBear;
   string   nBodyTxt;
   string   nBullTxt;
   string   nBearTxt;
  };

SFvg g_fvgs[];

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
color BlendColor(color base, color bg, uchar alpha)
  {
   double a = (double)alpha / 255.0;
   int br = (int)((base & 0xFF));
   int bgr = (int)((base >> 8) & 0xFF);
   int bb = (int)((base >> 16) & 0xFF);
   int gr = (int)((bg & 0xFF));
   int ggr= (int)((bg >> 8) & 0xFF);
   int gb = (int)((bg >> 16) & 0xFF);
   int rr = (int)(br * a + gr  * (1.0 - a));
   int rg = (int)(bgr* a + ggr * (1.0 - a));
   int rb = (int)(bb * a + gb  * (1.0 - a));
   return (color)((rb << 16) | (rg << 8) | rr);
  }

double GetBufVal(int handle, int shift)
  {
   if(handle == INVALID_HANDLE)
      return 0.0;
   double tmp[];
   if(CopyBuffer(handle, 0, shift, 1, tmp) != 1)
      return 0.0;
   return tmp[0];
  }

void DeleteFvgObjects(const SFvg &f)
  {
   ObjectDelete(0, f.nBody);
   ObjectDelete(0, f.nBull);
   ObjectDelete(0, f.nBear);
   ObjectDelete(0, f.nBodyTxt);
   ObjectDelete(0, f.nBullTxt);
   ObjectDelete(0, f.nBearTxt);
  }

void RemoveAt(int idx)
  {
   int n = ArraySize(g_fvgs);
   if(idx < 0 || idx >= n)
      return;
   DeleteFvgObjects(g_fvgs[idx]);
   for(int i = idx; i < n - 1; i++)
      g_fvgs[i] = g_fvgs[i + 1];
   ArrayResize(g_fvgs, n - 1);
  }

//--- Descending insertion sort by qualityScore (n is small, <=200)
void SortDesc()
  {
   int n = ArraySize(g_fvgs);
   for(int i = 1; i < n; i++)
     {
      SFvg key = g_fvgs[i];
      int j = i - 1;
      while(j >= 0 && g_fvgs[j].qualityScore < key.qualityScore)
        {
         g_fvgs[j + 1] = g_fvgs[j];
         j--;
        }
      g_fvgs[j + 1] = key;
     }
  }

//--- Create or update a rectangle
void EnsureRect(const string name, datetime t1, double p1, datetime t2, double p2,
                color clr, bool fill, bool back)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t1);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, name, OBJPROP_TIME, 1, t2);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, fill);
   ObjectSetInteger(0, name, OBJPROP_BACK, back);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void EnsureText(const string name, datetime t, double p, const string txt,
                color clr, int fontSize, ENUM_ANCHOR_POINT anchor)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
   ObjectSetInteger(0, name, OBJPROP_TIME, 0, t);
   ObjectSetDouble (0, name, OBJPROP_PRICE, 0, p);
   ObjectSetString (0, name, OBJPROP_TEXT, txt);
   ObjectSetString (0, name, OBJPROP_FONT, "Arial");
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void HideText(const string name)
  {
   if(ObjectFind(0, name) >= 0)
      ObjectSetString(0, name, OBJPROP_TEXT, "");
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);

   h_volMA = iMA(_Symbol, PERIOD_CURRENT, InpVolLength, 0, MODE_SMA, VOLUME_TICK);
   h_emaCl = iMA(_Symbol, PERIOD_CURRENT, InpTrendLength, 0, MODE_EMA, PRICE_CLOSE);
   h_atr14 = iATR(_Symbol, PERIOD_CURRENT, 14);

   if(h_volMA == INVALID_HANDLE || h_emaCl == INVALID_HANDLE || h_atr14 == INVALID_HANDLE)
     {
      Print("RFVG: failed to create indicator handles");
      return INIT_FAILED;
     }

   ArrayResize(g_fvgs, 0);
   g_lastBarTime = 0;
   g_topKey = "";
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, FVG_PREFIX);
   if(h_volMA != INVALID_HANDLE) IndicatorRelease(h_volMA);
   if(h_emaCl != INVALID_HANDLE) IndicatorRelease(h_emaCl);
   if(h_atr14 != INVALID_HANDLE) IndicatorRelease(h_atr14);
   Comment("");
  }

//+------------------------------------------------------------------+
//| Detect a new FVG using bar [2] (the just-closed third bar)       |
//| Pine: bullFVG = low > high[2]; the gap forms between bars [2]    |
//| and [0]. We evaluate when bar [2] in current series is closed.   |
//+------------------------------------------------------------------+
void TryDetectFvg(const datetime &time[], const double &high[], const double &low[],
                  const double &open[], const double &close[], const long &tick_volume[],
                  int rates_total)
  {
   if(rates_total < 4)
      return;

   // index 0 = oldest (non-series). The "current" bar is rates_total-1.
   // Pine's "bar_index" trio is [2],[1],[0] in series notation. In our
   // non-series frame: i = rates_total-1 (current), i-2 = rates_total-3.
   int iCur = rates_total - 1;
   int iPrev2 = iCur - 2;
   if(iPrev2 < 0) return;

   bool bull = low[iCur] > high[iPrev2];
   bool bear = high[iCur] < low[iPrev2];
   if(!bull && !bear)
      return;

   // de-dup: same born time + direction
   datetime leftTime = time[iPrev2];
   int dir = bull ? 1 : -1;
   for(int k = 0; k < ArraySize(g_fvgs); k++)
      if(g_fvgs[k].leftTime == leftTime && g_fvgs[k].direction == dir)
         return;

   double top    = bull ? low[iCur]  : low[iPrev2];
   double bottom = bull ? high[iPrev2] : high[iCur];
   double sz     = MathAbs(top - bottom);

   double volMA = GetBufVal(h_volMA, 0);
   double atr   = GetBufVal(h_atr14, 0);
   double ema   = GetBufVal(h_emaCl, 0);
   double vol   = (double)tick_volume[iCur];
   double volScore = (volMA != 0.0) ? vol / volMA : 1.0;
   double trendScore = ((dir == 1 && close[iCur] > ema) || (dir == -1 && close[iCur] < ema)) ? 1.0 : 0.0;
   double mitigation = 0.0;

   double quality = sz * 100.0 + volScore * 10.0 + trendScore * 20.0 - mitigation * 50.0;

   double atrSafe = (atr > 0.0) ? atr : _Point;
   double gapStrength    = MathMin(sz / atrSafe, 2.0) / 2.0 * 40.0;
   double volStrength    = MathMin(volScore, 2.0) / 2.0 * 30.0;
   double trendStrength  = trendScore * 20.0;
   double rng = MathMax(high[iCur] - low[iCur], _Point);
   double candleStrength = MathAbs(close[iCur] - open[iCur]) / rng * 10.0;
   double total = gapStrength + volStrength + trendStrength + candleStrength;
   int main = (int)MathMax(MathMin(total, 100.0), 0.0);

   SFvg f;
   f.qualityScore = quality;
   f.top          = top;
   f.bottom       = bottom;
   f.direction    = dir;
   f.bornBar      = iCur;
   f.leftTime     = leftTime;
   f.size         = sz;
   f.mitigation   = 0.0;
   f.volumeScore  = volScore;
   f.trendScore   = trendScore;
   f.bullStrength = (dir == 1) ? main : 100 - main;
   f.bearStrength = (dir == -1) ? main : 100 - main;

   string base = FVG_PREFIX + IntegerToString((long)leftTime) + "_" + IntegerToString(dir);
   f.nBody    = base + "_body";
   f.nBull    = base + "_bull";
   f.nBear    = base + "_bear";
   f.nBodyTxt = base + "_btxt";
   f.nBullTxt = base + "_ultxt";
   f.nBearTxt = base + "_ertxt";

   int n = ArraySize(g_fvgs);
   ArrayResize(g_fvgs, n + 1);
   g_fvgs[n] = f;

   if(dir == 1 && InpAlertNewBull)
     {
      Alert(_Symbol, " ", EnumToString(_Period), ": new Bullish FVG");
      if(InpPushNotify) SendNotification(_Symbol + " new Bullish FVG");
     }
   if(dir == -1 && InpAlertNewBear)
     {
      Alert(_Symbol, " ", EnumToString(_Period), ": new Bearish FVG");
      if(InpPushNotify) SendNotification(_Symbol + " new Bearish FVG");
     }
  }

//+------------------------------------------------------------------+
//| Update mitigation/age/quality for all stored FVGs                |
//+------------------------------------------------------------------+
void UpdateFvgs(const datetime &time[], const double &high[], const double &low[], int rates_total)
  {
   int iCur = rates_total - 1;
   double curHigh = high[iCur];
   double curLow  = low[iCur];

   for(int i = ArraySize(g_fvgs) - 1; i >= 0; i--)
     {
      SFvg f = g_fvgs[i];
      int age = iCur - f.bornBar;

      bool touched = (f.direction == 1) ? (curLow <= f.top) : (curHigh >= f.bottom);

      if(touched && f.mitigation < 1.0)
        {
         double fillDist = (f.direction == 1) ? (f.top - curLow) : (curHigh - f.bottom);
         double zoneSize = MathMax(f.top - f.bottom, _Point);
         double newMit = MathMin(MathMax(fillDist / zoneSize, 0.0), 1.0);
         if(newMit > f.mitigation)
           {
            f.mitigation = newMit;
            if(f.direction == 1 && InpAlertBullTouch)
              {
               Alert(_Symbol, " bullish FVG touched");
               if(InpPushNotify) SendNotification(_Symbol + " bullish FVG touched");
              }
            if(f.direction == -1 && InpAlertBearTouch)
              {
               Alert(_Symbol, " bearish FVG touched");
               if(InpPushNotify) SendNotification(_Symbol + " bearish FVG touched");
              }
           }
        }

      f.qualityScore = f.size * 100.0 + f.volumeScore * 10.0 + f.trendScore * 20.0
                       - f.mitigation * 50.0 - (double)age * 0.1;

      if(f.mitigation >= 1.0)
        {
         if(InpAlertFullyMitigated)
           {
            Alert(_Symbol, " FVG fully mitigated");
            if(InpPushNotify) SendNotification(_Symbol + " FVG fully mitigated");
           }
         RemoveAt(i);
        }
      else
        {
         g_fvgs[i] = f;
        }
     }
  }

//+------------------------------------------------------------------+
//| Render: top-N visible, rest grayed                               |
//+------------------------------------------------------------------+
void Render(const datetime &time[], int rates_total)
  {
   int iCur = rates_total - 1;
   long secs = PeriodSeconds(PERIOD_CURRENT);
   if(secs <= 0) secs = 60;

   color bg = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   color fg = (color)ChartGetInteger(0, CHART_COLOR_FOREGROUND);
   color grayBody = BlendColor(clrGray, bg, 40);
   color bullSoft = BlendColor(InpBullColor, bg, InpBodyAlpha);
   color bearSoft = BlendColor(InpBearColor, bg, InpBodyAlpha);

   int n = ArraySize(g_fvgs);
   for(int i = 0; i < n; i++)
     {
      SFvg f = g_fvgs[i];
      bool show = (i < InpMaxZones);

      datetime left  = f.leftTime;
      datetime right = (datetime)(time[iCur] + secs * EXTEND_BARS);
      long width = (long)right - (long)left;
      long sizeUnit = MathMax(width / 200, 1);

      double topP = f.top;
      double botP = f.bottom;
      double midP = (topP + botP) * 0.5;

      color bodyClr = show ? (f.direction == 1 ? bullSoft : bearSoft) : grayBody;
      EnsureRect(f.nBody, left, topP, right, botP, bodyClr, true, true);

      if(show && InpShowBars)
        {
         color bullClr = InpBullColor;
         color bearClr = InpBearColor;

         datetime bullR = (datetime)((long)left + sizeUnit * f.bullStrength);
         datetime bearR = (datetime)((long)left + sizeUnit * f.bearStrength);

         EnsureRect(f.nBull, left, midP, bullR, botP, bullClr, true, false);
         EnsureRect(f.nBear, left, topP, bearR, midP, bearClr, true, false);

         string bullPct = IntegerToString(f.bullStrength) + "%";
         string bearPct = IntegerToString(f.bearStrength) + "%";
         EnsureText(f.nBullTxt, bullR, (midP + botP) * 0.5, bullPct, fg,
                    (int)InpStrengthSize, ANCHOR_RIGHT);
         EnsureText(f.nBearTxt, bearR, (topP + midP) * 0.5, bearPct, fg,
                    (int)InpStrengthSize, ANCHOR_RIGHT);

         string label = "";
         if(f.direction == -1)
           {
            if(f.bearStrength >= 70)            label = "Strong Bearish Imbalance";
            else if(f.bearStrength >= 55)       label = "Bearish Bias";
            else if(f.bullStrength > f.bearStrength) label = "Weak Bearish (Bull Pressure)";
            else                                 label = "Neutral Bearish";
           }
         else
           {
            if(f.bullStrength >= 70)            label = "Strong Bullish Imbalance";
            else if(f.bullStrength >= 55)       label = "Bullish Bias";
            else if(f.bearStrength > f.bullStrength) label = "Weak Bullish (Bear Pressure)";
            else                                 label = "Neutral Bullish";
           }

         if(InpShowBlockText)
            EnsureText(f.nBodyTxt, right, topP, label, bg, (int)InpBlockSize, ANCHOR_RIGHT_UPPER);
         else
            HideText(f.nBodyTxt);
        }
      else
        {
         // hide bars / text for grayed or bars-disabled rows
         if(ObjectFind(0, f.nBull) >= 0) ObjectDelete(0, f.nBull);
         if(ObjectFind(0, f.nBear) >= 0) ObjectDelete(0, f.nBear);
         HideText(f.nBullTxt);
         HideText(f.nBearTxt);
         HideText(f.nBodyTxt);
        }
     }
  }

//+------------------------------------------------------------------+
//| Trim to InpMaxStored (drop tail / lowest quality)                |
//+------------------------------------------------------------------+
void TrimStored()
  {
   while(ArraySize(g_fvgs) > InpMaxStored)
      RemoveAt(ArraySize(g_fvgs) - 1);
  }

//+------------------------------------------------------------------+
//| Sort + detect new top                                            |
//+------------------------------------------------------------------+
void SortAndCheckTop()
  {
   SortDesc();
   if(ArraySize(g_fvgs) == 0)
     {
      g_topKey = "";
      return;
     }
   string key = IntegerToString((long)g_fvgs[0].leftTime) + "_" + IntegerToString(g_fvgs[0].direction);
   if(key != g_topKey)
     {
      g_topKey = key;
      if(InpAlertTopRank)
        {
         Alert(_Symbol, " new top-ranked FVG");
         if(InpPushNotify) SendNotification(_Symbol + " new top-ranked FVG");
        }
     }
  }

//+------------------------------------------------------------------+
//| OnCalculate                                                      |
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
   if(rates_total < 4)
      return 0;

   bool newBar = (time[rates_total - 1] != g_lastBarTime);
   if(newBar)
     {
      g_lastBarTime = time[rates_total - 1];
      TryDetectFvg(time, high, low, open, close, tick_volume, rates_total);
     }

   UpdateFvgs(time, high, low, rates_total);
   SortAndCheckTop();
   TrimStored();
   Render(time, rates_total);

   ChartRedraw(0);
   return rates_total;
  }
//+------------------------------------------------------------------+
