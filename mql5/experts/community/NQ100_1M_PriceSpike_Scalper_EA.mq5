//+------------------------------------------------------------------+
//| NQ100 1-Minute Price Spike Scalper                               |
//| Entry: price spikes >= threshold from minute open, aligned       |
//|        with hourly direction                                     |
//| Exit: price bounces threshold from minute extreme                |
//| Designed for NAS100/NDAQ100 on M1 timeframe                     |
//| Source: Gero0Nikolov/MT5-TradingBot-Admiral (1M-Slicer)         |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade g_Trade;

input group "=== Expert ==="
input long   InpMagicNumber     = 20260415;
input double InpFixedLot        = 0.10;
input int    InpDeviation       = 20;

input group "=== Spike Detection ==="
input double InpMinSpike        = 10.0;    // Min points from minute open to trigger
input double InpTPBounce        = 3.0;     // Points bounce from extreme for TP

input group "=== Session Filter ==="
input bool   InpAvoidFridayLate = true;    // No trades Friday after 20:00
input int    InpFridayHour      = 20;

datetime g_MinuteOpen_Time = 0;
double   g_MinuteOpen      = 0;
double   g_MinuteHigh      = 0;
double   g_MinuteLow       = 0;

double   g_HourOpen         = 0;
datetime g_HourOpen_Time    = 0;

bool IsNewMinute()
{
   datetime t = iTime(_Symbol, PERIOD_M1, 0);
   if(t != g_MinuteOpen_Time)
   {
      g_MinuteOpen_Time = t;
      return true;
   }
   return false;
}

bool IsNewHour()
{
   datetime t = iTime(_Symbol, PERIOD_H1, 0);
   if(t != g_HourOpen_Time)
   {
      g_HourOpen_Time = t;
      return true;
   }
   return false;
}

ulong FindPosition(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            (long)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
            return ticket;
   }
   return 0;
}

bool HasAnyPosition()
{
   return (FindPosition(POSITION_TYPE_BUY) > 0 || FindPosition(POSITION_TYPE_SELL) > 0);
}

double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0) tick = _Point;
   return NormalizeDouble(MathRound(price / tick) * tick, (int)_Digits);
}

bool IsFridayLate()
{
   if(!InpAvoidFridayLate) return false;
   MqlDateTime dt;
   TimeCurrent(dt);
   return (dt.day_of_week == 5 && dt.hour >= InpFridayHour);
}

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   Print("NQ100_1M_PriceSpike_Scalper initialized. ", _Symbol, " Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {}

void OnTick()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Track hourly direction
   if(IsNewHour())
      g_HourOpen = iOpen(_Symbol, PERIOD_H1, 0);

   // Track minute OHLC
   if(IsNewMinute())
   {
      g_MinuteOpen = iOpen(_Symbol, PERIOD_M1, 0);
      g_MinuteHigh = g_MinuteOpen;
      g_MinuteLow  = g_MinuteOpen;
   }
   else
   {
      if(bid > g_MinuteHigh) g_MinuteHigh = bid;
      if(bid < g_MinuteLow)  g_MinuteLow  = bid;
   }

   // Determine hourly direction
   int hourDir = 0;
   if(g_HourOpen > 0)
   {
      if(bid > g_HourOpen) hourDir = 1;
      if(bid < g_HourOpen) hourDir = -1;
   }

   // Check exit conditions for open positions
   ulong buyTicket = FindPosition(POSITION_TYPE_BUY);
   if(buyTicket > 0)
   {
      // TP: price drops InpTPBounce from minute high
      if(g_MinuteHigh - bid >= InpTPBounce)
         g_Trade.PositionClose(buyTicket);
   }

   ulong sellTicket = FindPosition(POSITION_TYPE_SELL);
   if(sellTicket > 0)
   {
      // TP: price rises InpTPBounce from minute low
      if(bid - g_MinuteLow >= InpTPBounce)
         g_Trade.PositionClose(sellTicket);
   }

   // Entry logic
   if(HasAnyPosition()) return;
   if(IsFridayLate()) return;
   if(g_MinuteOpen <= 0 || g_HourOpen <= 0) return;

   double spikeUp = bid - g_MinuteOpen;
   double spikeDn = g_MinuteOpen - bid;

   // BUY: price spiked up from minute open + hour trending up
   if(spikeUp >= InpMinSpike && hourDir == 1)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      g_Trade.Buy(InpFixedLot, _Symbol, 0.0, 0, 0, "Spike BUY");
   }
   // SELL: price spiked down from minute open + hour trending down
   else if(spikeDn >= InpMinSpike && hourDir == -1)
   {
      g_Trade.Sell(InpFixedLot, _Symbol, 0.0, 0, 0, "Spike SELL");
   }
}
//+------------------------------------------------------------------+
