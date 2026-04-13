//+------------------------------------------------------------------+
//| Gold Regime ONNX XGBoost EA                                      |
//| Uses ONNX-exported XGBoost model for regime classification       |
//| Features: HMM state proxy, RSI delta, normalized ATR, log return |
//| Entry: bull_prob > threshold AND bullish regime -> BUY            |
//|        bear_prob > threshold AND bearish regime -> SELL           |
//| SL: ATR-based (2.0x), adaptive position sizing by account tier   |
//| Designed for XAUUSD H1                                           |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade g_Trade;

input group "=== Expert ==="
input long   InpMagicNumber     = 20260418;
input int    InpDeviation       = 20;

input group "=== ONNX Model ==="
input string InpONNXPath        = "GoldRegimeX.onnx";  // Model file in MQL5/Files
input double InpProbThreshold   = 0.65;    // Min probability for entry
input double InpShortThreshold  = 0.35;    // Below this = bearish

input group "=== Indicators ==="
input int    InpATRPeriod       = 14;
input double InpATRMultiplier   = 2.0;
input int    InpRSIPeriod       = 14;

input group "=== Risk ==="
input double InpRiskPercent     = 1.0;
input double InpFixedLot        = 0.01;    // Fallback lot
input bool   InpIsCentAccount   = false;

input group "=== Session ==="
input int    InpMaxDailyTrades  = 5;

int    hATR = INVALID_HANDLE;
int    hRSI = INVALID_HANDLE;
long   hONNX = INVALID_HANDLE;

datetime g_LastBarTime = 0;
int    g_DailyTrades = 0;
int    g_LastDay = 0;
double g_PrevRSI = 0;
double g_PrevClose = 0;

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_LastBarTime) { g_LastBarTime = t; return true; }
   return false;
}

ulong FindPosition(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            (long)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
            return ticket;
   }
   return 0;
}

bool HasAnyPosition()
{
   return (FindPosition(POSITION_TYPE_BUY) > 0 || FindPosition(POSITION_TYPE_SELL) > 0);
}

double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0) tick = _Point;
   return NormalizeDouble(MathRound(price / tick) * tick, (int)_Digits);
}

double NormalizeLot(double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   double l = MathMax(lots, minLot);
   l = MathMin(l, maxLot);
   l = MathFloor(l / stepLot) * stepLot;
   return MathMax(l, minLot);
}

double CalcLotSize(double slDistance)
{
   if(slDistance <= 0) return NormalizeLot(InpFixedLot);

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0) return NormalizeLot(InpFixedLot);

   double slMoney = (slDistance / tickSize) * tickValue;
   if(slMoney <= 0) return NormalizeLot(InpFixedLot);

   return NormalizeLot(riskMoney / slMoney);
}

void ResetDaily()
{
   MqlDateTime dt; TimeCurrent(dt);
   if(dt.day != g_LastDay) { g_DailyTrades = 0; g_LastDay = dt.day; }
}

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hATR = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   hRSI = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);

   if(hATR == INVALID_HANDLE || hRSI == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. err=", GetLastError());
      return INIT_FAILED;
   }

   // Load ONNX model
   hONNX = OnnxCreate(InpONNXPath, ONNX_DEFAULT);
   if(hONNX == INVALID_HANDLE)
   {
      Print("WARNING: ONNX model not loaded (", InpONNXPath, "). Running in indicator-only mode.");
      // Continue without ONNX - will use RSI/ATR heuristic as fallback
   }
   else
   {
      // Set input shape [1, 4] for 4 features
      long inputShape[] = {1, 4};
      OnnxSetInputShape(hONNX, 0, inputShape);
      // Output 0: label [1] int64, Output 1: probabilities [1,3] float
      long labelShape[] = {1};
      OnnxSetOutputShape(hONNX, 0, labelShape);
      long probShape[] = {1, 3};
      OnnxSetOutputShape(hONNX, 1, probShape);
      Print("ONNX model loaded: ", InpONNXPath);
   }

   Print("GoldRegime_ONNX initialized. ", _Symbol, " Magic=", InpMagicNumber,
         " ONNX=", (hONNX != INVALID_HANDLE ? "YES" : "NO"));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hATR  != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hRSI  != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hONNX != INVALID_HANDLE) OnnxRelease(hONNX);
}

void OnTick()
{
   ResetDaily();
   if(!IsNewBar()) return;
   if(HasAnyPosition()) return;
   if(InpMaxDailyTrades > 0 && g_DailyTrades >= InpMaxDailyTrades) return;

   // Get indicator values for bar[1]
   double atrBuf[2], rsiBuf[2];
   ArraySetAsSeries(atrBuf, true); ArraySetAsSeries(rsiBuf, true);
   if(CopyBuffer(hATR, 0, 0, 2, atrBuf) < 2) return;
   if(CopyBuffer(hRSI, 0, 0, 2, rsiBuf) < 2) return;

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double atr1   = atrBuf[1];
   double rsi1   = rsiBuf[1];

   if(atr1 <= 0 || close1 <= 0) return;

   // Build 4 features matching the Python pipeline
   // Feature 1: HMM state proxy (simplified: trend direction from returns)
   double logReturn = (g_PrevClose > 0) ? MathLog(close1 / g_PrevClose) : 0;
   double hmmState  = (logReturn > 0) ? 1.0 : ((logReturn < 0) ? 0.0 : 0.5);

   // Feature 2: RSI delta (rate of change of RSI)
   double rsiDelta = rsi1 - g_PrevRSI;

   // Feature 3: Normalized ATR (ATR / price)
   double atrNorm = atr1 / close1;

   // Feature 4: Log return
   // (already computed above)

   g_PrevRSI   = rsi1;
   g_PrevClose = close1;

   // Skip first bar (no previous values)
   if(g_PrevClose == close1 && g_PrevRSI == rsi1) return;

   double bullProb = 0.5, bearProb = 0.5;
   bool isChop = false;

   if(hONNX != INVALID_HANDLE)
   {
      // Run ONNX inference — XGBoost outputs: [0]=label(int64), [1]=probs(float[1,3])
      float features[1][4];
      features[0][0] = (float)hmmState;
      features[0][1] = (float)rsiDelta;
      features[0][2] = (float)atrNorm;
      features[0][3] = (float)logReturn;

      long   labels[1];
      float  probs[1][3]; // [Bull=0, Bear=1, Chop=2]
      if(OnnxRun(hONNX, ONNX_DEFAULT, features, labels, probs))
      {
         bullProb = probs[0][0];
         bearProb = probs[0][1];
         double chopProb = probs[0][2];
         isChop = (chopProb > bullProb && chopProb > bearProb);
      }
   }
   else
   {
      // Fallback heuristic without ONNX
      if(rsi1 > 55 && logReturn > 0 && rsiDelta > 0) bullProb = 0.70;
      else if(rsi1 < 45 && logReturn < 0 && rsiDelta < 0) bearProb = 0.70;
      isChop = (MathAbs(rsi1 - 50) < 10 && MathAbs(logReturn) < atrNorm * 0.5);
   }

   if(isChop) return;

   double slDist = InpATRMultiplier * atr1;

   // BUY: bullish probability exceeds threshold and not chopping
   if(bullProb > InpProbThreshold)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizePrice(ask - slDist);
      double tp  = NormalizePrice(ask + slDist * 1.5);
      double lots = CalcLotSize(slDist);

      if(g_Trade.Buy(lots, _Symbol, 0.0, sl, tp, "GoldRegime BUY"))
      {
         g_DailyTrades++;
         Print("BUY: bullProb=", DoubleToString(bullProb, 3),
               " rsi=", DoubleToString(rsi1, 1), " atr=", DoubleToString(atr1, 2));
      }
   }
   // SELL: bear probability exceeds threshold
   else if(bearProb > InpProbThreshold)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizePrice(bid + slDist);
      double tp  = NormalizePrice(bid - slDist * 1.5);
      double lots = CalcLotSize(slDist);

      if(g_Trade.Sell(lots, _Symbol, 0.0, sl, tp, "GoldRegime SELL"))
      {
         g_DailyTrades++;
         Print("SELL: bearProb=", DoubleToString(bearProb, 3),
               " rsi=", DoubleToString(rsi1, 1), " atr=", DoubleToString(atr1, 2));
      }
   }
}
//+------------------------------------------------------------------+
