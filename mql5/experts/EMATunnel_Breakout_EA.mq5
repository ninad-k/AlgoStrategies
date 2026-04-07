//+------------------------------------------------------------------+
//|                                    EMATunnel_Breakout_EA.mq5    |
//|                                         AlgoStrategies           |
//|  Triple EMA Tunnel Breakout Strategy                             |
//|                                                                  |
//|  Three EMAs (Fast/Mid/Slow) form a price "tunnel".               |
//|  Entries are taken ONLY when price breaks OUTSIDE the tunnel,    |
//|  eliminating low-quality trades during consolidation.            |
//|                                                                  |
//|  New vs EMA200Squeeze_EA:                                        |
//|  + EMA Fast (150) + EMA Slow (250) added alongside EMA Mid (200) |
//|  + Band Breakout filter  - close must be outside Fast/Slow band  |
//|  + EMA Stack filter      - all 3 EMAs must be aligned            |
//|  + Minimum Band Width    - tunnel must be wide (not compressed)  |
//|  + EMA Slope filter      - Mid EMA must slope in trade direction  |
//|  + Candle Body filter    - signal bar must have directional body  |
//|  All original features preserved: 3 partial TPs, trailing SL,   |
//|  SuperTrend trail, ADX filter, P&L dashboard, reverse on exit.   |
//|                                                                  |
//|  Consolidation avoidance — implemented filters:                  |
//|  1. Tunnel breakout  : close beyond EMA_Fast/EMA_Slow band       |
//|  2. EMA stack align  : 150>200>250 (bull) or 150<200<250 (bear)  |
//|  3. Band width       : min pips between EMA_Fast & EMA_Slow      |
//|  4. EMA slope        : Mid EMA must be rising/falling            |
//|  5. Candle body      : strong directional candle on signal bar   |
//|  6. ADX filter       : inherited from EMA200Squeeze              |
//|                                                                  |
//|  Future consolidation filters (not yet implemented):             |
//|  - Bollinger Band Width < threshold => skip (BB squeeze)         |
//|  - Choppiness Index > 61.8 => skip (CI consolidation zone)       |
//|  - Volume < N-bar avg => skip (low participation)                |
//|  - Fractal swing breakout confirmation                           |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property link      ""
#property version   "1.00"
#property description "Triple EMA Tunnel Breakout: trade only on breakout outside the EMA Fast/Mid/Slow band"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_EXIT_MODE {
   EXIT_CANDLE_CLOSE,   // Candle Close (close crosses Mid EMA)
   EXIT_CANDLE_TOUCH    // Candle Touch (wick crosses Mid EMA)
};

enum ENUM_LOT_MODE {
   LOT_FIXED,           // Fixed Lot
   LOT_RISK_PCT         // Risk % of Balance
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
sinput string sep0 = "=== Triple EMA Tunnel ===";
input int              InpEMAFastLen    = 150;                        // Fast EMA Length
input int              InpEMAMidLen     = 200;                        // Mid EMA Length  (core signal)
input int              InpEMASlowLen    = 250;                        // Slow EMA Length
input ENUM_EXIT_MODE   InpExitMode      = EXIT_CANDLE_CLOSE;          // Exit Mode (based on Mid EMA)

sinput string sep0b = "=== Consolidation Filters ===";
input bool             InpUseBandBreak  = true;                       // Require close OUTSIDE Fast/Slow band
input int              InpMinBandPips   = 5;                          // Min band width in pips (0=OFF)
input int              InpMinGapPips    = 0;                          // Min extra pips beyond band (0=OFF)
input bool             InpUseEMAStack   = true;                       // Require full EMA alignment (150>200>250)
input bool             InpUseEMASlope   = false;                      // Require Mid EMA sloping in trade direction
input bool             InpUseBodyFilter = false;                      // Require directional candle body
input int              InpMinBodyPips   = 3;                          // Min candle body size in pips

sinput string sep0c = "=== SuperTrend Trailing (Optional) ===";
input bool             InpUseSTTrail    = false;                      // Use SuperTrend to Trail Remaining Qty
input int              InpSTPeriod      = 10;                         // SuperTrend ATR Period
input double           InpSTMultiplier  = 3.0;                        // SuperTrend Multiplier

sinput string sep0d = "=== ADX Filter (Optional) ===";
input bool             InpUseADX        = false;                      // Enable ADX Filter
input int              InpADXPeriod     = 14;                         // ADX Period
input double           InpADXThreshold  = 25.0;                       // ADX Minimum Threshold

sinput string sep1 = "=== Lot Settings ===";
input ENUM_LOT_MODE    InpLotMode       = LOT_FIXED;                  // Lot Mode
input double           InpFixedLot      = 0.1;                        // Fixed Lot Size
input double           InpRiskPct       = 1.0;                        // Risk % of Balance
input int              InpSLPoints      = 0;                          // Entry SL Points (0=OFF, virtual SL)

sinput string sep2 = "=== Partial Profit Booking (Points from Entry) ===";
input bool             InpTP1Enable     = true;
input int              InpTP1Points     = 30;
input double           InpTP1QtyPct     = 20.0;
input bool             InpTP2Enable     = true;
input int              InpTP2Points     = 60;
input double           InpTP2QtyPct     = 20.0;
input bool             InpTP3Enable     = true;
input int              InpTP3Points     = 90;
input double           InpTP3QtyPct     = 20.0;

sinput string sep3 = "=== Trailing Stop Loss ===";
input bool             InpUseTSL        = false;
input double           InpTSLTriggerPct = 1.5;
input double           InpTSLOffsetPct  = 0.5;

sinput string sep4 = "=== Display ===";
input bool             InpShowEMA       = true;                       // Plot all 3 EMA Lines
input bool             InpShowSignals   = true;
input bool             InpShowTPLines   = true;
input bool             InpShowDashboard = true;

sinput string sep5 = "=== General ===";
input long             InpMagic         = 200300;
input string           InpComment       = "EMATunnel";

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CTrade g_Trade;

// Triple EMA
double g_EMA_FAST     = 0;
double g_EMA_MID      = 0;
double g_EMA_SLOW     = 0;
bool   g_EMAInitialized = false;
double g_PrevEMA_FAST = 0;
double g_PrevEMA_MID  = 0;
double g_PrevEMA_SLOW = 0;
datetime g_PrevBarTime = 0;
int    g_EMAFastLineCount = 0;
int    g_EMAMidLineCount  = 0;
int    g_EMASlowLineCount = 0;

// SuperTrend
double g_STUpperBand  = 0;
double g_STLowerBand  = 0;
double g_SuperTrend   = 0;
int    g_STDirection  = 0;
double g_PrevSTUpper  = 0;
double g_PrevSTLower  = 0;
int    g_PrevSTDir    = 0;
bool   g_STInitialized = false;
double g_ATR          = 0;
double g_SmoothedATR  = 0;
int    g_ATRBarCount  = 0;

// ADX
double g_ADX          = 0;
double g_PlusDI       = 0;
double g_MinusDI      = 0;
double g_PrevTR       = 0;
double g_SmoothedTR   = 0;
double g_SmoothedPlusDM = 0;
double g_SmoothedMinusDM = 0;
double g_SmoothedDX   = 0;
int    g_ADXBarCount  = 0;
bool   g_ADXInitialized = false;
double g_PrevClose    = 0;
double g_PrevHigh     = 0;
double g_PrevLow      = 0;

// Trade state
int    g_TradeState   = 0;
double g_EntryPrice   = 0;
double g_OriginalLots = 0;
double g_StopLoss     = 0;
bool   g_TP1Hit       = false;
bool   g_TP2Hit       = false;
bool   g_TP3Hit       = false;
double g_TrailStop    = 0;
bool   g_TSLActive    = false;

// Dashboard
#define DASH_PREFIX "EMATunnel_"
#define DASH_ROWS   17

// Stats
int    g_TotalTrades  = 0;
int    g_WinTrades    = 0;
int    g_LossTrades   = 0;
double g_GrossProfit  = 0;
double g_GrossLoss    = 0;
double g_MaxEquity    = 0;
double g_MaxDrawdown  = 0;
double g_TotalWinAmt  = 0;
double g_TotalLossAmt = 0;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpEMAFastLen <= 0 || InpEMAMidLen <= 0 || InpEMASlowLen <= 0)
   { Print("All EMA lengths must be > 0"); return INIT_FAILED; }
   if(InpEMAFastLen >= InpEMAMidLen || InpEMAMidLen >= InpEMASlowLen)
   { Print("Required: EMAFast < EMAMid < EMASlow (e.g. 150 < 200 < 250)"); return INIT_FAILED; }

   g_EMA_FAST = g_EMA_MID = g_EMA_SLOW = 0;
   g_PrevEMA_FAST = g_PrevEMA_MID = g_PrevEMA_SLOW = 0;
   g_PrevBarTime = 0;
   g_EMAFastLineCount = g_EMAMidLineCount = g_EMASlowLineCount = 0;
   g_EMAInitialized = false;

   g_STInitialized = false;
   g_ATRBarCount = 0;
   g_SmoothedATR = 0;
   g_ADXInitialized = false;
   g_ADXBarCount = 0;
   g_SmoothedTR = g_SmoothedPlusDM = g_SmoothedMinusDM = g_SmoothedDX = 0;
   g_PrevClose = g_PrevHigh = g_PrevLow = 0;

   g_Trade.SetExpertMagicNumber(InpMagic);
   g_Trade.SetDeviationInPoints(10);
   g_Trade.SetTypeFilling(ORDER_FILLING_FOK);

   g_MaxEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   LoadHistoricalStats();

   if(InpShowDashboard) CreateDashboard();
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, DASH_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   // Intra-bar checks on every tick
   if(g_EMAInitialized && g_TradeState != 0 && g_EntryPrice > 0)
   {
      double liveHigh = iHigh(_Symbol, PERIOD_CURRENT, 0);
      double liveLow  = iLow(_Symbol, PERIOD_CURRENT, 0);
      double liveBid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double liveAsk  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      CheckFixedSL(liveBid, liveAsk);
      if(g_TradeState != 0)
      {
         ProcessPartialTP(liveHigh, liveLow);
         if(InpUseTSL) ProcessTrailingSL(liveHigh, liveLow);
      }
   }

   // New bar gate
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime) return;
   lastBarTime = currentBarTime;

   double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);
   double openPrice  = iOpen(_Symbol, PERIOD_CURRENT, 1);
   double highPrice  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double lowPrice   = iLow(_Symbol, PERIOD_CURRENT, 1);
   datetime barTime  = iTime(_Symbol, PERIOD_CURRENT, 1);

   // Warmup: seed all three EMAs with first close
   if(!g_EMAInitialized)
   {
      g_EMA_FAST = g_EMA_MID = g_EMA_SLOW = closePrice;
      g_EMAInitialized = true;
      return;
   }

   // Update all three EMAs
   double kF = 2.0 / (InpEMAFastLen + 1);
   double kM = 2.0 / (InpEMAMidLen  + 1);
   double kS = 2.0 / (InpEMASlowLen + 1);
   g_EMA_FAST = closePrice * kF + g_EMA_FAST * (1.0 - kF);
   g_EMA_MID  = closePrice * kM + g_EMA_MID  * (1.0 - kM);
   g_EMA_SLOW = closePrice * kS + g_EMA_SLOW * (1.0 - kS);

   // SuperTrend + ADX (use Mid EMA bar data)
   if(InpUseSTTrail) CalcSuperTrend(highPrice, lowPrice, closePrice);
   if(InpUseADX)     CalcADX(highPrice, lowPrice, closePrice);

   SyncTradeState();

   // ── Tunnel geometry ────────────────────────────────────────────
   double upperBand  = MathMax(g_EMA_FAST, g_EMA_SLOW);   // top of tunnel
   double lowerBand  = MathMin(g_EMA_FAST, g_EMA_SLOW);   // bottom of tunnel
   double bandWidth  = upperBand - lowerBand;

   // ── Core signal (same as EMA200Squeeze) ────────────────────────
   bool emaTouched   = (lowPrice <= g_EMA_MID && highPrice >= g_EMA_MID);
   bool prevBarBelow = (g_PrevClose < g_PrevEMA_MID);
   bool prevBarAbove = (g_PrevClose > g_PrevEMA_MID);

   // ── Consolidation filter 1: Band Breakout ──────────────────────
   // Price must close cleanly OUTSIDE the EMA_Fast/EMA_Slow tunnel.
   // If price is inside the tunnel, the EMAs haven't separated yet
   // — we are likely in a consolidation / mean-reversion phase.
   bool aboveTunnel = !InpUseBandBreak ||
                      (closePrice >= upperBand + InpMinGapPips * _Point);
   bool belowTunnel = !InpUseBandBreak ||
                      (closePrice <= lowerBand - InpMinGapPips * _Point);

   // ── Consolidation filter 2: Band Width ─────────────────────────
   // If the tunnel is very narrow the three EMAs are compressed —
   // a classic consolidation signature. Skip until the band opens.
   bool bandWide = (InpMinBandPips <= 0) ||
                   (bandWidth >= InpMinBandPips * _Point);

   // ── Consolidation filter 3: EMA Stack Alignment ────────────────
   // A true trend requires all three EMAs in perfect order.
   // Mixed or flat stacks indicate sideways / transitional price action.
   bool bullishStack = (g_EMA_FAST > g_EMA_MID && g_EMA_MID > g_EMA_SLOW);
   bool bearishStack = (g_EMA_FAST < g_EMA_MID && g_EMA_MID < g_EMA_SLOW);
   bool stackOKBuy   = !InpUseEMAStack || bullishStack;
   bool stackOKSell  = !InpUseEMAStack || bearishStack;

   // ── Consolidation filter 4: EMA Slope ──────────────────────────
   // Mid EMA must currently be sloping in the trade direction.
   // A flat or reversing Mid EMA suggests fading momentum.
   bool emaMidRising  = (g_EMA_MID > g_PrevEMA_MID);
   bool emaMidFalling = (g_EMA_MID < g_PrevEMA_MID);
   bool slopeOKBuy    = !InpUseEMASlope || emaMidRising;
   bool slopeOKSell   = !InpUseEMASlope || emaMidFalling;

   // ── Consolidation filter 5: Candle Body ────────────────────────
   // Doji / spinning-top candles signal indecision; require a
   // meaningful directional body on the signal bar.
   double bodySize     = MathAbs(closePrice - openPrice);
   bool   bodyIsBull   = (closePrice > openPrice);
   bool   bodyIsBear   = (closePrice < openPrice);
   bool   bodyOKBuy    = !InpUseBodyFilter ||
                         (bodyIsBull && bodySize >= InpMinBodyPips * _Point);
   bool   bodyOKSell   = !InpUseBodyFilter ||
                         (bodyIsBear && bodySize >= InpMinBodyPips * _Point);

   // ── Composite entry conditions ──────────────────────────────────
   bool buyCondition  = emaTouched
                        && closePrice > g_EMA_MID   // closes above Mid
                        && prevBarBelow              // previous bar was below Mid
                        && aboveTunnel               // close above the full tunnel
                        && bandWide                  // tunnel is wide enough
                        && stackOKBuy                // EMAs bullishly stacked
                        && slopeOKBuy                // Mid EMA sloping up
                        && bodyOKBuy;                // directional candle body

   bool sellCondition = emaTouched
                        && closePrice < g_EMA_MID
                        && prevBarAbove
                        && belowTunnel
                        && bandWide
                        && stackOKSell
                        && slopeOKSell
                        && bodyOKSell;

   // Store previous bar values AFTER entry conditions (uses bar[2] in next call)
   g_PrevClose = closePrice;
   g_PrevHigh  = highPrice;
   g_PrevLow   = lowPrice;

   // ── ADX entry filter ───────────────────────────────────────────
   if(InpUseADX && g_ADXInitialized && g_ADX < InpADXThreshold)
   { buyCondition = false; sellCondition = false; }

   // ── Exit conditions (Mid EMA based, same as EMA200Squeeze) ─────
   bool longEmaExit  = false;
   bool shortEmaExit = false;

   if(g_TradeState == 1)
   {
      if(InpExitMode == EXIT_CANDLE_CLOSE) longEmaExit = (closePrice < g_EMA_MID);
      else                                 longEmaExit = (lowPrice   <= g_EMA_MID);
   }
   if(g_TradeState == -1)
   {
      if(InpExitMode == EXIT_CANDLE_CLOSE) shortEmaExit = (closePrice > g_EMA_MID);
      else                                 shortEmaExit = (highPrice  >= g_EMA_MID);
   }

   // ── SuperTrend trailing exit ───────────────────────────────────
   if(InpUseSTTrail && g_STInitialized && g_TradeState != 0)
   {
      if(g_TradeState == 1 && g_STDirection == -1)
      {
         CloseAllPositions("ST Trail Long");
         if(InpShowSignals) DrawArrow(barTime, highPrice, false, clrOrange, "ST_EXIT");
         Print("SuperTrend flipped bearish — closed remaining LONG qty");
      }
      else if(g_TradeState == -1 && g_STDirection == 1)
      {
         CloseAllPositions("ST Trail Short");
         if(InpShowSignals) DrawArrow(barTime, lowPrice, true, clrOrange, "ST_EXIT");
         Print("SuperTrend flipped bullish — closed remaining SHORT qty");
      }
   }

   // ── EMA Exit + Reverse ─────────────────────────────────────────
   if(longEmaExit && g_TradeState == 1)
   {
      CloseAllPositions("Exit Long → Reverse Short");
      if(InpShowSignals)
      {
         DrawArrow(barTime, highPrice, false, clrRed, "EXIT");
         DrawArrow(barTime, highPrice + 10 * _Point, false, clrMagenta, "REV_SELL");
      }
      SyncTradeState();
      if(g_TradeState == 0) OpenEntry(-1, barTime, highPrice, lowPrice);
   }
   else if(shortEmaExit && g_TradeState == -1)
   {
      CloseAllPositions("Exit Short → Reverse Long");
      if(InpShowSignals)
      {
         DrawArrow(barTime, lowPrice, true, clrGreen, "EXIT");
         DrawArrow(barTime, lowPrice - 10 * _Point, true, clrMagenta, "REV_BUY");
      }
      SyncTradeState();
      if(g_TradeState == 0) OpenEntry(1, barTime, highPrice, lowPrice);
   }

   // ── New entry when flat ────────────────────────────────────────
   SyncTradeState();
   if(g_TradeState == 0 && buyCondition)
      OpenEntry(1, barTime, highPrice, lowPrice);
   else if(g_TradeState == 0 && sellCondition)
      OpenEntry(-1, barTime, highPrice, lowPrice);

   // ── Plot EMA lines (3 coloured segments per bar) ───────────────
   if(InpShowEMA && g_PrevBarTime > 0)
   {
      DrawEMAsegment(DASH_PREFIX + "EMAF_" + IntegerToString(g_EMAFastLineCount++),
                     g_PrevBarTime, g_PrevEMA_FAST, barTime, g_EMA_FAST, clrCyan, 1);
      DrawEMAsegment(DASH_PREFIX + "EMAM_" + IntegerToString(g_EMAMidLineCount++),
                     g_PrevBarTime, g_PrevEMA_MID,  barTime, g_EMA_MID,  clrYellow, 2);
      DrawEMAsegment(DASH_PREFIX + "EMAS_" + IntegerToString(g_EMASlowLineCount++),
                     g_PrevBarTime, g_PrevEMA_SLOW, barTime, g_EMA_SLOW, clrOrange, 1);
   }

   // ── Plot SuperTrend dots ───────────────────────────────────────
   if(InpShowEMA && g_STInitialized && InpUseSTTrail)
   {
      string stName = DASH_PREFIX + "ST_" + IntegerToString(g_EMAMidLineCount);
      color stClr = (g_STDirection == 1) ? clrLime : clrRed;
      ObjectCreate(0, stName, OBJ_ARROW, 0, barTime, g_SuperTrend);
      ObjectSetInteger(0, stName, OBJPROP_ARROWCODE, 159);
      ObjectSetInteger(0, stName, OBJPROP_COLOR, stClr);
      ObjectSetInteger(0, stName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, stName, OBJPROP_BACK, true);
   }

   g_PrevEMA_FAST = g_EMA_FAST;
   g_PrevEMA_MID  = g_EMA_MID;
   g_PrevEMA_SLOW = g_EMA_SLOW;
   g_PrevBarTime  = barTime;

   if(InpShowTPLines) PlotTPLines(); else RemoveTPLines();
   if(InpShowDashboard) UpdateDashboard();

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_MaxEquity) g_MaxEquity = equity;
   double dd = g_MaxEquity - equity;
   if(dd > g_MaxDrawdown) g_MaxDrawdown = dd;
}

//+------------------------------------------------------------------+
//| OnTrade                                                          |
//+------------------------------------------------------------------+
void OnTrade()
{
   LoadHistoricalStats();
   if(InpShowDashboard) UpdateDashboard();
}

//+------------------------------------------------------------------+
//| Open entry                                                       |
//+------------------------------------------------------------------+
void OpenEntry(int direction, datetime barTime, double highPrice, double lowPrice)
{
   double lots = CalcLotSize();
   if(direction == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(g_Trade.Buy(lots, _Symbol, ask, 0, 0, InpComment + " Buy"))
      {
         g_TradeState = 1; g_EntryPrice = ask;
         g_StopLoss   = (InpSLPoints > 0) ? ask - InpSLPoints * _Point : 0;
         g_OriginalLots = lots;
         g_TP1Hit = g_TP2Hit = g_TP3Hit = false;
         g_TrailStop = 0; g_TSLActive = false;
         Print("BUY opened @ ", ask, " | Tunnel upper=", DoubleToString(MathMax(g_EMA_FAST, g_EMA_SLOW), _Digits));
         if(InpShowSignals) DrawArrow(barTime, lowPrice, true, clrGreen, "BUY");
      }
      else Print("BUY FAILED: ", g_Trade.ResultRetcode(), " ", g_Trade.ResultComment());
   }
   else
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(g_Trade.Sell(lots, _Symbol, bid, 0, 0, InpComment + " Sell"))
      {
         g_TradeState = -1; g_EntryPrice = bid;
         g_StopLoss   = (InpSLPoints > 0) ? bid + InpSLPoints * _Point : 0;
         g_OriginalLots = lots;
         g_TP1Hit = g_TP2Hit = g_TP3Hit = false;
         g_TrailStop = 0; g_TSLActive = false;
         Print("SELL opened @ ", bid, " | Tunnel lower=", DoubleToString(MathMin(g_EMA_FAST, g_EMA_SLOW), _Digits));
         if(InpShowSignals) DrawArrow(barTime, highPrice, false, clrRed, "SELL");
      }
      else Print("SELL FAILED: ", g_Trade.ResultRetcode(), " ", g_Trade.ResultComment());
   }
}

//+------------------------------------------------------------------+
//| Sync trade state with actual open position                       |
//+------------------------------------------------------------------+
void SyncTradeState()
{
   bool hasPosition = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      hasPosition = true;
      g_TradeState = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      break;
   }
   if(!hasPosition)
   {
      g_TradeState = 0; g_EntryPrice = 0; g_StopLoss = 0;
      g_TrailStop = 0; g_TSLActive = false;
      g_TP1Hit = g_TP2Hit = g_TP3Hit = false;
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size                                               |
//+------------------------------------------------------------------+
double CalcLotSize()
{
   if(InpLotMode == LOT_FIXED) return InpFixedLot;
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPct / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue == 0 || tickSize == 0) return InpFixedLot;
   double slMoney = (InpSLPoints * _Point / tickSize) * tickValue;
   if(slMoney == 0) return InpFixedLot;
   double lot     = NormalizeDouble(riskMoney / slMoney, 2);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   return NormalizeDouble(MathFloor(lot / stepLot) * stepLot, 2);
}

//+------------------------------------------------------------------+
//| Check Fixed SL                                                   |
//+------------------------------------------------------------------+
void CheckFixedSL(double bid, double ask)
{
   if(g_StopLoss == 0) return;
   bool slHit = (g_TradeState == 1 && bid <= g_StopLoss) ||
                (g_TradeState == -1 && ask >= g_StopLoss);
   if(slHit)
   {
      Print("FIXED SL HIT | state=", g_TradeState, " SL=", g_StopLoss);
      CloseAllPositions("Fixed SL");
   }
}

//+------------------------------------------------------------------+
//| Process Partial TP                                               |
//+------------------------------------------------------------------+
void ProcessPartialTP(double highPrice, double lowPrice)
{
   if(g_TradeState == 1)
   {
      if(InpTP1Enable && !g_TP1Hit && highPrice >= g_EntryPrice + InpTP1Points * _Point)
      { double l = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0); if(l > 0 && PartialClose(l, "TP1")) g_TP1Hit = true; return; }
      if(InpTP2Enable && !g_TP2Hit && highPrice >= g_EntryPrice + InpTP2Points * _Point)
      { double l = NormalizeLots(g_OriginalLots * InpTP2QtyPct / 100.0); if(l > 0 && PartialClose(l, "TP2")) g_TP2Hit = true; return; }
      if(InpTP3Enable && !g_TP3Hit && highPrice >= g_EntryPrice + InpTP3Points * _Point)
      { double l = NormalizeLots(g_OriginalLots * InpTP3QtyPct / 100.0); if(l > 0 && PartialClose(l, "TP3")) g_TP3Hit = true; return; }
   }
   else if(g_TradeState == -1)
   {
      if(InpTP1Enable && !g_TP1Hit && lowPrice <= g_EntryPrice - InpTP1Points * _Point)
      { double l = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0); if(l > 0 && PartialClose(l, "TP1")) g_TP1Hit = true; return; }
      if(InpTP2Enable && !g_TP2Hit && lowPrice <= g_EntryPrice - InpTP2Points * _Point)
      { double l = NormalizeLots(g_OriginalLots * InpTP2QtyPct / 100.0); if(l > 0 && PartialClose(l, "TP2")) g_TP2Hit = true; return; }
      if(InpTP3Enable && !g_TP3Hit && lowPrice <= g_EntryPrice - InpTP3Points * _Point)
      { double l = NormalizeLots(g_OriginalLots * InpTP3QtyPct / 100.0); if(l > 0 && PartialClose(l, "TP3")) g_TP3Hit = true; return; }
   }
}

//+------------------------------------------------------------------+
//| Process Trailing SL                                              |
//+------------------------------------------------------------------+
void ProcessTrailingSL(double highPrice, double lowPrice)
{
   if(g_TradeState == 1)
   {
      double triggerPrice = g_EntryPrice * (1.0 + InpTSLTriggerPct / 100.0);
      if(highPrice >= triggerPrice)
      {
         double newStop = highPrice * (1.0 - InpTSLOffsetPct / 100.0);
         if(!g_TSLActive || newStop > g_TrailStop)
         { g_TrailStop = newStop; g_TSLActive = true; ModifyPositionSL(newStop); }
      }
      if(g_TSLActive && lowPrice <= g_TrailStop) { CloseAllPositions("TSL Long"); }
   }
   else if(g_TradeState == -1)
   {
      double triggerPrice = g_EntryPrice * (1.0 - InpTSLTriggerPct / 100.0);
      if(lowPrice <= triggerPrice)
      {
         double newStop = lowPrice * (1.0 + InpTSLOffsetPct / 100.0);
         if(!g_TSLActive || newStop < g_TrailStop)
         { g_TrailStop = newStop; g_TSLActive = true; ModifyPositionSL(newStop); }
      }
      if(g_TSLActive && highPrice >= g_TrailStop) { CloseAllPositions("TSL Short"); }
   }
}

//+------------------------------------------------------------------+
//| Partial close                                                    |
//+------------------------------------------------------------------+
bool PartialClose(double lots, string comment)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ulong ticket = PositionGetInteger(POSITION_TICKET);
      double posVol = PositionGetDouble(POSITION_VOLUME);
      if(lots >= posVol) lots = posVol;
      lots = NormalizeLots(lots);
      if(lots <= 0) return false;
      Print("Partial close [", comment, "] lots=", lots, "/", posVol);
      return g_Trade.PositionClosePartial(ticket, lots, ULONG_MAX);
   }
   return false;
}

//+------------------------------------------------------------------+
//| Modify position SL                                               |
//+------------------------------------------------------------------+
void ModifyPositionSL(double newSL)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ulong  ticket = PositionGetInteger(POSITION_TICKET);
      double curSL  = PositionGetDouble(POSITION_SL);
      if(g_TradeState == 1 && newSL > curSL)
      { if(g_Trade.PositionModify(ticket, newSL, 0)) g_StopLoss = newSL; }
      else if(g_TradeState == -1 && newSL < curSL)
      { if(g_Trade.PositionModify(ticket, newSL, 0)) g_StopLoss = newSL; }
      return;
   }
}

//+------------------------------------------------------------------+
//| Close all positions                                              |
//+------------------------------------------------------------------+
void CloseAllPositions(string comment)
{
   for(int attempt = 1; attempt <= 5; attempt++)
   {
      bool anyOpen = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
         anyOpen = true;
         ulong ticket = PositionGetInteger(POSITION_TICKET);
         if(!g_Trade.PositionClose(ticket, ULONG_MAX))
            Print("Close FAILED attempt=", attempt, " rc=", g_Trade.ResultRetcode());
         break;
      }
      if(!anyOpen) break;
   }
   g_TradeState = 0; g_EntryPrice = 0; g_TrailStop = 0; g_TSLActive = false;
}

//+------------------------------------------------------------------+
//| Normalize lots                                                   |
//+------------------------------------------------------------------+
double NormalizeLots(double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot == 0) return minLot;
   lots = MathFloor(lots / stepLot) * stepLot;
   if(lots < minLot) lots = 0;
   if(lots > maxLot) lots = maxLot;
   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Load historical stats                                            |
//+------------------------------------------------------------------+
void LoadHistoricalStats()
{
   g_TotalTrades = g_WinTrades = g_LossTrades = 0;
   g_GrossProfit = g_GrossLoss = g_TotalWinAmt = g_TotalLossAmt = 0;
   HistorySelect(0, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT &&
         HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT_BY) continue;
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                    + HistoryDealGetDouble(ticket, DEAL_SWAP)
                    + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      g_TotalTrades++;
      if(profit >= 0) { g_WinTrades++; g_GrossProfit += profit; g_TotalWinAmt += profit; }
      else            { g_LossTrades++; g_GrossLoss  += profit; g_TotalLossAmt += MathAbs(profit); }
   }
}

//+------------------------------------------------------------------+
//| Draw EMA trend-line segment                                      |
//+------------------------------------------------------------------+
void DrawEMAsegment(string name, datetime t1, double p1, datetime t2, double p2, color clr, int width)
{
   ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

//+------------------------------------------------------------------+
//| Draw arrow                                                       |
//+------------------------------------------------------------------+
void DrawArrow(datetime time, double price, bool isUp, color clr, string label)
{
   string name = DASH_PREFIX + "ARR_" + TimeToString(time) + "_" + label;
   ObjectCreate(0, name, OBJ_ARROW, 0, time, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, isUp ? 233 : 234);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, label + " @ " + DoubleToString(price, _Digits));
}

//+------------------------------------------------------------------+
//| Draw horizontal line                                             |
//+------------------------------------------------------------------+
void DrawHLine(string name, double price, color clr, ENUM_LINE_STYLE style, int width)
{
   if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

//+------------------------------------------------------------------+
//| Plot TP level lines                                              |
//+------------------------------------------------------------------+
void PlotTPLines()
{
   if(g_TradeState == 0 || g_EntryPrice == 0) { RemoveTPLines(); return; }
   double mult = (g_TradeState == 1) ? 1.0 : -1.0;
   if(InpTP1Enable && !g_TP1Hit)
      DrawHLine(DASH_PREFIX + "TP1_LINE", g_EntryPrice + mult * InpTP1Points * _Point, clrLime, STYLE_DASH, 1);
   else ObjectDelete(0, DASH_PREFIX + "TP1_LINE");
   if(InpTP2Enable && !g_TP2Hit)
      DrawHLine(DASH_PREFIX + "TP2_LINE", g_EntryPrice + mult * InpTP2Points * _Point, clrDodgerBlue, STYLE_DASH, 1);
   else ObjectDelete(0, DASH_PREFIX + "TP2_LINE");
   if(InpTP3Enable && !g_TP3Hit)
      DrawHLine(DASH_PREFIX + "TP3_LINE", g_EntryPrice + mult * InpTP3Points * _Point, clrAqua, STYLE_DASH, 1);
   else ObjectDelete(0, DASH_PREFIX + "TP3_LINE");
   if(InpUseTSL && g_TSLActive && g_TrailStop > 0)
      DrawHLine(DASH_PREFIX + "TSL_LINE", g_TrailStop, clrMagenta, STYLE_DASHDOT, 2);
   else ObjectDelete(0, DASH_PREFIX + "TSL_LINE");
}

//+------------------------------------------------------------------+
//| Remove TP lines                                                  |
//+------------------------------------------------------------------+
void RemoveTPLines()
{
   ObjectDelete(0, DASH_PREFIX + "TP1_LINE");
   ObjectDelete(0, DASH_PREFIX + "TP2_LINE");
   ObjectDelete(0, DASH_PREFIX + "TP3_LINE");
   ObjectDelete(0, DASH_PREFIX + "TSL_LINE");
}

//+------------------------------------------------------------------+
//| Create dashboard                                                 |
//+------------------------------------------------------------------+
void CreateDashboard()
{
   int x = 10, y = 30;
   int cellW = 140, cellH = 20;
   int fontSize = 8;

   string bgName = DASH_PREFIX + "BG";
   ObjectCreate(0, bgName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bgName, OBJPROP_XDISTANCE, x - 5);
   ObjectSetInteger(0, bgName, OBJPROP_YDISTANCE, y - 5);
   ObjectSetInteger(0, bgName, OBJPROP_XSIZE, cellW * 2 + 15);
   ObjectSetInteger(0, bgName, OBJPROP_YSIZE, cellH * DASH_ROWS + 15);
   ObjectSetInteger(0, bgName, OBJPROP_BGCOLOR, C'20,20,30');
   ObjectSetInteger(0, bgName, OBJPROP_BORDER_COLOR, clrDimGray);
   ObjectSetInteger(0, bgName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, bgName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bgName, OBJPROP_BACK, false);

   CreateLabel(DASH_PREFIX + "TITLE", x + cellW / 2, y, "EMA Tunnel Breakout", 10, clrDodgerBlue);

   string labels[] = {"",
      "Net Profit", "Open P&L",    "Gross Profit",  "Gross Loss",
      "Total Trades","Win / Loss",  "Win Rate",      "Profit Factor",
      "Avg Win",    "Avg Loss",    "Avg R:R",       "Max Drawdown",
      "Status",     "Band Width",  "EMA Stack",     "ADX"};

   for(int r = 1; r < DASH_ROWS; r++)
   {
      CreateLabel(DASH_PREFIX + "LBL_" + IntegerToString(r), x,           y + r * cellH, labels[r], fontSize, clrSilver);
      CreateLabel(DASH_PREFIX + "VAL_" + IntegerToString(r), x + cellW + 10, y + r * cellH, "-",     fontSize, clrWhite);
   }
}

//+------------------------------------------------------------------+
//| Create label                                                     |
//+------------------------------------------------------------------+
void CreateLabel(string name, int x, int y, string text, int fontSize, color clr)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
}

//+------------------------------------------------------------------+
//| Update dashboard                                                 |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   double netProfit    = g_GrossProfit + g_GrossLoss;
   double winRate      = g_TotalTrades > 0 ? (double)g_WinTrades / g_TotalTrades * 100.0 : 0;
   double profitFactor = g_TotalLossAmt > 0 ? g_GrossProfit / g_TotalLossAmt : 0;
   double avgWin       = g_WinTrades   > 0 ? g_TotalWinAmt  / g_WinTrades   : 0;
   double avgLoss      = g_LossTrades  > 0 ? g_TotalLossAmt / g_LossTrades  : 0;
   double avgRR        = avgLoss       > 0 ? avgWin / avgLoss                : 0;
   double initBal      = AccountInfoDouble(ACCOUNT_BALANCE) - netProfit;
   double netProfitPct = initBal > 0 ? netProfit / initBal * 100.0 : 0;
   double maxDDPct     = initBal > 0 ? g_MaxDrawdown / initBal * 100.0 : 0;

   double openPnL = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      openPnL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }

   double upperBand = MathMax(g_EMA_FAST, g_EMA_SLOW);
   double lowerBand = MathMin(g_EMA_FAST, g_EMA_SLOW);
   double bandPips  = (upperBand - lowerBand) / _Point;
   bool bullStack   = g_EMA_FAST > g_EMA_MID && g_EMA_MID > g_EMA_SLOW;
   bool bearStack   = g_EMA_FAST < g_EMA_MID && g_EMA_MID < g_EMA_SLOW;
   string stackStr  = bullStack ? "BULLISH" : (bearStack ? "BEARISH" : "MIXED");
   color  stackClr  = bullStack ? clrLime : (bearStack ? clrRed : clrYellow);

   SetDashValue(1,  DoubleToString(netProfit, 2) + " (" + DoubleToString(netProfitPct, 1) + "%)", netProfit >= 0 ? clrLime : clrRed);
   SetDashValue(2,  DoubleToString(openPnL, 2),                                                    openPnL   >= 0 ? clrLime : clrRed);
   SetDashValue(3,  DoubleToString(g_GrossProfit, 2),                                              clrLime);
   SetDashValue(4,  DoubleToString(MathAbs(g_GrossLoss), 2),                                       clrRed);
   SetDashValue(5,  IntegerToString(g_TotalTrades),                                                clrWhite);
   SetDashValue(6,  IntegerToString(g_WinTrades) + " / " + IntegerToString(g_LossTrades),          clrWhite);
   SetDashValue(7,  DoubleToString(winRate, 1) + "%",                                              winRate >= 50 ? clrLime : clrRed);
   SetDashValue(8,  DoubleToString(profitFactor, 2),                                               profitFactor >= 1.5 ? clrLime : (profitFactor >= 1.0 ? clrYellow : clrRed));
   SetDashValue(9,  DoubleToString(avgWin, 2),                                                     clrLime);
   SetDashValue(10, DoubleToString(avgLoss, 2),                                                    clrRed);
   SetDashValue(11, DoubleToString(avgRR, 2),                                                      avgRR >= 2 ? clrLime : (avgRR >= 1 ? clrYellow : clrRed));
   SetDashValue(12, DoubleToString(g_MaxDrawdown, 2) + " (" + DoubleToString(maxDDPct, 1) + "%)", maxDDPct <= 10 ? clrLime : (maxDDPct <= 20 ? clrYellow : clrRed));

   string status = g_TradeState == 1 ? "LONG" : (g_TradeState == -1 ? "SHORT" : "FLAT");
   SetDashValue(13, status, g_TradeState == 1 ? clrLime : (g_TradeState == -1 ? clrRed : clrGray));
   SetDashValue(14, DoubleToString(bandPips, 1) + " pts", bandPips >= InpMinBandPips ? clrLime : clrYellow);
   SetDashValue(15, stackStr, stackClr);
   SetDashValue(16, g_ADXInitialized ? DoubleToString(g_ADX, 1) : "n/a",
                    g_ADX >= InpADXThreshold ? clrLime : clrYellow);

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Set dashboard value cell                                         |
//+------------------------------------------------------------------+
void SetDashValue(int row, string text, color clr)
{
   string name = DASH_PREFIX + "VAL_" + IntegerToString(row);
   if(ObjectFind(0, name) >= 0)
   {
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   }
}

//+------------------------------------------------------------------+
//| Calculate SuperTrend (Wilder ATR-based)                          |
//+------------------------------------------------------------------+
void CalcSuperTrend(double highPrice, double lowPrice, double closePrice)
{
   g_ATRBarCount++;
   double tr = (g_ATRBarCount == 1) ? highPrice - lowPrice :
               MathMax(highPrice - lowPrice, MathMax(MathAbs(highPrice - g_PrevClose), MathAbs(lowPrice - g_PrevClose)));
   if(g_ATRBarCount <= InpSTPeriod)
   {
      g_SmoothedATR += tr;
      if(g_ATRBarCount == InpSTPeriod) g_ATR = g_SmoothedATR / InpSTPeriod;
      return;
   }
   g_ATR = (g_ATR * (InpSTPeriod - 1) + tr) / InpSTPeriod;
   double midPrice  = (highPrice + lowPrice) / 2.0;
   double upperBand = midPrice + InpSTMultiplier * g_ATR;
   double lowerBand = midPrice - InpSTMultiplier * g_ATR;
   if(!g_STInitialized)
   {
      g_STUpperBand = upperBand; g_STLowerBand = lowerBand;
      g_STDirection = (closePrice > g_STUpperBand) ? 1 : -1;
      g_SuperTrend  = (g_STDirection == 1) ? g_STLowerBand : g_STUpperBand;
      g_STInitialized = true;
   }
   else
   {
      g_STLowerBand = (lowerBand > g_PrevSTLower || g_PrevClose < g_PrevSTLower) ? lowerBand : g_PrevSTLower;
      g_STUpperBand = (upperBand < g_PrevSTUpper || g_PrevClose > g_PrevSTUpper) ? upperBand : g_PrevSTUpper;
      g_STDirection = (g_PrevSTDir == 1) ? (closePrice < g_STLowerBand ? -1 : 1) : (closePrice > g_STUpperBand ? 1 : -1);
      g_SuperTrend  = (g_STDirection == 1) ? g_STLowerBand : g_STUpperBand;
   }
   g_PrevSTUpper = g_STUpperBand; g_PrevSTLower = g_STLowerBand; g_PrevSTDir = g_STDirection;
}

//+------------------------------------------------------------------+
//| Calculate ADX (Wilder's method)                                  |
//+------------------------------------------------------------------+
void CalcADX(double highPrice, double lowPrice, double closePrice)
{
   g_ADXBarCount++;
   if(g_ADXBarCount == 1) return;
   double plusDM  = MathMax(highPrice - g_PrevHigh, 0);
   double minusDM = MathMax(g_PrevLow - lowPrice, 0);
   if(plusDM > minusDM) minusDM = 0; else if(minusDM > plusDM) plusDM = 0; else { plusDM = 0; minusDM = 0; }
   double tr = MathMax(highPrice - lowPrice, MathMax(MathAbs(highPrice - g_PrevClose), MathAbs(lowPrice - g_PrevClose)));
   int n = InpADXPeriod;
   if(g_ADXBarCount <= n + 1)
   {
      g_SmoothedTR += tr; g_SmoothedPlusDM += plusDM; g_SmoothedMinusDM += minusDM;
      if(g_ADXBarCount == n + 1)
      {
         g_PlusDI  = g_SmoothedTR > 0 ? (g_SmoothedPlusDM / g_SmoothedTR) * 100.0 : 0;
         g_MinusDI = g_SmoothedTR > 0 ? (g_SmoothedMinusDM / g_SmoothedTR) * 100.0 : 0;
         double diSum = g_PlusDI + g_MinusDI;
         double dx    = diSum > 0 ? MathAbs(g_PlusDI - g_MinusDI) / diSum * 100.0 : 0;
         g_SmoothedDX = dx; g_ADX = dx; g_ADXInitialized = true;
      }
      return;
   }
   g_SmoothedTR      = g_SmoothedTR      - g_SmoothedTR / n      + tr;
   g_SmoothedPlusDM  = g_SmoothedPlusDM  - g_SmoothedPlusDM / n  + plusDM;
   g_SmoothedMinusDM = g_SmoothedMinusDM - g_SmoothedMinusDM / n + minusDM;
   g_PlusDI  = g_SmoothedTR > 0 ? (g_SmoothedPlusDM / g_SmoothedTR) * 100.0 : 0;
   g_MinusDI = g_SmoothedTR > 0 ? (g_SmoothedMinusDM / g_SmoothedTR) * 100.0 : 0;
   double diSum = g_PlusDI + g_MinusDI;
   double dx    = diSum > 0 ? MathAbs(g_PlusDI - g_MinusDI) / diSum * 100.0 : 0;
   g_ADX = (g_SmoothedDX * (n - 1) + dx) / n;
   g_SmoothedDX = g_ADX;
}
//+------------------------------------------------------------------+
