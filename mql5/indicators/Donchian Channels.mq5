//+------------------------------------------------------------------+
//|                                            Donchian Channels.mq5 |
//|                          Ported from TradingView Pine v6 script  |
//+------------------------------------------------------------------+
#property copyright "Donchian Channels"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 3
#property indicator_plots   3

//--- Basis
#property indicator_label1  "Basis"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrOrange          // #FF6D00
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

//--- Upper
#property indicator_label2  "Upper"
#property indicator_type2   DRAW_LINE
#property indicator_color2  C'41,98,255'       // #2962FF
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

//--- Lower
#property indicator_label3  "Lower"
#property indicator_type3   DRAW_LINE
#property indicator_color3  C'41,98,255'       // #2962FF
#property indicator_style3  STYLE_SOLID
#property indicator_width3  1

//--- Inputs
input int InpLength = 96;   // Length
input int InpOffset = 0;    // Offset

//--- Buffers
double BasisBuffer[];
double UpperBuffer[];
double LowerBuffer[];

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpLength < 1)
     {
      Print("Length must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
     }

   SetIndexBuffer(0, BasisBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, UpperBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, LowerBuffer, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_SHIFT, InpOffset);
   PlotIndexSetInteger(1, PLOT_SHIFT, InpOffset);
   PlotIndexSetInteger(2, PLOT_SHIFT, InpOffset);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(2, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, InpLength - 1);
   PlotIndexSetInteger(1, PLOT_DRAW_BEGIN, InpLength - 1);
   PlotIndexSetInteger(2, PLOT_DRAW_BEGIN, InpLength - 1);

   IndicatorSetString(INDICATOR_SHORTNAME, StringFormat("DC(%d)", InpLength));
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   return(INIT_SUCCEEDED);
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
   if(rates_total < InpLength)
      return(0);

   int start = (prev_calculated == 0) ? InpLength - 1 : prev_calculated - 1;

   for(int i = start; i < rates_total; i++)
     {
      double hh = high[i];
      double ll = low[i];
      for(int j = 1; j < InpLength; j++)
        {
         int idx = i - j;
         if(high[idx] > hh) hh = high[idx];
         if(low[idx]  < ll) ll = low[idx];
        }
      UpperBuffer[i] = hh;
      LowerBuffer[i] = ll;
      BasisBuffer[i] = (hh + ll) / 2.0;
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
