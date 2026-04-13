//+------------------------------------------------------------------+
//| Boom/Crash Z-Score Spike Detector EA                             |
//| Detects statistical price spikes using Z-score analysis          |
//| Boom symbols: BUY only | Crash symbols: SELL only                |
//| SL/TP: ATR-based (1.5x SL, 3x TP)                              |
//| Source: Sidoine1991/KolaTradeboT                                 |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade g_Trade;

input group "=== Expert ==="
input long   InpMagicNumber   = 20260413;
input double InpFixedLot      = 0.10;
input int    InpDeviation     = 20;

input group "=== Z-Score Spike Detection ==="
input int    InpLookback      = 20;       // Lookback period for mean/std
input double InpZScoreThresh  = 1.5;      // Z-score threshold for spike
input double InpMoveMultiple  = 2.0;      // Spike if move >= N * mean_move

input group "=== Risk Management ==="
input int    InpATRPeriod     = 14;
input double InpATRSLMult     = 1.5;      // ATR multiplier for SL
input double InpATRTPMult     = 3.0;      // ATR multiplier for TP

int    hATR = INVALID_HANDLE;
datetime g_LastBarTime = 0;

// Detect if symbol is Boom or Crash type
int DetectSymbolType()
{
   string s = _Symbol;
   StringToUpper(s);
   if(StringFind(s, "BOOM") >= 0) return 1;   // Boom = BUY only
   if(StringFind(s, "CRASH") >= 0) return -1;  // Crash = SELL only
   return 0; // Unknown = both directions
}

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

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hATR = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   if(hATR == INVALID_HANDLE)
   {
      Print("Failed to create ATR handle. err=", GetLastError());
      return INIT_FAILED;
   }

   int symType = DetectSymbolType();
   string typeStr = symType == 1 ? "BOOM(BUY only)" : (symType == -1 ? "CRASH(SELL only)" : "BOTH");
   Print("BoomCrash_ZScore initialized. ", _Symbol, " Type=", typeStr, " Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
}

void OnTick()
{
   if(!IsNewBar()) return;
   if(HasAnyPosition()) return; // Max 1 position

   int symType = DetectSymbolType();

   // Get close prices for Z-score calculation
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(_Symbol, PERIOD_CURRENT, 1, InpLookback + 1, closes) < InpLookback + 1) return;

   // Calculate close-to-close moves
   double moves[];
   ArrayResize(moves, InpLookback);
   for(int i = 0; i < InpLookback; i++)
      moves[i] = closes[i] - closes[i + 1];

   // Mean and standard deviation of moves
   double sum = 0, sumSq = 0;
   for(int i = 0; i < InpLookback; i++)
   {
      sum += moves[i];
      sumSq += moves[i] * moves[i];
   }
   double mean = sum / InpLookback;
   double variance = (sumSq / InpLookback) - (mean * mean);
   double stdDev = (variance > 0) ? MathSqrt(variance) : 0;

   if(stdDev <= 0) return;

   // Latest move (bar[1] - bar[2])
   double latestMove = moves[0];
   double zScore = (latestMove - mean) / stdDev;
   double absMean = MathAbs(mean) > 0 ? MathAbs(mean) : 1e-10;

   // Spike detection: Z-score threshold OR move >= multiple of mean
   bool spikeUp = (zScore >= InpZScoreThresh || latestMove >= InpMoveMultiple * absMean) && latestMove > 0;
   bool spikeDn = (zScore <= -InpZScoreThresh || MathAbs(latestMove) >= InpMoveMultiple * absMean) && latestMove < 0;

   // Directional filter for Boom/Crash
   if(symType == 1 && spikeDn) spikeDn = false;  // Boom: no SELL
   if(symType == -1 && spikeUp) spikeUp = false;  // Crash: no BUY

   // Get ATR for SL/TP
   double atrBuf[1];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1) return;
   double atr = atrBuf[0];
   if(atr <= 0) return;

   if(spikeUp)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizePrice(ask - InpATRSLMult * atr);
      double tp  = NormalizePrice(ask + InpATRTPMult * atr);
      g_Trade.Buy(InpFixedLot, _Symbol, 0.0, sl, tp, "ZSpike BUY");
      Print("Z-Score spike UP: z=", DoubleToString(zScore, 2), " move=", DoubleToString(latestMove, (int)_Digits));
   }
   else if(spikeDn)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizePrice(bid + InpATRSLMult * atr);
      double tp  = NormalizePrice(bid - InpATRTPMult * atr);
      g_Trade.Sell(InpFixedLot, _Symbol, 0.0, sl, tp, "ZSpike SELL");
      Print("Z-Score spike DN: z=", DoubleToString(zScore, 2), " move=", DoubleToString(latestMove, (int)_Digits));
   }
}
//+------------------------------------------------------------------+
