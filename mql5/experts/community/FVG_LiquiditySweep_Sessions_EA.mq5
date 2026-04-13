//+------------------------------------------------------------------+
//| FVG + Liquidity Sweep + Session Filter EA                        |
//| Institutional-style trading engine                               |
//| Entry: trend alignment + liquidity sweep + FVG zone              |
//| Sessions: London and New York kill zones                         |
//| SL/TP: ATR-based with 1.8x multiplier                           |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade g_Trade;

input group "=== Expert ==="
input long    InpMagicNumber   = 20260417;
input double  InpFixedLot      = 0.10;
input int     InpDeviation     = 20;

input group "=== Trend Detection ==="
input int     InpEMAFast       = 9;
input int     InpEMASlow       = 21;
input int     InpEMATrend      = 50;       // Long-term trend EMA

input group "=== FVG Detection ==="
input int     InpFVGLookback   = 50;       // Bars to scan for FVGs
input double  InpFVGMinGap     = 0.0;      // Min gap size (0 = auto from ATR)

input group "=== Liquidity Sweep ==="
input int     InpSwingLookback = 20;       // Bars to detect swing points
input double  InpSweepWickMin  = 0.5;      // Min wick ratio beyond level

input group "=== Risk ==="
input int     InpATRPeriod     = 14;
input double  InpATRMult       = 1.8;      // ATR mult for SL
input double  InpRiskReward    = 2.0;      // R:R ratio
input int     InpMaxPositions  = 3;

input group "=== Kill Zone Sessions (server hour) ==="
input int     InpLondonOpen    = 7;
input int     InpLondonClose   = 10;
input int     InpNYOpen        = 12;
input int     InpNYClose       = 15;

int hEMAFast = INVALID_HANDLE, hEMASlow = INVALID_HANDLE, hEMATrend = INVALID_HANDLE;
int hATR = INVALID_HANDLE;
datetime g_LastBarTime = 0;

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_LastBarTime) { g_LastBarTime = t; return true; }
   return false;
}

int CountPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            (long)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            count++;
   }
   return count;
}

double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0) tick = _Point;
   return NormalizeDouble(MathRound(price / tick) * tick, (int)_Digits);
}

bool IsInKillZone()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int h = dt.hour;
   return (h >= InpLondonOpen && h <= InpLondonClose) || (h >= InpNYOpen && h <= InpNYClose);
}

// Detect Fair Value Gap on bar[barIdx] looking at 3-candle pattern
// Bullish FVG: bar[barIdx+1].high < bar[barIdx-1].low (gap up)
// Returns gap midpoint price, 0 if no FVG
double DetectFVG(int direction, double &highs[], double &lows[], int startBar, double minGap)
{
   for(int i = startBar; i < startBar + InpFVGLookback - 2; i++)
   {
      if(i + 2 >= ArraySize(highs)) break;

      if(direction == 1) // Bullish FVG
      {
         double gap = lows[i] - highs[i + 2]; // bar[i] low vs bar[i+2] high
         if(gap > minGap)
            return (lows[i] + highs[i + 2]) / 2.0;
      }
      else // Bearish FVG
      {
         double gap = lows[i + 2] - highs[i]; // bar[i+2] low vs bar[i] high
         if(gap > minGap)
            return (highs[i] + lows[i + 2]) / 2.0;
      }
   }
   return 0;
}

// Detect if recent price swept a swing high/low (liquidity grab)
bool DetectLiquiditySweep(int direction, double &highs[], double &lows[], double &closes[])
{
   // Find swing point in lookback range
   for(int i = 2; i < InpSwingLookback - 1 && i + 1 < ArraySize(highs); i++)
   {
      if(direction == -1) // Looking for swept swing high (bearish setup)
      {
         // Swing high: highs[i] > both neighbors
         if(highs[i] > highs[i - 1] && highs[i] > highs[i + 1])
         {
            // Bar[1] wick pierced above but closed below
            if(highs[1] > highs[i] && closes[1] < highs[i])
               return true;
         }
      }
      else // Looking for swept swing low (bullish setup)
      {
         if(lows[i] < lows[i - 1] && lows[i] < lows[i + 1])
         {
            if(lows[1] < lows[i] && closes[1] > lows[i])
               return true;
         }
      }
   }
   return false;
}

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hEMAFast  = iMA(_Symbol, PERIOD_CURRENT, InpEMAFast,  0, MODE_EMA, PRICE_CLOSE);
   hEMASlow  = iMA(_Symbol, PERIOD_CURRENT, InpEMASlow,  0, MODE_EMA, PRICE_CLOSE);
   hEMATrend = iMA(_Symbol, PERIOD_CURRENT, InpEMATrend, 0, MODE_EMA, PRICE_CLOSE);
   hATR      = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);

   if(hEMAFast == INVALID_HANDLE || hEMASlow == INVALID_HANDLE ||
      hEMATrend == INVALID_HANDLE || hATR == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. err=", GetLastError());
      return INIT_FAILED;
   }

   Print("FVG_LiquiditySweep_Sessions initialized. ", _Symbol, " Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEMAFast  != INVALID_HANDLE) IndicatorRelease(hEMAFast);
   if(hEMASlow  != INVALID_HANDLE) IndicatorRelease(hEMASlow);
   if(hEMATrend != INVALID_HANDLE) IndicatorRelease(hEMATrend);
   if(hATR      != INVALID_HANDLE) IndicatorRelease(hATR);
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(!IsInKillZone()) return;
   if(CountPositions() >= InpMaxPositions) return;

   int barsNeeded = InpFVGLookback + 5;
   double emaF[2], emaS[2], emaT[2], atrBuf[2];
   ArraySetAsSeries(emaF, true); ArraySetAsSeries(emaS, true);
   ArraySetAsSeries(emaT, true); ArraySetAsSeries(atrBuf, true);

   if(CopyBuffer(hEMAFast,  0, 0, 2, emaF) < 2) return;
   if(CopyBuffer(hEMASlow,  0, 0, 2, emaS) < 2) return;
   if(CopyBuffer(hEMATrend, 0, 0, 2, emaT) < 2) return;
   if(CopyBuffer(hATR,      0, 0, 2, atrBuf) < 2) return;

   double atr = atrBuf[1];
   if(atr <= 0) return;

   // Price data for FVG and sweep detection
   double highs[], lows[], closes[];
   ArraySetAsSeries(highs, true); ArraySetAsSeries(lows, true); ArraySetAsSeries(closes, true);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, 0, barsNeeded, highs) < barsNeeded) return;
   if(CopyLow(_Symbol, PERIOD_CURRENT, 0, barsNeeded, lows) < barsNeeded) return;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 0, barsNeeded, closes) < barsNeeded) return;

   // Trend alignment: EMA stack
   bool bullTrend = (emaF[1] > emaS[1] && emaS[1] > emaT[1]);
   bool bearTrend = (emaF[1] < emaS[1] && emaS[1] < emaT[1]);

   double minGap = (InpFVGMinGap > 0) ? InpFVGMinGap : atr * 0.3;

   if(bullTrend)
   {
      // Require liquidity sweep (sell-side swept) + bullish FVG
      bool swept = DetectLiquiditySweep(1, highs, lows, closes);
      double fvgLevel = DetectFVG(1, highs, lows, 1, minGap);

      if(swept && fvgLevel > 0)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl  = NormalizePrice(ask - InpATRMult * atr);
         double tp  = NormalizePrice(ask + InpATRMult * InpRiskReward * atr);
         g_Trade.Buy(InpFixedLot, _Symbol, 0.0, sl, tp, "FVG_Sweep BUY");
         Print("FVG+Sweep BUY: fvg=", DoubleToString(fvgLevel, (int)_Digits), " atr=", DoubleToString(atr, (int)_Digits));
      }
   }
   else if(bearTrend)
   {
      bool swept = DetectLiquiditySweep(-1, highs, lows, closes);
      double fvgLevel = DetectFVG(-1, highs, lows, 1, minGap);

      if(swept && fvgLevel > 0)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl  = NormalizePrice(bid + InpATRMult * atr);
         double tp  = NormalizePrice(bid - InpATRMult * InpRiskReward * atr);
         g_Trade.Sell(InpFixedLot, _Symbol, 0.0, sl, tp, "FVG_Sweep SELL");
         Print("FVG+Sweep SELL: fvg=", DoubleToString(fvgLevel, (int)_Digits), " atr=", DoubleToString(atr, (int)_Digits));
      }
   }
}
//+------------------------------------------------------------------+
