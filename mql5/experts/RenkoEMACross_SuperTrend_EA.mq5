//+------------------------------------------------------------------+
//|                                   RenkoEMACross_SuperTrend_EA.mq5 |
//| EMA 9/15 crossover + inline Renko direction + SuperTrend          |
//| Triple confirmation entry, SuperTrend trailing & partial TP      |
//| Optimized for XAUUSD M15 with 150-point fixed Renko bricks      |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>

CTrade g_Trade;

//--- Enums
enum ENUM_LOT_MODE
{
   LOT_FIXED = 0,     // Fixed Lot
   LOT_RISK_PCT = 1   // Risk % of Balance
};

enum BrickCalcMode
{
   BRICK_ATR = 0,      // ATR-based
   BRICK_PERCENT = 1,  // Percentage of price
   BRICK_FIXED = 2     // Fixed points
};

//--- Inputs
input group "=== Expert ==="
input long    InpMagicNumber   = 20260412;              // Magic Number
input string  InpComment       = "RenkoEMACross_ST";    // Order Comment
input int     InpDeviationPts  = 20;                    // Deviation (points)

input group "=== Lot Settings ==="
input ENUM_LOT_MODE InpLotMode = LOT_FIXED;             // Lot Mode
input double  InpFixedLot      = 0.10;                  // Fixed Lot Size
input double  InpRiskPct       = 1.0;                   // Risk % of Balance

input group "=== EMA Crossover Signal ==="
input int     InpEMAFastPeriod = 9;                     // Fast EMA Period
input int     InpEMASlowPeriod = 15;                    // Slow EMA Period

input group "=== SuperTrend ==="
input int     InpSTPeriod      = 10;                    // SuperTrend ATR Period
input double  InpSTMultiplier  = 3.0;                   // SuperTrend Multiplier

input group "=== Renko Engine (inline) ==="
input BrickCalcMode InpBrickCalc       = BRICK_FIXED;   // Brick Size Calculation
input int           InpATRLen          = 14;            // ATR Length (for brick calc)
input double        InpATRMult         = 1.0;           // ATR Mult
input double        InpCustomPct       = 1.0;           // Custom % (if Percentage selected)
input double        InpFixedBoxPoints  = 150.0;         // Fixed Box Size (Points) - 150 for GOLD
input double        InpRoundingStep    = 0.0;           // Rounding Step (0 = tick size)
input bool          InpAllowMultiBrick = true;          // Allow Multi-Brick Jumps
input bool          InpInitRoundFirst  = false;         // Initialization: round first close to brick

input group "=== Stop Loss ==="
input bool    InpSLUseSuperTrend = true;                // SL from SuperTrend level
input bool    InpSLUseBrick      = true;                // SL from Renko brick (fallback/wider)
input double  InpSLBrickMult     = 1.5;                 // Brick multiplier for SL

input group "=== Partial Profit Booking ==="
input bool    InpUsePartialTP    = true;                // Enable 3-tier partial TP
input double  InpTP1BrickMult    = 1.5;                 // TP1 distance (brick multiples)
input double  InpTP1ClosePct     = 40.0;                // TP1 close %
input double  InpTP2BrickMult    = 3.0;                 // TP2 distance (brick multiples)
input double  InpTP2ClosePct     = 30.0;                // TP2 close %
input double  InpTP3BrickMult    = 5.0;                 // TP3 distance (brick multiples)
input double  InpTP3ClosePct     = 30.0;                // TP3 close %

input group "=== Trailing / Exit ==="
input bool    InpTrailBySuperTrend = true;              // Trail SL by SuperTrend line
input bool    InpExitOnSTFlip      = true;              // Exit on SuperTrend direction flip
input bool    InpUseTimeExit       = false;             // Time-based exit
input int     InpExitHour          = 15;                // Force exit hour (server time)
input int     InpExitMinute        = 30;                // Force exit minute

input group "=== Display ==="
input bool    InpShowDashboard     = true;              // Show info dashboard on chart

//--- Indicator handles (EMA only, Renko is inline)
int hEMAFast  = INVALID_HANDLE;
int hEMASlow  = INVALID_HANDLE;
int hRenkoATR = INVALID_HANDLE;   // ATR for Renko brick calculation

//--- Renko engine state
double g_RenkoLevel     = 0;
double g_RenkoDir       = 0;     // -1, 0, 1
double g_RenkoBrick     = 0;
bool   g_RenkoInit      = false;

//--- SuperTrend state (manual calculation)
double g_ATR           = 0;
double g_SmoothedATR   = 0;
int    g_ATRBarCount   = 0;
double g_STUpperBand   = 0;
double g_STLowerBand   = 0;
double g_SuperTrend    = 0;
int    g_STDirection   = 0;    // 1=bullish, -1=bearish
double g_PrevSTUpper   = 0;
double g_PrevSTLower   = 0;
int    g_PrevSTDir     = 0;
bool   g_STInitialized = false;
double g_PrevClose     = 0;

//--- Trade state
int      g_TradeState     = 0;     // 0=flat, 1=long, -1=short
double   g_EntryPrice     = 0;
double   g_EntryBrickSize = 0;
double   g_EntryLots      = 0;
datetime g_LastBarTime    = 0;

//--- Partial TP tracking
bool g_TP1Hit = false;
bool g_TP2Hit = false;
bool g_TP3Hit = false;

//+------------------------------------------------------------------+
//| Helper functions                                                  |
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
   if(t != g_LastBarTime)
   {
      g_LastBarTime = t;
      return true;
   }
   return false;
}

ulong FindPositionTicket(const ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            (long)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
            return ticket;
      }
   }
   return 0;
}

//+------------------------------------------------------------------+
//| Lot sizing                                                       |
//+------------------------------------------------------------------+
double CalcLotSize(const double slDistancePrice)
{
   if(InpLotMode == LOT_FIXED || slDistancePrice <= 0)
      return NormalizeLot(InpFixedLot);

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPct / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = GetTickSize();

   if(tickValue <= 0 || tickSize <= 0)
      return NormalizeLot(InpFixedLot);

   double slMoney = (slDistancePrice / tickSize) * tickValue;
   if(slMoney <= 0)
      return NormalizeLot(InpFixedLot);

   double lot = riskMoney / slMoney;
   return NormalizeLot(lot);
}

//+------------------------------------------------------------------+
//| Inline Renko engine — updates g_RenkoLevel, g_RenkoDir, Brick   |
//+------------------------------------------------------------------+
void CalcRenko(double closePrice, double atrValue)
{
   const double tickSize = GetTickSize();
   const double step = (InpRoundingStep > 0.0) ? InpRoundingStep : tickSize;

   // Compute brick size
   double brickRaw = 0.0;
   if(InpBrickCalc == BRICK_ATR)
      brickRaw = atrValue * InpATRMult;
   else if(InpBrickCalc == BRICK_PERCENT)
      brickRaw = closePrice * (InpCustomPct / 100.0);
   else
      brickRaw = InpFixedBoxPoints;

   double brick = RoundToStep(brickRaw, step);
   if(brick < tickSize) brick = tickSize;
   g_RenkoBrick = brick;

   // Initialize on first call
   if(!g_RenkoInit)
   {
      g_RenkoLevel = InpInitRoundFirst ? RoundToStep(closePrice, brick) : closePrice;
      g_RenkoDir   = 0;
      g_RenkoInit  = true;
      return;
   }

   // Step logic
   double upMove = closePrice - g_RenkoLevel;
   double dnMove = g_RenkoLevel - closePrice;

   if(upMove >= brick)
   {
      int bricks = 1;
      if(InpAllowMultiBrick)
         bricks = (int)MathFloor(upMove / brick);
      g_RenkoLevel += bricks * brick;
      g_RenkoDir = 1;
   }
   else if(dnMove >= brick)
   {
      int bricks = 1;
      if(InpAllowMultiBrick)
         bricks = (int)MathFloor(dnMove / brick);
      g_RenkoLevel -= bricks * brick;
      g_RenkoDir = -1;
   }
}

//+------------------------------------------------------------------+
//| SuperTrend calculation (manual Wilder's ATR)                     |
//+------------------------------------------------------------------+
void CalcSuperTrend(double highPrice, double lowPrice, double closePrice)
{
   g_ATRBarCount++;

   // True Range
   double tr;
   if(g_ATRBarCount == 1)
      tr = highPrice - lowPrice;
   else
      tr = MathMax(highPrice - lowPrice, MathMax(MathAbs(highPrice - g_PrevClose), MathAbs(lowPrice - g_PrevClose)));

   // ATR (RMA/Wilder smoothing)
   if(g_ATRBarCount <= InpSTPeriod)
   {
      g_SmoothedATR += tr;
      if(g_ATRBarCount == InpSTPeriod)
         g_ATR = g_SmoothedATR / InpSTPeriod;
      g_PrevClose = closePrice;
      return;
   }
   else
   {
      g_ATR = (g_ATR * (InpSTPeriod - 1) + tr) / InpSTPeriod;
   }

   // SuperTrend bands
   double midPrice  = (highPrice + lowPrice) / 2.0;
   double upperBand = midPrice + InpSTMultiplier * g_ATR;
   double lowerBand = midPrice - InpSTMultiplier * g_ATR;

   // Carry forward bands
   if(!g_STInitialized)
   {
      g_STUpperBand = upperBand;
      g_STLowerBand = lowerBand;
      g_STDirection = closePrice > g_STUpperBand ? 1 : -1;
      g_SuperTrend  = g_STDirection == 1 ? g_STLowerBand : g_STUpperBand;
      g_STInitialized = true;
   }
   else
   {
      if(lowerBand > g_PrevSTLower || g_PrevClose < g_PrevSTLower)
         g_STLowerBand = lowerBand;
      else
         g_STLowerBand = g_PrevSTLower;

      if(upperBand < g_PrevSTUpper || g_PrevClose > g_PrevSTUpper)
         g_STUpperBand = upperBand;
      else
         g_STUpperBand = g_PrevSTUpper;

      if(g_PrevSTDir == 1)
         g_STDirection = closePrice < g_STLowerBand ? -1 : 1;
      else
         g_STDirection = closePrice > g_STUpperBand ? 1 : -1;

      g_SuperTrend = g_STDirection == 1 ? g_STLowerBand : g_STUpperBand;
   }

   g_PrevSTUpper = g_STUpperBand;
   g_PrevSTLower = g_STLowerBand;
   g_PrevSTDir   = g_STDirection;
   g_PrevClose   = closePrice;
}

//+------------------------------------------------------------------+
//| Sync trade state with broker positions                           |
//+------------------------------------------------------------------+
void SyncTradeState()
{
   ulong buyTicket  = FindPositionTicket(POSITION_TYPE_BUY);
   ulong sellTicket = FindPositionTicket(POSITION_TYPE_SELL);

   if(g_TradeState == 1 && buyTicket == 0)
   {
      g_TradeState = 0;
      g_TP1Hit = false;
      g_TP2Hit = false;
      g_TP3Hit = false;
   }
   else if(g_TradeState == -1 && sellTicket == 0)
   {
      g_TradeState = 0;
      g_TP1Hit = false;
      g_TP2Hit = false;
      g_TP3Hit = false;
   }
   else if(g_TradeState == 0)
   {
      if(buyTicket > 0) g_TradeState = 1;
      else if(sellTicket > 0) g_TradeState = -1;
   }
}

//+------------------------------------------------------------------+
//| Time-based exit                                                  |
//+------------------------------------------------------------------+
void CheckTimeExit()
{
   if(!InpUseTimeExit || g_TradeState == 0)
      return;

   MqlDateTime dt;
   TimeCurrent(dt);

   if(dt.hour > InpExitHour || (dt.hour == InpExitHour && dt.min >= InpExitMinute))
   {
      ulong ticket = FindPositionTicket(g_TradeState == 1 ? POSITION_TYPE_BUY : POSITION_TYPE_SELL);
      if(ticket > 0)
      {
         g_Trade.PositionClose(ticket);
         Print(InpComment, ": Time exit at ", dt.hour, ":", dt.min);
      }
      g_TradeState = 0;
      g_TP1Hit = false;
      g_TP2Hit = false;
      g_TP3Hit = false;
   }
}

//+------------------------------------------------------------------+
//| Partial profit booking (every tick)                              |
//+------------------------------------------------------------------+
void ManagePartialTP()
{
   if(!InpUsePartialTP || g_TradeState == 0 || g_EntryBrickSize <= 0)
      return;

   ENUM_POSITION_TYPE posType = g_TradeState == 1 ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   ulong ticket = FindPositionTicket(posType);
   if(ticket == 0)
      return;

   if(!PositionSelectByTicket(ticket))
      return;

   double currentVolume = PositionGetDouble(POSITION_VOLUME);
   double currentPrice  = g_TradeState == 1
                          ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                          : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   double priceDist = g_TradeState == 1
                      ? (currentPrice - g_EntryPrice)
                      : (g_EntryPrice - currentPrice);

   // TP1
   if(!g_TP1Hit && priceDist >= InpTP1BrickMult * g_EntryBrickSize)
   {
      double closeLots = NormalizeLot(g_EntryLots * InpTP1ClosePct / 100.0);
      if(closeLots > 0 && closeLots <= currentVolume)
      {
         if(g_Trade.PositionClosePartial(ticket, closeLots))
            Print(InpComment, ": TP1 hit. Closed ", closeLots, " lots at ", currentPrice);
      }
      g_TP1Hit = true;
   }

   // TP2
   if(!g_TP2Hit && g_TP1Hit && priceDist >= InpTP2BrickMult * g_EntryBrickSize)
   {
      if(PositionSelectByTicket(ticket))
         currentVolume = PositionGetDouble(POSITION_VOLUME);
      double closeLots = NormalizeLot(g_EntryLots * InpTP2ClosePct / 100.0);
      if(closeLots > 0 && closeLots <= currentVolume)
      {
         if(g_Trade.PositionClosePartial(ticket, closeLots))
            Print(InpComment, ": TP2 hit. Closed ", closeLots, " lots at ", currentPrice);
      }
      g_TP2Hit = true;
   }

   // TP3
   if(!g_TP3Hit && g_TP2Hit && priceDist >= InpTP3BrickMult * g_EntryBrickSize)
   {
      if(PositionSelectByTicket(ticket))
         currentVolume = PositionGetDouble(POSITION_VOLUME);
      double closeLots = NormalizeLot(g_EntryLots * InpTP3ClosePct / 100.0);
      if(closeLots > 0 && closeLots <= currentVolume)
      {
         if(g_Trade.PositionClosePartial(ticket, closeLots))
            Print(InpComment, ": TP3 hit. Closed ", closeLots, " lots at ", currentPrice);
      }
      g_TP3Hit = true;
   }
}

//+------------------------------------------------------------------+
//| Trail SL to SuperTrend line (every tick)                         |
//+------------------------------------------------------------------+
void TrailStopBySuperTrend()
{
   if(!InpTrailBySuperTrend || !g_STInitialized || g_TradeState == 0)
      return;

   ENUM_POSITION_TYPE posType = g_TradeState == 1 ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   ulong ticket = FindPositionTicket(posType);
   if(ticket == 0)
      return;

   if(!PositionSelectByTicket(ticket))
      return;

   double currentSL = PositionGetDouble(POSITION_SL);
   double currentTP = PositionGetDouble(POSITION_TP);
   double newSL     = NormalizePrice(g_SuperTrend);

   if(g_TradeState == 1)
   {
      if(newSL > currentSL && newSL < SymbolInfoDouble(_Symbol, SYMBOL_BID))
      {
         g_Trade.PositionModify(ticket, newSL, currentTP);
      }
   }
   else
   {
      if((currentSL == 0 || newSL < currentSL) && newSL > SymbolInfoDouble(_Symbol, SYMBOL_ASK))
      {
         g_Trade.PositionModify(ticket, newSL, currentTP);
      }
   }
}

//+------------------------------------------------------------------+
//| Dashboard display                                                |
//+------------------------------------------------------------------+
void DrawDashboard(int renkoDir, double emaFast, double emaSlow, double brick)
{
   if(!InpShowDashboard)
      return;

   string stDir = g_STDirection == 1 ? "BULLISH" : (g_STDirection == -1 ? "BEARISH" : "FLAT");
   string rkDir = renkoDir == 1 ? "UP" : (renkoDir == -1 ? "DOWN" : "FLAT");
   string state = g_TradeState == 1 ? "LONG" : (g_TradeState == -1 ? "SHORT" : "FLAT");

   string emaCross = emaFast > emaSlow ? "FAST > SLOW (Bullish)" : "FAST < SLOW (Bearish)";

   string txt = "=== RenkoEMACross SuperTrend ===\n";
   txt += "Renko Dir: " + rkDir + "  |  Brick: " + DoubleToString(brick, (int)_Digits) + "\n";
   txt += "EMA " + IntegerToString(InpEMAFastPeriod) + ": " + DoubleToString(emaFast, (int)_Digits)
        + "  |  EMA " + IntegerToString(InpEMASlowPeriod) + ": " + DoubleToString(emaSlow, (int)_Digits) + "\n";
   txt += "EMA Cross: " + emaCross + "\n";
   txt += "SuperTrend: " + DoubleToString(g_SuperTrend, (int)_Digits) + "  (" + stDir + ")\n";
   txt += "Position: " + state;
   if(g_TradeState != 0)
   {
      txt += "  |  Entry: " + DoubleToString(g_EntryPrice, (int)_Digits);
      txt += "  |  TP1:" + (g_TP1Hit ? "Y" : "N")
           + " TP2:" + (g_TP2Hit ? "Y" : "N")
           + " TP3:" + (g_TP3Hit ? "Y" : "N");
   }
   txt += "\n";

   Comment(txt);
}

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviationPts);

   // ATR handle for Renko brick calculation (only needed for ATR mode)
   if(InpBrickCalc == BRICK_ATR)
   {
      hRenkoATR = iATR(_Symbol, PERIOD_CURRENT, InpATRLen);
      if(hRenkoATR == INVALID_HANDLE)
      {
         Print(InpComment, ": failed to create Renko ATR handle. err=", GetLastError());
         return INIT_FAILED;
      }
   }

   // EMA handles
   hEMAFast = iMA(_Symbol, PERIOD_CURRENT, InpEMAFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(hEMAFast == INVALID_HANDLE)
   {
      Print(InpComment, ": failed to create EMA Fast handle. err=", GetLastError());
      return INIT_FAILED;
   }

   hEMASlow = iMA(_Symbol, PERIOD_CURRENT, InpEMASlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(hEMASlow == INVALID_HANDLE)
   {
      Print(InpComment, ": failed to create EMA Slow handle. err=", GetLastError());
      return INIT_FAILED;
   }

   // Reset Renko state
   g_RenkoInit  = false;
   g_RenkoLevel = 0;
   g_RenkoDir   = 0;
   g_RenkoBrick = 0;

   // Reset SuperTrend state
   g_STInitialized = false;
   g_ATRBarCount   = 0;
   g_SmoothedATR   = 0;
   g_ATR           = 0;
   g_PrevClose     = 0;
   g_PrevSTDir     = 0;
   g_PrevSTUpper   = 0;
   g_PrevSTLower   = 0;

   // Reset trade state
   g_TradeState = 0;
   g_TP1Hit = false;
   g_TP2Hit = false;
   g_TP3Hit = false;

   Print(InpComment, " v2.00 initialized (inline Renko). Symbol=", _Symbol,
         " TF=", EnumToString(Period()),
         " Magic=", InpMagicNumber,
         " EMA=", InpEMAFastPeriod, "/", InpEMASlowPeriod,
         " ST=", InpSTPeriod, "/", DoubleToString(InpSTMultiplier, 1),
         " Brick=", EnumToString((ENUM_LOT_MODE)InpBrickCalc), "/", InpFixedBoxPoints);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hRenkoATR != INVALID_HANDLE) IndicatorRelease(hRenkoATR);
   if(hEMAFast  != INVALID_HANDLE) IndicatorRelease(hEMAFast);
   if(hEMASlow  != INVALID_HANDLE) IndicatorRelease(hEMASlow);
   Comment("");
}

//+------------------------------------------------------------------+
//| OnTick - main logic                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Step 1: Sync with broker
   SyncTradeState();

   //--- Step 2: Time exit
   CheckTimeExit();

   //--- Step 3: Partial TP (every tick)
   ManagePartialTP();

   //--- Step 4: Trail SL (every tick)
   TrailStopBySuperTrend();

   //--- Step 5: New bar gate
   if(!IsNewBar())
      return;

   //--- Step 6: EMA buffers (3 bars, series order)
   double emaFastBuf[3], emaSlowBuf[3];
   ArraySetAsSeries(emaFastBuf, true);
   ArraySetAsSeries(emaSlowBuf, true);

   if(CopyBuffer(hEMAFast, 0, 0, 3, emaFastBuf) < 3) return;
   if(CopyBuffer(hEMASlow, 0, 0, 3, emaSlowBuf) < 3) return;

   //--- Step 7: OHLC for bar[1]
   double high1  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow(_Symbol, PERIOD_CURRENT, 1);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);

   //--- Step 8: Renko engine on bar[1] close
   double renkoATR = 0;
   if(InpBrickCalc == BRICK_ATR && hRenkoATR != INVALID_HANDLE)
   {
      double atrBuf[1];
      if(CopyBuffer(hRenkoATR, 0, 1, 1, atrBuf) < 1) return;
      renkoATR = atrBuf[0];
   }
   CalcRenko(close1, renkoATR);

   //--- Step 9: SuperTrend calculation for bar[1]
   CalcSuperTrend(high1, low1, close1);

   //--- Step 10: Skip if not ready
   double brick = g_RenkoBrick;
   if(brick <= 0 || !g_STInitialized)
   {
      DrawDashboard(0, emaFastBuf[1], emaSlowBuf[1], brick);
      return;
   }

   //--- Step 11: EMA crossover detection on bar[1] vs bar[2]
   bool emaCrossUp = (emaFastBuf[2] <= emaSlowBuf[2] && emaFastBuf[1] > emaSlowBuf[1]);
   bool emaCrossDn = (emaFastBuf[2] >= emaSlowBuf[2] && emaFastBuf[1] < emaSlowBuf[1]);

   //--- Step 12: Renko direction (from inline engine)
   int renkoDir = (int)MathRound(g_RenkoDir);

   //--- Step 13: SuperTrend flip exit
   if(InpExitOnSTFlip && g_TradeState != 0)
   {
      if(g_TradeState == 1 && g_STDirection == -1)
      {
         ulong ticket = FindPositionTicket(POSITION_TYPE_BUY);
         if(ticket > 0)
         {
            g_Trade.PositionClose(ticket);
            Print(InpComment, ": SuperTrend flipped bearish - closed LONG");
         }
         g_TradeState = 0;
         g_TP1Hit = false;
         g_TP2Hit = false;
         g_TP3Hit = false;
      }
      else if(g_TradeState == -1 && g_STDirection == 1)
      {
         ulong ticket = FindPositionTicket(POSITION_TYPE_SELL);
         if(ticket > 0)
         {
            g_Trade.PositionClose(ticket);
            Print(InpComment, ": SuperTrend flipped bullish - closed SHORT");
         }
         g_TradeState = 0;
         g_TP1Hit = false;
         g_TP2Hit = false;
         g_TP3Hit = false;
      }
   }

   //--- Step 14-15: Triple confirmation entry
   bool buySignal  = emaCrossUp && renkoDir == 1  && g_STDirection == 1;
   bool sellSignal = emaCrossDn && renkoDir == -1 && g_STDirection == -1;

   ulong buyTicket  = FindPositionTicket(POSITION_TYPE_BUY);
   ulong sellTicket = FindPositionTicket(POSITION_TYPE_SELL);

   if(buySignal && buyTicket == 0)
   {
      if(sellTicket > 0)
         g_Trade.PositionClose(sellTicket);

      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      double sl = 0;
      double slFromST    = InpSLUseSuperTrend ? g_SuperTrend : 0;
      double slFromBrick = InpSLUseBrick ? NormalizePrice(ask - InpSLBrickMult * brick) : 0;

      if(slFromST > 0 && slFromBrick > 0)
         sl = MathMin(slFromST, slFromBrick);
      else if(slFromST > 0)
         sl = slFromST;
      else if(slFromBrick > 0)
         sl = slFromBrick;

      sl = NormalizePrice(sl);
      double tp = 0;
      ApplyMinStops(true, ask, sl, tp);

      double slDist = ask - sl;
      double lots = CalcLotSize(slDist);

      bool ok = g_Trade.Buy(lots, _Symbol, 0.0, sl, tp, InpComment + " BUY");
      if(ok)
      {
         g_TradeState     = 1;
         g_EntryPrice     = ask;
         g_EntryBrickSize = brick;
         g_EntryLots      = lots;
         g_TP1Hit = false;
         g_TP2Hit = false;
         g_TP3Hit = false;
         Print(InpComment, ": BUY opened. lots=", lots, " entry=", ask,
               " sl=", sl, " brick=", brick,
               " EMA9=", emaFastBuf[1], " EMA15=", emaSlowBuf[1],
               " ST=", g_SuperTrend);
      }
      else
         Print(InpComment, ": BUY failed. err=", GetLastError());
   }
   else if(sellSignal && sellTicket == 0)
   {
      if(buyTicket > 0)
         g_Trade.PositionClose(buyTicket);

      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

      double sl = 0;
      double slFromST    = InpSLUseSuperTrend ? g_SuperTrend : 0;
      double slFromBrick = InpSLUseBrick ? NormalizePrice(bid + InpSLBrickMult * brick) : 0;

      if(slFromST > 0 && slFromBrick > 0)
         sl = MathMax(slFromST, slFromBrick);
      else if(slFromST > 0)
         sl = slFromST;
      else if(slFromBrick > 0)
         sl = slFromBrick;

      sl = NormalizePrice(sl);
      double tp = 0;
      ApplyMinStops(false, bid, sl, tp);

      double slDist = sl - bid;
      double lots = CalcLotSize(slDist);

      bool ok = g_Trade.Sell(lots, _Symbol, 0.0, sl, tp, InpComment + " SELL");
      if(ok)
      {
         g_TradeState     = -1;
         g_EntryPrice     = bid;
         g_EntryBrickSize = brick;
         g_EntryLots      = lots;
         g_TP1Hit = false;
         g_TP2Hit = false;
         g_TP3Hit = false;
         Print(InpComment, ": SELL opened. lots=", lots, " entry=", bid,
               " sl=", sl, " brick=", brick,
               " EMA9=", emaFastBuf[1], " EMA15=", emaSlowBuf[1],
               " ST=", g_SuperTrend);
      }
      else
         Print(InpComment, ": SELL failed. err=", GetLastError());
   }

   //--- Step 16: Dashboard
   DrawDashboard(renkoDir, emaFastBuf[1], emaSlowBuf[1], brick);
}
//+------------------------------------------------------------------+
