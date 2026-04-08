//+------------------------------------------------------------------+
//|                                     EMA200Squeeze_ML_EA.mq5      |
//|                                         AlgoStrategies           |
//|  200 EMA Squeeze Strategy + ML/ONNX Probability Filter            |
//|  Extends base strategy with ONNX-based buy/sell probability.      |
//|  Includes: reverse on exit, ADX filter, ST trail remaining qty,   |
//|  3 partial TPs, trailing SL, P&L dashboard.                       |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property link      ""
#property version   "1.00"
#property description "200 EMA Squeeze + ML: ONNX probability filter, reverse on exit, ADX filter, ST trail, 3 partial TPs, trailing SL, P&L dashboard"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_EXIT_MODE {                                                 //--- Exit mode
   EXIT_CANDLE_CLOSE,                                                  // Candle Close (close crosses EMA)
   EXIT_CANDLE_TOUCH                                                   // Candle Touch (wick touches EMA)
};

enum ENUM_LOT_MODE {                                                  //--- Lot sizing mode
   LOT_FIXED,                                                         // Fixed Lot
   LOT_RISK_PCT                                                       // Risk % of Balance
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
sinput string sep0 = "=== EMA Settings ===";
input int              InpEMALen        = 200;                         // EMA Length
input ENUM_EXIT_MODE   InpExitMode      = EXIT_CANDLE_CLOSE;          // Exit Mode

sinput string sep0b = "=== SuperTrend Trailing (Optional) ===";
input bool             InpUseSTTrail    = false;                      // Use SuperTrend to Trail Remaining Qty
input int              InpSTPeriod      = 10;                         // SuperTrend ATR Period
input double           InpSTMultiplier  = 3.0;                        // SuperTrend Multiplier

sinput string sep0c = "=== ADX Filter (Optional) ===";
input bool             InpUseADX        = false;                      // Enable ADX Filter
input int              InpADXPeriod     = 14;                         // ADX Period
input double           InpADXThreshold  = 25.0;                       // ADX Minimum Threshold

sinput string sep0d = "=== ML / ONNX Probability Filter ===";
input bool             InpUseML         = true;                       // Enable ML Probability Filter
input string           InpONNXFile      = "ema200_squeeze_model.onnx"; // ONNX Model File (in MQL5/Files/)
input double           InpMLThreshold   = 0.6;                        // ML Min Probability to Trade

sinput string sep1 = "=== Lot Settings ===";
input ENUM_LOT_MODE    InpLotMode       = LOT_FIXED;                  // Lot Mode
input double           InpFixedLot      = 0.1;                        // Fixed Lot Size
input double           InpRiskPct       = 1.0;                        // Risk % of Balance
input int              InpSLPoints      = 0;                          // Entry SL Points (0=OFF, virtual SL via CheckFixedSL)

sinput string sep2 = "=== Partial Profit Booking (Points from Entry) ===";
input bool             InpTP1Enable     = true;                       // Enable TP1
input int              InpTP1Points     = 30;                         // TP1 Points from Entry
input double           InpTP1QtyPct     = 20.0;                       // TP1 Close Qty %
input bool             InpTP2Enable     = true;                       // Enable TP2
input int              InpTP2Points     = 60;                         // TP2 Points from Entry (TP1 + 30)
input double           InpTP2QtyPct     = 20.0;                       // TP2 Close Qty %
input bool             InpTP3Enable     = true;                       // Enable TP3
input int              InpTP3Points     = 90;                         // TP3 Points from Entry (TP2 + 30)
input double           InpTP3QtyPct     = 20.0;                       // TP3 Close Qty %

sinput string sep3 = "=== Trailing Stop Loss ===";
input bool             InpUseTSL        = false;                      // Enable Trailing SL
input double           InpTSLTriggerPct = 1.5;                        // TSL Trigger Profit %
input double           InpTSLOffsetPct  = 0.5;                        // TSL Trail Offset %

sinput string sep4 = "=== Display ===";
input bool             InpShowEMA       = true;                       // Plot EMA Line
input bool             InpShowSignals   = true;                       // Plot Entry/Exit Arrows
input bool             InpShowTPLines   = true;                       // Plot TP Level Lines
input bool             InpShowDashboard = true;                       // Show P&L Dashboard

sinput string sep5 = "=== General ===";
input long             InpMagic         = 200201;                     // Magic Number
input string           InpComment       = "EMA200SQ_ML";              // Order Comment

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CTrade g_Trade;                                                       //--- Trade object

// Manual EMA
double g_EMA = 0;                                                     //--- EMA current value
bool   g_EMAInitialized = false;                                      //--- EMA warmup done flag
double g_PrevEMA = 0;                                                 //--- Previous bar EMA value
datetime g_PrevBarTime = 0;                                           //--- Previous bar time
int    g_EMALineCount = 0;                                            //--- EMA line segment counter

// SuperTrend
double g_STUpperBand  = 0;                                            //--- SuperTrend upper band
double g_STLowerBand  = 0;                                            //--- SuperTrend lower band
double g_SuperTrend   = 0;                                            //--- Current SuperTrend value
int    g_STDirection  = 0;                                            //--- 1=up (bullish), -1=down (bearish)
double g_PrevSTUpper  = 0;
double g_PrevSTLower  = 0;
int    g_PrevSTDir    = 0;
bool   g_STInitialized = false;

// ADX
double g_ADX          = 0;                                            //--- Current ADX value
double g_PlusDI       = 0;                                            //--- +DI value
double g_MinusDI      = 0;                                            //--- -DI value
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

// ATR for SuperTrend
double g_ATR          = 0;
double g_SmoothedATR  = 0;
int    g_ATRBarCount  = 0;

// ML / ONNX
long   g_ONNXHandle   = INVALID_HANDLE;                               //--- ONNX session handle
double g_MLProbBuy    = 0.5;                                          //--- Last ML buy probability
double g_MLProbSell   = 0.5;                                          //--- Last ML sell probability
bool   g_MLReady      = false;                                        //--- ML model loaded flag

// Feature buffers for ML (24 features)
#define ML_FEATURES 24
double g_MLFeatures[ML_FEATURES];

// Additional indicators for ML features
double g_RSI14        = 50;
double g_RSI7         = 50;
double g_EMA12        = 0;
double g_EMA26        = 0;
double g_MACDLine     = 0;
double g_MACDSignal   = 0;
double g_BB_Upper     = 0;
double g_BB_Lower     = 0;
double g_BB_SMA       = 0;
double g_VolSMA20     = 0;
int    g_CandlesSinceTouch = 0;

int    g_TradeState   = 0;                                            //--- 0=flat, 1=long, -1=short
double g_EntryPrice   = 0;                                            //--- Entry price
double g_OriginalLots = 0;                                            //--- Original position lots
double g_StopLoss     = 0;                                            //--- Current SL price
bool   g_TP1Hit       = false;                                        //--- TP1 hit flag
bool   g_TP2Hit       = false;                                        //--- TP2 hit flag
bool   g_TP3Hit       = false;                                        //--- TP3 hit flag
double g_TrailStop    = 0;                                            //--- Trailing stop price
bool   g_TSLActive    = false;                                        //--- TSL active flag

// Dashboard object names
#define DASH_PREFIX "EMA200ML_"
#define DASH_ROWS   15
#define DASH_COLS   2

// Stats tracking
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
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpEMALen <= 0)
   {
      Print("EMA Length must be > 0");
      return INIT_FAILED;
   }

   g_EMA = 0;
   g_PrevEMA = 0;
   g_PrevBarTime = 0;
   g_EMALineCount = 0;
   g_EMAInitialized = false;

   g_STInitialized = false;
   g_ATRBarCount = 0;
   g_SmoothedATR = 0;
   g_ADXInitialized = false;
   g_ADXBarCount = 0;
   g_SmoothedTR = 0;
   g_SmoothedPlusDM = 0;
   g_SmoothedMinusDM = 0;
   g_SmoothedDX = 0;
   g_PrevClose = 0;
   g_PrevHigh = 0;
   g_PrevLow = 0;

   g_Trade.SetExpertMagicNumber(InpMagic);
   g_Trade.SetDeviationInPoints(10);
   g_Trade.SetTypeFilling(ORDER_FILLING_FOK);

   // Load ONNX model if ML filter enabled
   g_MLReady = false;
   if(InpUseML)
   {
      g_ONNXHandle = OnnxCreate(InpONNXFile, 0);
      if(g_ONNXHandle != INVALID_HANDLE)
      {
         // Set input shape [1, 24]
         ulong inputShape[]  = {1, ML_FEATURES};
         if(OnnxSetInputShape(g_ONNXHandle, 0, inputShape))
         {
            // Set output shapes
            ulong outputShape1[] = {1};         // label
            ulong outputShape2[] = {1, 2};      // probabilities
            OnnxSetOutputShape(g_ONNXHandle, 0, outputShape1);
            OnnxSetOutputShape(g_ONNXHandle, 1, outputShape2);
            g_MLReady = true;
            Print("ML model loaded: ", InpONNXFile);
         }
         else
            Print("Failed to set ONNX input shape");
      }
      else
         Print("Failed to load ONNX model: ", InpONNXFile, " (place in MQL5/Files/)");
   }

   g_MaxEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   LoadHistoricalStats();

   if(InpShowDashboard)
      CreateDashboard();

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ONNXHandle != INVALID_HANDLE)
   {
      OnnxRelease(g_ONNXHandle);
      g_ONNXHandle = INVALID_HANDLE;
   }
   ObjectsDeleteAll(0, DASH_PREFIX);
   RemoveTPLines();
   RemoveSignalArrows();
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Intra-bar checks on EVERY tick using live current bar prices:
   //    Fixed SL      → closes ALL lots immediately if hit (highest priority)
   //    Partial TP    → booked immediately when price hits TP level
   //    Trailing SL   → trail updates and hit check in real time
   if(g_EMAInitialized && g_TradeState != 0 && g_EntryPrice > 0)
   {
      double liveHigh = iHigh(_Symbol, PERIOD_CURRENT, 0);
      double liveLow  = iLow(_Symbol, PERIOD_CURRENT, 0);
      double liveBid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double liveAsk  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      //--- Check fixed SL FIRST (closes all lots immediately)
      CheckFixedSL(liveBid, liveAsk);

      //--- Only process TP/TSL if SL hasn't been hit
      if(g_TradeState != 0)
      {
         ProcessPartialTP(liveHigh, liveLow);
         if(InpUseTSL)
            ProcessTrailingSL(liveHigh, liveLow);
      }
   }

   //--- All other logic: only process on new bar (bar close signal)
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime) return;
   lastBarTime = currentBarTime;

   //--- Bar 1 = last closed candle
   double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);
   double highPrice  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double lowPrice   = iLow(_Symbol, PERIOD_CURRENT, 1);
   datetime barTime  = iTime(_Symbol, PERIOD_CURRENT, 1);

   //--- Warmup: seed EMA with first close
   if(!g_EMAInitialized)
   {
      g_EMA = closePrice;
      g_EMAInitialized = true;
      return;
   }

   //--- Update EMA: EMA = close * k + prevEMA * (1-k), k = 2/(n+1)
   double k = 2.0 / (InpEMALen + 1);
   g_EMA = closePrice * k + g_EMA * (1.0 - k);

   //--- Calculate SuperTrend (manual ATR-based) — needed for ST trail or ML features
   if(InpUseSTTrail || InpUseML)
      CalcSuperTrend(highPrice, lowPrice, closePrice);

   //--- Calculate ADX (manual) — needed for ADX filter or ML features
   if(InpUseADX || InpUseML)
      CalcADX(highPrice, lowPrice, closePrice);

   //--- Sync trade state with actual position
   SyncTradeState();

   //--- Entry conditions: price must TOUCH/CROSS EMA (candle range spans EMA)
   //    PLUS: previous bar must have been on the opposite side (no consolidation)
   //    NOTE: g_PrevClose/g_PrevEMA still hold BAR[2] values here (not yet overwritten)
   bool emaTouched = (lowPrice <= g_EMA && highPrice >= g_EMA);
   bool prevBarBelow = (g_PrevClose < g_PrevEMA);  // bar[2] closed below bar[2]'s EMA
   bool prevBarAbove = (g_PrevClose > g_PrevEMA);  // bar[2] closed above bar[2]'s EMA
   bool buyCondition  = emaTouched && closePrice > g_EMA && prevBarBelow;    // breakout UP
   bool sellCondition = emaTouched && closePrice < g_EMA && prevBarAbove;    // breakout DOWN

   //--- Store current bar data for NEXT bar's previous-bar checks (must be AFTER entry conditions)
   g_PrevClose = closePrice;
   g_PrevHigh  = highPrice;
   g_PrevLow   = lowPrice;

   //--- ADX entry filter: skip trade if ADX below threshold (no trend)
   if(InpUseADX && g_ADXInitialized)
   {
      if(g_ADX < InpADXThreshold)
      {
         buyCondition  = false;
         sellCondition = false;
      }
   }

   //--- ML probability filter
   if(InpUseML && g_MLReady && (buyCondition || sellCondition))
   {
      ComputeMLFeatures(closePrice, highPrice, lowPrice);
      RunONNXInference();

      if(buyCondition && g_MLProbBuy < InpMLThreshold)
         buyCondition = false;    // ML says buy probability too low
      if(sellCondition && g_MLProbSell < InpMLThreshold)
         sellCondition = false;   // ML says sell probability too low
   }

   //--- Exit conditions based on selected exit mode
   bool longEmaExit  = false;
   bool shortEmaExit = false;

   if(g_TradeState == 1)
   {
      if(InpExitMode == EXIT_CANDLE_CLOSE)
         longEmaExit = closePrice < g_EMA;
      else if(InpExitMode == EXIT_CANDLE_TOUCH)
         longEmaExit = lowPrice <= g_EMA;
   }

   if(g_TradeState == -1)
   {
      if(InpExitMode == EXIT_CANDLE_CLOSE)
         shortEmaExit = closePrice > g_EMA;
      else if(InpExitMode == EXIT_CANDLE_TOUCH)
         shortEmaExit = highPrice >= g_EMA;
   }

   bool longExit  = longEmaExit;
   bool shortExit = shortEmaExit;

   //--- Partial TP is handled intra-bar (every tick) above.
   //    No second call here — TP flags (g_TP1Hit etc.) prevent double-firing.

   //--- SuperTrend trailing exit for remaining qty (after partial TPs)
   if(InpUseSTTrail && g_STInitialized && g_TradeState != 0)
   {
      if(g_TradeState == 1 && g_STDirection == -1)
      {
         CloseAllPositions("ST Trail Long");
         if(InpShowSignals)
            DrawArrow(barTime, highPrice, false, clrOrange, "ST_EXIT");
         Print("SuperTrend flipped bearish - closed remaining LONG qty");
      }
      else if(g_TradeState == -1 && g_STDirection == 1)
      {
         CloseAllPositions("ST Trail Short");
         if(InpShowSignals)
            DrawArrow(barTime, lowPrice, true, clrOrange, "ST_EXIT");
         Print("SuperTrend flipped bullish - closed remaining SHORT qty");
      }
   }

   //--- Trailing SL is handled intra-bar (every tick) above.

   //--- EMA Exit + Reverse: close current position and open opposite
   if(longExit && g_TradeState == 1)
   {
      CloseAllPositions("Exit Long -> Reverse Short");
      if(InpShowSignals)
      {
         DrawArrow(barTime, highPrice, false, clrRed, "EXIT");
         DrawArrow(barTime, highPrice + 10 * _Point, false, clrMagenta, "REV_SELL");
      }
      SyncTradeState();
      if(g_TradeState == 0)
         OpenEntry(-1, barTime, highPrice, lowPrice);  // Reverse to short
   }
   else if(shortExit && g_TradeState == -1)
   {
      CloseAllPositions("Exit Short -> Reverse Long");
      if(InpShowSignals)
      {
         DrawArrow(barTime, lowPrice, true, clrGreen, "EXIT");
         DrawArrow(barTime, lowPrice - 10 * _Point, true, clrMagenta, "REV_BUY");
      }
      SyncTradeState();
      if(g_TradeState == 0)
         OpenEntry(1, barTime, highPrice, lowPrice);   // Reverse to long
   }

   //--- New entries (only when flat - no position and no reverse happened)
   SyncTradeState();

   bool buySignal  = g_TradeState == 0 && buyCondition;
   bool sellSignal = g_TradeState == 0 && sellCondition;

   if(buySignal)
      OpenEntry(1, barTime, highPrice, lowPrice);
   else if(sellSignal)
      OpenEntry(-1, barTime, highPrice, lowPrice);

   //--- Plot EMA line as connected segments bar-to-bar
   if(InpShowEMA && g_PrevBarTime > 0)
   {
      string segName = DASH_PREFIX + "EMA_" + IntegerToString(g_EMALineCount);
      ObjectCreate(0, segName, OBJ_TREND, 0, g_PrevBarTime, g_PrevEMA, barTime, g_EMA);
      ObjectSetInteger(0, segName, OBJPROP_COLOR, clrYellow);
      ObjectSetInteger(0, segName, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, segName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, segName, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, segName, OBJPROP_BACK, true);
      g_EMALineCount++;
   }
   g_PrevEMA = g_EMA;
   g_PrevBarTime = barTime;

   //--- Plot SuperTrend line (green=bullish, red=bearish)
   if(InpShowEMA && g_STInitialized && InpUseSTTrail)
   {
      string stName = DASH_PREFIX + "ST_" + IntegerToString(g_EMALineCount);
      color stColor = g_STDirection == 1 ? clrLime : clrRed;
      ObjectCreate(0, stName, OBJ_ARROW, 0, barTime, g_SuperTrend);
      ObjectSetInteger(0, stName, OBJPROP_ARROWCODE, 159);  // small dot
      ObjectSetInteger(0, stName, OBJPROP_COLOR, stColor);
      ObjectSetInteger(0, stName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, stName, OBJPROP_BACK, true);
   }

   //--- Plot TP level lines
   if(InpShowTPLines)
      PlotTPLines();
   else
      RemoveTPLines();

   //--- Update dashboard
   if(InpShowDashboard)
      UpdateDashboard();

   //--- Track max equity and drawdown
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_MaxEquity)
      g_MaxEquity = equity;
   double dd = g_MaxEquity - equity;
   if(dd > g_MaxDrawdown)
      g_MaxDrawdown = dd;
}

//+------------------------------------------------------------------+
//| OnTrade - track completed trades                                 |
//+------------------------------------------------------------------+
void OnTrade()
{
   LoadHistoricalStats();
   if(InpShowDashboard)
      UpdateDashboard();
}

//+------------------------------------------------------------------+
//| Open a new entry (1=Long, -1=Short)                              |
//+------------------------------------------------------------------+
void OpenEntry(int direction, datetime barTime, double highPrice, double lowPrice)
{
   double lots = CalcLotSize();
   if(direction == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      //--- Send order WITHOUT broker SL (sl=0) to avoid "invalid stops" rejection.
      //    Virtual SL is monitored every tick by CheckFixedSL().
      if(g_Trade.Buy(lots, _Symbol, ask, 0, 0, "EMA 200 Buy"))
      {
         g_TradeState   = 1;
         g_EntryPrice   = ask;
         g_StopLoss     = (InpSLPoints > 0) ? ask - InpSLPoints * _Point : 0;
         g_OriginalLots = lots;
         g_TP1Hit = false;
         g_TP2Hit = false;
         g_TP3Hit = false;
         g_TrailStop = 0;
         g_TSLActive = false;
         Print("BUY opened @ ", ask,
               (InpSLPoints > 0 ? " virtual SL=" + DoubleToString(g_StopLoss, _Digits) : " SL=OFF"));
         if(InpShowSignals)
            DrawArrow(barTime, lowPrice, true, clrGreen, "BUY");
      }
      else
         Print("BUY FAILED: retcode=", g_Trade.ResultRetcode(), " ", g_Trade.ResultComment());
   }
   else
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(g_Trade.Sell(lots, _Symbol, bid, 0, 0, "EMA 200 Sell"))
      {
         g_TradeState   = -1;
         g_EntryPrice   = bid;
         g_StopLoss     = (InpSLPoints > 0) ? bid + InpSLPoints * _Point : 0;
         g_OriginalLots = lots;
         g_TP1Hit = false;
         g_TP2Hit = false;
         g_TP3Hit = false;
         g_TrailStop = 0;
         g_TSLActive = false;
         Print("SELL opened @ ", bid,
               (InpSLPoints > 0 ? " virtual SL=" + DoubleToString(g_StopLoss, _Digits) : " SL=OFF"));
         if(InpShowSignals)
            DrawArrow(barTime, highPrice, false, clrRed, "SELL");
      }
      else
         Print("SELL FAILED: retcode=", g_Trade.ResultRetcode(), " ", g_Trade.ResultComment());
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
      long posType = PositionGetInteger(POSITION_TYPE);
      if(posType == POSITION_TYPE_BUY)
         g_TradeState = 1;
      else
         g_TradeState = -1;
      break;
   }
   if(!hasPosition)
   {
      g_TradeState = 0;
      g_EntryPrice = 0;
      g_StopLoss   = 0;
      g_TrailStop  = 0;
      g_TSLActive  = false;
      g_TP1Hit     = false;
      g_TP2Hit     = false;
      g_TP3Hit     = false;
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size                                               |
//+------------------------------------------------------------------+
double CalcLotSize()
{
   if(InpLotMode == LOT_FIXED)
      return InpFixedLot;

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
   lot = MathFloor(lot / stepLot) * stepLot;
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Check Fixed SL — closes ALL remaining lots if hit                |
//+------------------------------------------------------------------+
void CheckFixedSL(double bid, double ask)
{
   if(g_StopLoss == 0) return;  // no SL set

   bool slHit = false;

   if(g_TradeState == 1)  // LONG position
   {
      //--- SL hit if bid drops to or below the SL price
      if(bid <= g_StopLoss)
      {
         slHit = true;
         Print("FIXED SL HIT for LONG: bid=", bid, " SL=", g_StopLoss);
      }
   }
   else if(g_TradeState == -1)  // SHORT position
   {
      //--- SL hit if ask rises to or above the SL price
      if(ask >= g_StopLoss)
      {
         slHit = true;
         Print("FIXED SL HIT for SHORT: ask=", ask, " SL=", g_StopLoss);
      }
   }

   if(slHit)
   {
      //--- Close ALL remaining lots (entire position)
      CloseAllPositions("Fixed SL");
   }
}

//+------------------------------------------------------------------+
//| Process Partial Take Profit                                      |
//+------------------------------------------------------------------+
void ProcessPartialTP(double highPrice, double lowPrice)
{
   if(g_TradeState == 1) // Long
   {
      double tp1Price = g_EntryPrice + InpTP1Points * _Point;
      double tp2Price = g_EntryPrice + InpTP2Points * _Point;
      double tp3Price = g_EntryPrice + InpTP3Points * _Point;

      if(InpTP1Enable && !g_TP1Hit && highPrice >= tp1Price)
      {
         double closeLots = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0);
         if(closeLots > 0 && PartialClose(closeLots, "TP1"))
            g_TP1Hit = true;
         return; // max one TP per bar
      }
      if(InpTP2Enable && !g_TP2Hit && highPrice >= tp2Price)
      {
         double closeLots = NormalizeLots(g_OriginalLots * InpTP2QtyPct / 100.0);
         if(closeLots > 0 && PartialClose(closeLots, "TP2"))
            g_TP2Hit = true;
         return; // max one TP per bar
      }
      if(InpTP3Enable && !g_TP3Hit && highPrice >= tp3Price)
      {
         double closeLots = NormalizeLots(g_OriginalLots * InpTP3QtyPct / 100.0);
         if(closeLots > 0 && PartialClose(closeLots, "TP3"))
            g_TP3Hit = true;
         return; // max one TP per bar
      }
   }
   else if(g_TradeState == -1) // Short
   {
      double tp1Price = g_EntryPrice - InpTP1Points * _Point;
      double tp2Price = g_EntryPrice - InpTP2Points * _Point;
      double tp3Price = g_EntryPrice - InpTP3Points * _Point;

      if(InpTP1Enable && !g_TP1Hit && lowPrice <= tp1Price)
      {
         double closeLots = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0);
         if(closeLots > 0 && PartialClose(closeLots, "TP1"))
            g_TP1Hit = true;
         return; // max one TP per bar
      }
      if(InpTP2Enable && !g_TP2Hit && lowPrice <= tp2Price)
      {
         double closeLots = NormalizeLots(g_OriginalLots * InpTP2QtyPct / 100.0);
         if(closeLots > 0 && PartialClose(closeLots, "TP2"))
            g_TP2Hit = true;
         return; // max one TP per bar
      }
      if(InpTP3Enable && !g_TP3Hit && lowPrice <= tp3Price)
      {
         double closeLots = NormalizeLots(g_OriginalLots * InpTP3QtyPct / 100.0);
         if(closeLots > 0 && PartialClose(closeLots, "TP3"))
            g_TP3Hit = true;
         return; // max one TP per bar
      }
   }
}

//+------------------------------------------------------------------+
//| Process Trailing Stop Loss                                       |
//+------------------------------------------------------------------+
void ProcessTrailingSL(double highPrice, double lowPrice)
{
   if(g_TradeState == 1) // Long
   {
      double triggerPrice = g_EntryPrice * (1.0 + InpTSLTriggerPct / 100.0);
      if(highPrice >= triggerPrice)
      {
         double newStop = highPrice * (1.0 - InpTSLOffsetPct / 100.0);
         if(!g_TSLActive || newStop > g_TrailStop)
         {
            g_TrailStop = newStop;
            g_TSLActive = true;
         }
      }
      if(g_TSLActive && lowPrice <= g_TrailStop)
      {
         CloseAllPositions("TSL Long");
         Print("Trailing SL hit for LONG at ", g_TrailStop);
      }
   }
   else if(g_TradeState == -1) // Short
   {
      double triggerPrice = g_EntryPrice * (1.0 - InpTSLTriggerPct / 100.0);
      if(lowPrice <= triggerPrice)
      {
         double newStop = lowPrice * (1.0 + InpTSLOffsetPct / 100.0);
         if(!g_TSLActive || newStop < g_TrailStop)
         {
            g_TrailStop = newStop;
            g_TSLActive = true;
         }
      }
      if(g_TSLActive && highPrice >= g_TrailStop)
      {
         CloseAllPositions("TSL Short");
         Print("Trailing SL hit for SHORT at ", g_TrailStop);
      }
   }
}

//+------------------------------------------------------------------+
//| Partial close of position                                        |
//+------------------------------------------------------------------+
bool PartialClose(double lots, string comment)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      ulong ticket = PositionGetInteger(POSITION_TICKET);
      double posVol = PositionGetDouble(POSITION_VOLUME);

      if(lots >= posVol)
         lots = posVol;

      lots = NormalizeLots(lots);
      if(lots <= 0) return false;

      Print("Partial close [", comment, "] lots=", lots, " of ", posVol);
      return g_Trade.PositionClosePartial(ticket, lots, ULONG_MAX);
   }
   return false;
}

//+------------------------------------------------------------------+
//| Close all positions for this EA                                  |
//+------------------------------------------------------------------+
void CloseAllPositions(string comment)
{
   //--- Retry loop: re-scan from scratch after each close to handle
   //    netting and hedging accounts safely and catch failed closes
   for(int attempt = 1; attempt <= 5; attempt++)
   {
      bool anyOpen = false;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(PositionGetSymbol(i) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
         anyOpen = true;
         ulong  ticket = PositionGetInteger(POSITION_TICKET);
         double vol    = PositionGetDouble(POSITION_VOLUME);
         Print("CloseAll [", comment, "] attempt=", attempt,
               " ticket=", ticket, " vol=", vol);
         if(!g_Trade.PositionClose(ticket, ULONG_MAX))
            Print("  Close FAILED retcode=", g_Trade.ResultRetcode(),
                  " ", g_Trade.ResultComment());
         break; // re-scan after every close attempt
      }
      if(!anyOpen) break;
   }
   g_TradeState = 0;
   g_EntryPrice = 0;
   g_TrailStop  = 0;
   g_TSLActive  = false;
}

//+------------------------------------------------------------------+
//| Normalize lots to valid volume                                   |
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
//| Load historical stats from account deal history                  |
//+------------------------------------------------------------------+
void LoadHistoricalStats()
{
   g_TotalTrades  = 0;
   g_WinTrades    = 0;
   g_LossTrades   = 0;
   g_GrossProfit  = 0;
   g_GrossLoss    = 0;
   g_TotalWinAmt  = 0;
   g_TotalLossAmt = 0;

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
      if(profit >= 0)
      {
         g_WinTrades++;
         g_GrossProfit += profit;
         g_TotalWinAmt += profit;
      }
      else
      {
         g_LossTrades++;
         g_GrossLoss += profit;
         g_TotalLossAmt += MathAbs(profit);
      }
   }
}

//+------------------------------------------------------------------+
//| Draw entry/exit arrow on chart                                   |
//+------------------------------------------------------------------+
void DrawArrow(datetime time, double price, bool isUp, color clr, string label)
{
   string name = DASH_PREFIX + "ARR_" + TimeToString(time) + "_" + label;
   int code = isUp ? 233 : 234;
   ObjectCreate(0, name, OBJ_ARROW, 0, time, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, label + " @ " + DoubleToString(price, _Digits));
}

//+------------------------------------------------------------------+
//| Remove signal arrows                                             |
//+------------------------------------------------------------------+
void RemoveSignalArrows()
{
   ObjectsDeleteAll(0, DASH_PREFIX + "ARR_");
}

//+------------------------------------------------------------------+
//| Draw horizontal line                                             |
//+------------------------------------------------------------------+
void DrawHLine(string name, double price, color clr, ENUM_LINE_STYLE style, int width)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
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
   if(g_TradeState == 0 || g_EntryPrice == 0)
   {
      RemoveTPLines();
      return;
   }

   double mult = (g_TradeState == 1) ? 1.0 : -1.0;

   if(InpTP1Enable && !g_TP1Hit)
      DrawHLine(DASH_PREFIX + "TP1_LINE", g_EntryPrice + mult * InpTP1Points * _Point, clrLime, STYLE_DASH, 1);
   else
      ObjectDelete(0, DASH_PREFIX + "TP1_LINE");

   if(InpTP2Enable && !g_TP2Hit)
      DrawHLine(DASH_PREFIX + "TP2_LINE", g_EntryPrice + mult * InpTP2Points * _Point, clrDodgerBlue, STYLE_DASH, 1);
   else
      ObjectDelete(0, DASH_PREFIX + "TP2_LINE");

   if(InpTP3Enable && !g_TP3Hit)
      DrawHLine(DASH_PREFIX + "TP3_LINE", g_EntryPrice + mult * InpTP3Points * _Point, clrAqua, STYLE_DASH, 1);
   else
      ObjectDelete(0, DASH_PREFIX + "TP3_LINE");

   // Trailing SL line
   if(InpUseTSL && g_TSLActive && g_TrailStop > 0)
      DrawHLine(DASH_PREFIX + "TSL_LINE", g_TrailStop, clrMagenta, STYLE_DASHDOT, 2);
   else
      ObjectDelete(0, DASH_PREFIX + "TSL_LINE");
}

//+------------------------------------------------------------------+
//| Remove TP level lines                                            |
//+------------------------------------------------------------------+
void RemoveTPLines()
{
   ObjectDelete(0, DASH_PREFIX + "TP1_LINE");
   ObjectDelete(0, DASH_PREFIX + "TP2_LINE");
   ObjectDelete(0, DASH_PREFIX + "TP3_LINE");
   ObjectDelete(0, DASH_PREFIX + "TSL_LINE");
}

//+------------------------------------------------------------------+
//| Create Dashboard Table                                           |
//+------------------------------------------------------------------+
void CreateDashboard()
{
   int x = 10, y = 30;
   int cellW = 130, cellH = 20;
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

   CreateLabel(DASH_PREFIX + "TITLE", x + cellW / 2, y, "EMA200 Squeeze + ML", 10, clrDodgerBlue);

   string labels[] = {"", "Net Profit", "Open P&L", "Gross Profit", "Gross Loss",
                       "Total Trades", "Win / Loss", "Win Rate", "Profit Factor",
                       "Avg Win", "Avg Loss", "Avg R:R", "Max Drawdown", "Status",
                       "ML Prob (B/S)"};

   for(int r = 1; r < DASH_ROWS; r++)
   {
      string lblName = DASH_PREFIX + "LBL_" + IntegerToString(r);
      CreateLabel(lblName, x, y + r * cellH, labels[r], fontSize, clrSilver);

      string valName = DASH_PREFIX + "VAL_" + IntegerToString(r);
      CreateLabel(valName, x + cellW + 10, y + r * cellH, "-", fontSize, clrWhite);
   }
}

//+------------------------------------------------------------------+
//| Create text label object                                         |
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
//| Update Dashboard Values                                          |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   double netProfit    = g_GrossProfit + g_GrossLoss;
   double winRate      = g_TotalTrades > 0 ? (double)g_WinTrades / g_TotalTrades * 100.0 : 0;
   double profitFactor = g_TotalLossAmt > 0 ? g_GrossProfit / g_TotalLossAmt : 0;
   double avgWin       = g_WinTrades > 0 ? g_TotalWinAmt / g_WinTrades : 0;
   double avgLoss      = g_LossTrades > 0 ? g_TotalLossAmt / g_LossTrades : 0;
   double avgRR        = avgLoss > 0 ? avgWin / avgLoss : 0;
   double initBal      = AccountInfoDouble(ACCOUNT_BALANCE) - netProfit;
   double netProfitPct = initBal > 0 ? netProfit / initBal * 100.0 : 0;

   double openPnL = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      openPnL += PositionGetDouble(POSITION_PROFIT)
               + PositionGetDouble(POSITION_SWAP);
   }

   double maxDDPct = initBal > 0 ? g_MaxDrawdown / initBal * 100.0 : 0;

   color netClr  = netProfit >= 0 ? clrLime : clrRed;
   color openClr = openPnL >= 0 ? clrLime : clrRed;
   color wrClr   = winRate >= 50 ? clrLime : clrRed;
   color pfClr   = profitFactor >= 1.5 ? clrLime : (profitFactor >= 1.0 ? clrYellow : clrRed);
   color ddClr   = maxDDPct <= 10 ? clrLime : (maxDDPct <= 20 ? clrYellow : clrRed);
   color rrClr   = avgRR >= 2 ? clrLime : (avgRR >= 1 ? clrYellow : clrRed);

   SetDashValue(1,  DoubleToString(netProfit, 2) + " (" + DoubleToString(netProfitPct, 1) + "%)", netClr);
   SetDashValue(2,  DoubleToString(openPnL, 2), openClr);
   SetDashValue(3,  DoubleToString(g_GrossProfit, 2), clrLime);
   SetDashValue(4,  DoubleToString(MathAbs(g_GrossLoss), 2), clrRed);
   SetDashValue(5,  IntegerToString(g_TotalTrades), clrWhite);
   SetDashValue(6,  IntegerToString(g_WinTrades) + " / " + IntegerToString(g_LossTrades), clrWhite);
   SetDashValue(7,  DoubleToString(winRate, 1) + "%", wrClr);
   SetDashValue(8,  DoubleToString(profitFactor, 2), pfClr);
   SetDashValue(9,  DoubleToString(avgWin, 2), clrLime);
   SetDashValue(10, DoubleToString(avgLoss, 2), clrRed);
   SetDashValue(11, DoubleToString(avgRR, 2), rrClr);
   SetDashValue(12, DoubleToString(g_MaxDrawdown, 2) + " (" + DoubleToString(maxDDPct, 1) + "%)", ddClr);

   string status = g_TradeState == 1 ? "LONG" : (g_TradeState == -1 ? "SHORT" : "FLAT");
   color  stClr  = g_TradeState == 1 ? clrLime : (g_TradeState == -1 ? clrRed : clrGray);
   SetDashValue(13, status, stClr);

   // ML probability row
   string mlStr = DoubleToString(g_MLProbBuy, 2) + " / " + DoubleToString(g_MLProbSell, 2);
   color  mlClr = g_MLReady ? clrAqua : clrGray;
   if(!g_MLReady) mlStr = "Not loaded";
   SetDashValue(14, mlStr, mlClr);

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
//| Calculate SuperTrend (manual ATR-based)                          |
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

   // Carry forward bands (don't widen against the trend)
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
      // Lower band: only allow it to move up
      if(lowerBand > g_PrevSTLower || g_PrevClose < g_PrevSTLower)
         g_STLowerBand = lowerBand;
      else
         g_STLowerBand = g_PrevSTLower;

      // Upper band: only allow it to move down
      if(upperBand < g_PrevSTUpper || g_PrevClose > g_PrevSTUpper)
         g_STUpperBand = upperBand;
      else
         g_STUpperBand = g_PrevSTUpper;

      // Direction
      if(g_PrevSTDir == 1)
         g_STDirection = closePrice < g_STLowerBand ? -1 : 1;
      else
         g_STDirection = closePrice > g_STUpperBand ? 1 : -1;

      g_SuperTrend = g_STDirection == 1 ? g_STLowerBand : g_STUpperBand;
   }

   g_PrevSTUpper = g_STUpperBand;
   g_PrevSTLower = g_STLowerBand;
   g_PrevSTDir   = g_STDirection;
}

//+------------------------------------------------------------------+
//| Calculate ADX (manual Wilder's method)                           |
//+------------------------------------------------------------------+
void CalcADX(double highPrice, double lowPrice, double closePrice)
{
   g_ADXBarCount++;

   if(g_ADXBarCount == 1)
      return;  // need previous bar

   // Directional Movement
   double plusDM  = highPrice - g_PrevHigh;
   double minusDM = g_PrevLow - lowPrice;
   if(plusDM < 0) plusDM = 0;
   if(minusDM < 0) minusDM = 0;
   if(plusDM > minusDM) minusDM = 0;
   else if(minusDM > plusDM) plusDM = 0;
   else { plusDM = 0; minusDM = 0; }

   // True Range
   double tr = MathMax(highPrice - lowPrice,
                MathMax(MathAbs(highPrice - g_PrevClose), MathAbs(lowPrice - g_PrevClose)));

   int n = InpADXPeriod;

   if(g_ADXBarCount <= n + 1)
   {
      // Accumulation phase
      g_SmoothedTR      += tr;
      g_SmoothedPlusDM  += plusDM;
      g_SmoothedMinusDM += minusDM;

      if(g_ADXBarCount == n + 1)
      {
         // First smoothed values
         g_PlusDI  = g_SmoothedTR > 0 ? (g_SmoothedPlusDM / g_SmoothedTR) * 100.0 : 0;
         g_MinusDI = g_SmoothedTR > 0 ? (g_SmoothedMinusDM / g_SmoothedTR) * 100.0 : 0;
         double diSum = g_PlusDI + g_MinusDI;
         double dx = diSum > 0 ? MathAbs(g_PlusDI - g_MinusDI) / diSum * 100.0 : 0;
         g_SmoothedDX = dx;
         g_ADX = dx;
         g_ADXInitialized = true;
      }
      return;
   }

   // Wilder smoothing: smoothed = prev - (prev/n) + current
   g_SmoothedTR      = g_SmoothedTR - (g_SmoothedTR / n) + tr;
   g_SmoothedPlusDM  = g_SmoothedPlusDM - (g_SmoothedPlusDM / n) + plusDM;
   g_SmoothedMinusDM = g_SmoothedMinusDM - (g_SmoothedMinusDM / n) + minusDM;

   g_PlusDI  = g_SmoothedTR > 0 ? (g_SmoothedPlusDM / g_SmoothedTR) * 100.0 : 0;
   g_MinusDI = g_SmoothedTR > 0 ? (g_SmoothedMinusDM / g_SmoothedTR) * 100.0 : 0;

   double diSum = g_PlusDI + g_MinusDI;
   double dx = diSum > 0 ? MathAbs(g_PlusDI - g_MinusDI) / diSum * 100.0 : 0;

   // ADX smoothing
   g_ADX = (g_SmoothedDX * (n - 1) + dx) / n;
   g_SmoothedDX = g_ADX;
}

//+------------------------------------------------------------------+
//| Compute ML feature vector (24 features matching Python model)    |
//+------------------------------------------------------------------+
void ComputeMLFeatures(double closePrice, double highPrice, double lowPrice)
{
   // Update additional indicators
   double k12 = 2.0 / 13.0;
   double k26 = 2.0 / 27.0;
   double k9  = 2.0 / 10.0;
   double k14 = 2.0 / 15.0;
   double k7  = 2.0 / 8.0;

   if(g_EMA12 == 0) g_EMA12 = closePrice;
   if(g_EMA26 == 0) g_EMA26 = closePrice;
   g_EMA12 = closePrice * k12 + g_EMA12 * (1.0 - k12);
   g_EMA26 = closePrice * k26 + g_EMA26 * (1.0 - k26);
   g_MACDLine = g_EMA12 - g_EMA26;
   g_MACDSignal = g_MACDLine * k9 + g_MACDSignal * (1.0 - k9);
   double macdHist = g_MACDLine - g_MACDSignal;

   // Simple RSI approximation using EMA
   static double prevClose = 0;
   static double avgGain14 = 0, avgLoss14 = 0;
   static double avgGain7 = 0, avgLoss7 = 0;
   if(prevClose > 0)
   {
      double change = closePrice - prevClose;
      double gain = change > 0 ? change : 0;
      double loss = change < 0 ? -change : 0;
      avgGain14 = avgGain14 * (13.0/14.0) + gain * (1.0/14.0);
      avgLoss14 = avgLoss14 * (13.0/14.0) + loss * (1.0/14.0);
      avgGain7 = avgGain7 * (6.0/7.0) + gain * (1.0/7.0);
      avgLoss7 = avgLoss7 * (6.0/7.0) + loss * (1.0/7.0);
      g_RSI14 = avgLoss14 > 0 ? 100.0 - 100.0/(1.0 + avgGain14/avgLoss14) : 50.0;
      g_RSI7 = avgLoss7 > 0 ? 100.0 - 100.0/(1.0 + avgGain7/avgLoss7) : 50.0;
   }
   prevClose = closePrice;

   // Bollinger Bands (20-period SMA + 2 std)
   static double closeBuf[20];
   static int bbIdx = 0;
   static bool bbFull = false;
   closeBuf[bbIdx] = closePrice;
   bbIdx = (bbIdx + 1) % 20;
   if(bbIdx == 0) bbFull = true;
   if(bbFull)
   {
      double sum = 0, sum2 = 0;
      for(int i = 0; i < 20; i++) { sum += closeBuf[i]; sum2 += closeBuf[i]*closeBuf[i]; }
      g_BB_SMA = sum / 20.0;
      double variance = sum2/20.0 - g_BB_SMA*g_BB_SMA;
      double std = variance > 0 ? MathSqrt(variance) : 0;
      g_BB_Upper = g_BB_SMA + 2.0*std;
      g_BB_Lower = g_BB_SMA - 2.0*std;
   }

   // Volume SMA 20
   static double volBuf[20];
   static int volIdx = 0;
   static bool volFull = false;
   double vol = (double)iVolume(_Symbol, PERIOD_CURRENT, 1);
   volBuf[volIdx] = vol;
   volIdx = (volIdx + 1) % 20;
   if(volIdx == 0) volFull = true;
   if(volFull)
   {
      double sum = 0;
      for(int i = 0; i < 20; i++) sum += volBuf[i];
      g_VolSMA20 = sum / 20.0;
   }

   // Price changes
   static double close1 = 0, close3 = 0, close5 = 0;
   static double closeHist[5];
   static int chIdx = 0;
   double priceChange1 = close1 > 0 ? (closePrice - close1) / close1 * 100.0 : 0;
   double priceChange3 = close3 > 0 ? (closePrice - close3) / close3 * 100.0 : 0;
   double priceChange5 = (chIdx >= 4 && closeHist[(chIdx+1)%5] > 0) ?
      (closePrice - closeHist[(chIdx+1)%5]) / closeHist[(chIdx+1)%5] * 100.0 : 0;
   close3 = (chIdx >= 2) ? closeHist[(chIdx+5-2)%5] : closePrice;
   close1 = closePrice;
   closeHist[chIdx % 5] = closePrice;
   chIdx++;

   // EMA touch tracking
   bool touched = (lowPrice <= g_EMA && highPrice >= g_EMA);
   if(touched)
      g_CandlesSinceTouch = 0;
   else
      g_CandlesSinceTouch++;

   // EMA slope (approximate using current vs 5 bars ago)
   static double ema5ago[5];
   static int emaSlIdx = 0;
   double emaSlope = (emaSlIdx >= 4 && ema5ago[(emaSlIdx+1)%5] > 0) ?
      (g_EMA - ema5ago[(emaSlIdx+1)%5]) / ema5ago[(emaSlIdx+1)%5] * 100.0 : 0;
   ema5ago[emaSlIdx % 5] = g_EMA;
   emaSlIdx++;

   // Build feature vector (must match FEATURE_NAMES order from Python)
   double bbWidth = g_BB_SMA > 0 ? (g_BB_Upper - g_BB_Lower) / g_BB_SMA : 0;
   double bbPct = (g_BB_Upper - g_BB_Lower) > 0 ?
      (closePrice - g_BB_Lower) / (g_BB_Upper - g_BB_Lower) : 0.5;
   double volRatio = g_VolSMA20 > 0 ? vol / g_VolSMA20 : 1.0;
   double atrPct = g_ATR > 0 ? g_ATR / closePrice * 100.0 : 0;

   g_MLFeatures[0]  = g_EMA > 0 ? (closePrice - g_EMA) / closePrice * 100.0 : 0; // ema200_dist
   g_MLFeatures[1]  = emaSlope;                                                     // ema_slope
   g_MLFeatures[2]  = g_RSI14;                                                      // rsi_14
   g_MLFeatures[3]  = g_RSI7;                                                       // rsi_7
   g_MLFeatures[4]  = atrPct;                                                       // atr_14_pct
   g_MLFeatures[5]  = g_ADX;                                                        // adx
   g_MLFeatures[6]  = g_PlusDI;                                                     // plus_di
   g_MLFeatures[7]  = g_MinusDI;                                                    // minus_di
   g_MLFeatures[8]  = g_PlusDI - g_MinusDI;                                         // di_diff
   g_MLFeatures[9]  = (double)g_STDirection;                                         // st_direction
   g_MLFeatures[10] = g_SuperTrend > 0 ? (closePrice - g_SuperTrend)/closePrice*100 : 0; // st_dist
   g_MLFeatures[11] = g_MACDLine;                                                   // macd
   g_MLFeatures[12] = g_MACDSignal;                                                 // macd_signal
   g_MLFeatures[13] = macdHist;                                                     // macd_hist
   g_MLFeatures[14] = bbWidth;                                                      // bb_width
   g_MLFeatures[15] = bbPct;                                                        // bb_pct
   g_MLFeatures[16] = volRatio;                                                     // vol_ratio
   g_MLFeatures[17] = priceChange1;                                                 // price_change_1
   g_MLFeatures[18] = priceChange3;                                                 // price_change_3
   g_MLFeatures[19] = priceChange5;                                                 // price_change_5
   g_MLFeatures[20] = closePrice > 0 ? (highPrice-lowPrice)/closePrice*100 : 0;     // high_low_range
   g_MLFeatures[21] = iOpen(_Symbol,PERIOD_CURRENT,1) > 0 ?
      (closePrice - iOpen(_Symbol,PERIOD_CURRENT,1))/iOpen(_Symbol,PERIOD_CURRENT,1)*100 : 0; // close_vs_open
   g_MLFeatures[22] = touched ? 1.0 : 0.0;                                          // ema_touch
   g_MLFeatures[23] = (double)g_CandlesSinceTouch;                                  // candles_since_touch
}

//+------------------------------------------------------------------+
//| Run ONNX inference and update g_MLProbBuy/g_MLProbSell           |
//+------------------------------------------------------------------+
void RunONNXInference()
{
   if(!g_MLReady || g_ONNXHandle == INVALID_HANDLE) return;

   // Prepare input (float32)
   float inputData[];
   ArrayResize(inputData, ML_FEATURES);
   for(int i = 0; i < ML_FEATURES; i++)
      inputData[i] = (float)g_MLFeatures[i];

   // Output buffers
   long   outputLabel[1];
   float  outputProbs[];
   ArrayResize(outputProbs, 2);

   // Run inference
   if(OnnxRun(g_ONNXHandle, 0, inputData, outputLabel, outputProbs))
   {
      g_MLProbBuy  = (double)outputProbs[1];  // index 1 = buy probability
      g_MLProbSell = (double)outputProbs[0];  // index 0 = sell probability
   }
   else
   {
      Print("ONNX inference failed, error: ", GetLastError());
      g_MLProbBuy  = 0.5;
      g_MLProbSell = 0.5;
   }
}
//+------------------------------------------------------------------+
