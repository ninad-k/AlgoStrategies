//+------------------------------------------------------------------+
//| SMA 9/21 Crossover Expert Advisor                                |
//| Entry: fast SMA crosses slow SMA on new bar                      |
//| Exit: reverse crossover closes position, opens opposite          |
//| SL/TP: fixed price offset from entry                             |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

input int    InpMAPeriodShort = 9;
input int    InpMAPeriodLong  = 21;
input int    InpMAShift       = 0;
input ENUM_MA_METHOD InpMAMethodS = MODE_SMA;
input ENUM_MA_METHOD InpMAMethodL = MODE_SMA;
input ENUM_APPLIED_PRICE InpMAPrice = PRICE_CLOSE;
input double InpStopLoss      = 0.1;
input double InpTakeProfit     = 0.3;
input double InpVolume         = 0.10;
input int    InpMagicNumber    = 20260413;
input int    InpDeviation      = 10;

#include <Trade/Trade.mqh>
CTrade g_Trade;

int    hMAShort = INVALID_HANDLE;
int    hMALong  = INVALID_HANDLE;
datetime g_LastBarTime = 0;

bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t != g_LastBarTime) { g_LastBarTime = t; return true; }
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

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hMAShort = iMA(_Symbol, PERIOD_CURRENT, InpMAPeriodShort, InpMAShift, InpMAMethodS, InpMAPrice);
   hMALong  = iMA(_Symbol, PERIOD_CURRENT, InpMAPeriodLong, InpMAShift, InpMAMethodL, InpMAPrice);

   if(hMAShort == INVALID_HANDLE || hMALong == INVALID_HANDLE)
   {
      Print("Failed to create MA handles. err=", GetLastError());
      return INIT_FAILED;
   }

   Print("SMA_Crossover_9_21 initialized. ", _Symbol, " Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hMAShort != INVALID_HANDLE) IndicatorRelease(hMAShort);
   if(hMALong  != INVALID_HANDLE) IndicatorRelease(hMALong);
}

void OnTick()
{
   if(!IsNewBar()) return;

   double maS[3], maL[3];
   ArraySetAsSeries(maS, true);
   ArraySetAsSeries(maL, true);

   if(CopyBuffer(hMAShort, 0, 0, 3, maS) < 3) return;
   if(CopyBuffer(hMALong,  0, 0, 3, maL) < 3) return;

   // Crossover on bar[1] vs bar[2] (completed bars only)
   bool crossUp = (maS[2] <= maL[2] && maS[1] > maL[1]);
   bool crossDn = (maS[2] >= maL[2] && maS[1] < maL[1]);

   ulong buyTicket  = FindPosition(POSITION_TYPE_BUY);
   ulong sellTicket = FindPosition(POSITION_TYPE_SELL);

   if(crossUp)
   {
      if(sellTicket > 0) g_Trade.PositionClose(sellTicket);
      if(buyTicket == 0)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double sl  = NormalizeDouble(ask - InpStopLoss, (int)_Digits);
         double tp  = NormalizeDouble(ask + InpTakeProfit, (int)_Digits);
         g_Trade.Buy(InpVolume, _Symbol, 0.0, sl, tp, "SMA_Cross BUY");
      }
   }
   else if(crossDn)
   {
      if(buyTicket > 0) g_Trade.PositionClose(buyTicket);
      if(sellTicket == 0)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl  = NormalizeDouble(bid + InpStopLoss, (int)_Digits);
         double tp  = NormalizeDouble(bid - InpTakeProfit, (int)_Digits);
         g_Trade.Sell(InpVolume, _Symbol, 0.0, sl, tp, "SMA_Cross SELL");
      }
   }
}
//+------------------------------------------------------------------+
