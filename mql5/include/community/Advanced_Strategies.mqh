//+------------------------------------------------------------------+
//| Advanced Multi-Strategy Signal Confirmation Library               |
//| Candlestick patterns, multi-indicator confluence, volatility,    |
//| multi-timeframe alignment, dynamic S/R detection                 |
//| Source: Sidoine1991/KolaTradeboT                                 |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"

// Composite signal score
struct SignalScore
{
   int    direction;       // 1=buy, -1=sell, 0=neutral
   double score;           // 0.0 to 1.0
   int    confirmations;   // Number of strategies that agree
   string reasons;         // Comma-separated reason tags
};

// Candlestick pattern detection on bar[barIdx]
// Returns: 1=bullish, -1=bearish, 0=neutral
int DetectCandlePattern(const double &opens[], const double &highs[],
                        const double &lows[], const double &closes[], int barIdx)
{
   if(barIdx + 1 >= ArraySize(opens)) return 0;

   double body = MathAbs(closes[barIdx] - opens[barIdx]);
   double range = highs[barIdx] - lows[barIdx];
   if(range <= 0) return 0;

   double bodyRatio = body / range;
   double upperWick = highs[barIdx] - MathMax(opens[barIdx], closes[barIdx]);
   double lowerWick = MathMin(opens[barIdx], closes[barIdx]) - lows[barIdx];

   // Hammer: small body at top, long lower wick (bullish reversal)
   if(bodyRatio < 0.3 && lowerWick > body * 2.0 && upperWick < body)
      return 1;

   // Shooting Star: small body at bottom, long upper wick (bearish reversal)
   if(bodyRatio < 0.3 && upperWick > body * 2.0 && lowerWick < body)
      return -1;

   // Bullish Engulfing
   if(barIdx + 1 < ArraySize(opens))
   {
      double prevBody = MathAbs(closes[barIdx + 1] - opens[barIdx + 1]);
      if(closes[barIdx + 1] < opens[barIdx + 1] && // Previous bearish
         closes[barIdx] > opens[barIdx] &&          // Current bullish
         body > prevBody * 1.5)                     // Engulfs
         return 1;

      // Bearish Engulfing
      if(closes[barIdx + 1] > opens[barIdx + 1] &&
         closes[barIdx] < opens[barIdx] &&
         body > prevBody * 1.5)
         return -1;
   }

   return 0;
}

// Multi-indicator confirmation score
// Checks RSI, MACD, Bollinger, Stochastic agreement
// Returns score 0.0 to 1.0 and direction
double CalcIndicatorConfluence(double rsi, double macdMain, double macdSignal,
                               double bbUpper, double bbLower, double price,
                               double stochK, double stochD,
                               int &direction)
{
   int bullVotes = 0, bearVotes = 0;

   // RSI
   if(rsi < 30) bullVotes++;
   else if(rsi > 70) bearVotes++;

   // MACD crossover
   if(macdMain > macdSignal) bullVotes++;
   else if(macdMain < macdSignal) bearVotes++;

   // Bollinger Band position
   if(price < bbLower) bullVotes++;
   else if(price > bbUpper) bearVotes++;

   // Stochastic
   if(stochK < 20 && stochK > stochD) bullVotes++;
   else if(stochK > 80 && stochK < stochD) bearVotes++;

   int total = bullVotes + bearVotes;
   if(total == 0) { direction = 0; return 0; }

   if(bullVotes > bearVotes)
   {
      direction = 1;
      return (double)bullVotes / 4.0;
   }
   else if(bearVotes > bullVotes)
   {
      direction = -1;
      return (double)bearVotes / 4.0;
   }

   direction = 0;
   return 0;
}

// Volatility/Volume filter
// Returns true if conditions are suitable for trading
bool CheckVolatilityFilter(double currentATR, double avgATR, double volumeRatio,
                           double atrExpansionThresh = 1.2)
{
   if(avgATR <= 0) return false;
   // Need ATR expansion (trending) and decent volume
   return (currentATR / avgATR >= atrExpansionThresh && volumeRatio >= 1.0);
}

// Multi-timeframe EMA alignment check
// Returns: 1 if all TFs bullish, -1 if all bearish, 0 if mixed
int CheckMTFAlignment(double emaFast_M5, double emaSlow_M5,
                      double emaFast_H1, double emaSlow_H1)
{
   bool m5Bull = (emaFast_M5 > emaSlow_M5);
   bool h1Bull = (emaFast_H1 > emaSlow_H1);

   if(m5Bull && h1Bull) return 1;
   if(!m5Bull && !h1Bull) return -1;
   return 0;
}

// Dynamic Support/Resistance detection
// Looks for price levels with 3+ touches in the lookback period
double FindDynamicSR(const double &highs[], const double &lows[], int lookback,
                     int direction, double tolerance)
{
   // Build array of significant levels (swing highs for resistance, lows for support)
   for(int i = 1; i < lookback && i + 1 < ArraySize(highs); i++)
   {
      double level = (direction == 1) ? lows[i] : highs[i];
      int touches = 0;

      for(int j = 0; j < lookback && j < ArraySize(highs); j++)
      {
         if(j == i) continue;
         double checkLevel = (direction == 1) ? lows[j] : highs[j];
         if(MathAbs(checkLevel - level) <= tolerance)
            touches++;
      }

      if(touches >= 3)
         return level;
   }
   return 0;
}

// Calculate composite signal score from all strategies
SignalScore CalcCompositeSignal(int candleSignal, double indicatorScore, int indicatorDir,
                                bool volFilter, int mtfAlignment, double srLevel, double price)
{
   SignalScore result;
   result.direction = 0;
   result.score = 0;
   result.confirmations = 0;
   result.reasons = "";

   double bullScore = 0, bearScore = 0;
   int bullConf = 0, bearConf = 0;

   // Candlestick pattern (weight: 15%)
   if(candleSignal == 1) { bullScore += 0.15; bullConf++; }
   if(candleSignal == -1) { bearScore += 0.15; bearConf++; }

   // Multi-indicator confluence (weight: 30%)
   if(indicatorDir == 1) { bullScore += 0.30 * indicatorScore; bullConf++; }
   if(indicatorDir == -1) { bearScore += 0.30 * indicatorScore; bearConf++; }

   // Volatility filter (weight: 15%)
   if(volFilter) { bullScore += 0.15; bearScore += 0.15; }

   // MTF alignment (weight: 25%)
   if(mtfAlignment == 1) { bullScore += 0.25; bullConf++; }
   if(mtfAlignment == -1) { bearScore += 0.25; bearConf++; }

   // Dynamic S/R proximity (weight: 15%)
   if(srLevel > 0)
   {
      double dist = MathAbs(price - srLevel);
      if(dist < price * 0.002) // Within 0.2% of S/R
      {
         if(price > srLevel) { bullScore += 0.15; bullConf++; } // Support bounce
         else { bearScore += 0.15; bearConf++; }                // Resistance rejection
      }
   }

   if(bullScore > bearScore && bullScore >= 0.65 && bullConf >= 2)
   {
      result.direction = 1;
      result.score = bullScore;
      result.confirmations = bullConf;
   }
   else if(bearScore > bullScore && bearScore >= 0.65 && bearConf >= 2)
   {
      result.direction = -1;
      result.score = bearScore;
      result.confirmations = bearConf;
   }

   return result;
}
//+------------------------------------------------------------------+
