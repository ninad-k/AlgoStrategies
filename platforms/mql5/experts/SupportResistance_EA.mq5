//+------------------------------------------------------------------+
//|                                         SupportResistance_EA.mq5 |
//|                                         Ninad Sanjay Kulkarni    |
//+------------------------------------------------------------------+
#property copyright "Ninad Sanjay Kulkarni"
#property link      ""
#property version   "1.00"
#property strict
#property description "Support & Resistance reversal + breakout EA (EUR/USD H1 reference)"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Support & Resistance
input group "=========== SUPPORT & RESISTANCE ==========="
input int    InpLookback         = 50;
input int    InpZoneBuffer       = 8;
input bool   InpUseSwingSR       = true;
input int    InpSwingLeftRight   = 5;
input bool   InpShowSRLines      = true;

//--- RSI
input group "=========== RSI SETTINGS ==========="
input int    InpRSIPeriod        = 14;
input double InpRSIOversold      = 30;
input double InpRSIOverbought    = 70;

//--- Candlestick patterns
input group "=========== PATTERN SETTINGS ==========="
input bool   InpUseEngulfing     = true;
input bool   InpUsePinBar        = true;
input double InpPinBarRatio      = 2.0;
input double InpPinBarMaxBody    = 0.3;

//--- Reversal trade settings
input group "=========== REVERSAL TRADES ==========="
input bool   InpTradeReversal    = true;
input double InpRevStopLoss      = 20.0;
input double InpRevTakeProfit    = 0.0;   // 0 = use Risk:Reward
input double InpRevRiskReward    = 2.0;

//--- Breakout trade settings
input group "=========== BREAKOUT TRADES ==========="
input bool   InpTradeBreakout    = true;
input int    InpBreakoutBars     = 5;
input double InpBreakStopLoss    = 15.0;
input double InpBreakRiskReward  = 2.0;

//--- Risk management
input group "=========== RISK MANAGEMENT ==========="
input double InpLotSize          = 0.1;
input int    InpMaxTrades        = 1;
input ulong  InpMagicNumber      = 123456;

//--- General
input group "=========== GENERAL SETTINGS ==========="
input string InpTradeComment     = "SR_Strat";
input int    InpSlippage         = 10;

//--- Globals
CTrade         trade;
CPositionInfo  positionInfo;
CSymbolInfo    symbolInfo;

int            rsiHandle;
double         supportLevel = 0;
double         resistanceLevel = 0;
datetime       lastBarTime = 0;

// Breakout retest tracking: breakoutStartBar == -1 means inactive
int            breakoutStartBar = -1;
int            breakoutType = -1;          // 1 = buy breakout, -1 = sell breakout
double         breakoutLevel = 0;

string         objSupport        = "SR_Support";
string         objResistance     = "SR_Resistance";
string         objSupportZone    = "SR_SupportZone";
string         objResistanceZone = "SR_ResistanceZone";
string         objPanel          = "SR_Panel";

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!symbolInfo.Name(_Symbol))
   {
      Print("Error initializing symbol info");
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFilling(GetFillingMode());
   trade.SetMarginMode();

   rsiHandle = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
   if(rsiHandle == INVALID_HANDLE)
   {
      Print("Error creating RSI indicator: ", GetLastError());
      return(INIT_FAILED);
   }

   DetectSupportResistance();

   if(InpShowSRLines)
      CreateChartObjects();

   Print("SupportResistance EA initialized | ",
         "Symbol: ", _Symbol,
         " | Support: ", DoubleToString(supportLevel, _Digits),
         " | Resistance: ", DoubleToString(resistanceLevel, _Digits),
         " | Pip: ", DoubleToString(GetPipValue(), _Digits));

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(rsiHandle != INVALID_HANDLE)
      IndicatorRelease(rsiHandle);

   DeleteChartObjects();
   breakoutStartBar = -1;

   Print("EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   Comment(StringFormat("Equity %.2f | Balance %.2f",
                         AccountInfoDouble(ACCOUNT_EQUITY),
                         AccountInfoDouble(ACCOUNT_BALANCE)));

   if(!symbolInfo.RefreshRates())
      return;

   // Process once per completed bar
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime)
      return;
   lastBarTime = currentBarTime;

   DetectSupportResistance();

   if(InpShowSRLines)
      UpdateChartObjects();

   if(CountOpenTrades() >= InpMaxTrades)
      return;

   double bid = symbolInfo.Bid();
   double ask = symbolInfo.Ask();
   double rsiValue = GetRSIValue(1);

   double pipValue = GetPipValue();
   double buffer   = InpZoneBuffer * pipValue;

   double supportUpper    = supportLevel + buffer;
   double supportLower    = supportLevel - buffer;
   double resistanceUpper = resistanceLevel + buffer;
   double resistanceLower = resistanceLevel - buffer;

   // Last completed bar
   double prevOpen  = iOpen (_Symbol, PERIOD_CURRENT, 1);
   double prevHigh  = iHigh (_Symbol, PERIOD_CURRENT, 1);
   double prevLow   = iLow  (_Symbol, PERIOD_CURRENT, 1);
   double prevClose = iClose(_Symbol, PERIOD_CURRENT, 1);

   // Prior completed bar (for engulfing + breakout detection)
   double prev2Open  = iOpen (_Symbol, PERIOD_CURRENT, 2);
   double prev2Close = iClose(_Symbol, PERIOD_CURRENT, 2);

   bool bullishPattern = false;
   bool bearishPattern = false;

   if(InpUseEngulfing && InpUsePinBar)
   {
      bullishPattern = IsBullishEngulfing(prevOpen, prevClose, prev2Open, prev2Close)
                    || IsBullishPinBar  (prevOpen, prevHigh, prevLow, prevClose);
      bearishPattern = IsBearishEngulfing(prevOpen, prevClose, prev2Open, prev2Close)
                    || IsBearishPinBar  (prevOpen, prevHigh, prevLow, prevClose);
   }
   else if(InpUseEngulfing)
   {
      bullishPattern = IsBullishEngulfing(prevOpen, prevClose, prev2Open, prev2Close);
      bearishPattern = IsBearishEngulfing(prevOpen, prevClose, prev2Open, prev2Close);
   }
   else if(InpUsePinBar)
   {
      bullishPattern = IsBullishPinBar(prevOpen, prevHigh, prevLow, prevClose);
      bearishPattern = IsBearishPinBar(prevOpen, prevHigh, prevLow, prevClose);
   }

   //--- Reversal trades (blocked while a breakout retest is pending)
   if(InpTradeReversal && breakoutStartBar == -1)
   {
      if(prevLow <= supportUpper && prevLow >= supportLower)
      {
         if(rsiValue < InpRSIOversold && bullishPattern)
         {
            double sl = NormalizeDouble(supportLevel - InpRevStopLoss * pipValue, _Digits);
            double tp = CalculateTakeProfit(ask, sl, InpRevTakeProfit, InpRevRiskReward, true);

            if(ExecuteBuy(sl, tp, "Rev Buy"))
            {
               Print("Reversal BUY triggered at support zone");
               breakoutStartBar = -1;
            }
         }
      }

      if(prevHigh >= resistanceLower && prevHigh <= resistanceUpper)
      {
         if(rsiValue > InpRSIOverbought && bearishPattern)
         {
            double sl = NormalizeDouble(resistanceLevel + InpRevStopLoss * pipValue, _Digits);
            double tp = CalculateTakeProfit(bid, sl, InpRevTakeProfit, InpRevRiskReward, false);

            if(ExecuteSell(sl, tp, "Rev Sell"))
            {
               Print("Reversal SELL triggered at resistance zone");
               breakoutStartBar = -1;
            }
         }
      }
   }

   //--- Breakout trades (close beyond level, then wait for retest confirmation)
   if(InpTradeBreakout)
   {
      if(prevClose > resistanceLevel && prev2Close <= resistanceLevel)
      {
         breakoutStartBar = 1;
         breakoutType     = 1;
         breakoutLevel    = resistanceLevel;
         Print("Breakout BUY detected - waiting for retest");
      }

      if(prevClose < supportLevel && prev2Close >= supportLevel)
      {
         breakoutStartBar = 1;
         breakoutType     = -1;
         breakoutLevel    = supportLevel;
         Print("Breakout SELL detected - waiting for retest");
      }

      if(breakoutStartBar > 0)
      {
         if(breakoutStartBar > InpBreakoutBars)
         {
            Print("Breakout retest timeout - cancelled");
            breakoutStartBar = -1;
            breakoutType     = -1;
         }
         else
         {
            breakoutStartBar++;
            double breakBuffer = buffer * 1.5;

            if(breakoutType == 1)
            {
               // Retest from above: prior bar low dipped into the broken level
               if(prevLow <= breakoutLevel + breakBuffer && prevLow >= breakoutLevel - buffer)
               {
                  if(bullishPattern || (prevClose > prevOpen && prevClose > (prevHigh + prevLow) / 2))
                  {
                     double sl = NormalizeDouble(prevLow - InpBreakStopLoss * pipValue, _Digits);
                     double tp = CalculateTakeProfit(ask, sl, 0, InpBreakRiskReward, true);

                     if(ExecuteBuy(sl, tp, "Brk Buy"))
                     {
                        Print("Breakout BUY confirmed on retest");
                        breakoutStartBar = -1;
                        breakoutType     = -1;
                     }
                  }
               }
            }

            if(breakoutType == -1)
            {
               // Retest from below: prior bar high rose into the broken level
               if(prevHigh >= breakoutLevel - breakBuffer && prevHigh <= breakoutLevel + buffer)
               {
                  if(bearishPattern || (prevClose < prevOpen && prevClose < (prevHigh + prevLow) / 2))
                  {
                     double sl = NormalizeDouble(prevHigh + InpBreakStopLoss * pipValue, _Digits);
                     double tp = CalculateTakeProfit(bid, sl, 0, InpBreakRiskReward, false);

                     if(ExecuteSell(sl, tp, "Brk Sell"))
                     {
                        Print("Breakout SELL confirmed on retest");
                        breakoutStartBar = -1;
                        breakoutType     = -1;
                     }
                  }
               }
            }
         }
      }
   }

   UpdateInfoPanel(rsiValue, bid);
}

//+------------------------------------------------------------------+
//| Detect S/R (dispatch)                                            |
//+------------------------------------------------------------------+
void DetectSupportResistance()
{
   if(InpUseSwingSR)
   {
      DetectSwingSR();
   }
   else
   {
      int highestIdx = iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, InpLookback, 1);
      int lowestIdx  = iLowest (_Symbol, PERIOD_CURRENT, MODE_LOW,  InpLookback, 1);

      resistanceLevel = iHigh(_Symbol, PERIOD_CURRENT, highestIdx);
      supportLevel    = iLow (_Symbol, PERIOD_CURRENT, lowestIdx);
   }

   supportLevel    = NormalizeDouble(supportLevel,    _Digits);
   resistanceLevel = NormalizeDouble(resistanceLevel, _Digits);
}

//+------------------------------------------------------------------+
//| Swing High / Swing Low S/R                                       |
//+------------------------------------------------------------------+
void DetectSwingSR()
{
   double highestHigh = 0;
   double lowestLow   = DBL_MAX;
   int    swingBars   = InpSwingLeftRight;

   for(int i = swingBars; i <= InpLookback - swingBars; i++)
   {
      double high = iHigh(_Symbol, PERIOD_CURRENT, i);
      double low  = iLow (_Symbol, PERIOD_CURRENT, i);

      bool isSwingHigh = true;
      bool isSwingLow  = true;

      for(int j = 1; j <= swingBars; j++)
      {
         if(high <= iHigh(_Symbol, PERIOD_CURRENT, i - j)
         || high <= iHigh(_Symbol, PERIOD_CURRENT, i + j))
            isSwingHigh = false;

         if(low >= iLow(_Symbol, PERIOD_CURRENT, i - j)
         || low >= iLow(_Symbol, PERIOD_CURRENT, i + j))
            isSwingLow = false;
      }

      if(isSwingHigh && high > highestHigh) highestHigh = high;
      if(isSwingLow  && low  < lowestLow)   lowestLow   = low;
   }

   if(highestHigh > 0)        resistanceLevel = highestHigh;
   if(lowestLow  < DBL_MAX)   supportLevel    = lowestLow;
}

//+------------------------------------------------------------------+
//| RSI value for a specific bar                                     |
//+------------------------------------------------------------------+
double GetRSIValue(int bar)
{
   double rsiBuffer[];
   ArraySetAsSeries(rsiBuffer, true);

   if(CopyBuffer(rsiHandle, 0, bar, 1, rsiBuffer) <= 0)
   {
      Print("Error copying RSI buffer: ", GetLastError());
      return 50.0;
   }
   return rsiBuffer[0];
}

//+------------------------------------------------------------------+
//| Pattern detection                                                |
//+------------------------------------------------------------------+
bool IsBullishEngulfing(double currOpen, double currClose,
                        double prevOpen, double prevClose)
{
   if(currClose <= currOpen) return false;   // current must be bullish
   if(prevClose >= prevOpen) return false;   // previous must be bearish
   return (currOpen <= prevClose && currClose >= prevOpen);
}

bool IsBearishEngulfing(double currOpen, double currClose,
                        double prevOpen, double prevClose)
{
   if(currClose >= currOpen) return false;   // current must be bearish
   if(prevClose <= prevOpen) return false;   // previous must be bullish
   return (currOpen >= prevClose && currClose <= prevOpen);
}

bool IsBullishPinBar(double open, double high, double low, double close)
{
   double range = high - low;
   if(range == 0) return false;

   double body       = MathAbs(close - open);
   double bodyTop    = MathMax(open, close);
   double bodyBottom = MathMin(open, close);
   double lowerWick  = bodyBottom - low;
   double upperWick  = high - bodyTop;

   if(body / range > InpPinBarMaxBody) return false;
   if(body == 0)                        return false;
   if(lowerWick < body * InpPinBarRatio) return false;
   if(upperWick > lowerWick * 0.5)       return false;

   return true;
}

bool IsBearishPinBar(double open, double high, double low, double close)
{
   double range = high - low;
   if(range == 0) return false;

   double body       = MathAbs(close - open);
   double bodyTop    = MathMax(open, close);
   double bodyBottom = MathMin(open, close);
   double upperWick  = high - bodyTop;
   double lowerWick  = bodyBottom - low;

   if(body / range > InpPinBarMaxBody) return false;
   if(body == 0)                        return false;
   if(upperWick < body * InpPinBarRatio) return false;
   if(lowerWick > upperWick * 0.5)       return false;

   return true;
}

//+------------------------------------------------------------------+
//| TP from fixed pips or Risk:Reward                                |
//+------------------------------------------------------------------+
double CalculateTakeProfit(double entry, double sl, double fixedTP,
                            double rrRatio, bool isBuy)
{
   double risk = MathAbs(entry - sl);
   double tp;

   if(fixedTP > 0)
   {
      double pipValue = GetPipValue();
      tp = isBuy ? entry + fixedTP * pipValue
                 : entry - fixedTP * pipValue;
   }
   else
   {
      tp = isBuy ? entry + risk * rrRatio
                 : entry - risk * rrRatio;
   }

   return NormalizeDouble(tp, _Digits);
}

//+------------------------------------------------------------------+
//| Pip value — 5-digit FX / 3-digit JPY = 10 * point                |
//+------------------------------------------------------------------+
double GetPipValue()
{
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point  = SymbolInfoDouble (_Symbol, SYMBOL_POINT);

   if(digits == 5 || digits == 3)
      return point * 10;
   return point;
}

//+------------------------------------------------------------------+
//| Broker-compatible filling mode                                   |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING GetFillingMode()
{
   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);

   if((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK) return ORDER_FILLING_FOK;
   if((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
//| Order execution                                                  |
//+------------------------------------------------------------------+
bool ExecuteBuy(double sl, double tp, string comment)
{
   double ask = symbolInfo.Ask();
   string fullComment = InpTradeComment + "_" + comment;

   if(sl >= ask) { Print("Invalid Buy SL: SL(", sl, ") >= Ask(", ask, ")"); return false; }
   if(tp <= ask) { Print("Invalid Buy TP: TP(", tp, ") <= Ask(", ask, ")"); return false; }

   if(!trade.Buy(InpLotSize, _Symbol, ask, sl, tp, fullComment))
   {
      Print("Buy order failed: ", trade.ResultRetcode(),
            " - ", trade.ResultRetcodeDescription());
      return false;
   }

   Print("BUY ", fullComment,
         " | Entry ", ask, " | SL ", sl, " | TP ", tp, " | Lots ", InpLotSize);
   return true;
}

bool ExecuteSell(double sl, double tp, string comment)
{
   double bid = symbolInfo.Bid();
   string fullComment = InpTradeComment + "_" + comment;

   if(sl <= bid) { Print("Invalid Sell SL: SL(", sl, ") <= Bid(", bid, ")"); return false; }
   if(tp >= bid) { Print("Invalid Sell TP: TP(", tp, ") >= Bid(", bid, ")"); return false; }

   if(!trade.Sell(InpLotSize, _Symbol, bid, sl, tp, fullComment))
   {
      Print("Sell order failed: ", trade.ResultRetcode(),
            " - ", trade.ResultRetcodeDescription());
      return false;
   }

   Print("SELL ", fullComment,
         " | Entry ", bid, " | SL ", sl, " | TP ", tp, " | Lots ", InpLotSize);
   return true;
}

//+------------------------------------------------------------------+
//| Count positions owned by this EA                                 |
//+------------------------------------------------------------------+
int CountOpenTrades()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetString (POSITION_SYMBOL) == _Symbol
      && PositionGetInteger(POSITION_MAGIC)  == InpMagicNumber)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Chart visualization                                              |
//+------------------------------------------------------------------+
void CreateChartObjects()
{
   double pipValue = GetPipValue();
   double buffer   = InpZoneBuffer * pipValue;

   ObjectCreate    (0, objSupport, OBJ_HLINE, 0, 0, supportLevel);
   ObjectSetInteger(0, objSupport, OBJPROP_COLOR,  clrLime);
   ObjectSetInteger(0, objSupport, OBJPROP_STYLE,  STYLE_SOLID);
   ObjectSetInteger(0, objSupport, OBJPROP_WIDTH,  2);
   ObjectSetString (0, objSupport, OBJPROP_TOOLTIP, "Support Level");

   ObjectCreate    (0, objResistance, OBJ_HLINE, 0, 0, resistanceLevel);
   ObjectSetInteger(0, objResistance, OBJPROP_COLOR,  clrRed);
   ObjectSetInteger(0, objResistance, OBJPROP_STYLE,  STYLE_SOLID);
   ObjectSetInteger(0, objResistance, OBJPROP_WIDTH,  2);
   ObjectSetString (0, objResistance, OBJPROP_TOOLTIP, "Resistance Level");

   ObjectCreate    (0, objSupportZone, OBJ_RECTANGLE, 0,
                    iTime(_Symbol, PERIOD_CURRENT, InpLookback),
                    supportLevel - buffer,
                    TimeCurrent(),
                    supportLevel + buffer);
   ObjectSetInteger(0, objSupportZone, OBJPROP_COLOR, clrLime);
   ObjectSetInteger(0, objSupportZone, OBJPROP_FILL,  true);
   ObjectSetInteger(0, objSupportZone, OBJPROP_BACK,  true);
   ObjectSetInteger(0, objSupportZone, OBJPROP_STYLE, STYLE_SOLID);

   ObjectCreate    (0, objResistanceZone, OBJ_RECTANGLE, 0,
                    iTime(_Symbol, PERIOD_CURRENT, InpLookback),
                    resistanceLevel - buffer,
                    TimeCurrent(),
                    resistanceLevel + buffer);
   ObjectSetInteger(0, objResistanceZone, OBJPROP_COLOR, clrRed);
   ObjectSetInteger(0, objResistanceZone, OBJPROP_FILL,  true);
   ObjectSetInteger(0, objResistanceZone, OBJPROP_BACK,  true);
   ObjectSetInteger(0, objResistanceZone, OBJPROP_STYLE, STYLE_SOLID);
}

void UpdateChartObjects()
{
   double pipValue = GetPipValue();
   double buffer   = InpZoneBuffer * pipValue;

   ObjectSetDouble(0, objSupport,    OBJPROP_PRICE, supportLevel);
   ObjectSetDouble(0, objResistance, OBJPROP_PRICE, resistanceLevel);

   ObjectSetDouble (0, objSupportZone, OBJPROP_PRICE, 0, supportLevel - buffer);
   ObjectSetDouble (0, objSupportZone, OBJPROP_PRICE, 1, supportLevel + buffer);
   ObjectSetInteger(0, objSupportZone, OBJPROP_TIME,  1, TimeCurrent());

   ObjectSetDouble (0, objResistanceZone, OBJPROP_PRICE, 0, resistanceLevel - buffer);
   ObjectSetDouble (0, objResistanceZone, OBJPROP_PRICE, 1, resistanceLevel + buffer);
   ObjectSetInteger(0, objResistanceZone, OBJPROP_TIME,  1, TimeCurrent());
}

void DeleteChartObjects()
{
   ObjectDelete(0, objSupport);
   ObjectDelete(0, objResistance);
   ObjectDelete(0, objSupportZone);
   ObjectDelete(0, objResistanceZone);
   ObjectDelete(0, objPanel);
}

//+------------------------------------------------------------------+
//| Info panel                                                       |
//+------------------------------------------------------------------+
void UpdateInfoPanel(double rsi, double price)
{
   string panelText = "";
   panelText += "=== S/R Strategy EA ===\n";
   panelText += "Support:    " + DoubleToString(supportLevel,    _Digits) + "\n";
   panelText += "Resistance: " + DoubleToString(resistanceLevel, _Digits) + "\n";
   panelText += "---------------------\n";
   panelText += "RSI(" + IntegerToString(InpRSIPeriod) + "): " + DoubleToString(rsi, 1) + "\n";
   panelText += "Price: " + DoubleToString(price, _Digits) + "\n";
   panelText += "---------------------\n";
   panelText += "Open Trades: " + IntegerToString(CountOpenTrades()) + "/"
                                + IntegerToString(InpMaxTrades) + "\n";

   if(breakoutStartBar > 0)
   {
      string brkType = (breakoutType == 1) ? "BUY" : "SELL";
      panelText += "---------------------\n";
      panelText += "Waiting: " + brkType + " Retest\n";
      panelText += "Bar: " + IntegerToString(breakoutStartBar) + "/"
                           + IntegerToString(InpBreakoutBars) + "\n";
   }
   panelText += "=====================\n";

   if(ObjectFind(0, objPanel) < 0)
   {
      ObjectCreate    (0, objPanel, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objPanel, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objPanel, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, objPanel, OBJPROP_YDISTANCE, 30);
      ObjectSetString (0, objPanel, OBJPROP_FONT,      "Consolas");
      ObjectSetInteger(0, objPanel, OBJPROP_FONTSIZE,  9);
      ObjectSetInteger(0, objPanel, OBJPROP_COLOR,     clrWhite);
      ObjectSetInteger(0, objPanel, OBJPROP_BACK,      false);
   }

   ObjectSetString(0, objPanel, OBJPROP_TEXT, panelText);
}
//+------------------------------------------------------------------+
