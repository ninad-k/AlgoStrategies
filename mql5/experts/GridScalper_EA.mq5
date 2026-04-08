//+------------------------------------------------------------------+
//|                                      GridScalper_EA.mq5          |
//|      Grid Scalper EA with Interactive Dashboard Panel             |
//|      Dollar-based grid, trailing stop, adaptive spacing           |
//|      Grid Scalper Bot                                             |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property description "GridScalper - Dollar Based Grid EA with Interactive Panel"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| ENUMERATIONS                                                     |
//+------------------------------------------------------------------+
enum ENUM_PANEL_SIDE
{
   SIDE_LEFT,    // Left
   SIDE_RIGHT    // Right
};

enum ENUM_GRID_MODE
{
   MODE_STATIC,   // Static Spacing
   MODE_DYNAMIC   // Dynamic (10/20/30/40% bands)
};

enum ENUM_TRADE_DIR
{
   DIR_BUY,    // BUY Only
   DIR_SELL,   // SELL Only
   DIR_BOTH    // BOTH
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
input group "--- UI SETTINGS ---"
input ENUM_PANEL_SIDE InpSide          = SIDE_LEFT;    // Panel Side
input color           InpPanelColor    = C'15,15,15';  // Panel Color

input group "--- UI DISPLAY SECTIONS ---"
input bool InpShowStats    = true;   // Show Performance Statistics
input bool InpShowAccount  = true;   // Show Account Overview
input bool InpShowMarket   = true;   // Show Market & Goal Status
input bool InpShowLogs     = true;   // Show Live System Logs

input group "--- ADAPTIVE LOGIC SETTINGS ---"
input ENUM_GRID_MODE InpGridMode = MODE_DYNAMIC;  // Choose Spacing & Trailing Style

input group "--- GRID SCALPER (DOLLAR BASED) ---"
input ENUM_TRADE_DIR InpTradeDir       = DIR_BUY;   // Trade direction
input double         InpStartLot       = 0.01;      // Start lot
input double         InpLotStep        = 0.01;      // Lot step
input double         InpGridGap        = 150.0;     // Grid gap (USD)
input int            InpMaxPositions   = 20;        // Max positions
input double         InpFixedTP        = 150.0;     // TP (USD) - Used if Trailing is OFF
input double         InpMaxSpread      = 20.0;      // Max spread
input int            InpMagicNumber    = 999999;    // Magic number
input bool           InpShowNextLevel  = true;      // Show next level
input bool           InpCloseOpposite  = false;     // Close ALL opposite Opened Positions

input group "--- TRAILING STOP SETTINGS ---"
input bool   InpUseTrailing      = true;    // Use Trailing instead of Fixed TP
input double InpTrailStart       = 150.0;   // Start trailing when price moves X from bottom
input double InpTrailDistance    = 20.0;    // Trailing Stop distance (USD)

input group "--- DAILY TARGET & LOSS ---"
input bool   InpUseDailyTarget   = false;   // Use daily target (Realized + Floating)
input double InpDailyGoal        = 1000.0;  // Daily profit goal
input bool   InpUseDailyLoss     = false;   // Use daily max loss (Realized + Floating)
input double InpDailyMaxLoss     = 1000.0;  // Max Loss (Input as positive number)

input group "--- MARKET & NEWS ---"
input bool   InpSessionFilter    = false;   // Session filter
input bool   InpIST              = true;    // IST time (true=IST, false=Broker)
input int    InpStartHour        = 10;      // Start hour
input int    InpEndHour          = 22;      // End hour
input bool   InpNewsFilter       = false;   // News filter
input int    InpNewsBuffer       = 60;      // News buffer (minutes)

//+------------------------------------------------------------------+
//| CONSTANTS                                                        |
//+------------------------------------------------------------------+
#define PREFIX          "GS_"
#define PANEL_WIDTH     320
#define ROW_HEIGHT      18
#define FONT_SIZE       8
#define FONT_NAME       "Consolas"
#define BTN_HEIGHT      25
#define BTN_WIDTH       70
#define PADDING         8
#define IST_OFFSET      19800  // +5:30 in seconds

//+------------------------------------------------------------------+
//| GLOBAL STATE                                                     |
//+------------------------------------------------------------------+
CTrade g_trade;

// --- Runtime direction (can be changed via buttons)
ENUM_TRADE_DIR g_activeDir;
bool           g_isStopped = false;

// --- Grid tracking
struct GridLevel
{
   ulong  ticket;
   double openPrice;
   double lotSize;
   int    level;       // 0 = first, 1 = second, etc.
   int    direction;   // 0=buy, 1=sell
};
GridLevel g_buyGrid[];
GridLevel g_sellGrid[];

// --- P&L tracking
double g_realizedPnL     = 0;
double g_floatingPnL     = 0;
double g_dayStartBalance = 0;
int    g_dayOfYear       = -1;

// --- Max required margin tracking
double g_maxRequiredMargin = 0;

// --- Trailing peak P&L tracking
double g_buyPeakPnL  = 0;
double g_sellPeakPnL = 0;

// --- Log messages
#define MAX_LOGS 5
string g_logs[MAX_LOGS];
int    g_logCount = 0;

// --- Panel state
int    g_panelX = 0;
int    g_panelY = 0;
int    g_panelHeight = 0;

// --- Tick tracking
datetime g_lastTrailCheck = 0;

//+------------------------------------------------------------------+
//| INITIALIZATION                                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_activeDir = InpTradeDir;
   g_isStopped = false;

   // Initialize day tracking
   MqlDateTime dt;
   TimeCurrent(dt);
   g_dayOfYear = dt.day_of_year;
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);

   // Sync existing positions into grid arrays
   SyncGridFromPositions();

   // Calculate realized P&L from today's history
   CalcTodayRealizedPnL();

   // Panel position
   g_panelX = (InpSide == SIDE_LEFT) ? 10 : (int)(ChartGetInteger(0, CHART_WIDTH_IN_PIXELS) - PANEL_WIDTH - 10);
   g_panelY = 25;

   // Build panel
   BuildPanel();
   UpdatePanel();

   AddLog("EA initialized | " + EnumToString(g_activeDir));

   ChartRedraw(0);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| DEINITIALIZATION                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, PREFIX);
   Comment("");
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| MAIN TICK                                                        |
//+------------------------------------------------------------------+
void OnTick()
{
   // --- Day rollover
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day_of_year != g_dayOfYear)
   {
      g_dayOfYear = dt.day_of_year;
      g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      g_realizedPnL = 0;
      AddLog("New day - counters reset");
   }

   // --- Calculate floating P&L
   CalcFloatingPnL();

   // --- Check daily limits
   if(CheckDailyLimits()) { UpdatePanel(); return; }

   // --- Session filter
   if(InpSessionFilter && !IsSessionOpen()) { UpdatePanel(); return; }

   // --- If stopped, only update panel
   if(g_isStopped) { UpdatePanel(); return; }

   // --- Spread filter (InpMaxSpread is in points/pips)
   double spreadPoints = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   if(spreadPoints > InpMaxSpread)
   {
      UpdatePanel();
      return;
   }

   // --- Grid logic
   if(g_activeDir == DIR_BUY || g_activeDir == DIR_BOTH)
      ProcessGrid(0); // BUY side

   if(g_activeDir == DIR_SELL || g_activeDir == DIR_BOTH)
      ProcessGrid(1); // SELL side

   // --- Trailing / TP management
   ManageExits();

   // --- Update panel
   UpdatePanel();
}

//+------------------------------------------------------------------+
//| CHART EVENT (Button clicks)                                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      string name = sparam;

      if(name == PREFIX + "BTN_BUY")
      {
         if(InpCloseOpposite) CloseAllDirection(1); // close sells
         g_activeDir = DIR_BUY;
         g_isStopped = false;
         AddLog("Direction -> BUY ONLY");
         ResetButtonStates();
      }
      else if(name == PREFIX + "BTN_SELL")
      {
         if(InpCloseOpposite) CloseAllDirection(0); // close buys
         g_activeDir = DIR_SELL;
         g_isStopped = false;
         AddLog("Direction -> SELL ONLY");
         ResetButtonStates();
      }
      else if(name == PREFIX + "BTN_BOTH")
      {
         g_activeDir = DIR_BOTH;
         g_isStopped = false;
         AddLog("Direction -> BOTH");
         ResetButtonStates();
      }
      else if(name == PREFIX + "BTN_STOP")
      {
         g_isStopped = true;
         AddLog("STOPPED - No new trades");
         ResetButtonStates();
      }
      else if(name == PREFIX + "BTN_CLOSEALL")
      {
         CloseAllPositions();
         AddLog("CLOSE ALL executed");
         ResetButtonStates();
      }

      UpdatePanel();
      ChartRedraw(0);
   }

   // Handle chart resize for right-side panel
   if(id == CHARTEVENT_CHART_CHANGE && InpSide == SIDE_RIGHT)
   {
      int newX = (int)(ChartGetInteger(0, CHART_WIDTH_IN_PIXELS) - PANEL_WIDTH - 10);
      if(newX != g_panelX)
      {
         g_panelX = newX;
         ObjectsDeleteAll(0, PREFIX);
         BuildPanel();
         UpdatePanel();
         ChartRedraw(0);
      }
   }
}

//+------------------------------------------------------------------+
//| GRID PROCESSING                                                  |
//+------------------------------------------------------------------+
void ProcessGrid(int side) // 0=buy, 1=sell
{
   if(side == 0)
      ProcessGridSide(g_buyGrid, side);
   else
      ProcessGridSide(g_sellGrid, side);
}

void ProcessGridSide(GridLevel &grid[], int side)
{
   int count = ArraySize(grid);

   // If no positions on this side, open first trade
   if(count == 0)
   {
      double lot = InpStartLot;
      if(OpenTrade(side, lot, 0))
         AddLog(StringFormat("%s L0 @ %.2f [%.2f]", (side==0?"BUY":"SELL"),
                SymbolInfoDouble(_Symbol, (side==0?SYMBOL_ASK:SYMBOL_BID)), lot));
      return;
   }

   // Check if we can add another grid level
   if(count >= InpMaxPositions) return;

   // Get the worst price (last entry)
   double lastPrice = grid[count - 1].openPrice;
   double currentPrice = (side == 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                     : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Calculate required gap for next level
   double gap = GetGridGap(count);

   // For BUY: price must drop by gap; For SELL: price must rise by gap
   bool shouldOpen = false;
   if(side == 0 && currentPrice <= lastPrice - gap)
      shouldOpen = true;
   if(side == 1 && currentPrice >= lastPrice + gap)
      shouldOpen = true;

   if(shouldOpen)
   {
      double lot = InpStartLot + InpLotStep * count;
      // Validate lot
      double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      lot = MathMax(minLot, MathMin(maxLot, MathRound(lot / lotStep) * lotStep));

      if(OpenTrade(side, lot, count))
         AddLog(StringFormat("%s L%d @ %.2f [%.2f]",
                (side==0?"BUY":"SELL"), count, currentPrice, lot));
   }
}

//+------------------------------------------------------------------+
//| GET GRID GAP (Static or Dynamic)                                 |
//+------------------------------------------------------------------+
double GetGridGap(int level)
{
   if(InpGridMode == MODE_STATIC)
      return InpGridGap;

   // MODE_DYNAMIC: split into 4 bands (10%, 20%, 30%, 40% of max positions)
   // Band 1 (0-10%): gap * 0.5
   // Band 2 (10-30%): gap * 0.75
   // Band 3 (30-60%): gap * 1.0
   // Band 4 (60-100%): gap * 1.5
   double pct = (InpMaxPositions > 0) ? (double)level / InpMaxPositions : 0;

   if(pct < 0.10)      return InpGridGap * 0.5;
   else if(pct < 0.30) return InpGridGap * 0.75;
   else if(pct < 0.60) return InpGridGap * 1.0;
   else                 return InpGridGap * 1.5;
}

//+------------------------------------------------------------------+
//| GET TRAILING PARAMS (Static or Dynamic)                          |
//+------------------------------------------------------------------+
void GetTrailingParams(int level, double &startDist, double &trailDist)
{
   if(InpGridMode == MODE_STATIC)
   {
      startDist = InpTrailStart;
      trailDist = InpTrailDistance;
      return;
   }

   // Dynamic: tighter trailing for early levels, wider for deep levels
   double pct = (InpMaxPositions > 0) ? (double)level / InpMaxPositions : 0;

   if(pct < 0.10)      { startDist = InpTrailStart * 0.5;  trailDist = InpTrailDistance * 0.5;  }
   else if(pct < 0.30) { startDist = InpTrailStart * 0.75; trailDist = InpTrailDistance * 0.75; }
   else if(pct < 0.60) { startDist = InpTrailStart * 1.0;  trailDist = InpTrailDistance * 1.0;  }
   else                 { startDist = InpTrailStart * 1.5;  trailDist = InpTrailDistance * 1.5;  }
}

//+------------------------------------------------------------------+
//| OPEN TRADE                                                       |
//+------------------------------------------------------------------+
bool OpenTrade(int side, double lot, int level)
{
   bool result = false;
   string comment = StringFormat("GS_%d_L%d", InpMagicNumber, level);

   if(side == 0)
      result = g_trade.Buy(lot, _Symbol, 0, 0, 0, comment);
   else
      result = g_trade.Sell(lot, _Symbol, 0, 0, 0, comment);

   if(result)
   {
      GridLevel gl;
      gl.ticket = g_trade.ResultDeal();
      // Get actual fill price
      if(gl.ticket > 0)
      {
         if(HistoryDealSelect(gl.ticket))
            gl.openPrice = HistoryDealGetDouble(gl.ticket, DEAL_PRICE);
         else
            gl.openPrice = (side == 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      }
      else
         gl.openPrice = (side == 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

      gl.lotSize = lot;
      gl.level = level;
      gl.direction = side;

      // Find position ticket from the deal
      if(gl.ticket > 0 && HistoryDealSelect(gl.ticket))
         gl.ticket = HistoryDealGetInteger(gl.ticket, DEAL_POSITION_ID);
      else
         gl.ticket = g_trade.ResultOrder();

      int sz;
      if(side == 0)
      {
         sz = ArraySize(g_buyGrid);
         ArrayResize(g_buyGrid, sz + 1);
         g_buyGrid[sz] = gl;
      }
      else
      {
         sz = ArraySize(g_sellGrid);
         ArrayResize(g_sellGrid, sz + 1);
         g_sellGrid[sz] = gl;
      }
   }

   return result;
}

//+------------------------------------------------------------------+
//| MANAGE EXITS (Trailing or Fixed TP)                              |
//+------------------------------------------------------------------+
void ManageExits()
{
   ManageExitSide(g_buyGrid, 0);
   ManageExitSide(g_sellGrid, 1);
}

void ManageExitSide(GridLevel &grid[], int side)
{
   int count = ArraySize(grid);
   if(count == 0) return;

   // Calculate total P&L for this side
   double totalPnL = 0;
   double totalLots = 0;
   double weightedPrice = 0;

   for(int i = 0; i < count; i++)
   {
      double posProfit = GetPositionProfit(grid[i].ticket);
      totalPnL += posProfit;
      totalLots += grid[i].lotSize;
      weightedPrice += grid[i].openPrice * grid[i].lotSize;
   }

   double avgPrice = (totalLots > 0) ? weightedPrice / totalLots : 0;

   if(InpUseTrailing)
   {
      // Get trailing params based on deepest level
      double startDist, trailDist;
      GetTrailingParams(count - 1, startDist, trailDist);

      // Track peak profit using globals
      double peakPnL = (side == 0) ? g_buyPeakPnL : g_sellPeakPnL;

      // Update peak
      if(totalPnL > peakPnL) peakPnL = totalPnL;

      // Write back to global
      if(side == 0) g_buyPeakPnL = peakPnL;
      else          g_sellPeakPnL = peakPnL;

      // Once peak exceeds startDist, trailing is active
      // Close when P&L retraces by trailDist from peak
      if(peakPnL >= startDist && totalPnL <= peakPnL - trailDist && totalPnL > 0)
      {
         double closedPnL = totalPnL;
         CloseGridSide(grid, side);
         g_realizedPnL += closedPnL;
         if(side == 0) g_buyPeakPnL = 0;
         else          g_sellPeakPnL = 0;
         AddLog(StringFormat("TRAIL CLOSE %s P&L:%.2f", (side==0?"BUY":"SELL"), closedPnL));
         return;
      }

      // Reset peak if no positions
      if(ArraySize(grid) == 0)
      {
         if(side == 0) g_buyPeakPnL = 0;
         else          g_sellPeakPnL = 0;
      }
   }
   else
   {
      // Fixed TP
      if(totalPnL >= InpFixedTP)
      {
         CloseGridSide(grid, side);
         g_realizedPnL += totalPnL;
         AddLog(StringFormat("TP HIT %s P&L:%.2f", (side==0?"BUY":"SELL"), totalPnL));
      }
   }
}

//+------------------------------------------------------------------+
//| GET POSITION PROFIT by ticket                                    |
//+------------------------------------------------------------------+
double GetPositionProfit(ulong posId)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      // Match by position ID or ticket
      if(ticket == posId || PositionGetInteger(POSITION_IDENTIFIER) == (long)posId)
         return PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
   return 0;
}

//+------------------------------------------------------------------+
//| CLOSE GRID SIDE                                                  |
//+------------------------------------------------------------------+
void CloseGridSide(GridLevel &grid[], int side)
{
   for(int i = ArraySize(grid) - 1; i >= 0; i--)
   {
      // Try to close by position ID
      for(int j = PositionsTotal() - 1; j >= 0; j--)
      {
         ulong ticket = PositionGetTicket(j);
         if(ticket == 0) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         if(PositionGetInteger(POSITION_IDENTIFIER) == (long)grid[i].ticket ||
            ticket == grid[i].ticket)
         {
            g_trade.PositionClose(ticket);
            break;
         }
      }
   }
   ArrayResize(grid, 0);
}

//+------------------------------------------------------------------+
//| CLOSE ALL POSITIONS                                              |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      g_trade.PositionClose(ticket);
   }
   ArrayResize(g_buyGrid, 0);
   ArrayResize(g_sellGrid, 0);
}

//+------------------------------------------------------------------+
//| CLOSE ALL of one direction                                       |
//+------------------------------------------------------------------+
void CloseAllDirection(int side) // 0=buy, 1=sell
{
   ENUM_POSITION_TYPE ptype = (side == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_TYPE) == ptype)
         g_trade.PositionClose(ticket);
   }
   if(side == 0)
      ArrayResize(g_buyGrid, 0);
   else
      ArrayResize(g_sellGrid, 0);
}

//+------------------------------------------------------------------+
//| SYNC GRID FROM EXISTING POSITIONS                                |
//+------------------------------------------------------------------+
void SyncGridFromPositions()
{
   ArrayResize(g_buyGrid, 0);
   ArrayResize(g_sellGrid, 0);

   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      GridLevel gl;
      gl.ticket = PositionGetInteger(POSITION_IDENTIFIER);
      gl.openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      gl.lotSize = PositionGetDouble(POSITION_VOLUME);
      gl.direction = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 0 : 1;

      // Determine level from comment if available
      string cmt = PositionGetString(POSITION_COMMENT);
      gl.level = 0;
      int pos = StringFind(cmt, "_L");
      if(pos >= 0)
      {
         string lvlStr = StringSubstr(cmt, pos + 2);
         gl.level = (int)StringToInteger(lvlStr);
      }

      int sz;
      if(gl.direction == 0)
      {
         sz = ArraySize(g_buyGrid);
         ArrayResize(g_buyGrid, sz + 1);
         g_buyGrid[sz] = gl;
      }
      else
      {
         sz = ArraySize(g_sellGrid);
         ArrayResize(g_sellGrid, sz + 1);
         g_sellGrid[sz] = gl;
      }
   }

   // Sort by open price (buys descending, sells ascending)
   SortGrid(g_buyGrid, 0);
   SortGrid(g_sellGrid, 1);
}

//+------------------------------------------------------------------+
//| SORT GRID by price                                               |
//+------------------------------------------------------------------+
void SortGrid(GridLevel &grid[], int side)
{
   int n = ArraySize(grid);
   for(int i = 0; i < n - 1; i++)
   {
      for(int j = i + 1; j < n; j++)
      {
         bool swap = false;
         if(side == 0) // BUY: highest price first (first trade), lowest last (deepest)
            swap = (grid[j].openPrice > grid[i].openPrice);
         else          // SELL: lowest price first, highest last (deepest)
            swap = (grid[j].openPrice < grid[i].openPrice);

         if(swap)
         {
            GridLevel tmp = grid[i];
            grid[i] = grid[j];
            grid[j] = tmp;
         }
      }
   }
   // Reassign levels
   for(int i = 0; i < n; i++)
      grid[i].level = i;
}

//+------------------------------------------------------------------+
//| CALCULATE FLOATING P&L                                           |
//+------------------------------------------------------------------+
void CalcFloatingPnL()
{
   g_floatingPnL = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      g_floatingPnL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
}

//+------------------------------------------------------------------+
//| CALCULATE TODAY'S REALIZED P&L from history                      |
//+------------------------------------------------------------------+
void CalcTodayRealizedPnL()
{
   g_realizedPnL = 0;

   MqlDateTime dt;
   TimeCurrent(dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   if(!HistorySelect(dayStart, TimeCurrent())) return;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      {
         g_realizedPnL += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                        + HistoryDealGetDouble(ticket, DEAL_SWAP)
                        + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      }
   }
}

//+------------------------------------------------------------------+
//| CHECK DAILY LIMITS                                               |
//+------------------------------------------------------------------+
bool CheckDailyLimits()
{
   double totalPnL = g_realizedPnL + g_floatingPnL;

   if(InpUseDailyTarget && totalPnL >= InpDailyGoal)
   {
      if(!g_isStopped)
      {
         AddLog(StringFormat("DAILY GOAL HIT: %.2f", totalPnL));
         g_isStopped = true;
      }
      return true;
   }

   if(InpUseDailyLoss && totalPnL <= -InpDailyMaxLoss)
   {
      if(!g_isStopped)
      {
         AddLog(StringFormat("DAILY LOSS HIT: %.2f", totalPnL));
         g_isStopped = true;
      }
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| SESSION FILTER                                                   |
//+------------------------------------------------------------------+
bool IsSessionOpen()
{
   datetime now = TimeCurrent();
   if(InpIST) now += IST_OFFSET;

   MqlDateTime dt;
   TimeToStruct(now, dt);

   if(InpStartHour < InpEndHour)
      return (dt.hour >= InpStartHour && dt.hour < InpEndHour);
   else // overnight session
      return (dt.hour >= InpStartHour || dt.hour < InpEndHour);
}

//+------------------------------------------------------------------+
//| ADD LOG MESSAGE                                                  |
//+------------------------------------------------------------------+
void AddLog(string msg)
{
   // Shift logs down
   for(int i = MAX_LOGS - 1; i > 0; i--)
      g_logs[i] = g_logs[i - 1];

   MqlDateTime dt;
   TimeCurrent(dt);
   g_logs[0] = StringFormat("[%02d:%02d] %s", dt.hour, dt.min, msg);
   if(g_logCount < MAX_LOGS) g_logCount++;

   Print("GS: ", msg);
}

//+------------------------------------------------------------------+
//|                                                                  |
//|                    PANEL / DASHBOARD                              |
//|                                                                  |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| CREATE PANEL BACKGROUND                                          |
//+------------------------------------------------------------------+
void CreatePanelBG(string name, int x, int y, int w, int h, color bgColor)
{
   ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bgColor);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, clrDimGray);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
//| CREATE TEXT LABEL                                                 |
//+------------------------------------------------------------------+
void CreateLabel(string name, int x, int y, string text, color clr, int fontSize = FONT_SIZE)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_FONT, FONT_NAME);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
//| CREATE BUTTON                                                    |
//+------------------------------------------------------------------+
void CreateButton(string name, int x, int y, int w, int h, string text, color bgClr, color txtClr)
{
   ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_FONT, FONT_NAME);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, FONT_SIZE);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bgClr);
   ObjectSetInteger(0, name, OBJPROP_COLOR, txtClr);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, clrDimGray);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
//| BUILD PANEL                                                      |
//+------------------------------------------------------------------+
void BuildPanel()
{
   int x = g_panelX;
   int y = g_panelY;
   int row = 0;

   // Calculate total panel height
   int totalRows = 3; // Title + direction buttons + stop/close buttons
   if(InpShowStats)   totalRows += 10;
   if(InpShowAccount) totalRows += 5;
   if(InpShowMarket)  totalRows += 7;
   if(InpShowLogs)    totalRows += MAX_LOGS + 2;
   totalRows += 4; // spacing between sections

   g_panelHeight = totalRows * ROW_HEIGHT + PADDING * 2 + BTN_HEIGHT * 2 + 10;

   // Main background
   CreatePanelBG(PREFIX + "BG", x, y, PANEL_WIDTH, g_panelHeight, InpPanelColor);

   int cy = y + PADDING;
   int cx = x + PADDING;
   int contentWidth = PANEL_WIDTH - PADDING * 2;

   // --- TITLE
   CreateLabel(PREFIX + "TITLE", cx, cy, "GRID SCALPER", clrGold, 11);
   cy += ROW_HEIGHT + 2;
   CreateLabel(PREFIX + "SUBTITLE", cx, cy, _Symbol + " | " + EnumToString((ENUM_TIMEFRAMES)Period()), clrSilver, 8);
   cy += ROW_HEIGHT + 4;

   // --- DIRECTION BUTTONS ROW
   int btnW3 = (contentWidth - 8) / 3;
   CreateButton(PREFIX + "BTN_BUY",  cx,               cy, btnW3, BTN_HEIGHT, "BUY",  clrDarkGreen, clrWhite);
   CreateButton(PREFIX + "BTN_SELL", cx + btnW3 + 4,   cy, btnW3, BTN_HEIGHT, "SELL", clrDarkRed,   clrWhite);
   CreateButton(PREFIX + "BTN_BOTH", cx + (btnW3+4)*2, cy, btnW3, BTN_HEIGHT, "BOTH", clrDarkSlateGray, clrWhite);
   cy += BTN_HEIGHT + 4;

   // --- STOP / CLOSE ALL ROW
   int btnW2 = (contentWidth - 4) / 2;
   CreateButton(PREFIX + "BTN_STOP",     cx,            cy, btnW2, BTN_HEIGHT, "STOP",      clrOrange,  clrBlack);
   CreateButton(PREFIX + "BTN_CLOSEALL", cx + btnW2 + 4, cy, btnW2, BTN_HEIGHT, "CLOSE ALL", clrFireBrick, clrWhite);
   cy += BTN_HEIGHT + 8;

   // --- PERFORMANCE STATISTICS
   if(InpShowStats)
   {
      CreateLabel(PREFIX + "STATS_HDR", cx, cy, ">>> PERFORMANCE STATISTICS <<<", clrCyan, 8);
      cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "LBL_STATUS",   cx, cy, "STATUS:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_STATUS",    cx + 120, cy - ROW_HEIGHT, "---", clrLime);

      CreateLabel(PREFIX + "LBL_GRIDMODE", cx, cy, "GRID MODE:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_GRIDMODE",  cx + 120, cy - ROW_HEIGHT, "---", clrYellow);

      CreateLabel(PREFIX + "LBL_POS",      cx, cy, "POSITIONS:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_POS",       cx + 120, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_NEXTBUY",  cx, cy, "NEXT BUY:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_NEXTBUY",   cx + 120, cy - ROW_HEIGHT, "---", clrLime);

      CreateLabel(PREFIX + "LBL_NEXTSELL", cx, cy, "NEXT SELL:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_NEXTSELL",  cx + 120, cy - ROW_HEIGHT, "---", clrRed);

      CreateLabel(PREFIX + "LBL_SPREAD",   cx, cy, "SPREAD:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_SPREAD",    cx + 120, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_REALIZED", cx, cy, "REALIZED:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_REALIZED",  cx + 120, cy - ROW_HEIGHT, "---", clrLime);

      CreateLabel(PREFIX + "LBL_FLOATING", cx, cy, "FLOATING:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_FLOATING",  cx + 120, cy - ROW_HEIGHT, "---", clrYellow);

      CreateLabel(PREFIX + "LBL_MAXREQ",   cx, cy, "MAX REQ$:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_MAXREQ",    cx + 120, cy - ROW_HEIGHT, "---", clrOrange);

      cy += 4;
   }

   // --- ACCOUNT OVERVIEW
   if(InpShowAccount)
   {
      CreateLabel(PREFIX + "ACCT_HDR", cx, cy, ">>> ACCOUNT OVERVIEW <<<", clrCyan, 8);
      cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "LBL_BAL",    cx, cy, "BALANCE:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_BAL",     cx + 120, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_EQUITY", cx, cy, "EQUITY:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_EQUITY",  cx + 120, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_MARGIN", cx, cy, "MARGIN:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_MARGIN",  cx + 120, cy - ROW_HEIGHT, "---", clrWhite);

      cy += 4;
   }

   // --- MARKET & GOAL STATUS
   if(InpShowMarket)
   {
      CreateLabel(PREFIX + "MKT_HDR", cx, cy, ">>> MARKET & GOAL STATUS <<<", clrCyan, 8);
      cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "LBL_DGOAL",   cx, cy, "DAILY GOAL:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_DGOAL",    cx + 130, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_DLOSS",   cx, cy, "DAILY LOSS:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_DLOSS",    cx + 130, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_SWAP",    cx, cy, "SWAP MODE:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_SWAP",     cx + 130, cy - ROW_HEIGHT, "---", clrYellow);

      CreateLabel(PREFIX + "LBL_SESSION", cx, cy, "SESSION:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_SESSION",  cx + 130, cy - ROW_HEIGHT, "---", clrWhite);

      CreateLabel(PREFIX + "LBL_NEWS",    cx, cy, "NEWS:", clrDimGray); cy += ROW_HEIGHT;
      CreateLabel(PREFIX + "VAL_NEWS",     cx + 130, cy - ROW_HEIGHT, "---", clrWhite);

      cy += 4;
   }

   // --- LIVE SYSTEM LOG
   if(InpShowLogs)
   {
      CreateLabel(PREFIX + "LOG_HDR", cx, cy, ">>> LIVE SYSTEM LOG <<<", clrCyan, 8);
      cy += ROW_HEIGHT;
      for(int i = 0; i < MAX_LOGS; i++)
      {
         CreateLabel(PREFIX + "LOG_" + IntegerToString(i), cx, cy, "", clrDimGray, 7);
         cy += ROW_HEIGHT - 2;
      }
      cy += 4;
   }

   // Adjust background height
   g_panelHeight = cy - y + PADDING;
   ObjectSetInteger(0, PREFIX + "BG", OBJPROP_YSIZE, g_panelHeight);
}

//+------------------------------------------------------------------+
//| UPDATE PANEL VALUES                                              |
//+------------------------------------------------------------------+
void UpdatePanel()
{
   int buyCount = ArraySize(g_buyGrid);
   int sellCount = ArraySize(g_sellGrid);

   // --- Status
   string statusText = g_isStopped ? "STOPPED" : "RUNNING";
   color  statusClr  = g_isStopped ? clrRed : clrLime;
   SetLabelText(PREFIX + "VAL_STATUS", statusText, statusClr);

   // --- Grid Mode
   string modeText = "";
   if(InpGridMode == MODE_DYNAMIC)
   {
      // Show adaptive ratios for buy and sell
      double buyMult = 1.0, sellMult = 1.0;
      if(buyCount > 0)
      {
         double pct = (double)buyCount / InpMaxPositions;
         if(pct < 0.10) buyMult = 0.5;
         else if(pct < 0.30) buyMult = 0.75;
         else if(pct < 0.60) buyMult = 1.0;
         else buyMult = 1.5;
      }
      if(sellCount > 0)
      {
         double pct = (double)sellCount / InpMaxPositions;
         if(pct < 0.10) sellMult = 0.5;
         else if(pct < 0.30) sellMult = 0.75;
         else if(pct < 0.60) sellMult = 1.0;
         else sellMult = 1.5;
      }
      modeText = StringFormat("ADAPTIVE (B:%.1fx/S:%.1fx)", buyMult, sellMult);
   }
   else
      modeText = "STATIC";
   SetLabelText(PREFIX + "VAL_GRIDMODE", modeText, clrYellow);

   // --- Positions
   string posText = StringFormat("%dB | %dS [Max:%d]", buyCount, sellCount, InpMaxPositions);
   SetLabelText(PREFIX + "VAL_POS", posText, clrWhite);

   // --- Next buy/sell levels
   if(InpShowNextLevel && InpShowStats)
   {
      if(g_activeDir == DIR_BUY || g_activeDir == DIR_BOTH)
      {
         if(buyCount > 0 && buyCount < InpMaxPositions)
         {
            double nextBuyPrice = g_buyGrid[buyCount - 1].openPrice - GetGridGap(buyCount);
            SetLabelText(PREFIX + "VAL_NEXTBUY",
                        StringFormat("B:%.2f @ %.2f [%.2f]", InpStartLot + InpLotStep * buyCount,
                                    nextBuyPrice, GetGridGap(buyCount)), clrLime);
         }
         else if(buyCount == 0)
            SetLabelText(PREFIX + "VAL_NEXTBUY", "Waiting for entry...", clrLime);
         else
            SetLabelText(PREFIX + "VAL_NEXTBUY", "MAX REACHED", clrOrange);
      }
      else
         SetLabelText(PREFIX + "VAL_NEXTBUY", "OFF", clrDimGray);

      if(g_activeDir == DIR_SELL || g_activeDir == DIR_BOTH)
      {
         if(sellCount > 0 && sellCount < InpMaxPositions)
         {
            double nextSellPrice = g_sellGrid[sellCount - 1].openPrice + GetGridGap(sellCount);
            SetLabelText(PREFIX + "VAL_NEXTSELL",
                        StringFormat("S:%.2f @ %.2f [%.2f]", InpStartLot + InpLotStep * sellCount,
                                    nextSellPrice, GetGridGap(sellCount)), clrRed);
         }
         else if(sellCount == 0)
            SetLabelText(PREFIX + "VAL_NEXTSELL", "Waiting for entry...", clrRed);
         else
            SetLabelText(PREFIX + "VAL_NEXTSELL", "MAX REACHED", clrOrange);
      }
      else
         SetLabelText(PREFIX + "VAL_NEXTSELL", "OFF", clrDimGray);
   }

   // --- Spread (in points)
   double spreadPts = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   color spreadClr = (spreadPts > InpMaxSpread) ? clrRed : clrWhite;
   SetLabelText(PREFIX + "VAL_SPREAD",
               StringFormat("%.2f [Max:%.2f]", spreadPts, InpMaxSpread), spreadClr);

   // --- Realized
   color realClr = (g_realizedPnL >= 0) ? clrLime : clrRed;
   SetLabelText(PREFIX + "VAL_REALIZED",
               StringFormat("$ %.2f", g_realizedPnL), realClr);

   // --- Floating
   color floatClr = (g_floatingPnL >= 0) ? clrLime : clrRed;
   SetLabelText(PREFIX + "VAL_FLOATING",
               StringFormat("$ %.2f", g_floatingPnL), floatClr);

   // --- Max Required
   double totalMargin = AccountInfoDouble(ACCOUNT_MARGIN);
   if(totalMargin > g_maxRequiredMargin) g_maxRequiredMargin = totalMargin;

   // Calculate coverage and max lots
   double covLots = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      covLots += PositionGetDouble(POSITION_VOLUME);
   }
   SetLabelText(PREFIX + "VAL_MAXREQ",
               StringFormat("$%.0f [Cov: $%.0f | %.2f Lots]",
                           g_maxRequiredMargin, totalMargin, covLots), clrOrange);

   // --- Account
   if(InpShowAccount)
   {
      SetLabelText(PREFIX + "VAL_BAL",
                  StringFormat("$ %.2f", AccountInfoDouble(ACCOUNT_BALANCE)), clrWhite);

      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      double margin = AccountInfoDouble(ACCOUNT_MARGIN);
      SetLabelText(PREFIX + "VAL_EQUITY",
                  StringFormat("$ %.2f [MARGIN: $ %.2f]", equity, margin),
                  (equity >= AccountInfoDouble(ACCOUNT_BALANCE)) ? clrLime : clrOrange);

      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      double marginLevel = (margin > 0) ? (equity / margin * 100) : 0;
      SetLabelText(PREFIX + "VAL_MARGIN",
                  StringFormat("Free: $ %.2f | Level: %.0f%%", freeMargin, marginLevel), clrWhite);
   }

   // --- Market & Goal
   if(InpShowMarket)
   {
      // Daily goal
      if(InpUseDailyTarget)
         SetLabelText(PREFIX + "VAL_DGOAL",
                     StringFormat("%.2f [ON]", InpDailyGoal), clrLime);
      else
         SetLabelText(PREFIX + "VAL_DGOAL",
                     StringFormat("%.2f [OFF]", InpDailyGoal), clrDimGray);

      // Daily loss
      if(InpUseDailyLoss)
         SetLabelText(PREFIX + "VAL_DLOSS",
                     StringFormat("%.2f [ON]", InpDailyMaxLoss), clrRed);
      else
         SetLabelText(PREFIX + "VAL_DLOSS",
                     StringFormat("%.2f [OFF]", InpDailyMaxLoss), clrDimGray);

      // Swap mode
      SetLabelText(PREFIX + "VAL_SWAP", "KEEP OPPOSITE", clrYellow);

      // Session
      if(InpSessionFilter)
      {
         bool open = IsSessionOpen();
         SetLabelText(PREFIX + "VAL_SESSION",
                     (open ? "OPEN" : "CLOSED") + StringFormat(" (%d-%d)", InpStartHour, InpEndHour),
                     open ? clrLime : clrRed);
      }
      else
         SetLabelText(PREFIX + "VAL_SESSION", "NO FILTER", clrDimGray);

      // News
      if(InpNewsFilter)
         SetLabelText(PREFIX + "VAL_NEWS", StringFormat("ON [Buffer:%dmin]", InpNewsBuffer), clrYellow);
      else
         SetLabelText(PREFIX + "VAL_NEWS", "OFF", clrDimGray);
   }

   // --- Logs
   if(InpShowLogs)
   {
      for(int i = 0; i < MAX_LOGS; i++)
      {
         string logName = PREFIX + "LOG_" + IntegerToString(i);
         if(i < g_logCount)
            SetLabelText(logName, g_logs[i], (i == 0) ? clrWhite : clrDimGray);
         else
            SetLabelText(logName, "", clrDimGray);
      }
   }

   // --- Update trailing status in log header area
   if(InpShowLogs)
   {
      string trailText = "";
      if(g_activeDir == DIR_BUY || g_activeDir == DIR_BOTH)
         trailText += StringFormat("Monitoring BUY only (%d levels)", buyCount);
      if(g_activeDir == DIR_SELL || g_activeDir == DIR_BOTH)
      {
         if(trailText != "") trailText += " | ";
         trailText += StringFormat("SELL (%d levels)", sellCount);
      }
      if(InpUseTrailing) trailText += " | Trailing ON";
      // Use log header subtitle if desired
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| SET LABEL TEXT helper                                             |
//+------------------------------------------------------------------+
void SetLabelText(string name, string text, color clr)
{
   if(ObjectFind(0, name) >= 0)
   {
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   }
}

//+------------------------------------------------------------------+
//| RESET BUTTON STATES                                              |
//+------------------------------------------------------------------+
void ResetButtonStates()
{
   ObjectSetInteger(0, PREFIX + "BTN_BUY",  OBJPROP_STATE, false);
   ObjectSetInteger(0, PREFIX + "BTN_SELL", OBJPROP_STATE, false);
   ObjectSetInteger(0, PREFIX + "BTN_BOTH", OBJPROP_STATE, false);
   ObjectSetInteger(0, PREFIX + "BTN_STOP", OBJPROP_STATE, false);
   ObjectSetInteger(0, PREFIX + "BTN_CLOSEALL", OBJPROP_STATE, false);
}
//+------------------------------------------------------------------+
