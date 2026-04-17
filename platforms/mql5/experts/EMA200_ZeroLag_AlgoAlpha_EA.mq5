//+------------------------------------------------------------------+
//|                                  EMA200_ZeroLag_AlgoAlpha_EA.mq5 |
//|                                                    AlgoStrategies |
//|  EMA200 filter + AlgoAlpha-style Zero Lag channel (ATR bands).  |
//|  Optional dashboard gate: when enabled in Trading Dashboard API, |
//|  entry orders are sent; otherwise only MT5 alerts fire.           |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.12"
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

input double InpLots               = 0.10;      // Trade volume
input int    InpEMAPeriod          = 200;       // EMA filter period
input int    InpZLLength           = 70;        // Zero Lag length (same as Pine length)
input double InpBandMultiplier     = 1.2;       // Band multiplier
input bool   InpUseTrendFlipSignal = false;     // false = Bullish/Bearish Entry, true = Trend flip
input ulong  InpMagicNumber        = 260403;    // Magic number
input int    InpStopLossPoints     = 0;         // 0 = disabled
input int    InpTakeProfitPoints   = 0;         // 0 = disabled
input bool   InpAllowLong          = true;      // Allow buy trades
input bool   InpAllowShort         = true;      // Allow sell trades
input int    InpSlippagePoints     = 20;        // Max slippage in points
input int    InpBarsToCalculate    = 1500;      // Historical bars for signal calculation

input group    "=== Dashboard live execution (Trading Dashboard API) ==="
input bool     InpUseDashboardForExecution = true;   // false = always send orders (no HTTP)
input string   InpDashboardBaseUrl       = "http://127.0.0.1:8000"; // API root (no trailing slash)
input string   InpExecutionSecret        = "";     // Same as server MT5_EXECUTION_SECRET
input int      InpDashboardTimeoutMs     = 8000;   // WebRequest timeout (ms)

int      atrHandle   = INVALID_HANDLE;
int      emaHandle   = INVALID_HANDLE;
datetime lastBarTime = 0;

//+------------------------------------------------------------------+
string NormalizeBaseUrl(const string base)
{
   string s = base;
   int len = (int)StringLen(s);
   while(len > 0)
   {
      ushort c = StringGetCharacter(s, len - 1);
      if(c == '/' || c == '\\')
      {
         s = StringSubstr(s, 0, len - 1);
         len = (int)StringLen(s);
      }
      else
         break;
   }
   return s;
}

//+------------------------------------------------------------------+
string TfName(void)
{
   return EnumToString(_Period);
}

//+------------------------------------------------------------------+
bool ParseLiveTradingJson(const string json, bool &outEnabled)
{
   string compact = json;
   StringReplace(compact, " ", "");
   StringReplace(compact, "\r", "");
   StringReplace(compact, "\n", "");
   StringReplace(compact, "\t", "");
   if(StringFind(compact, "\"live_trading_enabled\":true") >= 0)
   {
      outEnabled = true;
      return true;
   }
   if(StringFind(compact, "\"live_trading_enabled\":false") >= 0)
   {
      outEnabled = false;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool FetchDashboardLiveTrading(bool &liveOut)
{
   liveOut = false;
   if(!InpUseDashboardForExecution)
   {
      liveOut = true;
      return true;
   }
   if(StringLen(InpExecutionSecret) == 0 || StringLen(InpDashboardBaseUrl) == 0)
   {
      Print("EMA200+ZL: InpExecutionSecret or InpDashboardBaseUrl empty — alert-only (no orders).");
      return false;
   }
   string url = NormalizeBaseUrl(InpDashboardBaseUrl) + "/api/v1/execution/mt5/live-trading";
   string headers = "X-MT5-Token: " + InpExecutionSecret + "\r\n";
   char   post[];
   char   result[];
   string result_headers;
   ResetLastError();
   int code = WebRequest("GET", url, headers, InpDashboardTimeoutMs, post, result, result_headers);
   if(code == -1)
   {
      int err = GetLastError();
      Print("EMA200+ZL: WebRequest failed (", err, "). Add URL in Tools → Options → Expert Advisors → WebRequest: ", url);
      return false;
   }
   string body = CharArrayToString(result);
   if(!ParseLiveTradingJson(body, liveOut))
   {
      Print("EMA200+ZL: unexpected JSON from dashboard: ", StringSubstr(body, 0, 200));
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
void HandleBuyEntrySignal(void)
{
   bool live = false;
   bool ok = FetchDashboardLiveTrading(live);
   if(!ok)
   {
      Alert(_Symbol, " ", TfName(), ": BUY signal — dashboard unreachable or misconfigured. No order sent.");
      return;
   }
   if(live)
   {
      Alert(_Symbol, " ", TfName(), ": BUY signal — live trading ON (dashboard). Sending order.");
      OpenBuy();
   }
   else
   {
      Alert(_Symbol, " ", TfName(), ": BUY signal — live trading OFF on dashboard. No order (manual only).");
   }
}

//+------------------------------------------------------------------+
void HandleSellEntrySignal(void)
{
   bool live = false;
   bool ok = FetchDashboardLiveTrading(live);
   if(!ok)
   {
      Alert(_Symbol, " ", TfName(), ": SELL signal — dashboard unreachable or misconfigured. No order sent.");
      return;
   }
   if(live)
   {
      Alert(_Symbol, " ", TfName(), ": SELL signal — live trading ON (dashboard). Sending order.");
      OpenSell();
   }
   else
   {
      Alert(_Symbol, " ", TfName(), ": SELL signal — live trading OFF on dashboard. No order (manual only).");
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   atrHandle = iATR(_Symbol, _Period, InpZLLength);
   emaHandle = iMA(_Symbol, _Period, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(atrHandle == INVALID_HANDLE || emaHandle == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles.");
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippagePoints);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(atrHandle != INVALID_HANDLE)
      IndicatorRelease(atrHandle);

   if(emaHandle != INVALID_HANDLE)
      IndicatorRelease(emaHandle);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!IsNewBar())
      return;

   bool   buyEntry   = false;
   bool   sellEntry  = false;
   bool   buyExit    = false;
   bool   sellExit   = false;
   double signalClose = 0.0;
   double ema200Value = 0.0;

   if(!GetStrategySignals(buyEntry, sellEntry, buyExit, sellExit, signalClose, ema200Value))
      return;

   int posType = GetOpenPositionType();

   if(posType == POSITION_TYPE_BUY && buyExit)
   {
      if(!ClosePositions(POSITION_TYPE_BUY))
         return;
      posType = GetOpenPositionType();
   }
   else if(posType == POSITION_TYPE_SELL && sellExit)
   {
      if(!ClosePositions(POSITION_TYPE_SELL))
         return;
      posType = GetOpenPositionType();
   }

   if(posType == -1)
   {
      if(buyEntry && InpAllowLong)
         HandleBuyEntrySignal();
      else if(sellEntry && InpAllowShort)
         HandleSellEntrySignal();
   }
}

//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime t[1];

   if(CopyTime(_Symbol, _Period, 0, 1, t) != 1)
      return(false);

   if(t[0] != lastBarTime)
   {
      lastBarTime = t[0];
      return(true);
   }

   return(false);
}

//+------------------------------------------------------------------+
double NormalizeVolume(const double volume)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double lots = MathMax(minLot, MathMin(maxLot, volume));

   if(lotStep > 0.0)
      lots = MathFloor(lots / lotStep) * lotStep;

   return(NormalizeDouble(lots, 8));
}

//+------------------------------------------------------------------+
int GetOpenPositionType()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      ulong  magic  = (ulong)PositionGetInteger(POSITION_MAGIC);

      if(symbol == _Symbol && magic == InpMagicNumber)
         return((int)PositionGetInteger(POSITION_TYPE));
   }

   return(-1);
}

//+------------------------------------------------------------------+
bool ClosePositions(const int typeToClose = -1)
{
   bool allClosed = true;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long   type   = PositionGetInteger(POSITION_TYPE);
      ulong  magic  = (ulong)PositionGetInteger(POSITION_MAGIC);

      if(symbol == _Symbol && magic == InpMagicNumber && (typeToClose < 0 || type == typeToClose))
      {
         if(!trade.PositionClose(ticket, InpSlippagePoints))
         {
            Print("Failed to close ticket ", ticket, ". Retcode: ", trade.ResultRetcode());
            allClosed = false;
         }
      }
   }

   return(allClosed);
}

//+------------------------------------------------------------------+
bool OpenBuy()
{
   double lots = NormalizeVolume(InpLots);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   if(ask <= 0.0)
      return(false);

   double sl = 0.0;
   double tp = 0.0;

   if(InpStopLossPoints > 0)
      sl = NormalizeDouble(ask - InpStopLossPoints * _Point, _Digits);

   if(InpTakeProfitPoints > 0)
      tp = NormalizeDouble(ask + InpTakeProfitPoints * _Point, _Digits);

   bool sent = trade.Buy(lots, _Symbol, 0.0, sl, tp, "EMA200 + ZeroLag Buy");

   if(!sent)
      Print("Buy order failed. Retcode: ", trade.ResultRetcode());

   return(sent);
}

//+------------------------------------------------------------------+
bool OpenSell()
{
   double lots = NormalizeVolume(InpLots);
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(bid <= 0.0)
      return(false);

   double sl = 0.0;
   double tp = 0.0;

   if(InpStopLossPoints > 0)
      sl = NormalizeDouble(bid + InpStopLossPoints * _Point, _Digits);

   if(InpTakeProfitPoints > 0)
      tp = NormalizeDouble(bid - InpTakeProfitPoints * _Point, _Digits);

   bool sent = trade.Sell(lots, _Symbol, 0.0, sl, tp, "EMA200 + ZeroLag Sell");

   if(!sent)
      Print("Sell order failed. Retcode: ", trade.ResultRetcode());

   return(sent);
}

//+------------------------------------------------------------------+
//| Entry: base ZL signal AND close vs EMA200 (same side).            |
//| Exit:  mirror opposite entry — close long iff short entry, etc.   |
//|        (no base-only exits without the EMA200 filter).            |
//+------------------------------------------------------------------+
bool GetStrategySignals(bool &buyEntry,
                        bool &sellEntry,
                        bool &buyExit,
                        bool &sellExit,
                        double &signalClose,
                        double &ema200Value)
{
   buyEntry    = false;
   sellEntry   = false;
   buyExit     = false;
   sellExit    = false;
   signalClose = 0.0;
   ema200Value = 0.0;

   if(InpZLLength < 2)
   {
      Print("InpZLLength must be at least 2.");
      return(false);
   }

   const int lag           = (InpZLLength - 1) / 2;
   const int window        = InpZLLength * 3;
   const int minBarsNeeded = MathMax(InpEMAPeriod + 10, window + lag + InpZLLength + 20);
   int barsToCopy          = MathMax(InpBarsToCalculate, minBarsNeeded + 100);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copiedRates = CopyRates(_Symbol, _Period, 0, barsToCopy, rates);
   if(copiedRates <= minBarsNeeded)
   {
      Print("Not enough price bars to calculate the strategy.");
      return(false);
   }

   double atr[];
   ArraySetAsSeries(atr, true);
   int copiedAtr = CopyBuffer(atrHandle, 0, 0, copiedRates, atr);
   if(copiedAtr <= minBarsNeeded)
   {
      Print("Not enough ATR data to calculate the strategy.");
      return(false);
   }

   int copied = MathMin(copiedRates, copiedAtr);
   if(copied <= minBarsNeeded)
      return(false);

   double ema200[];
   ArraySetAsSeries(ema200, true);
   if(CopyBuffer(emaHandle, 0, 0, 3, ema200) < 3)
   {
      Print("Could not read EMA values.");
      return(false);
   }

   signalClose = rates[1].close;
   ema200Value = ema200[1];

   int oldest = copied - 1 - MathMax(lag, window - 1);
   if(oldest < 3)
      return(false);

   double adjusted[];
   double zlema[];
   double volatility[];
   int    trend[];

   ArrayResize(adjusted, copied);
   ArrayResize(zlema, copied);
   ArrayResize(volatility, copied);
   ArrayResize(trend, copied);
   ArrayInitialize(trend, 0);

   const double alpha = 2.0 / (InpZLLength + 1.0);

   for(int i = oldest; i >= 0; --i)
      adjusted[i] = rates[i].close + (rates[i].close - rates[i + lag].close);

   zlema[oldest] = adjusted[oldest];
   for(int i = oldest - 1; i >= 0; --i)
      zlema[i] = alpha * adjusted[i] + (1.0 - alpha) * zlema[i + 1];

   for(int i = oldest; i >= 0; --i)
   {
      double highestAtr = atr[i];
      for(int j = i; j < i + window; ++j)
      {
         if(j < copied && atr[j] > highestAtr)
            highestAtr = atr[j];
      }
      volatility[i] = highestAtr * InpBandMultiplier;
   }

   trend[oldest] = 0;
   for(int i = oldest - 1; i >= 0; --i)
   {
      trend[i] = trend[i + 1];

      double upperNow  = zlema[i]     + volatility[i];
      double upperPrev = zlema[i + 1] + volatility[i + 1];
      double lowerNow  = zlema[i]     - volatility[i];
      double lowerPrev = zlema[i + 1] - volatility[i + 1];

      bool crossUpper = (rates[i].close > upperNow  && rates[i + 1].close <= upperPrev);
      bool crossLower = (rates[i].close < lowerNow  && rates[i + 1].close >= lowerPrev);

      if(crossUpper)
         trend[i] = 1;
      if(crossLower)
         trend[i] = -1;
   }

   const int bar = 1;

   bool bullishEntry = (rates[bar].close > zlema[bar] &&
                        rates[bar + 1].close <= zlema[bar + 1] &&
                        trend[bar] == 1 &&
                        trend[bar + 1] == 1);

   bool bearishEntry = (rates[bar].close < zlema[bar] &&
                        rates[bar + 1].close >= zlema[bar + 1] &&
                        trend[bar] == -1 &&
                        trend[bar + 1] == -1);

   bool bullishTrendFlip = (trend[bar] == 1  && trend[bar + 1] <= 0);
   bool bearishTrendFlip = (trend[bar] == -1 && trend[bar + 1] >= 0);

   bool baseBuySignal  = InpUseTrendFlipSignal ? bullishTrendFlip : bullishEntry;
   bool baseSellSignal = InpUseTrendFlipSignal ? bearishTrendFlip : bearishEntry;

   buyEntry  = (baseBuySignal  && rates[bar].close > ema200Value);
   sellEntry = (baseSellSignal && rates[bar].close < ema200Value);

   // Symmetric with entries: exit long only on full short-entry setup, exit short only on full long-entry setup.
   buyExit   = sellEntry;
   sellExit  = buyEntry;

   return(true);
}
