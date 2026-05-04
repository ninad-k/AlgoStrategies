//+------------------------------------------------------------------+
//| BearishEngulfingSuperTrend_GOLD_EA.mq5                            |
//| Bearish Engulfing entry on 2M timeframe, 1:2 RR, SuperTrend exit  |
//| - On entry: take full position                                    |
//| - At TP1 (1:2 RR): close 50%, move SL to breakeven               |
//| - At SuperTrend reversal: close remaining 50%                     |
//+------------------------------------------------------------------+
#property copyright "Ninad K"
#property version   "1.00"
#property description "Bearish Engulfing + SuperTrend scaling strategy for GOLD M2"
#property strict

input string   InpSymbol        = "GOLD";     // Symbol (XAUUSD, GOLD, etc.)
input double   InpRiskPercent   = 1.0;        // Risk % per trade
input int      InpSTrend_Period = 10;         // SuperTrend ATR period
input double   InpSTrend_Mult   = 3.0;        // SuperTrend multiplier
input int      InpMaxPositions  = 1;          // Max concurrent positions

input ulong    g_magic          = 10001;      // Magic number for order tracking

// State tracking
bool      g_inPosition     = false;
ulong     g_posTicket      = 0;
int       g_posStage       = 0;              // 0=initial, 1=TP1_hit, 2=exit_all
double    g_entryPrice     = 0;
double    g_stopLoss       = 0;
double    g_tp1            = 0;
double    g_tp2            = 0;
double    g_riskAmt        = 0;
double    g_lotSize        = 0;
datetime  g_entryTime      = 0;
int       g_strendDir      = 0;              // +1 uptrend, -1 downtrend

//--- Indicator handles
int h_atr = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!SymbolSelect(InpSymbol, true))
     {
      Print("Failed to select symbol: ", InpSymbol);
      return INIT_FAILED;
     }

   h_atr = iATR(InpSymbol, PERIOD_M2, InpSTrend_Period);
   if(h_atr == INVALID_HANDLE)
     {
      Print("Failed to create ATR handle");
      return INIT_FAILED;
     }

   g_inPosition = false;
   g_posTicket  = 0;
   g_posStage   = 0;

   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(h_atr != INVALID_HANDLE)
      IndicatorRelease(h_atr);
  }

//+------------------------------------------------------------------+
//| Helper: Get indicator value from a handle                         |
//+------------------------------------------------------------------+
double GetIndicatorValue(int handle, int shift, int buffer = 0)
  {
   if(handle == INVALID_HANDLE)
      return 0;
   double tmp[];
   if(CopyBuffer(handle, buffer, shift, 1, tmp) != 1)
      return 0;
   return tmp[0];
  }

//+------------------------------------------------------------------+
//| Helper: Calculate lot size from risk % and SL distance            |
//+------------------------------------------------------------------+
double CalcLotSize(double accountBalance, double riskPercent, double slDistance)
  {
   if(slDistance <= 0)
      return 0;

   double tickSize  = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_TICK_VALUE);

   if(tickSize <= 0 || tickValue <= 0)
      return 0.01;  // fallback

   double riskAmt   = accountBalance * (riskPercent / 100.0);
   double pipsRisk  = slDistance / tickSize;
   double lotSize   = riskAmt / (pipsRisk * tickValue);

   double minLot = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(InpSymbol, SYMBOL_VOLUME_STEP);

   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
   lotSize = MathRound(lotSize / step) * step;

   return lotSize;
  }

//+------------------------------------------------------------------+
//| Detect bearish engulfing: prev bullish, curr bearish, fully       |
//| engulfing (curr.open > prev.open && curr.close < prev.close)      |
//+------------------------------------------------------------------+
bool IsBearishEngulfing(const int shift)
  {
   MqlRates curr[], prev[];
   ArraySetAsSeries(curr, true);
   ArraySetAsSeries(prev, true);

   int copied = CopyRates(InpSymbol, PERIOD_M2, shift, 2, curr);
   if(copied < 2)
      return false;

   // curr = [0] (most recent), prev = [1]
   bool prevBull = (curr[1].close > curr[1].open);
   bool currBear = (curr[0].close < curr[0].open);
   bool engulfing = (curr[0].open > curr[1].open && curr[0].close < curr[1].close);

   return (prevBull && currBear && engulfing);
  }

//+------------------------------------------------------------------+
//| Calculate SuperTrend high/low/mid                                 |
//+------------------------------------------------------------------+
void CalcSuperTrend(int shift, double &st_high, double &st_low)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(InpSymbol, PERIOD_M2, shift, 1, rates) < 1)
     {
      st_high = 0;
      st_low  = 0;
      return;
     }

   double hl2 = (rates[0].high + rates[0].low) / 2.0;
   double atr = GetIndicatorValue(h_atr, shift);

   st_high = hl2 + (InpSTrend_Mult * atr);
   st_low  = hl2 - (InpSTrend_Mult * atr);
  }

//+------------------------------------------------------------------+
//| Detect SuperTrend direction change                                |
//+------------------------------------------------------------------+
int GetSuperTrendDir(int shift)
  {
   double st_h0, st_l0, st_h1, st_l1;
   CalcSuperTrend(shift, st_h0, st_l0);
   CalcSuperTrend(shift + 1, st_h1, st_l1);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(InpSymbol, PERIOD_M2, shift, 1, rates) < 1)
      return 0;

   // Simple: if close > st_high, uptrend; if close < st_low, downtrend
   if(rates[0].close > st_h0)
      return 1;
   else if(rates[0].close < st_l0)
      return -1;
   else
      return 0;
  }

//+------------------------------------------------------------------+
//| Check if an open position exists for this magic                   |
//+------------------------------------------------------------------+
bool GetOpenPosition(ulong &ticket, double &entryPrice, double &sl, double &tp)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong pos_ticket = PositionGetTicket(i);
      if(pos_ticket == 0)
         continue;

      if(PositionGetString(POSITION_SYMBOL) != InpSymbol)
         continue;

      if(PositionGetInteger(POSITION_MAGIC) != g_magic)
         continue;

      ticket     = pos_ticket;
      entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      sl         = PositionGetDouble(POSITION_SL);
      tp         = PositionGetDouble(POSITION_TP);
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Open a SHORT position (sell) at market                            |
//+------------------------------------------------------------------+
bool OpenShortPosition(double entryPrice, double slPrice, double tpPrice, double lot)
  {
   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action        = TRADE_ACTION_DEAL;
   request.symbol        = InpSymbol;
   request.type          = ORDER_TYPE_SELL;
   request.volume        = lot;
   request.price         = entryPrice;
   request.sl            = slPrice;
   request.tp            = tpPrice;
   request.magic         = g_magic;
   request.comment       = "BearishEngulfing_Entry";
   request.type_filling  = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
     {
      Print("Failed to open position: ", result.comment);
      return false;
     }

   if(result.deal != 0)
     {
      g_posTicket  = result.order;
      g_entryPrice = entryPrice;
      g_stopLoss   = slPrice;
      g_tp1        = tpPrice;
      g_entryTime  = TimeCurrent();
      g_posStage   = 0;
      g_inPosition = true;

      // TP2: SuperTrend reversal (set to a placeholder, updated dynamically)
      g_tp2 = g_entryPrice + (g_entryPrice - slPrice) * 2.0;

      Print("Opened SHORT at ", entryPrice, " SL=", slPrice, " TP1=", tpPrice, " TP2=", g_tp2);
      return true;
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Close partial position (50%) at TP1, move SL to breakeven         |
//+------------------------------------------------------------------+
bool ClosePartialTP1()
  {
   if(g_posTicket == 0)
      return false;

   if(PositionSelectByTicket(g_posTicket) == false)
      return false;

   double volume = PositionGetDouble(POSITION_VOLUME);
   double closeVol = volume * 0.5;  // 50%

   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action        = TRADE_ACTION_DEAL;
   request.symbol        = InpSymbol;
   request.type          = ORDER_TYPE_BUY;  // Close short = buy
   request.volume        = closeVol;
   request.price         = g_tp1;
   request.magic         = g_magic;
   request.comment       = "TP1_50pct";
   request.type_filling  = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
     {
      Print("Failed to close 50% at TP1: ", result.comment);
      return false;
     }

   // Move remaining SL to breakeven
   if(PositionSelectByTicket(g_posTicket))
     {
      MqlTradeRequest modRequest = {};
      MqlTradeResult modResult = {};

      modRequest.action   = TRADE_ACTION_SLTP;
      modRequest.symbol   = InpSymbol;
      modRequest.sl       = g_entryPrice;  // Breakeven
      modRequest.tp       = g_tp2;
      modRequest.position = g_posTicket;

      OrderSend(modRequest, modResult);
     }

   g_posStage = 1;
   Print("Closed 50% at TP1 (", g_tp1, "), moved SL to breakeven (", g_entryPrice, ")");
   return true;
  }

//+------------------------------------------------------------------+
//| Close remaining 50% at SuperTrend reversal or manually set TP2    |
//+------------------------------------------------------------------+
bool CloseRemainingSuperTrend()
  {
   if(g_posTicket == 0)
      return false;

   if(PositionSelectByTicket(g_posTicket) == false)
      return false;

   double volume = PositionGetDouble(POSITION_VOLUME);

   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   request.action        = TRADE_ACTION_DEAL;
   request.symbol        = InpSymbol;
   request.type          = ORDER_TYPE_BUY;  // Close short
   request.volume        = volume;
   request.price         = g_tp2;
   request.magic         = g_magic;
   request.comment       = "SuperTrend_Exit_50pct";
   request.type_filling  = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
     {
      Print("Failed to close remaining at SuperTrend: ", result.comment);
      return false;
     }

   g_inPosition = false;
   g_posTicket  = 0;
   g_posStage   = 2;
   Print("Closed remaining 50% at SuperTrend reversal (", g_tp2, ")");
   return true;
  }

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Check for open position
   ulong ticket = 0;
   double sl = 0, tp = 0;
   double entryP = 0;

   bool hasPos = GetOpenPosition(ticket, entryP, sl, tp);

   if(!hasPos)
     {
      // No position, look for entry signal
      if(g_inPosition)
        {
         g_inPosition = false;
         g_posTicket  = 0;
         g_posStage   = 0;
        }

      // Check for bearish engulfing at close of bar 1 (shift 1)
      if(IsBearishEngulfing(1))
        {
         MqlRates rates[];
         ArraySetAsSeries(rates, true);
         if(CopyRates(InpSymbol, PERIOD_M2, 1, 1, rates) < 1)
            return;

         double bid = SymbolInfoDouble(InpSymbol, SYMBOL_BID);
         double ask = SymbolInfoDouble(InpSymbol, SYMBOL_ASK);

         // For a SHORT (sell): entry at bid
         // SL: above the high of engulfing candle
         double entryPrice = bid;
         double slPrice    = rates[0].high + _Point * 5;  // buffer above high
         double slDistance = slPrice - entryPrice;

         // Calculate lot size (1% risk)
         double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
         double lotSize = CalcLotSize(accountBalance, InpRiskPercent, slDistance);

         if(lotSize > 0)
           {
            // TP1 at 1:2 ratio (entry - 2x SL distance)
            double tp1Price = entryPrice - (2.0 * slDistance);

            if(OpenShortPosition(entryPrice, slPrice, tp1Price, lotSize))
              {
               g_entryPrice = entryPrice;
               g_stopLoss   = slPrice;
               g_tp1        = tp1Price;
               g_riskAmt    = accountBalance * (InpRiskPercent / 100.0);
               g_lotSize    = lotSize;
              }
           }
        }
     }
   else
     {
      // Position is open, manage it
      MqlRates rates[];
      ArraySetAsSeries(rates, true);
      if(CopyRates(InpSymbol, PERIOD_M2, 0, 1, rates) < 1)
         return;

      double bid = SymbolInfoDouble(InpSymbol, SYMBOL_BID);

      // Stage 0: Initial entry, watch for TP1
      if(g_posStage == 0)
        {
         if(bid <= g_tp1)
           {
            ClosePartialTP1();
           }
        }

      // Stage 1: 50% closed at breakeven, watch for SuperTrend exit
      if(g_posStage == 1)
        {
         // Check SuperTrend direction
         int strendDir = GetSuperTrendDir(0);

         // For a short position, exit when SuperTrend reverses to uptrend
         if(strendDir == 1)
           {
            // Set TP2 at current price and exit
            g_tp2 = bid;
            CloseRemainingSuperTrend();
           }
        }
     }
  }
//+------------------------------------------------------------------+
