//+------------------------------------------------------------------+
//|                                           BoxStrategy_PDRange.mq5 |
//| Draws previous day High/Low "box" levels on current chart.        |
//| Exposes buffers: PDH (prev day high), PDL (prev day low).          |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "PD High"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrTomato
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

#property indicator_label2  "PD Low"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrDeepSkyBlue
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

input group "=== Display ==="
input bool  InpDrawRectangle = true;            // Draw filled box rectangle
input color InpBoxColor      = clrSlateGray;    // Box color
input int   InpBoxOpacity    = 85;              // Box opacity (0-255, higher=more transparent)
input int   InpExtendBars    = 500;             // Extend rectangle to right (bars)

double PDHBuffer[];
double PDLBuffer[];

//+------------------------------------------------------------------+
bool GetPrevDayRange(double &pdh, double &pdl, datetime &dayStart, datetime &dayEnd)
{
   MqlRates d1[3];
   ArraySetAsSeries(d1, true);
   int copied = CopyRates(_Symbol, PERIOD_D1, 0, 3, d1);
   if(copied < 2) return false;

   pdh = d1[1].high;
   pdl = d1[1].low;
   dayStart = d1[1].time;
   dayEnd = d1[0].time;
   return true;
}

void DrawBox(const datetime t1, const datetime t2, const double low, const double high)
{
   long chartId = ChartID();
   string name = "BOX_PD_RANGE";

   if(!InpDrawRectangle)
   {
      ObjectDelete(chartId, name);
      return;
   }

   if(ObjectFind(chartId, name) < 0)
      ObjectCreate(chartId, name, OBJ_RECTANGLE, 0, t1, low, t2, high);

   ObjectSetInteger(chartId, name, OBJPROP_COLOR, InpBoxColor);
   ObjectSetInteger(chartId, name, OBJPROP_FILL, true);
   ObjectSetInteger(chartId, name, OBJPROP_BACK, true);
   ObjectSetInteger(chartId, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(chartId, name, OBJPROP_SELECTABLE, false);

   // opacity via ARGB
   int a = MathMax(0, MathMin(255, InpBoxOpacity));
   color c = (color)ColorToARGB(InpBoxColor, a);
   ObjectSetInteger(chartId, name, OBJPROP_COLOR, c);
}

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, PDHBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, PDLBuffer, INDICATOR_DATA);
   ArraySetAsSeries(PDHBuffer, true);
   ArraySetAsSeries(PDLBuffer, true);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectDelete(ChartID(), "BOX_PD_RANGE");
}

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
   if(rates_total < 2) return 0;

   double pdh, pdl;
   datetime tStart, tEnd;
   if(!GetPrevDayRange(pdh, pdl, tStart, tEnd))
      return rates_total;

   // Fill buffers for all bars
   int start = (prev_calculated == 0) ? rates_total - 1 : rates_total - prev_calculated;
   if(start > rates_total - 1) start = rates_total - 1;
   for(int i = start; i >= 0; i--)
   {
      PDHBuffer[i] = pdh;
      PDLBuffer[i] = pdl;
   }

   // Draw rectangle extended to the right
   int sec = PeriodSeconds(PERIOD_CURRENT);
   if(sec <= 0) sec = 60;
   datetime t2 = time[0] + (datetime)((long)sec * InpExtendBars);
   DrawBox(time[rates_total - 1], t2, pdl, pdh);

   return rates_total;
}
//+------------------------------------------------------------------+

