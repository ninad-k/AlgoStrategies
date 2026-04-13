//+------------------------------------------------------------------+
//| Trend Breakout EA — EMA 9/21/50 + RSI + ADX + ATR               |
//| Entry: EMA stack alignment + RSI momentum + ADX trend strength   |
//| Exit: reverse signal or trailing stop                            |
//| Sessions: London (8-11) and New York (13-17) only                |
//| SL/TP: ATR-based (1.5x SL, configurable R:R)                    |
//| Source: Sidoine1991/KolaTradeboT (RoboCop_v2)                    |
//+------------------------------------------------------------------+
#property copyright "Community Strategy - AlgoStrategies"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade g_Trade;

input group "=== Expert ==="
input long    InpMagicNumber    = 20260414;
input double  InpFixedLot       = 0.10;
input int     InpDeviation      = 20;

input group "=== EMA Stack ==="
input int     InpEMAFast        = 9;
input int     InpEMAMid         = 21;
input int     InpEMASlow        = 50;

input group "=== Filters ==="
input int     InpRSIPeriod      = 14;
input double  InpRSIBuyLevel    = 50;      // RSI above this for BUY
input double  InpRSISellLevel   = 50;      // RSI below this for SELL
input int     InpADXPeriod      = 14;
input double  InpADXThreshold   = 20;      // ADX above this = trending
input double  InpMinConfidence  = 0.30;    // Minimum composite score

input group "=== Risk ==="
input int     InpATRPeriod      = 14;
input double  InpATRSLMult      = 1.5;     // ATR x for SL
input double  InpRiskReward     = 2.0;     // R:R ratio for TP
input bool    InpUseTrailing    = true;
input double  InpTrailATRMult   = 1.0;     // Trail distance in ATR

input group "=== Sessions (server hour) ==="
input int     InpLondonStart    = 8;
input int     InpLondonEnd      = 11;
input int     InpNYStart        = 13;
input int     InpNYEnd          = 17;

input group "=== Daily Limits ==="
input double  InpDailyProfitTarget = 0;    // 0 = disabled
input int     InpMaxDailyTrades    = 10;

int hEMAFast = INVALID_HANDLE, hEMAMid = INVALID_HANDLE, hEMASlow = INVALID_HANDLE;
int hRSI = INVALID_HANDLE, hADX = INVALID_HANDLE, hATR = INVALID_HANDLE;
datetime g_LastBarTime = 0;
int g_DailyTrades = 0;
int g_LastDay = 0;

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

bool IsInSession()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int h = dt.hour;
   return (h >= InpLondonStart && h <= InpLondonEnd) || (h >= InpNYStart && h <= InpNYEnd);
}

void ResetDailyCounters()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != g_LastDay)
   {
      g_DailyTrades = 0;
      g_LastDay = dt.day;
   }
}

// Trail stop for open positions
void ManageTrailing(double atr)
{
   if(!InpUseTrailing) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      double trailDist = InpTrailATRMult * atr;
      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

      if(type == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double newSL = NormalizePrice(bid - trailDist);
         if(newSL > currentSL && newSL < bid)
            g_Trade.PositionModify(ticket, newSL, currentTP);
      }
      else
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double newSL = NormalizePrice(ask + trailDist);
         if((currentSL == 0 || newSL < currentSL) && newSL > ask)
            g_Trade.PositionModify(ticket, newSL, currentTP);
      }
   }
}

int OnInit()
{
   g_Trade.SetExpertMagicNumber(InpMagicNumber);
   g_Trade.SetDeviationInPoints(InpDeviation);

   hEMAFast = iMA(_Symbol, PERIOD_CURRENT, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   hEMAMid  = iMA(_Symbol, PERIOD_CURRENT, InpEMAMid,  0, MODE_EMA, PRICE_CLOSE);
   hEMASlow = iMA(_Symbol, PERIOD_CURRENT, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   hRSI     = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
   hADX     = iADX(_Symbol, PERIOD_CURRENT, InpADXPeriod);
   hATR     = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);

   if(hEMAFast == INVALID_HANDLE || hEMAMid == INVALID_HANDLE || hEMASlow == INVALID_HANDLE ||
      hRSI == INVALID_HANDLE || hADX == INVALID_HANDLE || hATR == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. err=", GetLastError());
      return INIT_FAILED;
   }

   Print("TrendBreakout_EMA_RSI_ADX initialized. ", _Symbol, " Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEMAFast != INVALID_HANDLE) IndicatorRelease(hEMAFast);
   if(hEMAMid  != INVALID_HANDLE) IndicatorRelease(hEMAMid);
   if(hEMASlow != INVALID_HANDLE) IndicatorRelease(hEMASlow);
   if(hRSI     != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hADX     != INVALID_HANDLE) IndicatorRelease(hADX);
   if(hATR     != INVALID_HANDLE) IndicatorRelease(hATR);
}

void OnTick()
{
   // Trailing stop management every tick
   double atrBuf[1];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) >= 1 && atrBuf[0] > 0)
      ManageTrailing(atrBuf[0]);

   if(!IsNewBar()) return;
   ResetDailyCounters();

   if(!IsInSession()) return;
   if(HasAnyPosition()) return;
   if(InpMaxDailyTrades > 0 && g_DailyTrades >= InpMaxDailyTrades) return;

   // Copy indicator values for bar[1]
   double emaF[2], emaM[2], emaS[2], rsi[2], adx[2], diPlus[2], diMinus[2], atr[2];
   ArraySetAsSeries(emaF, true); ArraySetAsSeries(emaM, true); ArraySetAsSeries(emaS, true);
   ArraySetAsSeries(rsi, true); ArraySetAsSeries(adx, true);
   ArraySetAsSeries(diPlus, true); ArraySetAsSeries(diMinus, true); ArraySetAsSeries(atr, true);

   if(CopyBuffer(hEMAFast, 0, 0, 2, emaF) < 2) return;
   if(CopyBuffer(hEMAMid,  0, 0, 2, emaM) < 2) return;
   if(CopyBuffer(hEMASlow, 0, 0, 2, emaS) < 2) return;
   if(CopyBuffer(hRSI,     0, 0, 2, rsi)  < 2) return;
   if(CopyBuffer(hADX,     0, 0, 2, adx)  < 2) return;  // Main ADX line
   if(CopyBuffer(hADX,     1, 0, 2, diPlus) < 2) return; // +DI
   if(CopyBuffer(hADX,     2, 0, 2, diMinus) < 2) return; // -DI
   if(CopyBuffer(hATR,     0, 0, 2, atr)  < 2) return;

   if(atr[1] <= 0) return;

   // EMA stack alignment check on bar[1]
   bool bullStack = (emaF[1] > emaM[1] && emaM[1] > emaS[1]);
   bool bearStack = (emaF[1] < emaM[1] && emaM[1] < emaS[1]);

   // RSI momentum confirmation
   bool rsiBull = (rsi[1] > InpRSIBuyLevel);
   bool rsiBear = (rsi[1] < InpRSISellLevel);

   // ADX trend strength
   bool trending = (adx[1] > InpADXThreshold);
   bool diUp   = (diPlus[1] > diMinus[1]);
   bool diDown = (diMinus[1] > diPlus[1]);

   // Composite confidence score
   double buyScore = 0, sellScore = 0;
   if(bullStack) buyScore += 0.40;
   if(rsiBull)   buyScore += 0.30;
   if(trending && diUp) buyScore += 0.30;

   if(bearStack) sellScore += 0.40;
   if(rsiBear)   sellScore += 0.30;
   if(trending && diDown) sellScore += 0.30;

   if(buyScore >= InpMinConfidence)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizePrice(ask - InpATRSLMult * atr[1]);
      double tp  = NormalizePrice(ask + InpATRSLMult * InpRiskReward * atr[1]);
      if(g_Trade.Buy(InpFixedLot, _Symbol, 0.0, sl, tp, "TrendBrk BUY"))
         g_DailyTrades++;
   }
   else if(sellScore >= InpMinConfidence)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizePrice(bid + InpATRSLMult * atr[1]);
      double tp  = NormalizePrice(bid - InpATRSLMult * InpRiskReward * atr[1]);
      if(g_Trade.Sell(InpFixedLot, _Symbol, 0.0, sl, tp, "TrendBrk SELL"))
         g_DailyTrades++;
   }
}
//+------------------------------------------------------------------+
