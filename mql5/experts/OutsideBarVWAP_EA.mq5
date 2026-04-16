//+------------------------------------------------------------------+
//|                                        OutsideBarVWAP_EA.mq5      |
//|                   Outside Bar Breakout + Session VWAP Filter      |
//|                                                                   |
//|  Concept (minimal-indicator price-action strategy):               |
//|    • Outside bar = a bar whose HIGH > prev HIGH AND LOW < prev LOW|
//|      (i.e. it fully engulfs the previous bar's range).            |
//|    • Bias filter: session VWAP.                                   |
//|        - Outside bar ABOVE VWAP → only take LONG breakouts        |
//|        - Outside bar BELOW VWAP → only take SHORT breakdowns      |
//|    • Entry: stop order at the outside bar's high (long) or        |
//|      low (short).                                                 |
//|    • Stop-loss: opposite extreme of the outside bar.              |
//|    • Risk filter: skip trades whose SL distance (bar range) is    |
//|      too wide — keeps stops small, per the source strategy.       |
//|    • Best suited to 15-minute intraday charts of liquid indices.  |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "Outside Bar Breakout + Session VWAP Filter\nEnter on break of outside bar extreme in direction of VWAP bias; SL at opposite extreme; skips oversized bars."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

CTrade        g_trade;
CPositionInfo g_pos;

//============================================================
//  ENUMERATIONS
//============================================================
enum ENUM_SL_LIMIT_MODE
  {
   SL_LIMIT_ATR,      // Max SL distance = ATR * multiplier
   SL_LIMIT_PCT,      // Max SL distance = % of price
   SL_LIMIT_POINTS,   // Max SL distance = fixed points
   SL_LIMIT_OFF,      // Disable SL size filter
  };

enum ENUM_TP_MODE
  {
   TP_RR_MULTIPLE,    // Take profit = R-multiple of SL distance
   TP_POINTS,         // Take profit = fixed points
   TP_OFF,            // No take profit (trail / manual exit)
  };

//============================================================
//  INPUTS — STRATEGY
//============================================================
input group "━━━ Outside Bar Detection ━━━"
input bool   InpStrictOutside  = true;    // Strict outside bar (high>prevH AND low<prevL)
input bool   InpRequireClose   = false;   // Require close beyond prev bar extreme (directional outside bar)

input group "━━━ VWAP Filter (session-based) ━━━"
input bool   InpUseVWAP        = true;    // Enable VWAP bias filter
input int    InpSessionHour    = 9;       // Session start hour (broker/server time)
input int    InpSessionMin     = 15;      // Session start minute (09:15 = NSE open)
input bool   InpRequireBarAboveVWAP  = true; // Outside bar must close on bias side of VWAP

input group "━━━ Risk / Stop-Loss Filter ━━━"
input ENUM_SL_LIMIT_MODE InpSLLimitMode = SL_LIMIT_ATR;  // Max SL size filter mode
input double InpMaxSLATRMult   = 2.0;     // Max SL distance = ATR × this
input double InpMaxSLPct       = 0.5;     // Max SL distance as % of price
input int    InpMaxSLPoints    = 3000;    // Max SL distance in points
input int    InpATRPeriod      = 14;      // ATR period for SL-size filter

input group "━━━ Pending Order Behaviour ━━━"
input int    InpPendingExpiryBars = 3;    // Cancel pending order after N new bars
input int    InpEntryBufferPoints = 0;    // Points beyond bar extreme for trigger

input group "━━━ Trade Direction ━━━"
input bool   InpAllowLong      = true;    // Allow long breakouts
input bool   InpAllowShort     = true;    // Allow short breakdowns

input group "━━━ Take Profit / Trailing ━━━"
input ENUM_TP_MODE InpTPMode   = TP_RR_MULTIPLE;  // Take-profit mode
input double InpTPRRMult       = 2.0;     // TP R-multiple (of SL distance)
input int    InpTPPoints       = 0;       // TP in points (TP_POINTS mode)
input bool   InpTrailToBE      = true;    // Move SL to breakeven after 1R
input bool   InpTrailVWAP      = false;   // Trail SL along VWAP once in profit

input group "━━━ Session Window ━━━"
input bool   InpUseSessionWindow = false; // Only trade inside window
input int    InpWinStartH      = 9;       // Window start hour
input int    InpWinStartM      = 30;      // Window start minute
input int    InpWinEndH        = 15;      // Window end hour
input int    InpWinEndM        = 0;       // Window end minute

input group "━━━ Trade Management ━━━"
input double InpLotSize        = 0.1;     // Fixed lot size
input double InpRiskPctBalance = 0.0;     // Risk % of balance (0 = use fixed lot)
input int    InpMaxPositions   = 1;       // Max open positions (this EA)
input int    InpMaxPendings    = 1;       // Max pending orders (this EA)
input int    InpMagic          = 20260416; // Magic number
input string InpComment        = "OutsideBarVWAP";  // Order comment

//============================================================
//  GLOBALS
//============================================================
datetime g_lastBar     = 0;
datetime g_lastSession = 0;
double   g_vwap        = 0.0;
int      g_atrHandle   = INVALID_HANDLE;

// Track pending tickets so we can expire them
struct PendingInfo
  {
   ulong    ticket;
   datetime placedBar;
  };
PendingInfo g_pendings[];

//============================================================
//  INIT / DEINIT
//============================================================
int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);

   if(InpSLLimitMode == SL_LIMIT_ATR)
     {
      g_atrHandle = iATR(_Symbol, _Period, InpATRPeriod);
      if(g_atrHandle == INVALID_HANDLE)
        { Print("ATR handle creation failed"); return INIT_FAILED; }
     }

   Print("OutsideBarVWAP EA v1.00 — ", _Symbol, " ", EnumToString((ENUM_TIMEFRAMES)_Period));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
  }

//============================================================
//  TICK
//============================================================
void OnTick()
  {
   ManageOpenPositions();

   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == g_lastBar)
      return;
   g_lastBar = barTime;

   // Expire stale pending orders (count of *new* bars since placement)
   ExpirePendings();

   // Recalculate session VWAP on each new bar
   if(InpUseVWAP)
      g_vwap = CalcSessionVWAP();

   // Only scan for new setups if we have spare capacity
   if(CountPositions() >= InpMaxPositions) return;
   if(CountPendings()  >= InpMaxPendings)  return;
   if(!PassSessionWindow())                return;

   CheckOutsideBarSignal();
  }

//============================================================
//  OUTSIDE BAR DETECTION & ENTRY
//============================================================
void CheckOutsideBarSignal()
  {
   // Signal bar is the most recently *closed* bar (index 1); prev is index 2.
   double hi1 = iHigh(_Symbol,  _Period, 1);
   double lo1 = iLow(_Symbol,   _Period, 1);
   double cl1 = iClose(_Symbol, _Period, 1);
   double op1 = iOpen(_Symbol,  _Period, 1);
   double hi2 = iHigh(_Symbol,  _Period, 2);
   double lo2 = iLow(_Symbol,   _Period, 2);

   bool outside;
   if(InpStrictOutside)
      outside = (hi1 > hi2) && (lo1 < lo2);
   else
      outside = (hi1 >= hi2) && (lo1 <= lo2) && (hi1 - lo1) > (hi2 - lo2);
   if(!outside) return;

   double barRange = hi1 - lo1;
   if(barRange <= 0) return;

   // Direction filter from VWAP
   bool canLong  = InpAllowLong;
   bool canShort = InpAllowShort;
   if(InpUseVWAP && g_vwap > 0.0)
     {
      double ref = InpRequireBarAboveVWAP ? cl1 : (hi1 + lo1) * 0.5;
      if(ref <= g_vwap) canLong  = false;
      if(ref >= g_vwap) canShort = false;
     }

   // Optional directional close requirement
   if(InpRequireClose)
     {
      if(canLong  && cl1 <= hi2) canLong  = false;
      if(canShort && cl1 >= lo2) canShort = false;
     }

   if(!canLong && !canShort) return;

   // Risk filter: skip oversized outside bars (keeps SL small)
   if(!PassSLSizeFilter(barRange)) return;

   int buffer = InpEntryBufferPoints;
   double bufPrice = buffer * _Point;

   if(canLong)
     {
      double entry = NormalizeDouble(hi1 + bufPrice, _Digits);
      double sl    = NormalizeDouble(lo1,             _Digits);
      double tp    = CalcTP(entry, sl, true);
      PlacePending(ORDER_TYPE_BUY_STOP, entry, sl, tp);
     }
   if(canShort)
     {
      double entry = NormalizeDouble(lo1 - bufPrice, _Digits);
      double sl    = NormalizeDouble(hi1,             _Digits);
      double tp    = CalcTP(entry, sl, false);
      PlacePending(ORDER_TYPE_SELL_STOP, entry, sl, tp);
     }
  }

double CalcTP(double entry, double sl, bool isLong)
  {
   if(InpTPMode == TP_OFF) return 0.0;

   if(InpTPMode == TP_POINTS && InpTPPoints > 0)
     {
      double dist = InpTPPoints * _Point;
      return NormalizeDouble(isLong ? entry + dist : entry - dist, _Digits);
     }

   // RR multiple of SL distance
   double risk = MathAbs(entry - sl);
   if(risk <= 0.0) return 0.0;
   double dist = risk * InpTPRRMult;
   return NormalizeDouble(isLong ? entry + dist : entry - dist, _Digits);
  }

//============================================================
//  RISK / SL SIZE FILTER
//============================================================
bool PassSLSizeFilter(double slDistance)
  {
   if(InpSLLimitMode == SL_LIMIT_OFF) return true;

   if(InpSLLimitMode == SL_LIMIT_POINTS)
      return (slDistance <= InpMaxSLPoints * _Point);

   if(InpSLLimitMode == SL_LIMIT_PCT)
     {
      double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(price <= 0) return true;
      double pct = slDistance / price * 100.0;
      return (pct <= InpMaxSLPct);
     }

   // SL_LIMIT_ATR
   if(g_atrHandle == INVALID_HANDLE) return true;
   double atr[];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) < 1) return true;
   if(atr[0] <= 0) return true;
   return (slDistance <= atr[0] * InpMaxSLATRMult);
  }

//============================================================
//  VWAP — session-based, recalculated each bar
//============================================================
double CalcSessionVWAP()
  {
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = InpSessionHour;
   dt.min  = InpSessionMin;
   dt.sec  = 0;
   datetime sessStart = StructToTime(dt);
   if(now < sessStart)
      sessStart -= 86400;  // use previous day's session

   g_lastSession = sessStart;

   MqlRates rates[];
   int copied = CopyRates(_Symbol, _Period, sessStart, now, rates);
   if(copied < 1) return 0.0;

   double sumTPV = 0.0, sumVol = 0.0;
   for(int i = 0; i < copied; i++)
     {
      double tp  = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      double vol = (double)rates[i].tick_volume;
      if(vol < 1.0) vol = 1.0;
      sumTPV += tp * vol;
      sumVol += vol;
     }
   return (sumVol > 0.0) ? sumTPV / sumVol : 0.0;
  }

//============================================================
//  SESSION WINDOW
//============================================================
bool PassSessionWindow()
  {
   if(!InpUseSessionWindow) return true;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int nowMin   = dt.hour * 60 + dt.min;
   int startMin = InpWinStartH * 60 + InpWinStartM;
   int endMin   = InpWinEndH   * 60 + InpWinEndM;

   if(startMin < endMin)
      return (nowMin >= startMin && nowMin < endMin);
   return (nowMin >= startMin || nowMin < endMin);
  }

//============================================================
//  ORDER PLACEMENT & LIFECYCLE
//============================================================
void PlacePending(ENUM_ORDER_TYPE type, double price, double sl, double tp)
  {
   double volume = CalcLotSize(price, sl);
   if(volume <= 0.0) return;

   bool ok = false;
   if(type == ORDER_TYPE_BUY_STOP)
      ok = g_trade.BuyStop(volume, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, InpComment);
   else if(type == ORDER_TYPE_SELL_STOP)
      ok = g_trade.SellStop(volume, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, InpComment);

   if(!ok)
     {
      Print("Pending order failed: ", g_trade.ResultRetcodeDescription());
      return;
     }

   ulong ticket = g_trade.ResultOrder();
   if(ticket == 0) return;

   int n = ArraySize(g_pendings);
   ArrayResize(g_pendings, n + 1);
   g_pendings[n].ticket    = ticket;
   g_pendings[n].placedBar = iTime(_Symbol, _Period, 0);
  }

void ExpirePendings()
  {
   int n = ArraySize(g_pendings);
   for(int i = n - 1; i >= 0; i--)
     {
      ulong ticket = g_pendings[i].ticket;
      if(!OrderSelect(ticket))
        { // Order no longer exists (filled / cancelled) — drop from tracker
         ArrayRemoveAt(i);
         continue;
        }

      // Count how many new bars have closed since placement
      int barsSince = iBarShift(_Symbol, _Period, g_pendings[i].placedBar, false);
      if(barsSince >= InpPendingExpiryBars)
        {
         if(g_trade.OrderDelete(ticket))
            ArrayRemoveAt(i);
        }
     }
  }

void ArrayRemoveAt(int idx)
  {
   int sz = ArraySize(g_pendings);
   if(idx < 0 || idx >= sz) return;
   for(int i = idx; i < sz - 1; i++)
      g_pendings[i] = g_pendings[i + 1];
   ArrayResize(g_pendings, sz - 1);
  }

//============================================================
//  POSITION MANAGEMENT — breakeven / VWAP trail
//============================================================
void ManageOpenPositions()
  {
   if(!InpTrailToBE && !InpTrailVWAP) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol || g_pos.Magic() != InpMagic) continue;

      double openPr = g_pos.PriceOpen();
      double sl     = g_pos.StopLoss();
      double tp     = g_pos.TakeProfit();
      double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(g_pos.PositionType() == POSITION_TYPE_BUY)
        {
         double risk = openPr - sl;
         if(InpTrailToBE && risk > 0.0 && bid >= openPr + risk && sl < openPr)
           {
            g_trade.PositionModify(g_pos.Ticket(), NormalizeDouble(openPr, _Digits), tp);
            continue;
           }
         if(InpTrailVWAP && g_vwap > 0.0 && bid > openPr && g_vwap > sl && g_vwap < bid)
            g_trade.PositionModify(g_pos.Ticket(), NormalizeDouble(g_vwap, _Digits), tp);
        }
      else
        {
         double risk = sl - openPr;
         if(InpTrailToBE && risk > 0.0 && ask <= openPr - risk && (sl == 0.0 || sl > openPr))
           {
            g_trade.PositionModify(g_pos.Ticket(), NormalizeDouble(openPr, _Digits), tp);
            continue;
           }
         if(InpTrailVWAP && g_vwap > 0.0 && ask < openPr && (sl == 0.0 || g_vwap < sl) && g_vwap > ask)
            g_trade.PositionModify(g_pos.Ticket(), NormalizeDouble(g_vwap, _Digits), tp);
        }
     }
  }

//============================================================
//  LOT SIZING
//============================================================
double CalcLotSize(double entry, double sl)
  {
   if(InpRiskPctBalance <= 0.0)
      return NormalizeVolume(InpLotSize);

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskCash = balance * InpRiskPctBalance / 100.0;

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0)
      return NormalizeVolume(InpLotSize);

   double slDist = MathAbs(entry - sl);
   if(slDist <= 0.0)
      return NormalizeVolume(InpLotSize);

   double lossPerLot = (slDist / tickSize) * tickValue;
   if(lossPerLot <= 0.0)
      return NormalizeVolume(InpLotSize);

   double vol = riskCash / lossPerLot;
   return NormalizeVolume(vol);
  }

double NormalizeVolume(double vol)
  {
   double minV  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepV <= 0.0) stepV = 0.01;
   vol = MathFloor(vol / stepV) * stepV;
   if(vol < minV) vol = minV;
   if(vol > maxV) vol = maxV;
   return vol;
  }

//============================================================
//  HELPERS
//============================================================
int CountPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(g_pos.SelectByIndex(i) &&
         g_pos.Symbol() == _Symbol &&
         g_pos.Magic()  == InpMagic)
         n++;
     }
   return n;
  }

int CountPendings()
  {
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if((string)OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((long)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      n++;
     }
   return n;
  }
//+------------------------------------------------------------------+
