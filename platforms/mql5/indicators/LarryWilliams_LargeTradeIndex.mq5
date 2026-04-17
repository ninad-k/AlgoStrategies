//+------------------------------------------------------------------+
//|                              LarryWilliams_LargeTradeIndex.mq5  |
//|         Larry Williams Large Trade Index (LWTI) - ported from   |
//|         the Pine v5 script by Loxx                              |
//+------------------------------------------------------------------+
#property copyright "LWTI - ported from Loxx Pine v5"
#property version   "1.00"
#property indicator_separate_window
#property indicator_buffers 5
#property indicator_plots   2

//--- LWTI line (colored: green above 50, red below)
#property indicator_label1  "LWTI"
#property indicator_type1   DRAW_COLOR_LINE
#property indicator_color1  C'45,210,4', C'210,4,45'   // #2DD204, #D2042D
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

//--- Midline (50)
#property indicator_label2  "Mid"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrGray
#property indicator_style2  STYLE_DOT
#property indicator_width2  1

#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_level1  50

//--- Smoothing method enum (matches Pine options)
enum ENUM_SMOOTH_TYPE
  {
   SMOOTH_SMA = 0, // SMA
   SMOOTH_EMA = 1, // EMA
   SMOOTH_WMA = 2, // WMA
   SMOOTH_RMA = 3  // RMA (Wilder)
  };

//--- Inputs
input int             InpPeriod      = 25;          // Period
input bool            InpSmoothLWPI  = false;       // Smooth LWPI?
input ENUM_SMOOTH_TYPE InpSmoothType = SMOOTH_SMA;  // Smoothing Type
input int             InpSmoothPeriod = 20;         // Smoothing Period

//--- Buffers
double LwtiBuffer[];
double LwtiColors[];
double MidBuffer[];
double RawBuffer[];   // unsmoothed LWTI (calculations)
double AtrBuffer[];   // ATR (calculations)

int g_atr_handle = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpPeriod < 1 || InpSmoothPeriod < 1)
     {
      Print("Periods must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
     }

   SetIndexBuffer(0, LwtiBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, LwtiColors, INDICATOR_COLOR_INDEX);
   SetIndexBuffer(2, MidBuffer,  INDICATOR_DATA);
   SetIndexBuffer(3, RawBuffer,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(4, AtrBuffer,  INDICATOR_CALCULATIONS);

   int draw_begin = InpPeriod + (InpSmoothLWPI ? InpSmoothPeriod : 0);
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, draw_begin);
   PlotIndexSetInteger(1, PLOT_DRAW_BEGIN, 0);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("LWTI(%d%s)", InpPeriod,
                                   InpSmoothLWPI ? StringFormat(",smooth %d", InpSmoothPeriod) : ""));
   IndicatorSetInteger(INDICATOR_DIGITS, 2);

   g_atr_handle = iATR(_Symbol, _Period, InpPeriod);
   if(g_atr_handle == INVALID_HANDLE)
     {
      Print("Failed to create iATR handle");
      return(INIT_FAILED);
     }

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_atr_handle != INVALID_HANDLE)
      IndicatorRelease(g_atr_handle);
  }

//+------------------------------------------------------------------+
//| SMA over a source array (working on time-series index i back)    |
//+------------------------------------------------------------------+
double SmaOnArray(const double &arr[], int i, int len)
  {
   if(i < len - 1) return(EMPTY_VALUE);
   double sum = 0.0;
   for(int k = 0; k < len; k++)
      sum += arr[i - k];
   return(sum / len);
  }

//+------------------------------------------------------------------+
//| WMA over source array                                            |
//+------------------------------------------------------------------+
double WmaOnArray(const double &arr[], int i, int len)
  {
   if(i < len - 1) return(EMPTY_VALUE);
   double sum = 0.0, wsum = 0.0;
   for(int k = 0; k < len; k++)
     {
      double w = (double)(len - k);
      sum  += arr[i - k] * w;
      wsum += w;
     }
   return(sum / wsum);
  }

//+------------------------------------------------------------------+
//| Apply selected smoothing on Raw -> Lwti for index i              |
//| EMA / RMA are computed iteratively using prior LwtiBuffer        |
//+------------------------------------------------------------------+
double Smooth(int i, int len, ENUM_SMOOTH_TYPE type)
  {
   if(type == SMOOTH_SMA)
      return SmaOnArray(RawBuffer, i, len);

   if(type == SMOOTH_WMA)
      return WmaOnArray(RawBuffer, i, len);

   // EMA / RMA need a seed (SMA over first `len` valid raw values)
   if(i < len - 1)
      return(EMPTY_VALUE);

   if(i == len - 1 || LwtiBuffer[i-1] == EMPTY_VALUE)
      return SmaOnArray(RawBuffer, i, len);

   if(type == SMOOTH_EMA)
     {
      double k = 2.0 / (len + 1.0);
      return LwtiBuffer[i-1] + k * (RawBuffer[i] - LwtiBuffer[i-1]);
     }
   // RMA (Wilder)
   double a = 1.0 / (double)len;
   return LwtiBuffer[i-1] + a * (RawBuffer[i] - LwtiBuffer[i-1]);
  }

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
   if(rates_total < InpPeriod + 1)
      return(0);

   // Pull ATR series
   if(CopyBuffer(g_atr_handle, 0, 0, rates_total, AtrBuffer) <= 0)
      return(prev_calculated);

   int start = (prev_calculated == 0) ? InpPeriod : prev_calculated - 1;
   if(start < InpPeriod) start = InpPeriod;

   for(int i = start; i < rates_total; i++)
     {
      // ma = SMA(close - close[per], per)
      double sum = 0.0;
      for(int k = 0; k < InpPeriod; k++)
        {
         int idx = i - k;
         sum += close[idx] - close[idx - InpPeriod];
        }
      double ma = sum / InpPeriod;

      double atr = AtrBuffer[i];
      double raw = (atr > 0.0) ? (ma / atr * 50.0 + 50.0) : 50.0;
      RawBuffer[i] = raw;

      double val = InpSmoothLWPI ? Smooth(i, InpSmoothPeriod, InpSmoothType) : raw;
      LwtiBuffer[i] = val;
      LwtiColors[i] = (val != EMPTY_VALUE && val > 50.0) ? 0 : 1;

      MidBuffer[i] = 50.0;
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
