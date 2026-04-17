//+------------------------------------------------------------------+
//| Core logic: On each new bar, detect fast/slow MA crossover on   |
//| the chart (confirmed with prior-bar MAs); optionally require price |
//| vs a higher-timeframe MA. Flip position on opposite signal; size |
//| lots from equity (with gold override); optional SL/TP and exit   |
//| when price crosses back through the fast MA.                      |
//| Author: Ninad K                                                   |
//+------------------------------------------------------------------+
#property copyright "Ninad K"
#property version   "1.07"
#property description "Dual moving-average crossover EA with optional MTF filter, equity-based sizing, and pip SL/TP."

#include <Trade\Trade.mqh>
CTrade trade;

//--- Parameters: chart MAs (crossover on PERIOD_CURRENT)
input group "=== Chart MA (crossover) ==="
input ENUM_MA_METHOD mode_ma        = MODE_EMA;   // MA calculation method
input int            period_ma_fast = 100;        // Fast MA period (must be < slow)
input int            period_ma_slow = 200;        // Slow MA period

//--- Parameters: optional trend filter on another timeframe
input group "=== Optional MTF filter ==="
input bool             use_ma_filter        = false;           // Require price vs filter MA
input ENUM_MA_METHOD   mode_ma_filter       = MODE_SMA;        // Filter MA method
input ENUM_TIMEFRAMES  timeframe_ma_filter  = PERIOD_D1;       // Filter timeframe
input int              period_ma_filter     = 100;           // Filter MA period

//--- Parameters: exits and risk
input group "=== Risk and exits ==="
input double takeProfit    = 0.0;    // Take profit distance (pips; 0 = none)
input double stopLoss      = 0.0;    // Stop loss distance (pips; 0 = none)
input bool   useFastMAexit = false;  // Close if price crosses back through fast MA
input double maxLotSize    = 0.1;    // Cap on calculated lot size
input double minEquity       = 100.0; // Do not trade if equity below this (account currency)

//--- Parameters: identification
input group "=== Expert ==="
input int MagicNumber = 889;         // Magic number for this EA's orders

//--- Runtime: symbol scaling and indicator handles
double   myPoint;
datetime prevTime;
int      hFastMA;
int      hSlowMA;

double fastMA[];
double slowMA[];

//+------------------------------------------------------------------+
//| Initialization: validate inputs, create iMA handles, set trading |
//+------------------------------------------------------------------+
int OnInit()
{
   if(period_ma_fast >= period_ma_slow || period_ma_fast < 1 || period_ma_slow < 1)
   {
      Alert("Error: Fast MA period must be less than Slow MA period");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(takeProfit < 0 || stopLoss < 0 || maxLotSize < 0.01 || minEquity < 10)
   {
      Alert("Error: Invalid risk parameters");
      return INIT_PARAMETERS_INCORRECT;
   }

   hFastMA = iMA(_Symbol, PERIOD_CURRENT, period_ma_fast, 0, mode_ma, PRICE_CLOSE);
   hSlowMA = iMA(_Symbol, PERIOD_CURRENT, period_ma_slow, 0, mode_ma, PRICE_CLOSE);

   if(hFastMA == INVALID_HANDLE || hSlowMA == INVALID_HANDLE)
   {
      Print("Error: Failed to create MA indicators");
      return INIT_FAILED;
   }

   myPoint = GetPointValue(_Symbol);
   trade.SetExpertMagicNumber(MagicNumber);

   Print("MACrossover_Filtered_EA v1.07 initialized");
   Print("Symbol: ", _Symbol, " | Timeframe: ", EnumToString(PERIOD_CURRENT));
   Print("Fast MA: ", period_ma_fast, " | Slow MA: ", period_ma_slow);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Release indicator handles                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hFastMA != INVALID_HANDLE) IndicatorRelease(hFastMA);
   if(hSlowMA != INVALID_HANDLE) IndicatorRelease(hSlowMA);
}

//+------------------------------------------------------------------+
//| Each tick: update buffers; act only once per new bar after checks |
//+------------------------------------------------------------------+
void OnTick()
{
   ArraySetAsSeries(fastMA, true);
   ArraySetAsSeries(slowMA, true);

   if(CopyBuffer(hFastMA, 0, 0, 3, fastMA) < 0)
      Print("CopyBuffer fast MA failed, error=", GetLastError());
   if(CopyBuffer(hSlowMA, 0, 0, 3, slowMA) < 0)
      Print("CopyBuffer slow MA failed, error=", GetLastError());

   if(!CheckEquity())
      return;
   if(!IsNewBar())
      return;

   int signal = GetSignal();
   if(signal == -1)
      return;

   ProcessTrade(signal);
}

//+------------------------------------------------------------------+
//| New bar gate: first evaluation after bar open uses prior bar data |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBar = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(prevTime != currentBar)
   {
      prevTime = currentBar;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Block new entries when account equity is below minimum            |
//+------------------------------------------------------------------+
bool CheckEquity()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity < minEquity)
   {
      Print("Equity too low: ", equity, " < ", minEquity);
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Crossover rules on bar 1 close vs fast/slow MA[1], MA[2]; filter |
//+------------------------------------------------------------------+
int GetSignal()
{
   double close = iClose(_Symbol, PERIOD_CURRENT, 1);

   bool bullish =
      close > fastMA[1] &&
      fastMA[2] <= slowMA[2] &&
      fastMA[1] > slowMA[1] &&
      (!use_ma_filter || close > iMAOnArray(period_ma_filter, 0, mode_ma_filter, 1));

   if(bullish)
      return ORDER_TYPE_BUY;

   bool bearish =
      close < fastMA[1] &&
      fastMA[2] >= slowMA[2] &&
      fastMA[1] < slowMA[1] &&
      (!use_ma_filter || close < iMAOnArray(period_ma_filter, 0, mode_ma_filter, 1));

   if(bearish)
      return ORDER_TYPE_SELL;

   if(useFastMAexit)
   {
      if(PositionExists(POSITION_TYPE_BUY) && close <= fastMA[1])
         trade.PositionClose(_Symbol);

      if(PositionExists(POSITION_TYPE_SELL) && close >= fastMA[1])
         trade.PositionClose(_Symbol);
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Close opposite side if reversing; open if flat on that side      |
//+------------------------------------------------------------------+
void ProcessTrade(int signal)
{
   bool hasBuy  = PositionExists(POSITION_TYPE_BUY);
   bool hasSell = PositionExists(POSITION_TYPE_SELL);

   ulong closeTicket = GetOppositePosition(signal);
   if(closeTicket > 0)
      trade.PositionClose(closeTicket);

   double lotSize = NormalizeLotSize();
   if(lotSize <= 0)
      return;

   double price = (signal == ORDER_TYPE_BUY) ?
                  SymbolInfoDouble(_Symbol, SYMBOL_ASK) :
                  SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double sl = GetStopLoss(signal, price);
   double tp = GetTakeProfit(signal, price);

   bool result = false;
   if(signal == ORDER_TYPE_BUY && !hasBuy)
      result = trade.Buy(lotSize, _Symbol, 0.0, sl, tp, "MACross Buy");
   else if(signal == ORDER_TYPE_SELL && !hasSell)
      result = trade.Sell(lotSize, _Symbol, 0.0, sl, tp, "MACross Sell");

   if(result)
      Print("Trade executed: ", EnumToString((ENUM_ORDER_TYPE)signal),
            " | Lot: ", lotSize, " | Price: ", price);
}

//+------------------------------------------------------------------+
//| True if an open position exists for this symbol/magic/type        |
//+------------------------------------------------------------------+
bool PositionExists(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
            PositionGetInteger(POSITION_TYPE) == type)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Ticket of opposite position to close before reversing direction   |
//+------------------------------------------------------------------+
ulong GetOppositePosition(int signal)
{
   ENUM_POSITION_TYPE closeType = (signal == ORDER_TYPE_BUY) ? POSITION_TYPE_SELL : POSITION_TYPE_BUY;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
            PositionGetInteger(POSITION_TYPE) == closeType)
            return ticket;
      }
   }
   return 0;
}

//+------------------------------------------------------------------+
//| Lot size: gold metals fixed small lot; else equity/10000 capped   |
//+------------------------------------------------------------------+
double NormalizeLotSize()
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double lot = minLot;
   if(StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "GOLD") >= 0)
      lot = 0.01;
   else
   {
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      lot = equity / 10000.0;
      lot = MathMin(lot, maxLotSize);
   }

   lot = MathFloor(lot / stepLot) * stepLot;
   lot = MathMax(lot, minLot);
   lot = MathMin(lot, maxLot);
   return lot;
}

//+------------------------------------------------------------------+
//| SL in price from pip distance and broker minimum stop distance    |
//+------------------------------------------------------------------+
double GetStopLoss(int signal, double price)
{
   if(stopLoss <= 0.0)
      return 0.0;

   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = (stopLevel > 0) ? stopLevel * _Point : 20 * _Point;
   double distance = MathMax(stopLoss * myPoint, minDist);

   if(signal == ORDER_TYPE_BUY)
      return NormalizeDouble(price - distance, _Digits);
   return NormalizeDouble(price + distance, _Digits);
}

//+------------------------------------------------------------------+
//| TP in price from pip distance and broker minimum stop distance   |
//+------------------------------------------------------------------+
double GetTakeProfit(int signal, double price)
{
   if(takeProfit <= 0.0)
      return 0.0;

   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = (stopLevel > 0) ? stopLevel * _Point : 20 * _Point;
   double distance = MathMax(takeProfit * myPoint, minDist);

   if(signal == ORDER_TYPE_BUY)
      return NormalizeDouble(price + distance, _Digits);
   return NormalizeDouble(price - distance, _Digits);
}

//+------------------------------------------------------------------+
//| Pip/point multiplier for SL/TP (5-digit FX, metals, etc.)         |
//+------------------------------------------------------------------+
double GetPointValue(string symbol)
{
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "XAG") >= 0)
      return 0.1;
   if(digits == 5 || digits == 3)
      return _Point * 10;
   return _Point;
}

//+------------------------------------------------------------------+
//| MA value on filter timeframe: builds close series, then SMA/EMA/ |
//| SMMA/LWMA at requested shift (used only when filter is enabled)  |
//+------------------------------------------------------------------+
double iMAOnArray(int period, int ma_shift, ENUM_MA_METHOD ma_method, int shift)
{
   MqlRates _rates[];
   int _ratesCopied = CopyRates(_Symbol, timeframe_ma_filter, 0, period_ma_filter + 1, _rates);
   double array[];
   ArrayResize(array, _ratesCopied);
   if(_ratesCopied > 0)
      for(int i = 1; i < _ratesCopied; i++)
         array[i] = _rates[i - 1].close;
   ArrayReverse(array, 0, WHOLE_ARRAY);

   double buf[], arr[];
   int total = ArraySize(array);

   if(total <= period)
      return 0;

   if(shift > total - period - ma_shift)
      return 0;

   switch(ma_method)
   {
   case MODE_SMA:
   {
      total = ArrayCopy(arr, array, 0, shift + ma_shift, period);
      if(ArrayResize(buf, total) < 0)
         return 0;

      double sum = 0;
      int i, pos = total - 1;

      for(i = 1; i < period; i++, pos--)
         sum += arr[pos];

      while(pos >= 0)
      {
         sum += arr[pos];
         buf[pos] = sum / period;
         sum -= arr[pos + period - 1];
         pos--;
      }

      return buf[0];
   }

   case MODE_EMA:
   {
      if(ArrayResize(buf, total) < 0)
         return 0;

      double pr = 2.0 / (period + 1);
      int pos = total - 2;

      while(pos >= 0)
      {
         if(pos == total - 2)
            buf[pos + 1] = array[pos + 1];
         buf[pos] = array[pos] * pr + buf[pos + 1] * (1 - pr);
         pos--;
      }

      return buf[shift + ma_shift];
   }

   case MODE_SMMA:
   {
      if(ArrayResize(buf, total) < 0)
         return 0;

      double sum = 0;
      int i, k, pos;

      pos = total - period;
      while(pos >= 0)
      {
         if(pos == total - period)
         {
            for(i = 0, k = pos; i < period; i++, k++)
            {
               sum += array[k];
               buf[k] = 0;
            }
         }
         else
            sum = buf[pos + 1] * (period - 1) + array[pos];

         buf[pos] = sum / period;
         pos--;
      }

      return buf[shift + ma_shift];
   }

   case MODE_LWMA:
   {
      if(ArrayResize(buf, total) < 0)
         return 0;

      double sum = 0.0, lsum = 0.0;
      double price;
      int i, weight = 0, pos = total - 1;

      for(i = 1; i <= period; i++, pos--)
      {
         price = array[pos];
         sum += price * i;
         lsum += price;
         weight += i;
      }

      pos++;
      i = pos + period;

      while(pos >= 0)
      {
         buf[pos] = sum / weight;

         if(pos == 0)
            break;

         pos--;
         i--;
         price = array[pos];
         sum = sum - lsum + price * period;
         lsum -= array[i];
         lsum += price;
      }

      return buf[shift + ma_shift];
   }
   }

   return 0;
}
//+------------------------------------------------------------------+
