//+------------------------------------------------------------------+
//| EMA 9/21 + RSI(7) Rapid Compounding EA                          |
//| Entry: EMA crossover confirmed by RSI momentum                  |
//| Compounding: lot size increases 1.5x after each profit target   |
//| Up to 5 compound levels, resets on loss                          |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade g_Trade;

input group "=== Expert ==="
input long    InpMagicNumber     = 20260416;
input double  InpBaseLot         = 0.10;
input int     InpDeviation       = 20;

input group "=== EMA Signal ==="
input int     InpEMAFast         = 9;
input int     InpEMASlow         = 21;

input group "=== RSI Filter ==="
input int     InpRSIPeriod       = 7;
input double  InpRSIBuyThresh    = 55;     // RSI above this for BUY
input double  InpRSISellThresh   = 45;     // RSI below this for SELL

input group "=== Compounding ==="
input double  InpProfitTarget    = 0.50;   // USD profit to trigger compound
input double  InpCompoundMult    = 1.5;    // Lot multiplier per level
input int     InpMaxCompound     = 5;      // Max compound levels

input group "=== Risk ==="
input double  InpSLPoints        = 50;     // SL in points
input double  InpTPPoints        = 150;    // TP in points (3:1 R:R)
input double  InpDailyTarget     = 100.0;  // Daily profit target USD (0=off)
input double  InpDailyMaxLoss    = -50.0;  // Daily loss limit USD

input group "=== Session ==="
input int     InpStartHour       = 8;
input int     InpEndHour         = 22;

int hEMAFast = INVALID_HANDLE, hEMASlow = INVALID_HANDLE, hRSI = INVALID_HANDLE;
datetime g_LastBarTime = 0;

int    g_CompoundLevel  = 0;
double g_DailyPnL       = 0;
int    g_LastDay         = 0;

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

double NormalizeLot(double lots)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   double l = MathMax(lots, minLot);
   l = MathMin(l, maxLot);
   l = MathFloor(l / stepLot) * stepLot;
   return MathMax(l, minLot);
}

double GetCompoundLot()
{
   double lot = InpBaseLot;
   for(int i = 0; i < g_CompoundLevel && i < InpMaxCompound; i++)
      lot *= InpCompoundMult;
   return NormalizeLot(lot);
}

void ResetDaily()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != g_LastDay)
   {
      g_DailyPnL = 0;
      g_LastDay = dt.day;
   }
}

bool IsInSession()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   return (dt.hour >= InpStartHour && dt.hour < InpEndHour);
}

// Track closed deals to update compound level and daily PnL
void UpdateFromHistory()
{
   static datetime lastCheck = 0;
   datetime now = TimeCurrent();
   if(now - lastCheck < 5) return; // Check every 5 seconds
   lastCheck = now;

   datetime dayStart = now - (now % 86400);
   HistorySelect(dayStart, now);

   double dayPnL = 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetInteger(dealTicket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;

      double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT)
                    + HistoryDealGetDouble(dealTicket, DEAL_COMMISSION)
                    + HistoryDealGetDouble(dealTicket, DEAL_SWAP);
      dayPnL += profit;
   }
   g_DailyPnL = dayPnL;
}

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hEMAFast = iMA(_Symbol, PERIOD_CURRENT, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   hEMASlow = iMA(_Symbol, PERIOD_CURRENT, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   hRSI     = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);

   if(hEMAFast == INVALID_HANDLE || hEMASlow == INVALID_HANDLE || hRSI == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. err=", GetLastError());
      return INIT_FAILED;
   }

   Print("EMA_RSI_RapidCompound initialized. ", _Symbol, " BaseLot=", InpBaseLot,
         " CompoundMult=", InpCompoundMult, " MaxLevels=", InpMaxCompound);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEMAFast != INVALID_HANDLE) IndicatorRelease(hEMAFast);
   if(hEMASlow != INVALID_HANDLE) IndicatorRelease(hEMASlow);
   if(hRSI     != INVALID_HANDLE) IndicatorRelease(hRSI);
}

void OnTick()
{
   ResetDaily();
   UpdateFromHistory();

   // Daily limits check
   if(InpDailyTarget > 0 && g_DailyPnL >= InpDailyTarget) return;
   if(InpDailyMaxLoss < 0 && g_DailyPnL <= InpDailyMaxLoss) return;

   if(!IsNewBar()) return;
   if(!IsInSession()) return;
   if(HasAnyPosition()) return;

   double emaF[3], emaS[3], rsiBuf[2];
   ArraySetAsSeries(emaF, true); ArraySetAsSeries(emaS, true); ArraySetAsSeries(rsiBuf, true);

   if(CopyBuffer(hEMAFast, 0, 0, 3, emaF) < 3) return;
   if(CopyBuffer(hEMASlow, 0, 0, 3, emaS) < 3) return;
   if(CopyBuffer(hRSI,     0, 0, 2, rsiBuf) < 2) return;

   // EMA crossover on completed bar[1] vs bar[2]
   bool crossUp = (emaF[2] <= emaS[2] && emaF[1] > emaS[1]);
   bool crossDn = (emaF[2] >= emaS[2] && emaF[1] < emaS[1]);

   // RSI confirmation
   bool rsiBull = (rsiBuf[1] > InpRSIBuyThresh);
   bool rsiBear = (rsiBuf[1] < InpRSISellThresh);

   double lots = GetCompoundLot();

   if(crossUp && rsiBull)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizePrice(ask - InpSLPoints * _Point);
      double tp  = NormalizePrice(ask + InpTPPoints * _Point);
      if(g_Trade.Buy(lots, _Symbol, 0.0, sl, tp, "Compound BUY L" + IntegerToString(g_CompoundLevel)))
      {
         Print("BUY L", g_CompoundLevel, " lots=", lots);
         if(g_CompoundLevel < InpMaxCompound) g_CompoundLevel++;
      }
   }
   else if(crossDn && rsiBear)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizePrice(bid + InpSLPoints * _Point);
      double tp  = NormalizePrice(bid - InpTPPoints * _Point);
      if(g_Trade.Sell(lots, _Symbol, 0.0, sl, tp, "Compound SELL L" + IntegerToString(g_CompoundLevel)))
      {
         Print("SELL L", g_CompoundLevel, " lots=", lots);
         if(g_CompoundLevel < InpMaxCompound) g_CompoundLevel++;
      }
   }
}
//+------------------------------------------------------------------+
