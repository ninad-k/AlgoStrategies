//+------------------------------------------------------------------+
//|                                              SmartRenkoLikeEA.mq5 |
//| Trades Renko-like direction flips with EMA30 filter               |
//| Entry: dir flip on last closed bar AND close vs EMA30 filter      |
//| Risk: fixed lot, SL = 1 brick, TP = 2 bricks                      |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

//--- Inputs
input group "=== Expert ==="
input double InpFixedLot      = 0.10;      // Fixed lot size
input int    InpMagicNumber   = 20260408;  // Magic Number
input int    InpDeviationPts  = 20;        // Deviation (points)

input group "=== Signal ==="
input int    InpEMA30Period   = 30;        // EMA period (filter)

input group "=== SmartRenkoLikeStep indicator inputs ==="
input bool   InpAutoDetectAsset = true;          // Asset Selection Mode (Auto-Detect)
input string InpManualAsset     = "XAUUSD/GOLD"; // Manual Asset Pick (label only)

enum BrickCalcMode
{
   BRICK_ATR = 0,
   BRICK_PERCENT = 1,
   BRICK_FIXED = 2
};
input BrickCalcMode InpBrickCalc      = BRICK_ATR;  // Brick Size Calculation
input int           InpATRLen         = 14;         // ATR Length
input double        InpATRMult        = 1.0;        // ATR Mult
input double        InpCustomPct      = 1.0;        // Custom % (if Percentage selected)
input double        InpFixedBoxPoints = 50.0;       // Fixed Box Size (Points)
input double        InpRoundingStep   = 0.0;        // Rounding Step (0 = tick size)
input bool          InpAllowMultiBrick = true;      // Allow Multi-Brick Jumps
input bool          InpInitRoundFirst  = false;     // Initialization: round first close to brick

//--- Handles
int hRenko = INVALID_HANDLE;
int hEma30 = INVALID_HANDLE;

//--- State
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
double GetTickSize()
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts > 0) return ts;
   return _Point;
}

double RoundToStep(const double value, const double step)
{
   if(step <= 0.0) return value;
   return MathRound(value / step) * step;
}

double NormalizePrice(const double price)
{
   const double tick = GetTickSize();
   double p = RoundToStep(price, tick);
   return NormalizeDouble(p, (int)_Digits);
}

double NormalizeLot(const double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;

   double l = lots;
   l = MathMax(l, minLot);
   l = MathMin(l, maxLot);
   l = MathFloor(l / stepLot) * stepLot;
   l = MathMax(l, minLot);
   return l;
}

double MinStopDistance()
{
   long stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = (stopLevelPts > 0) ? stopLevelPts * _Point : 0.0;
   return minDist;
}

void ApplyMinStops(const bool isBuy, const double entry, double &sl, double &tp)
{
   double minDist = MinStopDistance();
   if(minDist <= 0.0) return;

   if(isBuy)
   {
      if(sl > 0 && (entry - sl) < minDist) sl = entry - minDist;
      if(tp > 0 && (tp - entry) < minDist) tp = entry + minDist;
   }
   else
   {
      if(sl > 0 && (sl - entry) < minDist) sl = entry + minDist;
      if(tp > 0 && (entry - tp) < minDist) tp = entry - minDist;
   }

   sl = (sl > 0) ? NormalizePrice(sl) : 0.0;
   tp = (tp > 0) ? NormalizePrice(tp) : 0.0;
}

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_lastBarTime)
   {
      g_lastBarTime = t;
      return true;
   }
   return false;
}

// Return position ticket for this symbol/magic and type, else 0
ulong FindPositionTicket(const ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            (int)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
            return ticket;
      }
   }
   return 0;
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpDeviationPts);

   // Indicator handle (iCustom). Parameter order must match indicator inputs.
   hRenko = iCustom(_Symbol, PERIOD_CURRENT,
                    "SmartRenkoLikeStep",
                    InpAutoDetectAsset,
                    InpManualAsset,
                    (int)InpBrickCalc,
                    InpATRLen,
                    InpATRMult,
                    InpCustomPct,
                    InpFixedBoxPoints,
                    InpRoundingStep,
                    InpAllowMultiBrick,
                    InpInitRoundFirst);

   if(hRenko == INVALID_HANDLE)
   {
      Print("SmartRenkoLikeEA: failed to create iCustom handle. err=", GetLastError());
      return INIT_FAILED;
   }

   hEma30 = iMA(_Symbol, PERIOD_CURRENT, InpEMA30Period, 0, MODE_EMA, PRICE_CLOSE);
   if(hEma30 == INVALID_HANDLE)
   {
      Print("SmartRenkoLikeEA: failed to create EMA handle. err=", GetLastError());
      return INIT_FAILED;
   }

   Print("SmartRenkoLikeEA initialized. Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hRenko != INVALID_HANDLE) IndicatorRelease(hRenko);
   if(hEma30 != INVALID_HANDLE) IndicatorRelease(hEma30);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsNewBar())
      return;

   // Use closed bar index 1 for signal and filter
   double dirBuf[3];
   double brickBuf[3];
   ArraySetAsSeries(dirBuf, true);
   ArraySetAsSeries(brickBuf, true);

   if(CopyBuffer(hRenko, 1, 0, 3, dirBuf) < 3) { Print("CopyBuffer dir failed err=", GetLastError()); return; }
   if(CopyBuffer(hRenko, 2, 0, 3, brickBuf) < 3) { Print("CopyBuffer brick failed err=", GetLastError()); return; }

   double ema[3];
   ArraySetAsSeries(ema, true);
   if(CopyBuffer(hEma30, 0, 0, 3, ema) < 3) { Print("CopyBuffer ema failed err=", GetLastError()); return; }

   int dir1 = (int)MathRound(dirBuf[1]);
   int dir2 = (int)MathRound(dirBuf[2]);
   bool flipUp = (dir2 != 1 && dir1 == 1);
   bool flipDn = (dir2 != -1 && dir1 == -1);

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double ema1 = ema[1];

   bool buyFilter = close1 > ema1;
   bool sellFilter = close1 < ema1;

   double brick = brickBuf[1];
   if(brick <= 0) return;

   // Positions
   ulong buyTicket  = FindPositionTicket(POSITION_TYPE_BUY);
   ulong sellTicket = FindPositionTicket(POSITION_TYPE_SELL);

   if(flipUp && buyFilter)
   {
      if(sellTicket > 0)
         trade.PositionClose(sellTicket);

      if(buyTicket == 0)
      {
         double lots = NormalizeLot(InpFixedLot);
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl = NormalizePrice(ask - 1.0 * brick);
         double tp = NormalizePrice(ask + 2.0 * brick);
         ApplyMinStops(true, ask, sl, tp);
         bool ok = trade.Buy(lots, _Symbol, 0.0, sl, tp, "RenkoFlip BUY");
         if(ok)
            Print("BUY opened. brick=", brick, " close1=", close1, " ema1=", ema1, " sl=", sl, " tp=", tp);
         else
            Print("BUY failed. err=", GetLastError());
      }
   }
   else if(flipDn && sellFilter)
   {
      if(buyTicket > 0)
         trade.PositionClose(buyTicket);

      if(sellTicket == 0)
      {
         double lots = NormalizeLot(InpFixedLot);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl = NormalizePrice(bid + 1.0 * brick);
         double tp = NormalizePrice(bid - 2.0 * brick);
         ApplyMinStops(false, bid, sl, tp);
         bool ok = trade.Sell(lots, _Symbol, 0.0, sl, tp, "RenkoFlip SELL");
         if(ok)
            Print("SELL opened. brick=", brick, " close1=", close1, " ema1=", ema1, " sl=", sl, " tp=", tp);
         else
            Print("SELL failed. err=", GetLastError());
      }
   }
}
//+------------------------------------------------------------------+
