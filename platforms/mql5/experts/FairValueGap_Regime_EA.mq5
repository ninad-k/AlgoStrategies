//+------------------------------------------------------------------+
//| Core logic: Scan 3-candle Fair Value Gaps (imbalance zones), then |
//| enter on pullback into a fresh zone when HTF trend (EMA) and/or   |
//| ADX direction agree; size with fixed or risk-based lots; manage   |
//| trades with ATR/points SL-TP, partials, trail, BE, and DD limits. |
//| Author: Ninad K                                                   |
//+------------------------------------------------------------------+
#property copyright "Ninad K"
#property version   "1.00"
#property description "Fair Value Gap pullback EA with regime filter, ATR/points exits, and risk caps."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

CTrade         trade;
CPositionInfo  posInfo;

//--- How SL/TP distances are measured
enum ENUM_SL_TP_MODE
  {
   MODE_ATR    = 0,
   MODE_POINTS = 1
  };

//--- Which filters must pass before a signal is valid
enum ENUM_REGIME_FILTER
  {
   REGIME_NONE = 0,
   REGIME_EMA  = 1,
   REGIME_ADX  = 2,
   REGIME_BOTH = 3
  };

enum ENUM_LOT_MODE
  {
   LOT_FIXED = 0,
   LOT_RISK  = 1
  };

//--- Scale-out behaviour after entry
enum ENUM_PARTIAL_MODE
  {
   PARTIAL_OFF   = 0,
   PARTIAL_MIDTP = 1,
   PARTIAL_FIXED = 2
  };

//--- Preset higher timeframes for HTF EMA regime
enum ENUM_HTF
  {
   HTF_M15 = PERIOD_M15,
   HTF_M30 = PERIOD_M30,
   HTF_H1  = PERIOD_H1,
   HTF_H4  = PERIOD_H4,
   HTF_D1  = PERIOD_D1
  };

//--- One stored imbalance: price bounds, time span, state flags
struct FVGData
  {
   double    upper;
   double    lower;
   datetime  timeStart;
   datetime  timeEnd;
   int       barIndex;
   bool      isBullish;
   bool      isFilled;
   bool      isTraded;
  };

//--- Inputs: detection
input group              "=== FVG Detection ==="
input bool               InpShowBullish      = true;       // Trade Bullish FVGs
input bool               InpShowBearish      = true;       // Trade Bearish FVGs
input int                InpMinGapPoints     = 10;         // Minimum FVG Size (points)
input int                InpLookback         = 200;        // Lookback Bars for FVG Scan
input int                InpMaxFVGs          = 50;         // Max FVGs to Track

//--- Regime Filter
input group              "=== Regime Detection ==="
input ENUM_REGIME_FILTER InpRegimeFilter     = REGIME_BOTH;     // Regime Filter Type
input ENUM_HTF           InpHTF              = HTF_H4;           // Higher Timeframe for EMA
input int                InpEMAFast          = 50;               // Fast EMA Period (HTF)
input int                InpEMASlow          = 200;              // Slow EMA Period (HTF)
input int                InpADXPeriod        = 14;               // ADX Period
input double             InpADXMinStrength   = 20.0;            // Min ADX Value (trend strength)
input bool               InpHTFBiasRequired  = true;            // Require HTF EMA Alignment

//--- Stop Loss & Take Profit
input group              "=== Stop Loss ==="
input ENUM_SL_TP_MODE    InpSLMode           = MODE_ATR;    // SL Mode
input double             InpSLATRMult        = 1.5;         // SL ATR Multiplier
input int                InpSLPoints         = 150;         // SL Fixed Points
input int                InpATRPeriod        = 14;          // ATR Period

input group              "=== Take Profit ==="
input ENUM_SL_TP_MODE    InpTPMode           = MODE_ATR;    // TP Mode
input double             InpTPATRMult        = 3.0;         // TP ATR Multiplier
input int                InpTPPoints         = 300;         // TP Fixed Points

//--- Partial Close & Trailing
input group              "=== Partial Close & Trailing ==="
input ENUM_PARTIAL_MODE  InpPartialMode      = PARTIAL_MIDTP;  // Partial Close Mode
input double             InpPartialPercent   = 50.0;           // % to Close at Partial TP (1-99)
input double             InpPartialRR        = 1.0;            // Partial Close R:R Level
input bool               InpUseTrailing      = true;           // Enable Trailing Stop
input double             InpTrailATRMult     = 1.0;            // Trail ATR Multiplier
input int                InpTrailPoints      = 100;            // Trail Fixed Points (if SL=Points)
input bool               InpUseBreakEven     = true;           // Enable Break-Even Stop
input double             InpBEATRTrigger     = 1.0;            // Break-Even Trigger (ATR multiples from entry)
input int                InpBEPointsTrigger  = 100;            // Break-Even Trigger (Points, if SL=Points)
input int                InpBEBuffer         = 5;              // Break-Even Buffer Points (above/below entry)
input bool               InpConfirmCandle    = true;           // Require Confirmation Candle in FVG Zone
input int                InpMaxTradesPerDir  = 1;              // Max Open Trades Per Direction (1-3)

//--- Risk Management
input group              "=== Risk Management ==="
input ENUM_LOT_MODE      InpLotMode          = LOT_FIXED;  // Lot Sizing Mode
input double             InpFixedLot         = 0.10;       // Fixed Lot Size (if Fixed mode)
input double             InpRiskPercent      = 1.0;        // Risk Per Trade (%) (if Risk mode)
input double             InpMaxDailyDD       = 5.0;        // Max Daily Drawdown (%)
input double             InpMaxTotalDD       = 10.0;       // Max Total Drawdown (%)
input int                InpMaxOpenTrades    = 3;          // Max Simultaneous Trades
input int                InpMagicNumber      = 20250101;   // Magic Number
input string             InpTradeComment     = "FVG_Regime";  // Order comment tag

//--- Session Filter
input group              "=== Session Filter ==="
input bool               InpUseSessionFilter = false;      // Enable Session Filter
input int                InpSessionStartHour = 7;          // Session Start Hour (Server Time)
input int                InpSessionEndHour   = 20;         // Session End Hour (Server Time)

//--- Alerts
input group              "=== Alerts ==="
input bool               InpAlertEntry       = true;       // Alert on Entry
input bool               InpAlertExit        = false;      // Alert on Exit
input bool               InpPushNotify       = false;      // Push Notification

FVGData  g_fvgArray[];
int      g_fvgCount     = 0;
int      g_prevBars     = 0;
double   g_minGapSize   = 0;
double   g_startBalance = 0;
double   g_dailyStartBalance = 0;
datetime g_lastDayChecked    = 0;

int      h_ATR      = INVALID_HANDLE;
int      h_ADX      = INVALID_HANDLE;
int      h_EMAFast  = INVALID_HANDLE;
int      h_EMASlow  = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Bind magic, min gap size, drawdown baselines, create ATR/ADX/EMA   |
//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_FOK);

   g_minGapSize        = InpMinGapPoints * _Point;
   g_startBalance      = AccountInfoDouble(ACCOUNT_BALANCE);
   g_dailyStartBalance   = g_startBalance;
   g_lastDayChecked      = TimeCurrent();

   h_ATR = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   if(h_ATR == INVALID_HANDLE)
     {
      Print("ERROR: Failed to create ATR handle");
      return INIT_FAILED;
     }

   if(InpRegimeFilter == REGIME_ADX || InpRegimeFilter == REGIME_BOTH)
     {
      h_ADX = iADX(_Symbol, PERIOD_CURRENT, InpADXPeriod);
      if(h_ADX == INVALID_HANDLE)
        {
         Print("ERROR: Failed to create ADX handle");
         return INIT_FAILED;
        }
     }

   if(InpRegimeFilter == REGIME_EMA || InpRegimeFilter == REGIME_BOTH)
     {
      h_EMAFast = iMA(_Symbol, (ENUM_TIMEFRAMES)InpHTF, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
      h_EMASlow = iMA(_Symbol, (ENUM_TIMEFRAMES)InpHTF, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
      if(h_EMAFast == INVALID_HANDLE || h_EMASlow == INVALID_HANDLE)
        {
         Print("ERROR: Failed to create EMA handles");
         return INIT_FAILED;
        }
     }

   ArrayFree(g_fvgArray);
   g_fvgCount = 0;
   g_prevBars = 0;

   Print("FairValueGap_Regime_EA initialized | ", _Symbol, " | Magic ", InpMagicNumber);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Release handles and clear chart comment                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(h_ATR     != INVALID_HANDLE) IndicatorRelease(h_ATR);
   if(h_ADX     != INVALID_HANDLE) IndicatorRelease(h_ADX);
   if(h_EMAFast != INVALID_HANDLE) IndicatorRelease(h_EMAFast);
   if(h_EMASlow != INVALID_HANDLE) IndicatorRelease(h_EMASlow);
   Comment("");
  }

//+------------------------------------------------------------------+
//| Dashboard every tick; bar logic only on new bar                   |
//+------------------------------------------------------------------+
void OnTick()
  {
   UpdateDashboard();

   int bars = iBars(_Symbol, PERIOD_CURRENT);
   if(bars == g_prevBars)
      return;
   g_prevBars = bars;

   RefreshDailyBalance();

   if(IsDrawdownBreached())
      return;

   if(InpUseSessionFilter && !IsInSession())
      return;

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, 0, InpLookback + 5, rates);
   if(copied < 3) return;

   int ratesTotal = copied;

   ScanFVGs(rates, ratesTotal);
   UpdateFillStatus(rates, ratesTotal);
   ManageOpenPositions(rates);

   if(CountOpenTrades() < InpMaxOpenTrades)
      CheckFVGEntries(rates, ratesTotal);
  }

//+------------------------------------------------------------------+
//| Historical scan: 3-candle imbalance, size filter, dedupe by time   |
//+------------------------------------------------------------------+
void ScanFVGs(const MqlRates &rates[], int ratesTotal)
  {
   int startBar = MathMax(2, ratesTotal - InpLookback);
   int endBar   = ratesTotal - 2;

   for(int i = startBar; i <= endBar; i++)
     {
      if(InpShowBullish)
        {
         double gapLow  = rates[i - 2].high;
         double gapHigh = rates[i].low;

         if(gapHigh > gapLow && (gapHigh - gapLow) >= g_minGapSize)
           {
            if(!FVGExists(rates[i - 1].time, true))
               AddFVG(gapLow, gapHigh, rates[i - 1].time, rates[i].time, i, true);
           }
        }

      if(InpShowBearish)
        {
         double gapHigh = rates[i - 2].low;
         double gapLow  = rates[i].high;

         if(gapHigh > gapLow && (gapHigh - gapLow) >= g_minGapSize)
           {
            if(!FVGExists(rates[i - 1].time, false))
               AddFVG(gapLow, gapHigh, rates[i - 1].time, rates[i].time, i, false);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Last closed bar vs zone + regime + margin; one trade per zone flag |
//+------------------------------------------------------------------+
void CheckFVGEntries(const MqlRates &rates[], int ratesTotal)
  {
   if(ratesTotal < 2) return;

   MqlRates lastBar = rates[ratesTotal - 2];
   double   askPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double   bidPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double atr = GetATR();
   if(atr <= 0) return;

   for(int i = 0; i < g_fvgCount; i++)
     {
      if(g_fvgArray[i].isFilled) continue;
      if(g_fvgArray[i].isTraded) continue;

      if(g_fvgArray[i].isBullish && InpShowBullish)
        {
         bool priceInZone  = (lastBar.low <= g_fvgArray[i].upper &&
                              lastBar.low  >= g_fvgArray[i].lower - (g_fvgArray[i].upper - g_fvgArray[i].lower));
         bool bullishClose = !InpConfirmCandle || (lastBar.close > lastBar.open &&
                              lastBar.close >= g_fvgArray[i].lower);

         if(priceInZone && bullishClose && IsRegimeBullish() &&
            CountOpenTradesByDir(POSITION_TYPE_BUY) < InpMaxTradesPerDir)
           {
            double sl = CalculateSL(true, askPrice, atr);
            double tp = CalculateTP(true, askPrice, atr);
            double lots = CalculateLotSize(askPrice - sl);

            if(lots > 0 && sl > 0 && tp > 0 &&
               HasSufficientMargin(ORDER_TYPE_BUY, lots, askPrice))
              {
               if(trade.Buy(lots, _Symbol, askPrice, sl, tp, InpTradeComment))
                 {
                  g_fvgArray[i].isTraded = true;
                  string msg = "FVG_Regime BUY | " + _Symbol + " | Lots: " +
                               DoubleToString(lots, 2) + " | Zone: " +
                               DoubleToString(g_fvgArray[i].lower, _Digits) + "-" +
                               DoubleToString(g_fvgArray[i].upper, _Digits);
                  Print(msg);
                  if(InpAlertEntry) Alert(msg);
                  if(InpPushNotify) SendNotification(msg);
                 }
              }
           }
        }

      if(!g_fvgArray[i].isBullish && InpShowBearish)
        {
         bool priceInZone   = (lastBar.high >= g_fvgArray[i].lower &&
                               lastBar.high  <= g_fvgArray[i].upper + (g_fvgArray[i].upper - g_fvgArray[i].lower));
         bool bearishClose  = !InpConfirmCandle || (lastBar.close < lastBar.open &&
                               lastBar.close <= g_fvgArray[i].upper);

         if(priceInZone && bearishClose && IsRegimeBearish() &&
            CountOpenTradesByDir(POSITION_TYPE_SELL) < InpMaxTradesPerDir)
           {
            double sl = CalculateSL(false, bidPrice, atr);
            double tp = CalculateTP(false, bidPrice, atr);
            double lots = CalculateLotSize(sl - bidPrice);

            if(lots > 0 && sl > 0 && tp > 0 &&
               HasSufficientMargin(ORDER_TYPE_SELL, lots, bidPrice))
              {
               if(trade.Sell(lots, _Symbol, bidPrice, sl, tp, InpTradeComment))
                 {
                  g_fvgArray[i].isTraded = true;
                  string msg = "FVG_Regime SELL | " + _Symbol + " | Lots: " +
                               DoubleToString(lots, 2) + " | Zone: " +
                               DoubleToString(g_fvgArray[i].lower, _Digits) + "-" +
                               DoubleToString(g_fvgArray[i].upper, _Digits);
                  Print(msg);
                  if(InpAlertEntry) Alert(msg);
                  if(InpPushNotify) SendNotification(msg);
                 }
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| CHECK FREE MARGIN BEFORE ORDER PLACEMENT                         |
//+------------------------------------------------------------------+
bool HasSufficientMargin(ENUM_ORDER_TYPE orderType, double lots, double price)
  {
   double margin = 0;
   if(!OrderCalcMargin(orderType, _Symbol, lots, price, margin))
      return false;

   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);

   // Require at least 120% of margin needed (20% safety buffer)
   return (freeMargin >= margin * 1.2);
  }

//+------------------------------------------------------------------+
//| CALCULATE STOP LOSS PRICE                                         |
//+------------------------------------------------------------------+
double CalculateSL(bool isBuy, double entryPrice, double atr)
  {
   double slDist = 0;

   if(InpSLMode == MODE_ATR)
      slDist = atr * InpSLATRMult;
   else
      slDist = InpSLPoints * _Point;

   // Enforce broker minimum stop level + spread buffer
   long   stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double spread       = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   double minStop      = (stopLevelPts * _Point) + spread + _Point;
   slDist = MathMax(slDist, minStop);

   double sl = isBuy ? entryPrice - slDist : entryPrice + slDist;
   return NormalizeDouble(sl, _Digits);
  }

//+------------------------------------------------------------------+
//| CALCULATE TAKE PROFIT PRICE                                       |
//+------------------------------------------------------------------+
double CalculateTP(bool isBuy, double entryPrice, double atr)
  {
   double tpDist = 0;

   if(InpTPMode == MODE_ATR)
      tpDist = atr * InpTPATRMult;
   else
      tpDist = InpTPPoints * _Point;

   // TP must also clear the broker minimum stop level
   long   stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double spread       = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point;
   double minStop      = (stopLevelPts * _Point) + spread + _Point;
   tpDist = MathMax(tpDist, minStop);

   double tp = isBuy ? entryPrice + tpDist : entryPrice - tpDist;
   return NormalizeDouble(tp, _Digits);
  }

//+------------------------------------------------------------------+
//| CALCULATE LOT SIZE — Fixed or Risk-Based                         |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistance)
  {
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lots    = 0;

   if(InpLotMode == LOT_FIXED)
     {
      // Use the fixed lot directly — just normalize to broker constraints
      lots = InpFixedLot;
     }
   else // LOT_RISK
     {
      if(slDistance <= 0) return 0;

      double balance       = AccountInfoDouble(ACCOUNT_BALANCE);
      double riskAmount    = balance * InpRiskPercent / 100.0;
      double tickValue     = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize      = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

      if(tickValue <= 0 || tickSize <= 0) return 0;

      double valuePerPoint = tickValue / tickSize;
      lots = riskAmount / (slDistance * valuePerPoint);
     }

   // Normalize to broker constraints
   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   return NormalizeDouble(lots, 2);
  }

//+------------------------------------------------------------------+
//| MANAGE OPEN POSITIONS — Trailing & Partial Close                  |
//+------------------------------------------------------------------+
void ManageOpenPositions(const MqlRates &rates[])
  {
   double atr = GetATR();
   if(atr <= 0) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Magic() != InpMagicNumber) continue;
      if(posInfo.Symbol() != _Symbol) continue;

      double openPrice  = posInfo.PriceOpen();
      double currentSL  = posInfo.StopLoss();
      double currentTP  = posInfo.TakeProfit();
      double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      ulong  ticket     = posInfo.Ticket();
      ENUM_POSITION_TYPE posType = posInfo.PositionType();

      if(InpUseBreakEven)
         HandleBreakEven(ticket, posType, openPrice, currentSL,
                         currentBid, currentAsk, atr);

      if(InpPartialMode != PARTIAL_OFF)
         HandlePartialClose(ticket, posType, openPrice, currentSL, currentTP,
                            currentBid, currentAsk, atr);

      if(InpUseTrailing)
         HandleTrailingStop(ticket, posType, openPrice, currentSL,
                            currentBid, currentAsk, atr);
     }
  }

//+------------------------------------------------------------------+
//| PARTIAL CLOSE HANDLER                                             |
//+------------------------------------------------------------------+
void HandlePartialClose(ulong ticket, ENUM_POSITION_TYPE posType,
                        double openPrice, double sl, double tp,
                        double bid, double ask, double atr)
  {
   // Only close once — check if position volume is already at minimum
   double curVol  = posInfo.Volume();
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(curVol <= minLot + lotStep) return;

   double partialTrigger = 0;
   double slDist = MathAbs(openPrice - sl);

   if(InpPartialMode == PARTIAL_MIDTP)
     {
      // Trigger at 50% of TP distance
      double tpDist = MathAbs(tp - openPrice);
      partialTrigger = (posType == POSITION_TYPE_BUY)
                       ? openPrice + tpDist * 0.5
                       : openPrice - tpDist * 0.5;
     }
   else if(InpPartialMode == PARTIAL_FIXED)
     {
      partialTrigger = (posType == POSITION_TYPE_BUY)
                       ? openPrice + slDist * InpPartialRR
                       : openPrice - slDist * InpPartialRR;
     }

   bool triggered = (posType == POSITION_TYPE_BUY)
                    ? bid >= partialTrigger
                    : ask <= partialTrigger;

   if(triggered)
     {
      double closeVol = NormalizeDouble(curVol * (InpPartialPercent / 100.0), 2);
      double lotStep2 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      closeVol = MathFloor(closeVol / lotStep2) * lotStep2;
      closeVol = MathMax(minLot, closeVol);

      if(closeVol < curVol)
        {
         if(trade.PositionClosePartial(ticket, closeVol))
            Print("FVG_Regime: Partial close ", closeVol, " lots on ticket #", ticket);
        }
     }
  }

//+------------------------------------------------------------------+
//| BREAK-EVEN HANDLER                                               |
//+------------------------------------------------------------------+
void HandleBreakEven(ulong ticket, ENUM_POSITION_TYPE posType,
                     double openPrice, double currentSL,
                     double bid, double ask, double atr)
  {
   double beTriggerDist = (InpSLMode == MODE_ATR)
                          ? atr * InpBEATRTrigger
                          : InpBEPointsTrigger * _Point;

   double beBuffer = InpBEBuffer * _Point;
   double minStop  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

   if(posType == POSITION_TYPE_BUY)
     {
      double triggerPrice = openPrice + beTriggerDist;
      double beSL         = NormalizeDouble(openPrice + beBuffer, _Digits);

      // Only move SL to BE if: price has reached trigger AND current SL is still below entry
      if(bid >= triggerPrice && currentSL < openPrice)
        {
         beSL = MathMax(beSL, currentSL); // Never move SL backward
         if(beSL > currentSL + _Point && beSL < bid - minStop)
            trade.PositionModify(ticket, beSL, posInfo.TakeProfit());
        }
     }
   else if(posType == POSITION_TYPE_SELL)
     {
      double triggerPrice = openPrice - beTriggerDist;
      double beSL         = NormalizeDouble(openPrice - beBuffer, _Digits);

      if(ask <= triggerPrice && (currentSL > openPrice || currentSL == 0))
        {
         beSL = MathMin(beSL, currentSL == 0 ? beSL : currentSL);
         if((currentSL == 0 || beSL < currentSL - _Point) && beSL > ask + minStop)
            trade.PositionModify(ticket, beSL, posInfo.TakeProfit());
        }
     }
  }

//+------------------------------------------------------------------+
//| TRAILING STOP HANDLER                                             |
//+------------------------------------------------------------------+
void HandleTrailingStop(ulong ticket, ENUM_POSITION_TYPE posType,
                        double openPrice, double currentSL,
                        double bid, double ask, double atr)
  {
   double trailDist = (InpSLMode == MODE_ATR)
                      ? atr * InpTrailATRMult
                      : InpTrailPoints * _Point;

   double minStop = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   trailDist = MathMax(trailDist, minStop + _Point);

   double newSL = 0;

   if(posType == POSITION_TYPE_BUY)
     {
      newSL = NormalizeDouble(bid - trailDist, _Digits);
      // Only move SL up, and only if price has moved in profit
      if(newSL > currentSL + _Point && newSL < bid)
         trade.PositionModify(ticket, newSL, posInfo.TakeProfit());
     }
   else if(posType == POSITION_TYPE_SELL)
     {
      newSL = NormalizeDouble(ask + trailDist, _Digits);
      // Only move SL down
      if((currentSL == 0 || newSL < currentSL - _Point) && newSL > ask)
         trade.PositionModify(ticket, newSL, posInfo.TakeProfit());
     }
  }

//+------------------------------------------------------------------+
//| REGIME DETECTION — BULLISH                                        |
//+------------------------------------------------------------------+
bool IsRegimeBullish()
  {
   if(InpRegimeFilter == REGIME_NONE) return true;

   bool emaOK = true;
   bool adxOK = true;

   if(InpRegimeFilter == REGIME_EMA || InpRegimeFilter == REGIME_BOTH)
     {
      double emaFast[], emaSlow[];
      ArraySetAsSeries(emaFast, true);
      ArraySetAsSeries(emaSlow, true);

      if(CopyBuffer(h_EMAFast, 0, 0, 3, emaFast) < 1) return false;
      if(CopyBuffer(h_EMASlow, 0, 0, 3, emaSlow) < 1) return false;

      // Bullish: price above fast EMA, fast EMA above slow EMA
      double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      emaOK = (currentPrice > emaFast[0] && emaFast[0] > emaSlow[0]);
     }

   if(InpRegimeFilter == REGIME_ADX || InpRegimeFilter == REGIME_BOTH)
     {
      double adxVal[], diPlus[], diMinus[];
      ArraySetAsSeries(adxVal, true);
      ArraySetAsSeries(diPlus, true);
      ArraySetAsSeries(diMinus, true);

      if(CopyBuffer(h_ADX, 0, 0, 3, adxVal)   < 1) return false;
      if(CopyBuffer(h_ADX, 1, 0, 3, diPlus)   < 1) return false;
      if(CopyBuffer(h_ADX, 2, 0, 3, diMinus)  < 1) return false;

      // Bullish: ADX strong enough AND DI+ > DI-
      adxOK = (adxVal[0] >= InpADXMinStrength && diPlus[0] > diMinus[0]);
     }

   return (emaOK && adxOK);
  }

//+------------------------------------------------------------------+
//| REGIME DETECTION — BEARISH                                        |
//+------------------------------------------------------------------+
bool IsRegimeBearish()
  {
   if(InpRegimeFilter == REGIME_NONE) return true;

   bool emaOK = true;
   bool adxOK = true;

   if(InpRegimeFilter == REGIME_EMA || InpRegimeFilter == REGIME_BOTH)
     {
      double emaFast[], emaSlow[];
      ArraySetAsSeries(emaFast, true);
      ArraySetAsSeries(emaSlow, true);

      if(CopyBuffer(h_EMAFast, 0, 0, 3, emaFast) < 1) return false;
      if(CopyBuffer(h_EMASlow, 0, 0, 3, emaSlow) < 1) return false;

      // Bearish: price below fast EMA, fast EMA below slow EMA
      double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      emaOK = (currentPrice < emaFast[0] && emaFast[0] < emaSlow[0]);
     }

   if(InpRegimeFilter == REGIME_ADX || InpRegimeFilter == REGIME_BOTH)
     {
      double adxVal[], diPlus[], diMinus[];
      ArraySetAsSeries(adxVal, true);
      ArraySetAsSeries(diPlus, true);
      ArraySetAsSeries(diMinus, true);

      if(CopyBuffer(h_ADX, 0, 0, 3, adxVal)   < 1) return false;
      if(CopyBuffer(h_ADX, 1, 0, 3, diPlus)   < 1) return false;
      if(CopyBuffer(h_ADX, 2, 0, 3, diMinus)  < 1) return false;

      // Bearish: ADX strong enough AND DI- > DI+
      adxOK = (adxVal[0] >= InpADXMinStrength && diMinus[0] > diPlus[0]);
     }

   return (emaOK && adxOK);
  }

//+------------------------------------------------------------------+
//| UPDATE FILL STATUS FOR ALL FVGs                                   |
//+------------------------------------------------------------------+
void UpdateFillStatus(const MqlRates &rates[], int ratesTotal)
  {
   if(ratesTotal < 1) return;
   MqlRates latest = rates[ratesTotal - 1];

   for(int i = 0; i < g_fvgCount; i++)
     {
      if(g_fvgArray[i].isFilled) continue;

      if(g_fvgArray[i].isBullish)
        {
         // Bullish FVG filled when price drops into the zone
         if(latest.low <= g_fvgArray[i].upper && latest.low >= g_fvgArray[i].lower)
            g_fvgArray[i].isFilled = true;
         // Fully violated (price blew below the zone)
         else if(latest.low < g_fvgArray[i].lower)
            g_fvgArray[i].isFilled = true;
        }
      else
        {
         // Bearish FVG filled when price rises into the zone
         if(latest.high >= g_fvgArray[i].lower && latest.high <= g_fvgArray[i].upper)
            g_fvgArray[i].isFilled = true;
         else if(latest.high > g_fvgArray[i].upper)
            g_fvgArray[i].isFilled = true;
        }
     }
  }

//+------------------------------------------------------------------+
//| ADD A NEW FVG TO THE TRACKING ARRAY                               |
//+------------------------------------------------------------------+
void AddFVG(double lower, double upper, datetime tStart, datetime tEnd,
            int barIdx, bool bullish)
  {
   if(g_fvgCount >= InpMaxFVGs)
      RemoveOldestFVG();

   g_fvgCount++;
   ArrayResize(g_fvgArray, g_fvgCount, 20);

   int idx = g_fvgCount - 1;
   g_fvgArray[idx].upper     = upper;
   g_fvgArray[idx].lower     = lower;
   g_fvgArray[idx].timeStart = tStart;
   g_fvgArray[idx].timeEnd   = tEnd;
   g_fvgArray[idx].barIndex  = barIdx;
   g_fvgArray[idx].isBullish = bullish;
   g_fvgArray[idx].isFilled  = false;
   g_fvgArray[idx].isTraded  = false;
  }

//+------------------------------------------------------------------+
//| REMOVE OLDEST FVG FROM THE ARRAY                                  |
//+------------------------------------------------------------------+
void RemoveOldestFVG()
  {
   if(g_fvgCount <= 0) return;
   for(int i = 0; i < g_fvgCount - 1; i++)
      g_fvgArray[i] = g_fvgArray[i + 1];
   g_fvgCount--;
   ArrayResize(g_fvgArray, g_fvgCount, 20);
  }

//+------------------------------------------------------------------+
//| CHECK IF FVG ALREADY EXISTS (PREVENT DUPLICATES)                  |
//+------------------------------------------------------------------+
bool FVGExists(datetime tStart, bool bullish)
  {
   for(int i = 0; i < g_fvgCount; i++)
     {
      if(g_fvgArray[i].timeStart == tStart && g_fvgArray[i].isBullish == bullish)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| GET CURRENT ATR VALUE                                             |
//+------------------------------------------------------------------+
double GetATR()
  {
   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(h_ATR, 0, 1, 1, atrBuf) < 1) return 0;
   return atrBuf[0];
  }

//+------------------------------------------------------------------+
//| COUNT OPEN TRADES FOR THIS EA                                     |
//+------------------------------------------------------------------+
int CountOpenTrades()
  {
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      if(posInfo.SelectByIndex(i))
         if(posInfo.Magic() == InpMagicNumber && posInfo.Symbol() == _Symbol)
            count++;
     }
   return count;
  }

//+------------------------------------------------------------------+
//| COUNT OPEN TRADES BY DIRECTION FOR THIS EA                       |
//+------------------------------------------------------------------+
int CountOpenTradesByDir(ENUM_POSITION_TYPE dir)
  {
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      if(posInfo.SelectByIndex(i))
         if(posInfo.Magic() == InpMagicNumber && posInfo.Symbol() == _Symbol)
            if(posInfo.PositionType() == dir)
               count++;
     }
   return count;
  }

//+------------------------------------------------------------------+
//| SESSION FILTER CHECK                                              |
//+------------------------------------------------------------------+
bool IsInSession()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   return (now.hour >= InpSessionStartHour && now.hour < InpSessionEndHour);
  }

//+------------------------------------------------------------------+
//| DRAWDOWN PROTECTION                                               |
//+------------------------------------------------------------------+
void RefreshDailyBalance()
  {
   MqlDateTime today, lastCheck;
   TimeToStruct(TimeCurrent(), today);
   TimeToStruct(g_lastDayChecked, lastCheck);

   if(today.day != lastCheck.day)
     {
      g_dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      g_lastDayChecked    = TimeCurrent();
     }
  }

bool IsDrawdownBreached()
  {
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity         = AccountInfoDouble(ACCOUNT_EQUITY);

   // Daily drawdown check
   double dailyDD = (g_dailyStartBalance - equity) / g_dailyStartBalance * 100.0;
   if(dailyDD >= InpMaxDailyDD)
     {
      static datetime lastAlert = 0;
      if(TimeCurrent() - lastAlert > 3600)
        {
         Print("FVG_Regime: Daily drawdown limit reached (", DoubleToString(dailyDD, 2), "%)");
         lastAlert = TimeCurrent();
        }
      return true;
     }

   // Total drawdown check
   double totalDD = (g_startBalance - equity) / g_startBalance * 100.0;
   if(totalDD >= InpMaxTotalDD)
     {
      static datetime lastAlert2 = 0;
      if(TimeCurrent() - lastAlert2 > 3600)
        {
         Print("FVG_Regime: Total drawdown limit reached (", DoubleToString(totalDD, 2), "%)");
         lastAlert2 = TimeCurrent();
        }
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Corner comment: regime label, FVG count, open trades, balances     |
//+------------------------------------------------------------------+
void UpdateDashboard()
  {
   string regime = "UNKNOWN";
   if(InpRegimeFilter == REGIME_NONE)
      regime = "DISABLED";
   else
     {
      bool bull = IsRegimeBullish();
      bool bear = IsRegimeBearish();
      regime    = bull ? "BULLISH" : (bear ? "BEARISH" : "NEUTRAL / RANGING");
     }

   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dailyDD = 0.0;
   if(g_dailyStartBalance > 0.0)
      dailyDD = (g_dailyStartBalance - equity) / g_dailyStartBalance * 100.0;

   string info = "=== Fair Value Gap (Regime) ===\n" +
                 "Symbol : " + _Symbol + "  TF: " + EnumToString(Period()) + "\n" +
                 "FVGs tracked : " + IntegerToString(g_fvgCount) + "\n" +
                 "Open trades : " + IntegerToString(CountOpenTrades()) + "\n" +
                 "Regime : " + regime + "\n" +
                 "Balance : " + DoubleToString(balance, 2) + "\n" +
                 "Equity : " + DoubleToString(equity, 2) + "\n" +
                 "Daily DD : " + DoubleToString(dailyDD, 2) + "%";

   Comment(info);
  }
//+------------------------------------------------------------------+
