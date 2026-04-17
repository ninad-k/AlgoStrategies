//+------------------------------------------------------------------+
//|                                       PivotVwapEma_Indicator.mq5 |
//|      Plots Pivot Points (Daily), VWAP, 20 EMA on chart           |
//|      Shows entry signals based on confluence of all three        |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property indicator_chart_window
#property indicator_buffers 10
#property indicator_plots   10

//--- Pivot line
#property indicator_label1  "Pivot"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrGold
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

//--- R1
#property indicator_label2  "R1"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrRed
#property indicator_style2  STYLE_DOT
#property indicator_width2  1

//--- R2
#property indicator_label3  "R2"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrRed
#property indicator_style3  STYLE_DOT
#property indicator_width3  1

//--- R3
#property indicator_label4  "R3"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrRed
#property indicator_style4  STYLE_DASHDOT
#property indicator_width4  1

//--- S1
#property indicator_label5  "S1"
#property indicator_type5   DRAW_LINE
#property indicator_color5  clrLime
#property indicator_style5  STYLE_DOT
#property indicator_width5  1

//--- S2
#property indicator_label6  "S2"
#property indicator_type6   DRAW_LINE
#property indicator_color6  clrLime
#property indicator_style6  STYLE_DOT
#property indicator_width6  1

//--- S3
#property indicator_label7  "S3"
#property indicator_type7   DRAW_LINE
#property indicator_color7  clrLime
#property indicator_style7  STYLE_DASHDOT
#property indicator_width7  1

//--- VWAP
#property indicator_label8  "VWAP"
#property indicator_type8   DRAW_LINE
#property indicator_color8  clrDodgerBlue
#property indicator_style8  STYLE_SOLID
#property indicator_width8  2

//--- Buy signal arrows
#property indicator_label9  "Buy Signal"
#property indicator_type9   DRAW_ARROW
#property indicator_color9  clrLime
#property indicator_width9  3

//--- Sell signal arrows
#property indicator_label10 "Sell Signal"
#property indicator_type10  DRAW_ARROW
#property indicator_color10 clrRed
#property indicator_width10 3

//--- Input parameters
input int    InpEmaPeriod       = 20;       // EMA Period
input int    InpSessionStartHr  = 9;        // Session Start Hour
input int    InpSessionStartMin = 15;       // Session Start Minute

//--- Indicator buffers
double PivotBuffer[], R1Buffer[], R2Buffer[], R3Buffer[];
double S1Buffer[], S2Buffer[], S3Buffer[];
double VwapBuffer[];
double BuySignalBuffer[], SellSignalBuffer[];

//--- EMA handle
int emaHandle;

//+------------------------------------------------------------------+
int OnInit()
{
    SetIndexBuffer(0, PivotBuffer, INDICATOR_DATA);
    SetIndexBuffer(1, R1Buffer,    INDICATOR_DATA);
    SetIndexBuffer(2, R2Buffer,    INDICATOR_DATA);
    SetIndexBuffer(3, R3Buffer,    INDICATOR_DATA);
    SetIndexBuffer(4, S1Buffer,    INDICATOR_DATA);
    SetIndexBuffer(5, S2Buffer,    INDICATOR_DATA);
    SetIndexBuffer(6, S3Buffer,    INDICATOR_DATA);
    SetIndexBuffer(7, VwapBuffer,  INDICATOR_DATA);
    SetIndexBuffer(8, BuySignalBuffer,  INDICATOR_DATA);
    SetIndexBuffer(9, SellSignalBuffer, INDICATOR_DATA);

    // Arrow codes
    PlotIndexSetInteger(8, PLOT_ARROW, 233); // Up arrow
    PlotIndexSetInteger(9, PLOT_ARROW, 234); // Down arrow

    // EMA handle
    emaHandle = iMA(_Symbol, PERIOD_CURRENT, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
    if(emaHandle == INVALID_HANDLE)
    {
        Print("Failed to create EMA handle");
        return INIT_FAILED;
    }

    IndicatorSetString(INDICATOR_SHORTNAME, "PivotVwapEma(" + IntegerToString(InpEmaPeriod) + ")");
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(emaHandle != INVALID_HANDLE)
        IndicatorRelease(emaHandle);
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
    if(rates_total < InpEmaPeriod + 1)
        return 0;

    ArraySetAsSeries(time, true);
    ArraySetAsSeries(open, true);
    ArraySetAsSeries(high, true);
    ArraySetAsSeries(low, true);
    ArraySetAsSeries(close, true);
    ArraySetAsSeries(tick_volume, true);

    // Get EMA values
    double emaValues[];
    ArraySetAsSeries(emaValues, true);
    if(CopyBuffer(emaHandle, 0, 0, rates_total, emaValues) < rates_total)
        return 0;

    // Get daily bars for pivot calculation
    MqlRates daily[];
    ArraySetAsSeries(daily, true);
    int dailyBars = CopyRates(_Symbol, PERIOD_D1, 0, 10, daily);
    if(dailyBars < 2)
        return 0;

    int start = (prev_calculated == 0) ? rates_total - 1 : rates_total - prev_calculated;

    for(int i = start; i >= 0; i--)
    {
        // Find which daily bar this intraday bar belongs to
        datetime barDate = time[i];
        MqlDateTime barDT;
        TimeToStruct(barDate, barDT);

        // Use previous day for pivot calculation
        double prevH = daily[1].high;
        double prevL = daily[1].low;
        double prevC = daily[1].close;

        // Check if bar is from today or previous days
        MqlDateTime todayDT;
        TimeToStruct(daily[0].time, todayDT);

        if(barDT.day != todayDT.day || barDT.mon != todayDT.mon)
        {
            // For historical bars, find the correct daily bar
            for(int d = 0; d < dailyBars - 1; d++)
            {
                MqlDateTime dDT;
                TimeToStruct(daily[d].time, dDT);
                if(barDT.day == dDT.day && barDT.mon == dDT.mon && barDT.year == dDT.year)
                {
                    if(d + 1 < dailyBars)
                    {
                        prevH = daily[d + 1].high;
                        prevL = daily[d + 1].low;
                        prevC = daily[d + 1].close;
                    }
                    break;
                }
            }
        }

        // Calculate traditional pivot points
        double pivot = (prevH + prevL + prevC) / 3.0;
        double r1 = 2.0 * pivot - prevL;
        double s1 = 2.0 * pivot - prevH;
        double r2 = pivot + (prevH - prevL);
        double s2 = pivot - (prevH - prevL);
        double r3 = prevH + 2.0 * (pivot - prevL);
        double s3 = prevL - 2.0 * (prevH - pivot);

        PivotBuffer[i] = pivot;
        R1Buffer[i] = r1;
        R2Buffer[i] = r2;
        R3Buffer[i] = r3;
        S1Buffer[i] = s1;
        S2Buffer[i] = s2;
        S3Buffer[i] = s3;

        // Calculate session VWAP
        VwapBuffer[i] = CalculateVWAP(i, time, high, low, close, tick_volume, rates_total);

        // Initialize signal buffers
        BuySignalBuffer[i]  = EMPTY_VALUE;
        SellSignalBuffer[i] = EMPTY_VALUE;

        // Signal logic (skip first bar)
        if(i < rates_total - 1)
        {
            double ema = emaValues[i];
            double vwap = VwapBuffer[i];
            double closePrice = close[i];
            bool isGreenCandle = close[i] > open[i];
            bool isRedCandle   = close[i] < open[i];

            // LONG: Price > Pivot AND Price > EMA AND Price > VWAP AND green candle
            if(closePrice > pivot && closePrice > ema && closePrice > vwap && isGreenCandle)
            {
                // Check previous bar was not already above all three (new crossover)
                double prevClose = close[i + 1];
                if(prevClose <= pivot || prevClose <= ema || prevClose <= vwap)
                    BuySignalBuffer[i] = low[i] - (high[i] - low[i]) * 0.5;
            }

            // SHORT: Price < Pivot AND Price < EMA AND Price < VWAP AND red candle
            if(closePrice < pivot && closePrice < ema && closePrice < vwap && isRedCandle)
            {
                double prevClose = close[i + 1];
                if(prevClose >= pivot || prevClose >= ema || prevClose >= vwap)
                    SellSignalBuffer[i] = high[i] + (high[i] - low[i]) * 0.5;
            }
        }
    }

    return rates_total;
}

//+------------------------------------------------------------------+
//| Calculate VWAP from session start for a given bar                |
//+------------------------------------------------------------------+
double CalculateVWAP(int barIndex,
                     const datetime &time[],
                     const double &high[],
                     const double &low[],
                     const double &close[],
                     const long &tick_volume[],
                     int rates_total)
{
    MqlDateTime barDT;
    TimeToStruct(time[barIndex], barDT);

    double cumTPV = 0;
    double cumVol = 0;

    // Walk backwards from barIndex to find session start
    for(int j = barIndex; j < rates_total; j++)
    {
        MqlDateTime jDT;
        TimeToStruct(time[j], jDT);

        // Different day = session boundary
        if(jDT.day != barDT.day || jDT.mon != barDT.mon || jDT.year != barDT.year)
            break;

        // Before session start time
        if(jDT.hour < InpSessionStartHr ||
           (jDT.hour == InpSessionStartHr && jDT.min < InpSessionStartMin))
            break;

        double tp = (high[j] + low[j] + close[j]) / 3.0;
        double vol = (double)tick_volume[j];
        if(vol <= 0) vol = 1;

        cumTPV += tp * vol;
        cumVol += vol;
    }

    if(cumVol > 0)
        return cumTPV / cumVol;

    return close[barIndex];
}
//+------------------------------------------------------------------+
