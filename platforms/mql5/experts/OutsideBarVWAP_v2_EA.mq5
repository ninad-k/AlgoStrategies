//+------------------------------------------------------------------+
//|                                     OutsideBarVWAP_v2_EA.mq5      |
//|            Outside Bar Breakout + Session VWAP — v2               |
//|                                                                   |
//|  v2 adds the nuances emphasised in the source tutorial that v1    |
//|  under-weighted:                                                  |
//|                                                                   |
//|   1. VWAP-PROXIMITY FILTER (critical)                             |
//|      Setups are only traded when the outside bar forms near VWAP; |
//|      bars far from VWAP are ignored. Rationale: stops are tiny    |
//|      near VWAP, probability of getting hit is lower.              |
//|                                                                   |
//|   2. BAR-SIZE "SWEET SPOT"                                        |
//|      Min AND max bar range (vs ATR). Skip tiny noise bars and     |
//|      oversized bars — we want the "छोटी सी आउटसाइड बार" setup.    |
//|                                                                   |
//|   3. VOLUME CONFIRMATION                                          |
//|      Outside bar tick-volume must be > average × multiplier       |
//|      (engulfing trap on above-average participation).             |
//|                                                                   |
//|   4. PARTIAL TP + RUNNER                                          |
//|      Close part at 1R, trail the rest to breakeven/VWAP.          |
//|                                                                   |
//|   5. LOSS COOLDOWN                                                |
//|      Pause N bars after consecutive losing trades.                |
//|                                                                   |
//|   6. ON-CHART VISUALS                                             |
//|      Outside-bar boxes, entry arrows, VWAP line, stats dashboard. |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "2.00"
#property description "Outside Bar + Session VWAP v2 — proximity filter, bar sweet-spot, volume, partial TP, cooldown, chart visuals"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\DealInfo.mqh>

CTrade        g_trade;
CPositionInfo g_pos;
CDealInfo     g_deal;

//============================================================
//  ENUMERATIONS
//============================================================
enum ENUM_SL_LIMIT_MODE
  {
   SL_LIMIT_ATR,      // Max SL distance = ATR * multiplier
   SL_LIMIT_PCT,      // Max SL distance = % of price
   SL_LIMIT_POINTS,   // Max SL distance = fixed points
   SL_LIMIT_OFF,      // Disable max SL filter
  };

enum ENUM_TP_MODE
  {
   TP_RR_MULTIPLE,    // TP at R-multiple of SL distance
   TP_POINTS,         // TP at fixed points
   TP_OFF,            // No TP (trail only)
  };

enum ENUM_PROX_MODE
  {
   PROX_PCT,          // % distance from VWAP
   PROX_ATR,          // ATR multiple from VWAP
   PROX_OFF,          // Disable proximity filter
  };

//============================================================
//  INPUTS — OUTSIDE BAR DETECTION
//============================================================
input group "━━━ Outside Bar Detection ━━━"
input bool   InpStrictOutside  = true;    // Strict outside bar (H>prevH AND L<prevL)
input bool   InpRequireClose   = false;   // Require directional close beyond prev extreme
input double InpMinRangeATR    = 0.5;     // Min bar range (ATR mult) — 0 = off
input double InpMaxRangeATR    = 2.0;     // Max bar range (ATR mult) — keeps SL small
input int    InpATRPeriod      = 14;      // ATR period

//============================================================
//  INPUTS — VWAP & PROXIMITY
//============================================================
input group "━━━ VWAP Filter ━━━"
input bool           InpUseVWAP            = true;    // Enable VWAP bias filter
input int            InpSessionHour        = 9;       // Session start hour (server time)
input int            InpSessionMin         = 15;      // Session start minute (09:15 = NSE)
input bool           InpRequireBarAboveVWAP = true;   // Bar close must be on bias side of VWAP

input group "━━━ VWAP Proximity (critical filter) ━━━"
input ENUM_PROX_MODE InpProxMode           = PROX_ATR; // Proximity mode
input double         InpMaxProxATR         = 1.0;     // Max distance from VWAP in ATR
input double         InpMaxProxPct         = 0.3;     // Max distance from VWAP in %

//============================================================
//  INPUTS — VOLUME CONFIRMATION
//============================================================
input group "━━━ Volume Confirmation ━━━"
input bool   InpUseVolume      = true;    // Require above-average volume
input int    InpVolumeLookback = 20;      // Bars for volume average
input double InpMinVolumeMult  = 1.2;     // Bar volume ≥ avg × mult

//============================================================
//  INPUTS — RISK LIMIT (absolute SL cap)
//============================================================
input group "━━━ Risk / Stop-Loss Cap ━━━"
input ENUM_SL_LIMIT_MODE InpSLLimitMode = SL_LIMIT_ATR; // Max SL size mode
input double InpMaxSLATRMult   = 2.0;     // Max SL distance = ATR × this
input double InpMaxSLPct       = 0.5;     // Max SL distance as % of price
input int    InpMaxSLPoints    = 3000;    // Max SL distance in points

//============================================================
//  INPUTS — PENDING / ENTRY
//============================================================
input group "━━━ Pending Order Behaviour ━━━"
input int    InpPendingExpiryBars = 3;    // Cancel pending after N bars
input int    InpEntryBufferPoints = 0;    // Points beyond extreme to trigger

input group "━━━ Direction ━━━"
input bool   InpAllowLong      = true;    // Allow long breakouts
input bool   InpAllowShort     = true;    // Allow short breakdowns

//============================================================
//  INPUTS — EXITS
//============================================================
input group "━━━ Take Profit & Scaling ━━━"
input ENUM_TP_MODE InpTPMode   = TP_RR_MULTIPLE;  // TP mode
input double InpTPRRMult       = 2.0;     // Final TP R-multiple (of SL)
input int    InpTPPoints       = 0;       // TP points (TP_POINTS mode)
input bool   InpUsePartialTP   = true;    // Enable partial close at 1R
input double InpPartialRRMult  = 1.0;     // Partial TP at this R-multiple
input double InpPartialClosePct= 50.0;    // % of position closed at partial TP

input group "━━━ Trailing ━━━"
input bool   InpTrailToBE      = true;    // Move SL to BE after partial TP
input bool   InpTrailVWAP      = false;   // Trail SL along VWAP in profit

//============================================================
//  INPUTS — SESSION WINDOW
//============================================================
input group "━━━ Session Window ━━━"
input bool   InpUseSessionWindow = false; // Only trade inside window
input int    InpWinStartH      = 9;       // Window start hour
input int    InpWinStartM      = 30;      // Window start minute
input int    InpWinEndH        = 15;      // Window end hour
input int    InpWinEndM        = 0;       // Window end minute

//============================================================
//  INPUTS — COOLDOWN
//============================================================
input group "━━━ Loss Cooldown ━━━"
input bool   InpUseCooldown    = true;    // Enable cooldown after losses
input int    InpCooldownLosses = 2;       // Trigger after N consecutive losses
input int    InpCooldownBars   = 10;      // Pause for N bars after trigger

//============================================================
//  INPUTS — TRADE MGMT
//============================================================
input group "━━━ Trade Management ━━━"
input double InpLotSize        = 0.1;     // Fixed lot size
input double InpRiskPctBalance = 0.0;     // Risk % of balance (0 = fixed lot)
input int    InpMaxPositions   = 1;       // Max open positions
input int    InpMaxPendings    = 1;       // Max pending orders
input int    InpMagic          = 20260417; // Magic number
input string InpComment        = "OBVWAP2"; // Order comment

//============================================================
//  INPUTS — VISUALS
//============================================================
input group "━━━ Chart Visuals ━━━"
input bool   InpDrawVWAP       = true;    // Plot VWAP line
input bool   InpDrawOutsideBars = true;   // Highlight outside bars (box)
input bool   InpDrawArrows     = true;    // Arrows on entry/exit
input bool   InpShowDashboard  = true;    // Show stats dashboard
input color  InpColorVWAP      = clrYellow;
input color  InpColorBullBox   = clrLimeGreen;
input color  InpColorBearBox   = clrTomato;

//============================================================
//  GLOBALS
//============================================================
datetime g_lastBar     = 0;
datetime g_lastSession = 0;
double   g_vwap        = 0.0;
int      g_atrHandle   = INVALID_HANDLE;

int      g_consecLosses = 0;
datetime g_cooldownUntilBar = 0;

struct PendingInfo { ulong ticket; datetime placedBar; bool partialDone; };
PendingInfo g_pendings[];

// Track live positions for partial-TP state
struct PositionState { ulong ticket; bool partialDone; double origVolume; };
PositionState g_posStates[];

// Stats
int    g_statSetups = 0;
int    g_statTrades = 0;
int    g_statWins   = 0;
int    g_statLosses = 0;
double g_statRsum   = 0.0;   // cumulative R

string VWAP_LINE_NAME = "OBV2_VWAP";
string DASH_PREFIX    = "OBV2_DASH_";

//============================================================
//  INIT / DEINIT
//============================================================
int OnInit()
  {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);

   g_atrHandle = iATR(_Symbol, _Period, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     { Print("ATR handle creation failed"); return INIT_FAILED; }

   CleanupObjects();
   Print("OutsideBarVWAP_v2 EA v2.00 — ", _Symbol, " ", EnumToString((ENUM_TIMEFRAMES)_Period));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   CleanupObjects();
  }

void CleanupObjects()
  {
   ObjectDelete(0, VWAP_LINE_NAME);
   int total = ObjectsTotal(0, 0, -1);
   for(int i = total - 1; i >= 0; i--)
     {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, "OBV2_") == 0) ObjectDelete(0, name);
     }
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

   // Update stats from recently closed deals
   UpdateStatsFromHistory();

   // Expire stale pending orders
   ExpirePendings();

   // Recalc VWAP on new bar
   if(InpUseVWAP) g_vwap = CalcSessionVWAP();
   DrawVWAPLine();
   DrawDashboard();

   // Cooldown gate
   if(InpUseCooldown && barTime < g_cooldownUntilBar) return;

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
   double hi1 = iHigh(_Symbol,  _Period, 1);
   double lo1 = iLow(_Symbol,   _Period, 1);
   double cl1 = iClose(_Symbol, _Period, 1);
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

   g_statSetups++;

   double atr = GetATR();

   // Bar-range sweet spot (ATR band)
   if(atr > 0.0)
     {
      if(InpMinRangeATR > 0.0 && barRange < atr * InpMinRangeATR) return;
      if(InpMaxRangeATR > 0.0 && barRange > atr * InpMaxRangeATR) return;
     }

   // Volume confirmation
   if(InpUseVolume && !PassVolumeFilter()) return;

   // Direction via VWAP bias
   bool canLong  = InpAllowLong;
   bool canShort = InpAllowShort;
   if(InpUseVWAP && g_vwap > 0.0)
     {
      double ref = InpRequireBarAboveVWAP ? cl1 : (hi1 + lo1) * 0.5;
      if(ref <= g_vwap) canLong  = false;
      if(ref >= g_vwap) canShort = false;
     }

   // Proximity to VWAP — the key v2 filter
   if(InpUseVWAP && g_vwap > 0.0 && !PassProximityFilter(cl1, atr)) return;

   if(InpRequireClose)
     {
      if(canLong  && cl1 <= hi2) canLong  = false;
      if(canShort && cl1 >= lo2) canShort = false;
     }

   if(!canLong && !canShort) return;

   if(!PassSLSizeFilter(barRange)) return;

   // Draw box on the outside bar
   if(InpDrawOutsideBars)
      DrawOutsideBarBox(iTime(_Symbol, _Period, 1), hi1, lo1, canLong);

   double bufPrice = InpEntryBufferPoints * _Point;

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
   double risk = MathAbs(entry - sl);
   if(risk <= 0.0) return 0.0;
   double dist = risk * InpTPRRMult;
   return NormalizeDouble(isLong ? entry + dist : entry - dist, _Digits);
  }

//============================================================
//  FILTERS
//============================================================
double GetATR()
  {
   if(g_atrHandle == INVALID_HANDLE) return 0.0;
   double atr[];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) < 1) return 0.0;
   return atr[0];
  }

bool PassVolumeFilter()
  {
   long vols[];
   ArraySetAsSeries(vols, true);
   int need = InpVolumeLookback + 1;
   if(CopyTickVolume(_Symbol, _Period, 1, need, vols) < need) return true;

   double sum = 0;
   for(int i = 1; i < need; i++) sum += (double)vols[i];
   double avg = sum / (double)(need - 1);
   if(avg <= 0) return true;

   return ((double)vols[0] >= avg * InpMinVolumeMult);
  }

bool PassProximityFilter(double price, double atr)
  {
   if(InpProxMode == PROX_OFF) return true;
   double dist = MathAbs(price - g_vwap);

   if(InpProxMode == PROX_ATR)
     {
      if(atr <= 0) return true;
      return (dist <= atr * InpMaxProxATR);
     }
   // PROX_PCT
   if(g_vwap <= 0) return true;
   double pct = dist / g_vwap * 100.0;
   return (pct <= InpMaxProxPct);
  }

bool PassSLSizeFilter(double slDistance)
  {
   if(InpSLLimitMode == SL_LIMIT_OFF) return true;

   if(InpSLLimitMode == SL_LIMIT_POINTS)
      return (slDistance <= InpMaxSLPoints * _Point);

   if(InpSLLimitMode == SL_LIMIT_PCT)
     {
      double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(price <= 0) return true;
      return ((slDistance / price * 100.0) <= InpMaxSLPct);
     }
   // ATR
   double atr = GetATR();
   if(atr <= 0) return true;
   return (slDistance <= atr * InpMaxSLATRMult);
  }

bool PassSessionWindow()
  {
   if(!InpUseSessionWindow) return true;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int nowMin   = dt.hour * 60 + dt.min;
   int startMin = InpWinStartH * 60 + InpWinStartM;
   int endMin   = InpWinEndH   * 60 + InpWinEndM;
   if(startMin < endMin) return (nowMin >= startMin && nowMin < endMin);
   return (nowMin >= startMin || nowMin < endMin);
  }

//============================================================
//  VWAP (session-based)
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
   if(now < sessStart) sessStart -= 86400;
   g_lastSession = sessStart;

   MqlRates rates[];
   int copied = CopyRates(_Symbol, _Period, sessStart, now, rates);
   if(copied < 1) return 0.0;

   double sumTPV = 0, sumVol = 0;
   for(int i = 0; i < copied; i++)
     {
      double tp  = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      double vol = (double)rates[i].tick_volume;
      if(vol < 1.0) vol = 1.0;
      sumTPV += tp * vol;
      sumVol += vol;
     }
   return (sumVol > 0) ? sumTPV / sumVol : 0.0;
  }

//============================================================
//  ORDER LIFECYCLE
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

   if(!ok) { Print("Pending failed: ", g_trade.ResultRetcodeDescription()); return; }

   ulong ticket = g_trade.ResultOrder();
   if(ticket == 0) return;

   int n = ArraySize(g_pendings);
   ArrayResize(g_pendings, n + 1);
   g_pendings[n].ticket      = ticket;
   g_pendings[n].placedBar   = iTime(_Symbol, _Period, 0);
   g_pendings[n].partialDone = false;

   if(InpDrawArrows)
      DrawEntryArrow(type == ORDER_TYPE_BUY_STOP, price);
  }

void ExpirePendings()
  {
   for(int i = ArraySize(g_pendings) - 1; i >= 0; i--)
     {
      ulong t = g_pendings[i].ticket;
      if(!OrderSelect(t)) { RemovePendingAt(i); continue; }

      int barsSince = iBarShift(_Symbol, _Period, g_pendings[i].placedBar, false);
      if(barsSince >= InpPendingExpiryBars)
        {
         if(g_trade.OrderDelete(t)) RemovePendingAt(i);
        }
     }
  }

void RemovePendingAt(int idx)
  {
   int sz = ArraySize(g_pendings);
   if(idx < 0 || idx >= sz) return;
   for(int i = idx; i < sz - 1; i++) g_pendings[i] = g_pendings[i + 1];
   ArrayResize(g_pendings, sz - 1);
  }

//============================================================
//  POSITION MANAGEMENT (partial TP, BE, VWAP trail)
//============================================================
void ManageOpenPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol || g_pos.Magic() != InpMagic) continue;

      ulong  ticket = g_pos.Ticket();
      double openPr = g_pos.PriceOpen();
      double sl     = g_pos.StopLoss();
      double tp     = g_pos.TakeProfit();
      double vol    = g_pos.Volume();
      double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      int stateIdx = FindOrCreateState(ticket, vol);
      bool isLong  = (g_pos.PositionType() == POSITION_TYPE_BUY);
      double risk  = isLong ? (openPr - sl) : (sl - openPr);
      if(risk <= 0.0) continue;

      double priceNow = isLong ? bid : ask;
      double progress = isLong ? (priceNow - openPr) : (openPr - priceNow);

      // Partial TP at configured R
      if(InpUsePartialTP && !g_posStates[stateIdx].partialDone)
        {
         if(progress >= risk * InpPartialRRMult)
           {
            double closeVol = NormalizeVolume(g_posStates[stateIdx].origVolume * InpPartialClosePct / 100.0);
            if(closeVol > 0.0 && closeVol < vol)
              {
               if(g_trade.PositionClosePartial(ticket, closeVol))
                 {
                  g_posStates[stateIdx].partialDone = true;
                  if(InpTrailToBE)
                     g_trade.PositionModify(ticket, NormalizeDouble(openPr, _Digits), tp);
                 }
              }
           }
        }

      // BE move when no partial-TP enabled
      if(!InpUsePartialTP && InpTrailToBE && progress >= risk)
        {
         bool needsMove = isLong ? (sl < openPr) : (sl == 0.0 || sl > openPr);
         if(needsMove)
            g_trade.PositionModify(ticket, NormalizeDouble(openPr, _Digits), tp);
        }

      // VWAP trail once profitable
      if(InpTrailVWAP && g_vwap > 0.0 && progress > 0)
        {
         if(isLong && g_vwap > sl && g_vwap < bid)
            g_trade.PositionModify(ticket, NormalizeDouble(g_vwap, _Digits), tp);
         else if(!isLong && (sl == 0.0 || g_vwap < sl) && g_vwap > ask)
            g_trade.PositionModify(ticket, NormalizeDouble(g_vwap, _Digits), tp);
        }
     }
   PruneClosedStates();
  }

int FindOrCreateState(ulong ticket, double vol)
  {
   for(int i = 0; i < ArraySize(g_posStates); i++)
      if(g_posStates[i].ticket == ticket) return i;
   int n = ArraySize(g_posStates);
   ArrayResize(g_posStates, n + 1);
   g_posStates[n].ticket      = ticket;
   g_posStates[n].partialDone = false;
   g_posStates[n].origVolume  = vol;
   return n;
  }

void PruneClosedStates()
  {
   for(int i = ArraySize(g_posStates) - 1; i >= 0; i--)
     {
      if(!PositionSelectByTicket(g_posStates[i].ticket))
        {
         int sz = ArraySize(g_posStates);
         for(int j = i; j < sz - 1; j++) g_posStates[j] = g_posStates[j + 1];
         ArrayResize(g_posStates, sz - 1);
        }
     }
  }

//============================================================
//  STATS & COOLDOWN (from closed history)
//============================================================
datetime g_lastDealScanned = 0;

void UpdateStatsFromHistory()
  {
   datetime from = (g_lastDealScanned > 0) ? g_lastDealScanned : (TimeCurrent() - 7 * 86400);
   datetime to   = TimeCurrent();
   HistorySelect(from, to);
   int deals = HistoryDealsTotal();

   for(int i = 0; i < deals; i++)
     {
      ulong dt = HistoryDealGetTicket(i);
      if(dt == 0) continue;
      if((long)HistoryDealGetInteger(dt, DEAL_MAGIC) != InpMagic) continue;
      if((string)HistoryDealGetString(dt, DEAL_SYMBOL) != _Symbol) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(dt, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;

      datetime dtime = (datetime)HistoryDealGetInteger(dt, DEAL_TIME);
      if(dtime <= g_lastDealScanned) continue;

      double profit = HistoryDealGetDouble(dt, DEAL_PROFIT)
                    + HistoryDealGetDouble(dt, DEAL_SWAP)
                    + HistoryDealGetDouble(dt, DEAL_COMMISSION);

      g_statTrades++;
      if(profit > 0)  { g_statWins++;   g_consecLosses = 0; }
      else if(profit < 0)
        {
         g_statLosses++;
         g_consecLosses++;
         if(InpUseCooldown && g_consecLosses >= InpCooldownLosses)
           {
            g_cooldownUntilBar = iTime(_Symbol, _Period, 0) + InpCooldownBars * PeriodSeconds(_Period);
            PrintFormat("Cooldown triggered: %d losses → paused until %s",
                        g_consecLosses, TimeToString(g_cooldownUntilBar));
            g_consecLosses = 0;
           }
        }

      if(dtime > g_lastDealScanned) g_lastDealScanned = dtime;
     }
  }

//============================================================
//  LOT SIZING
//============================================================
double CalcLotSize(double entry, double sl)
  {
   if(InpRiskPctBalance <= 0.0)
      return NormalizeVolume(InpLotSize);

   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskCash = balance * InpRiskPctBalance / 100.0;

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return NormalizeVolume(InpLotSize);

   double slDist = MathAbs(entry - sl);
   if(slDist <= 0.0) return NormalizeVolume(InpLotSize);

   double lossPerLot = (slDist / tickSize) * tickValue;
   if(lossPerLot <= 0.0) return NormalizeVolume(InpLotSize);

   return NormalizeVolume(riskCash / lossPerLot);
  }

double NormalizeVolume(double vol)
  {
   double minV  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepV <= 0.0) stepV = 0.01;
   vol = MathFloor(vol / stepV) * stepV;
   if(vol < minV) vol = 0.0;          // below min → can't trade
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
      if(g_pos.SelectByIndex(i) &&
         g_pos.Symbol() == _Symbol &&
         g_pos.Magic()  == InpMagic) n++;
   return n;
  }

int CountPendings()
  {
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0) continue;
      if((string)OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((long)OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      n++;
     }
   return n;
  }

//============================================================
//  VISUALS
//============================================================
void DrawVWAPLine()
  {
   if(!InpDrawVWAP || g_vwap <= 0) { ObjectDelete(0, VWAP_LINE_NAME); return; }
   if(ObjectFind(0, VWAP_LINE_NAME) < 0)
      ObjectCreate(0, VWAP_LINE_NAME, OBJ_HLINE, 0, 0, g_vwap);
   ObjectSetDouble (0, VWAP_LINE_NAME, OBJPROP_PRICE,      g_vwap);
   ObjectSetInteger(0, VWAP_LINE_NAME, OBJPROP_COLOR,      InpColorVWAP);
   ObjectSetInteger(0, VWAP_LINE_NAME, OBJPROP_WIDTH,      2);
   ObjectSetInteger(0, VWAP_LINE_NAME, OBJPROP_STYLE,      STYLE_DOT);
   ObjectSetInteger(0, VWAP_LINE_NAME, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, VWAP_LINE_NAME, OBJPROP_BACK,       true);
   ObjectSetString (0, VWAP_LINE_NAME, OBJPROP_TOOLTIP,
                    "Session VWAP: " + DoubleToString(g_vwap, _Digits));
  }

void DrawOutsideBarBox(datetime t, double hi, double lo, bool bullish)
  {
   string name = "OBV2_OB_" + IntegerToString((long)t);
   datetime t2 = t + PeriodSeconds(_Period);
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t, hi, t2, lo);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      bullish ? InpColorBullBox : InpColorBearBox);
   ObjectSetInteger(0, name, OBJPROP_FILL,       true);
   ObjectSetInteger(0, name, OBJPROP_BACK,       true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,      1);
  }

void DrawEntryArrow(bool isLong, double price)
  {
   string name = "OBV2_ARR_" + IntegerToString((long)TimeCurrent()) + "_" +
                 IntegerToString((long)(price * MathPow(10, _Digits)));
   datetime t = iTime(_Symbol, _Period, 0);
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE,
                    isLong ? 233 : 234);    // up/down arrow
   ObjectSetInteger(0, name, OBJPROP_COLOR,
                    isLong ? InpColorBullBox : InpColorBearBox);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
  }

void DrawDashboard()
  {
   if(!InpShowDashboard) return;

   double winPct = (g_statTrades > 0)
                   ? 100.0 * g_statWins / (double)g_statTrades : 0.0;
   int x = 10, y = 24, dy = 18;
   string lines[7];
   lines[0] = StringFormat("OutsideBar+VWAP v2  (%s %s)",
                           _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period));
   lines[1] = StringFormat("VWAP: %s",
                           g_vwap > 0 ? DoubleToString(g_vwap, _Digits) : "-");
   lines[2] = StringFormat("Setups: %d   Trades: %d", g_statSetups, g_statTrades);
   lines[3] = StringFormat("W/L: %d/%d   WinRate: %.1f%%",
                           g_statWins, g_statLosses, winPct);
   lines[4] = StringFormat("ConsecLosses: %d", g_consecLosses);
   datetime barT = iTime(_Symbol, _Period, 0);
   lines[5] = (InpUseCooldown && barT < g_cooldownUntilBar)
              ? StringFormat("COOLDOWN until %s", TimeToString(g_cooldownUntilBar))
              : "Cooldown: inactive";
   lines[6] = StringFormat("OpenPos: %d  Pending: %d",
                           CountPositions(), CountPendings());

   for(int i = 0; i < 7; i++)
     {
      string name = DASH_PREFIX + IntegerToString(i);
      if(ObjectFind(0, name) < 0)
         ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y + i * dy);
      ObjectSetInteger(0, name, OBJPROP_COLOR,     clrWhite);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE,  9);
      ObjectSetString (0, name, OBJPROP_FONT,      "Consolas");
      ObjectSetString (0, name, OBJPROP_TEXT,      lines[i]);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_BACK,       false);
     }
  }
//+------------------------------------------------------------------+
