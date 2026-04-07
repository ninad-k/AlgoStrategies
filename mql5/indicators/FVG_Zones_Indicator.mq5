//+------------------------------------------------------------------+
//| Core logic: Detect 3-candle Fair Value Gaps on the chart TF and  |
//| draw semi-transparent rectangles (bull/bear) for the gap window.   |
//| Same geometry as FairValueGap_Regime_EA — for analysis only.       |
//| Author: Ninad K                                                   |
//+------------------------------------------------------------------+
#property copyright "Ninad K"
#property version   "1.00"
#property description "Visualizes bullish/bearish Fair Value Gap zones (no trading signals)."
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   0

input int    InpMinGapPoints = 10;    // Minimum gap height (points)
input int    InpLookback     = 200;   // Bars to scan backward
input int    InpMaxZones     = 50;    // Max rectangles on chart
input bool   InpShowBullish  = true;  // Draw demand gaps below price action
input bool   InpShowBearish  = true;  // Draw supply gaps above price action
input int    InpExtendBars   = 80;    // Extend each box to the right (bar count)
input color  InpBullColor    = clrDodgerBlue;
input color  InpBearColor    = clrCoral;
input bool   InpFill         = true;

double g_dummy[];

//+------------------------------------------------------------------+
//| Dummy buffer satisfies plot contract; graphics use chart objects |
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, g_dummy, INDICATOR_CALCULATIONS);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Remove all FVG rectangles created by this indicator               |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, "FVGZ_");
   Comment("");
  }

//+------------------------------------------------------------------+
//| Rebuild zone objects from OHLC (non-series order like the EA)      |
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
   if(rates_total < 3)
      return 0;

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpLookback + 5, rates);
   if(copied < 3)
      return rates_total;

   int    ratesTotal = copied;
   double minGap     = InpMinGapPoints * _Point;
   long   chartId    = ChartID();

   ObjectsDeleteAll(chartId, "FVGZ_");

   int startBar = MathMax(2, ratesTotal - InpLookback);
   int endBar   = ratesTotal - 2;
   int drawn    = 0;

   int sec = PeriodSeconds(PERIOD_CURRENT);
   if(sec <= 0)
      sec = 60;

   for(int i = startBar; i <= endBar && drawn < InpMaxZones; i++)
     {
      if(InpShowBullish)
        {
         double gapLow  = rates[i - 2].high;
         double gapHigh = rates[i].low;
         if(gapHigh > gapLow && (gapHigh - gapLow) >= minGap)
           {
            datetime t1 = rates[i - 1].time;
            datetime t2 = t1 + (datetime)((long)sec * InpExtendBars);
            string   name = "FVGZ_B_" + IntegerToString(drawn) + "_" + IntegerToString((int)t1);
            if(ObjectCreate(chartId, name, OBJ_RECTANGLE, 0, t1, gapLow, t2, gapHigh))
              {
               ObjectSetInteger(chartId, name, OBJPROP_COLOR, InpBullColor);
               ObjectSetInteger(chartId, name, OBJPROP_FILL, InpFill);
               ObjectSetInteger(chartId, name, OBJPROP_BACK, true);
               ObjectSetInteger(chartId, name, OBJPROP_WIDTH, 1);
               ObjectSetInteger(chartId, name, OBJPROP_SELECTABLE, false);
               drawn++;
              }
           }
        }

      if(drawn >= InpMaxZones)
         break;

      if(InpShowBearish)
        {
         double gapHigh = rates[i - 2].low;
         double gapLow  = rates[i].high;
         if(gapHigh > gapLow && (gapHigh - gapLow) >= minGap)
           {
            datetime t1 = rates[i - 1].time;
            datetime t2 = t1 + (datetime)((long)sec * InpExtendBars);
            string   name = "FVGZ_S_" + IntegerToString(drawn) + "_" + IntegerToString((int)t1);
            if(ObjectCreate(chartId, name, OBJ_RECTANGLE, 0, t1, gapLow, t2, gapHigh))
              {
               ObjectSetInteger(chartId, name, OBJPROP_COLOR, InpBearColor);
               ObjectSetInteger(chartId, name, OBJPROP_FILL, InpFill);
               ObjectSetInteger(chartId, name, OBJPROP_BACK, true);
               ObjectSetInteger(chartId, name, OBJPROP_WIDTH, 1);
               ObjectSetInteger(chartId, name, OBJPROP_SELECTABLE, false);
               drawn++;
              }
           }
        }
     }

   ChartRedraw(chartId);
   return rates_total;
  }
//+------------------------------------------------------------------+
