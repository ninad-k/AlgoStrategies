//+------------------------------------------------------------------+
//|                          EMA200HedgeBracket_EA.mq5               |
//|                                    AlgoStrategies                |
//|  When price touches EMA → open BUY + SELL bracket.              |
//|  Cut losing leg after X pts loss. Let winning leg run with       |
//|  partial TPs and trailing SL to capture the full rally.          |
//|                                                                  |
//|  IMPORTANT: Requires a HEDGING account (not netting).            |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property link      ""
#property version   "1.00"
#property description "EMA Hedge Bracket: BUY+SELL on EMA touch, cut loser at X pts, run winner with TPs and trail"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_EXIT_MODE {
   EXIT_CANDLE_CLOSE,   // Candle Close (close crosses EMA)
   EXIT_CANDLE_TOUCH    // Candle Touch (wick touches EMA)
};

enum ENUM_LOT_MODE {
   LOT_FIXED,           // Fixed Lot
   LOT_RISK_PCT         // Risk % of Balance
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
sinput string sep0 = "=== EMA Settings ===";
input int              InpEMALen          = 200;                  // EMA Length
input ENUM_EXIT_MODE   InpExitMode        = EXIT_CANDLE_CLOSE;   // Winner Exit Mode

sinput string sep1 = "=== Hedge Bracket Settings ===";
input int              InpHedgeLossPts    = 50;                   // Cut losing leg after X points loss

sinput string sep1b = "=== ADX Filter (Optional, Entry Only) ===";
input bool             InpUseADX          = false;                // Enable ADX Filter
input int              InpADXPeriod       = 14;                   // ADX Period
input double           InpADXThreshold    = 25.0;                 // ADX Minimum Threshold

sinput string sep2 = "=== Lot Settings ===";
input ENUM_LOT_MODE    InpLotMode         = LOT_FIXED;            // Lot Mode
input double           InpFixedLot        = 0.1;                  // Fixed Lot Size (per leg)
input double           InpRiskPct         = 1.0;                  // Risk % of Balance
input int              InpSLPoints        = 500;                  // SL Points (for risk calc)

sinput string sep3 = "=== Partial Profit Booking (Points from Winner Entry) ===";
input bool             InpTP1Enable       = true;                 // Enable TP1
input int              InpTP1Points       = 30;                   // TP1 Points from Entry
input double           InpTP1QtyPct       = 20.0;                 // TP1 Close Qty %
input bool             InpTP2Enable       = true;                 // Enable TP2
input int              InpTP2Points       = 60;                   // TP2 Points from Entry
input double           InpTP2QtyPct       = 20.0;                 // TP2 Close Qty %
input bool             InpTP3Enable       = true;                 // Enable TP3
input int              InpTP3Points       = 90;                   // TP3 Points from Entry
input double           InpTP3QtyPct       = 20.0;                 // TP3 Close Qty %

sinput string sep4 = "=== Trailing Stop Loss (Winner Only) ===";
input bool             InpUseTSL          = false;                // Enable Trailing SL on Winner
input double           InpTSLTriggerPct   = 1.5;                  // TSL Trigger Profit %
input double           InpTSLOffsetPct    = 0.5;                  // TSL Trail Offset %

sinput string sep5 = "=== Display ===";
input bool             InpShowEMA         = true;                 // Plot EMA Line
input bool             InpShowSignals     = true;                 // Plot Entry/Exit Arrows

sinput string sep6 = "=== General ===";
input long             InpMagic           = 200300;               // Magic Number

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CTrade g_Trade;

//--- EMA
double   g_EMA           = 0;
bool     g_EMAInit       = false;
double   g_PrevEMA       = 0;
datetime g_PrevBarTime   = 0;
int      g_EMALineCount  = 0;

//--- ADX
double g_ADX             = 0;
double g_PlusDI          = 0;
double g_MinusDI         = 0;
double g_PrevTR          = 0;
double g_SmoothedTR      = 0;
double g_SmoothedPlusDM  = 0;
double g_SmoothedMinusDM = 0;
double g_SmoothedDX      = 0;
int    g_ADXBarCount     = 0;
bool   g_ADXInitialized  = false;
double g_PrevClose       = 0;
double g_PrevHigh        = 0;
double g_PrevLow         = 0;

//--- Hedge state
//    0  = FLAT          no positions
//    1  = HEDGE         both BUY + SELL open, waiting for loser to hit limit
//    2  = BUY_WINNER    sell leg cut, buy leg running free
//   -2  = SELL_WINNER   buy leg cut, sell leg running free
int    g_State           = 0;
ulong  g_BuyTicket       = 0;     // buy leg position ticket
ulong  g_SellTicket      = 0;     // sell leg position ticket
double g_BuyEntry        = 0;     // buy leg fill price
double g_SellEntry       = 0;     // sell leg fill price
double g_OriginalLots    = 0;     // lots per leg (same for both sides)
double g_WinnerEntry     = 0;     // entry price of surviving winner
int    g_WinnerDir       = 0;     // 1 = buy winner, -1 = sell winner

//--- Winner TP / TSL flags
bool   g_TP1Hit          = false;
bool   g_TP2Hit          = false;
bool   g_TP3Hit          = false;
double g_TrailStop       = 0;
bool   g_TSLActive       = false;
double g_WinnerStopLoss  = 0;        // Fixed SL price for the winning leg

#define DASH_PREFIX "EMA200HB_"

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpEMALen <= 0)
   {
      Alert("EMA length must be > 0");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpHedgeLossPts <= 0)
   {
      Alert("Hedge Loss Points must be > 0");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_Trade.SetExpertMagicNumber(InpMagic);
   g_Trade.SetDeviationInPoints(ULONG_MAX);

   Print("EMA200 Hedge Bracket EA initialised. Magic=", InpMagic,
         " HedgeLossPts=", InpHedgeLossPts);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, DASH_PREFIX);
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   double liveAsk  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double liveBid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double liveHigh = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double liveLow  = iLow(_Symbol, PERIOD_CURRENT, 0);

   //--- [Every tick] HEDGE: check if losing leg crossed the loss limit
   if(g_EMAInit && g_State == 1)
      CheckCutLoser(liveBid, liveAsk);

   //--- [Every tick] WINNER running: check fixed SL FIRST, then book partial TPs and update/check TSL live
   if(g_EMAInit && (g_State == 2 || g_State == -2) && g_WinnerEntry > 0)
   {
      CheckFixedSL(liveBid, liveAsk);  // Check fixed SL FIRST (highest priority)

      //--- Only process TP/TSL if SL hasn't been hit
      if(g_State != 0)  // State still valid after SL check
      {
         ProcessPartialTP(liveHigh, liveLow);
         if(InpUseTSL)
            ProcessTrailingSL(liveHigh, liveLow);
      }
   }

   //--- [New bar only] entry signals + winner EMA exit
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime) return;
   lastBarTime = currentBarTime;

   //--- Bar 1 = last closed candle
   double closePrice = iClose(_Symbol, PERIOD_CURRENT, 1);
   double highPrice  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double lowPrice   = iLow(_Symbol, PERIOD_CURRENT, 1);
   datetime barTime  = iTime(_Symbol, PERIOD_CURRENT, 1);

   //--- Seed EMA on first bar
   if(!g_EMAInit)
   {
      g_EMA    = closePrice;
      g_EMAInit = true;
      return;
   }

   //--- Update EMA
   double k = 2.0 / (InpEMALen + 1);
   g_EMA = closePrice * k + g_EMA * (1.0 - k);

   //--- ADX (optional entry filter)
   if(InpUseADX)
      CalcADX(highPrice, lowPrice, closePrice);

   //--- Sync state with actual broker positions
   SyncState();

   //=================================================================
   //  WINNER EXIT: EMA signal on bar close
   //=================================================================
   if(g_State == 2 || g_State == -2)
   {
      bool winnerExit = false;

      if(g_State == 2)   // BUY winner — exit when price drops below EMA
      {
         if(InpExitMode == EXIT_CANDLE_CLOSE)
            winnerExit = (closePrice < g_EMA);
         else
            winnerExit = (lowPrice <= g_EMA);
      }
      else               // SELL winner — exit when price rises above EMA
      {
         if(InpExitMode == EXIT_CANDLE_CLOSE)
            winnerExit = (closePrice > g_EMA);
         else
            winnerExit = (highPrice >= g_EMA);
      }

      if(winnerExit)
      {
         if(InpShowSignals)
         {
            if(g_State == 2)
               DrawArrow(barTime, highPrice, false, clrRed, "WIN_EXIT");
            else
               DrawArrow(barTime, lowPrice,  true,  clrRed, "WIN_EXIT");
         }
         CloseWinner("EMA Exit");
         PlotEMASegment(barTime);
         return;
      }
   }

   //=================================================================
   //  ENTRY: price touches EMA + previous bar on opposite side (breakout)
   //=================================================================
   if(g_State == 0)
   {
      bool emaTouched  = (lowPrice <= g_EMA && highPrice >= g_EMA);
      bool prevBarBelow = (g_PrevClose < g_PrevEMA);  // prev bar below EMA
      bool prevBarAbove = (g_PrevClose > g_PrevEMA);  // prev bar above EMA
      bool isBreakout  = (emaTouched && (prevBarBelow || prevBarAbove)); // entering from consolidation

      if(isBreakout)
      {
         //--- ADX filter: skip if trend too weak
         bool adxOK = true;
         if(InpUseADX && g_ADXInitialized && g_ADX < InpADXThreshold)
            adxOK = false;

         if(adxOK)
            OpenHedge(barTime, liveAsk, liveBid);
      }
   }

   //--- Store current bar data for NEXT bar's previous-bar checks (must be AFTER entry conditions)
   g_PrevClose = closePrice;
   g_PrevHigh  = highPrice;
   g_PrevLow   = lowPrice;

   PlotEMASegment(barTime);
}

//+------------------------------------------------------------------+
//| Open BUY + SELL bracket simultaneously                           |
//+------------------------------------------------------------------+
void OpenHedge(datetime barTime, double ask, double bid)
{
   double lots = CalcLotSize();

   //--- BUY leg first
   if(!g_Trade.Buy(lots, _Symbol, ask, 0, 0, "EMA200HB Buy"))
   {
      Print("Hedge BUY failed: retcode=", g_Trade.ResultRetcode(),
            " ", g_Trade.ResultComment());
      return;
   }
   ulong  buyTicket = g_Trade.ResultOrder();
   double buyFill   = g_Trade.ResultPrice();
   if(buyFill == 0) buyFill = ask;

   //--- SELL leg immediately after
   if(!g_Trade.Sell(lots, _Symbol, bid, 0, 0, "EMA200HB Sell"))
   {
      Print("Hedge SELL failed: retcode=", g_Trade.ResultRetcode(),
            " ", g_Trade.ResultComment());
      //--- Roll back: close the BUY leg so we don't hold a naked long
      g_Trade.PositionClose(buyTicket, ULONG_MAX);
      return;
   }
   ulong  sellTicket = g_Trade.ResultOrder();
   double sellFill   = g_Trade.ResultPrice();
   if(sellFill == 0) sellFill = bid;

   //--- Store bracket state
   g_BuyTicket    = buyTicket;
   g_SellTicket   = sellTicket;
   g_BuyEntry     = buyFill;
   g_SellEntry    = sellFill;
   g_OriginalLots = lots;
   g_State        = 1;
   g_TP1Hit       = false;
   g_TP2Hit       = false;
   g_TP3Hit       = false;
   g_TrailStop    = 0;
   g_TSLActive    = false;
   g_WinnerEntry  = 0;
   g_WinnerDir    = 0;

   Print("Hedge bracket opened  BUY #", buyTicket,  " @ ", buyFill,
         "  SELL #", sellTicket, " @ ", sellFill,
         "  lots=", lots, " each");

   if(InpShowSignals)
   {
      DrawArrow(barTime, GetBarLow(barTime),  true,  clrGreen,  "HB_BUY");
      DrawArrow(barTime, GetBarHigh(barTime), false, clrOrange, "HB_SELL");
   }
}

//+------------------------------------------------------------------+
//| Every-tick: cut the losing leg once it exceeds loss limit        |
//+------------------------------------------------------------------+
void CheckCutLoser(double bid, double ask)
{
   //--- Check BUY leg loss: (entry - current_bid) / _Point
   if(g_BuyTicket > 0 && PositionSelectByTicket(g_BuyTicket))
   {
      double lossPoints = (g_BuyEntry - bid) / _Point;
      if(lossPoints >= InpHedgeLossPts)
      {
         Print("Cutting BUY leg (loser) | loss=", DoubleToString(lossPoints, 1), " pts");
         if(g_Trade.PositionClose(g_BuyTicket, ULONG_MAX))
         {
            g_BuyTicket   = 0;
            g_State       = -2;          // SELL is winner
            g_WinnerDir   = -1;
            g_WinnerEntry = g_SellEntry;
            //--- Set SL for SELL winner: entry + InpSLPoints (above entry for short)
            g_WinnerStopLoss = g_SellEntry + InpSLPoints * _Point;
            g_TP1Hit      = false;
            g_TP2Hit      = false;
            g_TP3Hit      = false;
            g_TrailStop   = 0;
            g_TSLActive   = false;
            Print("SELL leg is winner @ entry=", g_WinnerEntry, " SL=", g_WinnerStopLoss);
         }
         else
            Print("Cut BUY leg FAILED: retcode=", g_Trade.ResultRetcode());
         return; // one leg cut per tick
      }
   }

   //--- Check SELL leg loss: (current_ask - entry) / _Point
   if(g_SellTicket > 0 && PositionSelectByTicket(g_SellTicket))
   {
      double lossPoints = (ask - g_SellEntry) / _Point;
      if(lossPoints >= InpHedgeLossPts)
      {
         Print("Cutting SELL leg (loser) | loss=", DoubleToString(lossPoints, 1), " pts");
         if(g_Trade.PositionClose(g_SellTicket, ULONG_MAX))
         {
            g_SellTicket  = 0;
            g_State       = 2;           // BUY is winner
            g_WinnerDir   = 1;
            g_WinnerEntry = g_BuyEntry;
            //--- Set SL for BUY winner: entry - InpSLPoints (below entry for long)
            g_WinnerStopLoss = g_BuyEntry - InpSLPoints * _Point;
            g_TP1Hit      = false;
            g_TP2Hit      = false;
            g_TP3Hit      = false;
            g_TrailStop   = 0;
            g_TSLActive   = false;
            Print("BUY leg is winner @ entry=", g_WinnerEntry, " SL=", g_WinnerStopLoss);
         }
         else
            Print("Cut SELL leg FAILED: retcode=", g_Trade.ResultRetcode());
      }
   }
}

//+------------------------------------------------------------------+
//| Check Fixed SL for the winning leg                               |
//+------------------------------------------------------------------+
void CheckFixedSL(double bid, double ask)
{
   if(g_WinnerStopLoss == 0) return;  // no SL set

   bool slHit = false;

   if(g_WinnerDir == 1)  // BUY winner
   {
      if(bid <= g_WinnerStopLoss)
      {
         slHit = true;
         Print("FIXED SL HIT for BUY winner: bid=", bid, " SL=", g_WinnerStopLoss);
      }
   }
   else if(g_WinnerDir == -1)  // SELL winner
   {
      if(ask >= g_WinnerStopLoss)
      {
         slHit = true;
         Print("FIXED SL HIT for SELL winner: ask=", ask, " SL=", g_WinnerStopLoss);
      }
   }

   if(slHit)
   {
      CloseWinner("Fixed SL");  // Closes the winning leg
   }
}

//+------------------------------------------------------------------+
//| Close the surviving winner position                              |
//+------------------------------------------------------------------+
void CloseWinner(string reason)
{
   ulong winTicket = (g_WinnerDir == 1) ? g_BuyTicket : g_SellTicket;
   if(winTicket > 0 && PositionSelectByTicket(winTicket))
   {
      double vol = PositionGetDouble(POSITION_VOLUME);
      Print("Closing winner [", reason, "] ticket=", winTicket, " vol=", vol);
      if(!g_Trade.PositionClose(winTicket, ULONG_MAX))
         Print("  Close failed: retcode=", g_Trade.ResultRetcode(),
               " ", g_Trade.ResultComment());
   }
   ResetState();
}

//+------------------------------------------------------------------+
//| Reset all hedge state to flat                                    |
//+------------------------------------------------------------------+
void ResetState()
{
   g_State        = 0;
   g_BuyTicket    = 0;
   g_SellTicket   = 0;
   g_BuyEntry     = 0;
   g_SellEntry    = 0;
   g_OriginalLots = 0;
   g_WinnerEntry  = 0;
   g_WinnerDir    = 0;
   g_TP1Hit       = false;
   g_TP2Hit       = false;
   g_TP3Hit       = false;
   g_TrailStop    = 0;
   g_TSLActive    = false;
   g_WinnerStopLoss = 0;
}

//+------------------------------------------------------------------+
//| Sync EA state with actual broker positions (safety check)        |
//+------------------------------------------------------------------+
void SyncState()
{
   if(g_State == 0) return; // nothing to sync

   bool buyOpen  = (g_BuyTicket  > 0 && PositionSelectByTicket(g_BuyTicket));
   bool sellOpen = (g_SellTicket > 0 && PositionSelectByTicket(g_SellTicket));

   if(g_State == 1)  // Hedge: both should be open
   {
      if(!buyOpen && !sellOpen)
      {
         Print("SyncState: both hedge legs gone unexpectedly — resetting flat");
         ResetState();
      }
      else if(!buyOpen && sellOpen)
      {
         Print("SyncState: BUY leg gone externally — SELL becomes winner");
         g_BuyTicket   = 0;
         g_State       = -2;
         g_WinnerDir   = -1;
         g_WinnerEntry = g_SellEntry;
         //--- Set SL for SELL winner
         g_WinnerStopLoss = g_SellEntry + InpSLPoints * _Point;
      }
      else if(buyOpen && !sellOpen)
      {
         Print("SyncState: SELL leg gone externally — BUY becomes winner");
         g_SellTicket  = 0;
         g_State       = 2;
         g_WinnerDir   = 1;
         g_WinnerEntry = g_BuyEntry;
         //--- Set SL for BUY winner
         g_WinnerStopLoss = g_BuyEntry - InpSLPoints * _Point;
      }
   }
   else if(g_State == 2 || g_State == -2)  // Winner running
   {
      ulong winTicket = (g_WinnerDir == 1) ? g_BuyTicket : g_SellTicket;
      bool  winOpen   = (winTicket > 0 && PositionSelectByTicket(winTicket));
      if(!winOpen)
      {
         Print("SyncState: winner position gone externally — resetting flat");
         ResetState();
      }
   }
}

//+------------------------------------------------------------------+
//| Partial TP on winner — max one TP per tick                       |
//+------------------------------------------------------------------+
void ProcessPartialTP(double highPrice, double lowPrice)
{
   if(g_WinnerDir == 1)  // BUY winner: TP levels above entry
   {
      double tp1 = g_WinnerEntry + InpTP1Points * _Point;
      double tp2 = g_WinnerEntry + InpTP2Points * _Point;
      double tp3 = g_WinnerEntry + InpTP3Points * _Point;

      if(InpTP1Enable && !g_TP1Hit && highPrice >= tp1)
      {
         double lots = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0);
         if(lots > 0 && PartialCloseWinner(lots, "TP1")) g_TP1Hit = true;
         return;
      }
      if(InpTP2Enable && !g_TP2Hit && highPrice >= tp2)
      {
         double lots = NormalizeLots(g_OriginalLots * InpTP2QtyPct / 100.0);
         if(lots > 0 && PartialCloseWinner(lots, "TP2")) g_TP2Hit = true;
         return;
      }
      if(InpTP3Enable && !g_TP3Hit && highPrice >= tp3)
      {
         double lots = NormalizeLots(g_OriginalLots * InpTP3QtyPct / 100.0);
         if(lots > 0 && PartialCloseWinner(lots, "TP3")) g_TP3Hit = true;
         return;
      }
   }
   else if(g_WinnerDir == -1)  // SELL winner: TP levels below entry
   {
      double tp1 = g_WinnerEntry - InpTP1Points * _Point;
      double tp2 = g_WinnerEntry - InpTP2Points * _Point;
      double tp3 = g_WinnerEntry - InpTP3Points * _Point;

      if(InpTP1Enable && !g_TP1Hit && lowPrice <= tp1)
      {
         double lots = NormalizeLots(g_OriginalLots * InpTP1QtyPct / 100.0);
         if(lots > 0 && PartialCloseWinner(lots, "TP1")) g_TP1Hit = true;
         return;
      }
      if(InpTP2Enable && !g_TP2Hit && lowPrice <= tp2)
      {
         double lots = NormalizeLots(g_OriginalLots * InpTP2QtyPct / 100.0);
         if(lots > 0 && PartialCloseWinner(lots, "TP2")) g_TP2Hit = true;
         return;
      }
      if(InpTP3Enable && !g_TP3Hit && lowPrice <= tp3)
      {
         double lots = NormalizeLots(g_OriginalLots * InpTP3QtyPct / 100.0);
         if(lots > 0 && PartialCloseWinner(lots, "TP3")) g_TP3Hit = true;
         return;
      }
   }
}

//+------------------------------------------------------------------+
//| Partial close of winner by ticket                                |
//+------------------------------------------------------------------+
bool PartialCloseWinner(double lots, string comment)
{
   ulong winTicket = (g_WinnerDir == 1) ? g_BuyTicket : g_SellTicket;
   if(winTicket == 0) return false;
   if(!PositionSelectByTicket(winTicket)) return false;

   double posVol = PositionGetDouble(POSITION_VOLUME);
   if(lots >= posVol) lots = posVol;
   lots = NormalizeLots(lots);
   if(lots <= 0) return false;

   Print("PartialCloseWinner [", comment, "] lots=", lots, " of ", posVol);
   return g_Trade.PositionClosePartial(winTicket, lots, ULONG_MAX);
}

//+------------------------------------------------------------------+
//| Trailing SL on winner — runs every tick                          |
//+------------------------------------------------------------------+
void ProcessTrailingSL(double highPrice, double lowPrice)
{
   if(g_WinnerDir == 1)  // BUY winner
   {
      double trigger = g_WinnerEntry * (1.0 + InpTSLTriggerPct / 100.0);
      if(highPrice >= trigger)
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
         Print("TSL hit BUY winner at ", g_TrailStop);
         CloseWinner("TSL");
      }
   }
   else if(g_WinnerDir == -1)  // SELL winner
   {
      double trigger = g_WinnerEntry * (1.0 - InpTSLTriggerPct / 100.0);
      if(lowPrice <= trigger)
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
         Print("TSL hit SELL winner at ", g_TrailStop);
         CloseWinner("TSL");
      }
   }
}

//+------------------------------------------------------------------+
//| Lot size calculation                                             |
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
//| Normalize lots to valid broker volume step                       |
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
//| ADX calculation (Wilder's method, manual — no indicator handle)  |
//+------------------------------------------------------------------+
void CalcADX(double highPrice, double lowPrice, double closePrice)
{
   g_ADXBarCount++;
   if(g_ADXBarCount == 1) return; // need previous bar

   double plusDM  = highPrice - g_PrevHigh;
   double minusDM = g_PrevLow  - lowPrice;
   if(plusDM  < 0) plusDM  = 0;
   if(minusDM < 0) minusDM = 0;
   if(plusDM  > minusDM) minusDM = 0;
   else if(minusDM > plusDM) plusDM = 0;
   else { plusDM = 0; minusDM = 0; }

   double tr = MathMax(highPrice - lowPrice,
               MathMax(MathAbs(highPrice - g_PrevClose),
                       MathAbs(lowPrice  - g_PrevClose)));

   int n = InpADXPeriod;

   if(g_ADXBarCount <= n + 1)
   {
      g_SmoothedTR      += tr;
      g_SmoothedPlusDM  += plusDM;
      g_SmoothedMinusDM += minusDM;

      if(g_ADXBarCount == n + 1)
      {
         g_PlusDI  = g_SmoothedTR > 0 ? (g_SmoothedPlusDM  / g_SmoothedTR) * 100.0 : 0;
         g_MinusDI = g_SmoothedTR > 0 ? (g_SmoothedMinusDM / g_SmoothedTR) * 100.0 : 0;
         double diSum = g_PlusDI + g_MinusDI;
         double dx    = diSum > 0 ? MathAbs(g_PlusDI - g_MinusDI) / diSum * 100.0 : 0;
         g_SmoothedDX      = dx;
         g_ADX             = dx;
         g_ADXInitialized  = true;
      }
      return;
   }

   g_SmoothedTR      = g_SmoothedTR      - (g_SmoothedTR      / n) + tr;
   g_SmoothedPlusDM  = g_SmoothedPlusDM  - (g_SmoothedPlusDM  / n) + plusDM;
   g_SmoothedMinusDM = g_SmoothedMinusDM - (g_SmoothedMinusDM / n) + minusDM;

   g_PlusDI  = g_SmoothedTR > 0 ? (g_SmoothedPlusDM  / g_SmoothedTR) * 100.0 : 0;
   g_MinusDI = g_SmoothedTR > 0 ? (g_SmoothedMinusDM / g_SmoothedTR) * 100.0 : 0;

   double diSum = g_PlusDI + g_MinusDI;
   double dx    = diSum > 0 ? MathAbs(g_PlusDI - g_MinusDI) / diSum * 100.0 : 0;

   g_ADX        = (g_SmoothedDX * (n - 1) + dx) / n;
   g_SmoothedDX = g_ADX;
}

//+------------------------------------------------------------------+
//| Draw arrow on chart                                              |
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
//| Helper: get bar high/low by time for arrow placement             |
//+------------------------------------------------------------------+
double GetBarHigh(datetime barTime)
{
   int shift = iBarShift(_Symbol, PERIOD_CURRENT, barTime);
   return iHigh(_Symbol, PERIOD_CURRENT, shift);
}

double GetBarLow(datetime barTime)
{
   int shift = iBarShift(_Symbol, PERIOD_CURRENT, barTime);
   return iLow(_Symbol, PERIOD_CURRENT, shift);
}

//+------------------------------------------------------------------+
//| Plot EMA line segment bar-to-bar                                 |
//+------------------------------------------------------------------+
void PlotEMASegment(datetime barTime)
{
   if(!InpShowEMA || g_PrevBarTime == 0) { g_PrevEMA = g_EMA; g_PrevBarTime = barTime; return; }
   string seg = DASH_PREFIX + "EMA_" + IntegerToString(g_EMALineCount++);
   ObjectCreate(0, seg, OBJ_TREND, 0, g_PrevBarTime, g_PrevEMA, barTime, g_EMA);
   ObjectSetInteger(0, seg, OBJPROP_COLOR,     clrYellow);
   ObjectSetInteger(0, seg, OBJPROP_STYLE,     STYLE_SOLID);
   ObjectSetInteger(0, seg, OBJPROP_WIDTH,     2);
   ObjectSetInteger(0, seg, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, seg, OBJPROP_BACK,      true);
   g_PrevEMA     = g_EMA;
   g_PrevBarTime = barTime;
}
//+------------------------------------------------------------------+
