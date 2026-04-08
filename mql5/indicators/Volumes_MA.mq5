//+------------------------------------------------------------------+
//|                                                   Volumes_MA.mq5 |
//|                  Volumes histogram with a moving average overlay |
//+------------------------------------------------------------------+
#property copyright "Volumes MA"
#property version   "1.00"
#property indicator_separate_window
#property indicator_buffers 4
#property indicator_plots   2

//--- Volume histogram (up = green, down = red, like built-in Volumes)
#property indicator_label1  "Volume"
#property indicator_type1   DRAW_COLOR_HISTOGRAM
#property indicator_color1  clrGreen, clrRed
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

//--- Volume MA line
#property indicator_label2  "Volume MA"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrOrange
#property indicator_style2  STYLE_SOLID
#property indicator_width2  2

//--- Inputs
input bool               InpShowMA      = true;          // Show Volume MA
input int                InpMaLength    = 30;            // MA Length
input ENUM_MA_METHOD     InpMaMethod    = MODE_SMA;      // MA Method
input ENUM_APPLIED_VOLUME InpVolumeType = VOLUME_TICK;   // Volume Type

//--- Buffers
double VolumeBuffer[];
double VolumeColors[];
double MaBuffer[];
double MaSrcBuffer[]; // calculation source for iMAOnArray-like handling

int    g_ma_handle = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpMaLength < 1)
     {
      Print("MA Length must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
     }

   SetIndexBuffer(0, VolumeBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, VolumeColors, INDICATOR_COLOR_INDEX);
   SetIndexBuffer(2, MaBuffer,     INDICATOR_DATA);
   SetIndexBuffer(3, MaSrcBuffer,  INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, 0);
   PlotIndexSetInteger(1, PLOT_DRAW_BEGIN, InpMaLength - 1);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("Volumes MA(%d)", InpMaLength));
   IndicatorSetInteger(INDICATOR_DIGITS, 0);

   if(InpShowMA)
     {
      g_ma_handle = iMA(_Symbol, _Period, InpMaLength, 0, InpMaMethod, InpVolumeType);
      if(g_ma_handle == INVALID_HANDLE)
        {
         Print("Failed to create iMA handle");
         return(INIT_FAILED);
        }
     }
   else
     {
      PlotIndexSetString(1, PLOT_LABEL, "");
     }

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Custom indicator deinitialization                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_ma_handle != INVALID_HANDLE)
      IndicatorRelease(g_ma_handle);
  }

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
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
   if(rates_total <= 0)
      return(0);

   int start = (prev_calculated == 0) ? 0 : prev_calculated - 1;

   for(int i = start; i < rates_total; i++)
     {
      double v = (InpVolumeType == VOLUME_TICK)
                 ? (double)tick_volume[i]
                 : (double)volume[i];
      VolumeBuffer[i] = v;

      // Up bar = green (0), down bar = red (1); doji uses prior close direction
      if(close[i] > open[i])
         VolumeColors[i] = 0;
      else if(close[i] < open[i])
         VolumeColors[i] = 1;
      else
         VolumeColors[i] = (i > 0 && close[i] >= close[i-1]) ? 0 : 1;
     }

   // Copy MA values from the iMA handle (built on volume series)
   if(InpShowMA && g_ma_handle != INVALID_HANDLE)
     {
      int to_copy = (prev_calculated == 0) ? rates_total : (rates_total - prev_calculated + 1);
      if(to_copy > rates_total) to_copy = rates_total;

      if(CopyBuffer(g_ma_handle, 0, 0, to_copy, MaBuffer) <= 0)
         return(prev_calculated);
     }
   else
     {
      for(int i = start; i < rates_total; i++)
         MaBuffer[i] = EMPTY_VALUE;
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
