//+------------------------------------------------------------------+
//| FVG + Liquidity Sweep + XGBoost Filter EA                        |
//| Institutional setup detection with ML loss filtering              |
//| Entry: EMA stack + liquidity sweep + FVG + XGBoost confirmation  |
//| Sessions: Optional London/NY kill zones                          |
//| SL/TP: ATR-based with 1.8x multiplier                            |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "2.00"
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
input int     InpEMATrend      = 50;

input group "=== FVG Detection ==="
input int     InpFVGLookback   = 50;
input double  InpFVGMinGap     = 0.0;

input group "=== Liquidity Sweep ==="
input int     InpSwingLookback = 20;
input double  InpSweepWickMin  = 0.5;

input group "=== XGBoost Filter ==="
input string  InpONNXPath      = "FVG_Filter_XGB.onnx";
input double  InpONNXThreshold = 0.55;     // Probability threshold (0.5-1.0)
input bool    InpUseONNX       = true;     // Enable ONNX filtering

input group "=== Risk ==="
input int     InpATRPeriod     = 14;
input double  InpATRMult       = 1.8;
input double  InpRiskReward    = 2.0;
input int     InpMaxPositions  = 3;

input group "=== Kill Zone Sessions (optional, server hour) ==="
input bool    InpUseKillZones  = false;    // Enable session filter
input int     InpLondonOpen    = 7;
input int     InpLondonClose   = 10;
input int     InpNYOpen        = 12;
input int     InpNYClose       = 15;

int hEMAFast = INVALID_HANDLE, hEMASlow = INVALID_HANDLE, hEMATrend = INVALID_HANDLE;
int hATR = INVALID_HANDLE;
int hRSI = INVALID_HANDLE;
long hONNX = INVALID_HANDLE;
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
   if(!InpUseKillZones) return true;
   MqlDateTime dt;
   TimeCurrent(dt);
   int h = dt.hour;
   return (h >= InpLondonOpen && h <= InpLondonClose) || (h >= InpNYOpen && h <= InpNYClose);
}

double DetectFVG(int direction, double &highs[], double &lows[], int startBar, double minGap)
{
   for(int i = startBar; i < startBar + InpFVGLookback - 2; i++)
   {
      if(i + 2 >= ArraySize(highs)) break;

      if(direction == 1)
      {
         double gap = lows[i] - highs[i + 2];
         if(gap > minGap)
            return (lows[i] + highs[i + 2]) / 2.0;
      }
      else
      {
         double gap = lows[i + 2] - highs[i];
         if(gap > minGap)
            return (highs[i] + lows[i + 2]) / 2.0;
      }
   }
   return 0;
}

bool DetectLiquiditySweep(int direction, double &highs[], double &lows[], double &closes[])
{
   for(int i = 2; i < InpSwingLookback - 1 && i + 1 < ArraySize(highs); i++)
   {
      if(direction == -1)
      {
         if(highs[i] > highs[i - 1] && highs[i] > highs[i + 1])
         {
            if(highs[1] > highs[i] && closes[1] < highs[i])
               return true;
         }
      }
      else
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

// Build 8 features for ONNX inference
bool BuildONNXFeatures(int direction, double &highs[], double &lows[], double &closes[],
                       double emaF, double emaS, double emaT, double atr, double rsi,
                       double fvgGap, double sweepStr, float &features[])
{
   ArrayResize(features, 8);

   // Feature 0: EMA alignment
   features[0] = (direction == 1) ? 1.0f : ((direction == -1) ? -1.0f : 0.0f);

   // Feature 1: FVG gap normalized
   features[1] = (atr > 0) ? (float)(MathAbs(fvgGap) / atr) : 0.0f;

   // Feature 2: Liquidity sweep strength (estimated)
   features[2] = (float)sweepStr;

   // Feature 3: ATR normalized
   features[3] = (float)((closes[1] > 0) ? atr / closes[1] : 0.0);

   // Feature 4: RSI momentum
   features[4] = (float)((rsi - 50) / 50.0);

   // Feature 5: Bar body size
   double barBody = MathAbs(closes[1] - closes[2]);
   features[5] = (atr > 0) ? (float)(barBody / atr) : 0.0f;

   // Feature 6: Wick extension ratio
   double bodyMin = MathMin(closes[1], closes[2]);
   double bodyMax = MathMax(closes[1], closes[2]);
   if(direction == 1)
      features[6] = (float)((closes[2] - lows[1]) / (MathMax(bodyMax - bodyMin, 1e-6)));
   else
      features[6] = (float)((highs[1] - closes[2]) / (MathMax(bodyMax - bodyMin, 1e-6)));

   // Feature 7: Close position in bar range
   double range = highs[1] - lows[1];
   if(range > 0)
      features[7] = (float)((closes[1] - lows[1]) / range);
   else
      features[7] = 0.5f;

   return true;
}

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hEMAFast  = iMA(_Symbol, PERIOD_CURRENT, InpEMAFast,  0, MODE_EMA, PRICE_CLOSE);
   hEMASlow  = iMA(_Symbol, PERIOD_CURRENT, InpEMASlow,  0, MODE_EMA, PRICE_CLOSE);
   hEMATrend = iMA(_Symbol, PERIOD_CURRENT, InpEMATrend, 0, MODE_EMA, PRICE_CLOSE);
   hATR      = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   hRSI      = iRSI(_Symbol, PERIOD_CURRENT, 14, PRICE_CLOSE);

   if(hEMAFast == INVALID_HANDLE || hEMASlow == INVALID_HANDLE ||
      hEMATrend == INVALID_HANDLE || hATR == INVALID_HANDLE || hRSI == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. err=", GetLastError());
      return INIT_FAILED;
   }

   // Load ONNX model
   if(InpUseONNX)
   {
      hONNX = OnnxCreate(InpONNXPath, ONNX_DEFAULT);
      if(hONNX == INVALID_HANDLE)
      {
         Print("WARNING: ONNX model not loaded (", InpONNXPath, "). Running without filter.");
      }
      else
      {
         long inputShape[] = {1, 8};
         OnnxSetInputShape(hONNX, 0, inputShape);
         long labelShape[] = {1};
         OnnxSetOutputShape(hONNX, 0, labelShape);
         long probShape[] = {1, 2};
         OnnxSetOutputShape(hONNX, 1, probShape);
         Print("ONNX filter loaded: ", InpONNXPath);
      }
   }

   Print("FVG_LiquiditySweep_XGB initialized. ", _Symbol, " Magic=", InpMagicNumber);
   Print("  Kill zones: ", (InpUseKillZones ? "ON" : "OFF"));
   Print("  ONNX filter: ", (InpUseONNX && hONNX != INVALID_HANDLE ? "ON" : "OFF"));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEMAFast  != INVALID_HANDLE) IndicatorRelease(hEMAFast);
   if(hEMASlow  != INVALID_HANDLE) IndicatorRelease(hEMASlow);
   if(hEMATrend != INVALID_HANDLE) IndicatorRelease(hEMATrend);
   if(hATR      != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hRSI      != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hONNX     != INVALID_HANDLE) OnnxRelease(hONNX);
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(!IsInKillZone()) return;
   if(CountPositions() >= InpMaxPositions) return;

   int barsNeeded = InpFVGLookback + 5;
   double emaF[2], emaS[2], emaT[2], atrBuf[2], rsiBuf[2];
   ArraySetAsSeries(emaF, true); ArraySetAsSeries(emaS, true);
   ArraySetAsSeries(emaT, true); ArraySetAsSeries(atrBuf, true); ArraySetAsSeries(rsiBuf, true);

   if(CopyBuffer(hEMAFast,  0, 0, 2, emaF) < 2) return;
   if(CopyBuffer(hEMASlow,  0, 0, 2, emaS) < 2) return;
   if(CopyBuffer(hEMATrend, 0, 0, 2, emaT) < 2) return;
   if(CopyBuffer(hATR,      0, 0, 2, atrBuf) < 2) return;
   if(CopyBuffer(hRSI,      0, 0, 2, rsiBuf) < 2) return;

   double atr = atrBuf[1];
   if(atr <= 0) return;

   double highs[], lows[], closes[];
   ArraySetAsSeries(highs, true); ArraySetAsSeries(lows, true); ArraySetAsSeries(closes, true);
   if(CopyHigh(_Symbol, PERIOD_CURRENT, 0, barsNeeded, highs) < barsNeeded) return;
   if(CopyLow(_Symbol, PERIOD_CURRENT, 0, barsNeeded, lows) < barsNeeded) return;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 0, barsNeeded, closes) < barsNeeded) return;

   bool bullTrend = (emaF[1] > emaS[1] && emaS[1] > emaT[1]);
   bool bearTrend = (emaF[1] < emaS[1] && emaS[1] < emaT[1]);

   double minGap = (InpFVGMinGap > 0) ? InpFVGMinGap : atr * 0.3;

   if(bullTrend)
   {
      bool swept = DetectLiquiditySweep(1, highs, lows, closes);
      double fvgLevel = DetectFVG(1, highs, lows, 1, minGap);

      if(swept && fvgLevel > 0)
      {
         // Build features and check ONNX filter
         float features[8];
         BuildONNXFeatures(1, highs, lows, closes, emaF[1], emaS[1], emaT[1], atr, rsiBuf[1],
                          fvgLevel, 0.8, features);

         bool onnxOK = true;
         if(InpUseONNX && hONNX != INVALID_HANDLE)
         {
            long labels[1];
            float probs[1][2];
            if(OnnxRun(hONNX, ONNX_DEFAULT, features, labels, probs))
            {
               double winProb = probs[0][1];  // Class 1 = win
               onnxOK = (winProb > InpONNXThreshold);
               if(!onnxOK)
                  Print("FVG BUY filtered: win_prob=", DoubleToString(winProb, 3),
                        " threshold=", DoubleToString(InpONNXThreshold, 3));
            }
         }

         if(onnxOK)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizePrice(ask - InpATRMult * atr);
            double tp  = NormalizePrice(ask + InpATRMult * InpRiskReward * atr);
            g_Trade.Buy(InpFixedLot, _Symbol, 0.0, sl, tp, "FVG_Sweep_XGB BUY");
            Print("FVG+Sweep BUY: fvg=", DoubleToString(fvgLevel, (int)_Digits), " atr=", DoubleToString(atr, (int)_Digits));
         }
      }
   }
   else if(bearTrend)
   {
      bool swept = DetectLiquiditySweep(-1, highs, lows, closes);
      double fvgLevel = DetectFVG(-1, highs, lows, 1, minGap);

      if(swept && fvgLevel > 0)
      {
         float features[8];
         BuildONNXFeatures(-1, highs, lows, closes, emaF[1], emaS[1], emaT[1], atr, rsiBuf[1],
                          fvgLevel, 0.8, features);

         bool onnxOK = true;
         if(InpUseONNX && hONNX != INVALID_HANDLE)
         {
            long labels[1];
            float probs[1][2];
            if(OnnxRun(hONNX, ONNX_DEFAULT, features, labels, probs))
            {
               double winProb = probs[0][1];
               onnxOK = (winProb > InpONNXThreshold);
               if(!onnxOK)
                  Print("FVG SELL filtered: win_prob=", DoubleToString(winProb, 3),
                        " threshold=", DoubleToString(InpONNXThreshold, 3));
            }
         }

         if(onnxOK)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizePrice(bid + InpATRMult * atr);
            double tp  = NormalizePrice(bid - InpATRMult * InpRiskReward * atr);
            g_Trade.Sell(InpFixedLot, _Symbol, 0.0, sl, tp, "FVG_Sweep_XGB SELL");
            Print("FVG+Sweep SELL: fvg=", DoubleToString(fvgLevel, (int)_Digits), " atr=", DoubleToString(atr, (int)_Digits));
         }
      }
   }
}
//+------------------------------------------------------------------+
