//+------------------------------------------------------------------+
//| Smart Money Concepts (SMC/ICT) Library                           |
//| FVG, BOS, Order Blocks, Liquidity Sweeps, OTE, Kill Zones       |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"

// Fair Value Gap structure
struct FVGZone
{
   double   high;
   double   low;
   int      direction;  // 1=bullish, -1=bearish
   datetime time;
   bool     mitigated;
};

// Break of Structure event
struct BOSEvent
{
   double   level;
   int      direction;  // 1=bullish BOS, -1=bearish BOS
   datetime time;
   int      barIndex;
};

// Order Block zone
struct OrderBlock
{
   double   high;
   double   low;
   int      direction;  // 1=bullish OB, -1=bearish OB
   datetime time;
   bool     tested;
};

// Detect Fair Value Gaps in price data
// Bullish FVG: bar[i+1].high < bar[i-1].low (gap between wicks)
// Bearish FVG: bar[i+1].low > bar[i-1].high
int DetectFVGs(const double &highs[], const double &lows[], int startBar, int count,
               FVGZone &zones[], double minGap = 0)
{
   int found = 0;
   ArrayResize(zones, 0);

   for(int i = startBar + 1; i < startBar + count - 1 && i + 1 < ArraySize(highs); i++)
   {
      // Bullish FVG
      double bullGap = lows[i - 1] - highs[i + 1];
      if(bullGap > minGap)
      {
         ArrayResize(zones, found + 1);
         zones[found].high = lows[i - 1];
         zones[found].low  = highs[i + 1];
         zones[found].direction = 1;
         zones[found].mitigated = false;
         found++;
      }

      // Bearish FVG
      double bearGap = lows[i + 1] - highs[i - 1];
      if(bearGap > minGap)
      {
         ArrayResize(zones, found + 1);
         zones[found].high = lows[i + 1];
         zones[found].low  = highs[i - 1];
         zones[found].direction = -1;
         zones[found].mitigated = false;
         found++;
      }
   }
   return found;
}

// Detect Break of Structure
// Bullish BOS: close breaks above previous swing high
// Bearish BOS: close breaks below previous swing low
bool DetectBOS(const double &highs[], const double &lows[], const double &closes[],
               int swingLookback, BOSEvent &bos)
{
   // Find swing high and swing low in lookback
   double swingHigh = 0;
   double swingLow  = DBL_MAX;
   int shBar = 0, slBar = 0;

   for(int i = 2; i < swingLookback && i + 1 < ArraySize(highs); i++)
   {
      // Fractal swing high
      if(highs[i] > highs[i - 1] && highs[i] > highs[i + 1])
      {
         if(highs[i] > swingHigh)
         {
            swingHigh = highs[i];
            shBar = i;
         }
      }
      // Fractal swing low
      if(lows[i] < lows[i - 1] && lows[i] < lows[i + 1])
      {
         if(lows[i] < swingLow)
         {
            swingLow = lows[i];
            slBar = i;
         }
      }
   }

   // Check bar[1] for BOS
   if(swingHigh > 0 && closes[1] > swingHigh)
   {
      bos.level = swingHigh;
      bos.direction = 1;
      bos.barIndex = 1;
      return true;
   }
   if(swingLow < DBL_MAX && closes[1] < swingLow)
   {
      bos.level = swingLow;
      bos.direction = -1;
      bos.barIndex = 1;
      return true;
   }
   return false;
}

// Detect Order Blocks (last opposing candle before a strong move)
bool DetectOrderBlock(const double &opens[], const double &closes[],
                      const double &highs[], const double &lows[],
                      int direction, int lookback, OrderBlock &ob)
{
   for(int i = 2; i < lookback && i < ArraySize(opens); i++)
   {
      double bodySize = MathAbs(closes[i] - opens[i]);
      double range    = highs[i] - lows[i];
      if(range <= 0) continue;

      double bodyRatio = bodySize / range;

      if(direction == 1) // Bullish OB = last bearish candle before up move
      {
         if(closes[i] < opens[i] && bodyRatio > 0.6) // Strong bearish body
         {
            // Verify strong up move follows
            if(closes[i - 1] > opens[i - 1] && closes[i - 1] > highs[i])
            {
               ob.high = highs[i];
               ob.low  = lows[i];
               ob.direction = 1;
               ob.tested = false;
               return true;
            }
         }
      }
      else // Bearish OB = last bullish candle before down move
      {
         if(closes[i] > opens[i] && bodyRatio > 0.6)
         {
            if(closes[i - 1] < opens[i - 1] && closes[i - 1] < lows[i])
            {
               ob.high = highs[i];
               ob.low  = lows[i];
               ob.direction = -1;
               ob.tested = false;
               return true;
            }
         }
      }
   }
   return false;
}

// Detect Liquidity Sweep (stop hunt)
// Equal highs/lows swept by wick but close returns
bool DetectLiquiditySweep(const double &highs[], const double &lows[],
                          const double &closes[], int lookback, double tolerance,
                          int &sweepDirection)
{
   sweepDirection = 0;

   // Find equal highs (buy-side liquidity)
   for(int i = 3; i < lookback && i + 1 < ArraySize(highs); i++)
   {
      for(int j = i + 1; j < lookback && j < ArraySize(highs); j++)
      {
         double diff = MathAbs(highs[i] - highs[j]);
         double avg  = (highs[i] + highs[j]) / 2.0;
         if(avg <= 0) continue;

         if(diff / avg <= tolerance) // Equal highs found
         {
            double level = MathMax(highs[i], highs[j]);
            // Check if bar[1] swept above then closed below
            if(highs[1] > level && closes[1] < level)
            {
               sweepDirection = -1; // Bearish sweep (reversal expected)
               return true;
            }
         }
      }
   }

   // Find equal lows (sell-side liquidity)
   for(int i = 3; i < lookback && i + 1 < ArraySize(lows); i++)
   {
      for(int j = i + 1; j < lookback && j < ArraySize(lows); j++)
      {
         double diff = MathAbs(lows[i] - lows[j]);
         double avg  = (lows[i] + lows[j]) / 2.0;
         if(avg <= 0) continue;

         if(diff / avg <= tolerance)
         {
            double level = MathMin(lows[i], lows[j]);
            if(lows[1] < level && closes[1] > level)
            {
               sweepDirection = 1; // Bullish sweep
               return true;
            }
         }
      }
   }
   return false;
}

// Calculate OTE (Optimal Trade Entry) zone using Fibonacci
// Returns the 0.62-0.79 retracement zone of the impulse leg
void CalcOTEZone(double swingLow, double swingHigh, int direction,
                 double &oteUpper, double &oteLower)
{
   double span = swingHigh - swingLow;
   if(direction == 1) // Bullish: retrace down into discount
   {
      oteUpper = swingHigh - 0.62 * span;
      oteLower = swingHigh - 0.79 * span;
   }
   else // Bearish: retrace up into premium
   {
      oteLower = swingLow + 0.62 * span;
      oteUpper = swingLow + 0.79 * span;
   }
}

// Check if current time is in a Kill Zone (London/NY open)
bool IsInKillZone(int londonStart = 7, int londonEnd = 10, int nyStart = 12, int nyEnd = 15)
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int h = dt.hour;
   return (h >= londonStart && h <= londonEnd) || (h >= nyStart && h <= nyEnd);
}

// Premium/Discount equilibrium
// Returns 1 if price is in discount (below 50%), -1 if premium (above 50%)
int GetPremiumDiscount(double price, double rangeLow, double rangeHigh)
{
   if(rangeHigh <= rangeLow) return 0;
   double eq = (rangeLow + rangeHigh) / 2.0;
   if(price < eq) return 1;   // Discount = bullish bias
   if(price > eq) return -1;  // Premium = bearish bias
   return 0;
}
//+------------------------------------------------------------------+
