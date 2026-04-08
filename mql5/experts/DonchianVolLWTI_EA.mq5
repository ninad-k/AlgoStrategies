//+------------------------------------------------------------------+
//|                                            DonchianVolLWTI_EA.mq5 |
//|                                                  AlgoStrategies   |
//|  Donchian breakout EA filtered by Volume MA and LWTI direction.  |
//|  SL anchored to (and trailing) the Donchian basis line.          |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property link      ""
#property version   "1.00"
#property description "Buy/Sell on close beyond Donchian channel with volume>MA confirmation and LWTI slope. SL trails the DC basis. Partial TPs at 1R/2R, optional break-even, optional max-candle filter."

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum ENUM_LOT_MODE
  {
   LOT_FIXED    = 0, // Fixed lot
   LOT_RISK_PCT = 1  // Risk % of balance
  };

enum ENUM_SL_HIT_MODE
  {
   SL_CLOSE = 0, // Bar close beyond SL
   SL_TOUCH = 1  // Tick touches SL
  };

#define STATE_FLAT  0
#define STATE_LONG  1
#define STATE_SHORT -1

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
sinput string sep0 = "=== Donchian Settings ===";
input int  InpDcLength       = 96;          // Donchian Length
input int  InpDcOffset       = 0;           // Donchian Offset

sinput string sep1 = "=== Volume MA Settings ===";
input int                  InpVolMaLength = 30;          // Volume MA Length
input ENUM_MA_METHOD       InpVolMaMethod = MODE_SMA;    // Volume MA Method
input ENUM_APPLIED_VOLUME  InpVolType     = VOLUME_TICK; // Volume Type

sinput string sep2 = "=== LWTI Settings ===";
input int  InpLwtiPeriod    = 25;           // LWTI Period
input bool InpLwtiSmooth    = false;        // Smooth LWTI?
input int  InpLwtiSmoothPer = 20;           // LWTI Smoothing Period
input int  InpLwtiSlopeBars = 2;            // LWTI slope lookback (bars)

sinput string sep3 = "=== Entry Filters ===";
input int  InpMaxCandlePoints = 0;          // Max entry candle range in points (0=off)

sinput string sep4 = "=== Lot Sizing ===";
input ENUM_LOT_MODE InpLotMode  = LOT_FIXED; // Lot mode
input double        InpFixedLot = 0.10;      // Fixed lot
input double        InpRiskPct  = 1.0;       // Risk % (when Lot mode = Risk %)

sinput string sep5 = "=== TP / SL Management ===";
input ENUM_SL_HIT_MODE InpSLHitMode = SL_CLOSE; // SL trigger mode
input bool   InpTP1Enable = true;               // Enable TP1 (1R partial)
input double InpTP1Pct    = 50.0;               // TP1 close % of original lots
input bool   InpTP2Enable = true;               // Enable TP2 (2R, full close)
input bool   InpBreakEven = true;               // Move SL to entry after TP1

sinput string sep6 = "=== General ===";
input long   InpMagic   = 20250407;             // Magic number
input string InpComment = "DonchianVolLWTI";    // Order comment

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CTrade   g_Trade;

int      g_DcHandle   = INVALID_HANDLE;
int      g_VolHandle  = INVALID_HANDLE;
int      g_LwtiHandle = INVALID_HANDLE;

int      g_TradeState     = STATE_FLAT;
double   g_EntryPrice     = 0.0;
double   g_StopLoss       = 0.0;
double   g_OriginalLots   = 0.0;
double   g_RiskPoints     = 0.0;
bool     g_TP1Hit         = false;
bool     g_BreakEvenActive = false;
ulong    g_Ticket         = 0;

datetime g_LastBarTime    = 0;

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpDcLength < 1 || InpVolMaLength < 1 || InpLwtiPeriod < 1 || InpLwtiSmoothPer < 1)
     {
      Alert("Lengths/periods must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLwtiSlopeBars < 1)
     {
      Alert("LWTI slope bars must be >= 1");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpTP1Pct <= 0.0 || InpTP1Pct > 100.0)
     {
      Alert("InpTP1Pct must be in (0, 100]");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpFixedLot <= 0.0 || InpRiskPct <= 0.0)
     {
      Alert("Lot/risk inputs must be positive");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_Trade.SetExpertMagicNumber(InpMagic);
   g_Trade.SetDeviationInPoints(20);
   g_Trade.SetTypeFilling(ORDER_FILLING_FOK);

   g_DcHandle = iCustom(_Symbol, _Period, "Donchian Channels", InpDcLength, InpDcOffset);
   if(g_DcHandle == INVALID_HANDLE)
     {
      Print("Failed to load Donchian Channels indicator");
      return(INIT_FAILED);
     }

   g_VolHandle = iCustom(_Symbol, _Period, "Volumes_MA",
                         true, InpVolMaLength, InpVolMaMethod, InpVolType);
   if(g_VolHandle == INVALID_HANDLE)
     {
      Print("Failed to load Volumes_MA indicator");
      return(INIT_FAILED);
     }

   g_LwtiHandle = iCustom(_Symbol, _Period, "LarryWilliams_LargeTradeIndex",
                          InpLwtiPeriod, InpLwtiSmooth, 0 /*SMOOTH_SMA*/, InpLwtiSmoothPer);
   if(g_LwtiHandle == INVALID_HANDLE)
     {
      Print("Failed to load LarryWilliams_LargeTradeIndex indicator");
      return(INIT_FAILED);
     }

   Print("DonchianVolLWTI_EA initialized. Magic=", InpMagic,
         " DC=", InpDcLength, " VolMA=", InpVolMaLength, " LWTI=", InpLwtiPeriod);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_DcHandle   != INVALID_HANDLE) IndicatorRelease(g_DcHandle);
   if(g_VolHandle  != INVALID_HANDLE) IndicatorRelease(g_VolHandle);
   if(g_LwtiHandle != INVALID_HANDLE) IndicatorRelease(g_LwtiHandle);
  }

//+------------------------------------------------------------------+
//| Indicator buffer helpers                                         |
//+------------------------------------------------------------------+
bool GetDC(int shift, double &basis, double &upper, double &lower)
  {
   double b[1], u[1], l[1];
   if(CopyBuffer(g_DcHandle, 0, shift, 1, b) <= 0) return(false);
   if(CopyBuffer(g_DcHandle, 1, shift, 1, u) <= 0) return(false);
   if(CopyBuffer(g_DcHandle, 2, shift, 1, l) <= 0) return(false);
   basis = b[0]; upper = u[0]; lower = l[0];
   return(true);
  }

bool GetVol(int shift, double &vol, double &ma)
  {
   double v[1], m[1];
   if(CopyBuffer(g_VolHandle, 0, shift, 1, v) <= 0) return(false);
   if(CopyBuffer(g_VolHandle, 2, shift, 1, m) <= 0) return(false);
   vol = v[0]; ma = m[0];
   return(true);
  }

bool GetLwti(int shift, double &val)
  {
   double a[1];
   if(CopyBuffer(g_LwtiHandle, 0, shift, 1, a) <= 0) return(false);
   val = a[0];
   return(true);
  }

//+------------------------------------------------------------------+
//| Lot helpers                                                      |
//+------------------------------------------------------------------+
double NormalizeLots(double lots)
  {
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) return(minLot);
   lots = MathFloor(lots / stepLot) * stepLot;
   if(lots < minLot) lots = 0.0;
   if(lots > maxLot) lots = maxLot;
   return(NormalizeDouble(lots, 2));
  }

double CalcLot(double slPoints)
  {
   if(InpLotMode == LOT_FIXED || slPoints <= 0.0)
      return(NormalizeLots(InpFixedLot));

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPct / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0)
      return(NormalizeLots(InpFixedLot));

   double slMoney = (slPoints * _Point / tickSize) * tickValue;
   if(slMoney <= 0.0)
      return(NormalizeLots(InpFixedLot));

   double lot = riskMoney / slMoney;
   return(NormalizeLots(lot));
  }

//+------------------------------------------------------------------+
//| State management                                                 |
//+------------------------------------------------------------------+
void ResetState()
  {
   g_TradeState      = STATE_FLAT;
   g_EntryPrice      = 0.0;
   g_StopLoss        = 0.0;
   g_OriginalLots    = 0.0;
   g_RiskPoints      = 0.0;
   g_TP1Hit          = false;
   g_BreakEvenActive = false;
   g_Ticket          = 0;
  }

void SyncTradeState()
  {
   bool hasPos = PositionSelectByTicket(g_Ticket);
   if(!hasPos && g_TradeState != STATE_FLAT)
     {
      Print("Position no longer exists. Resetting state.");
      ResetState();
     }
  }

//+------------------------------------------------------------------+
//| Order helpers                                                    |
//+------------------------------------------------------------------+
bool ClosePartial(double lots, string tag)
  {
   if(!PositionSelectByTicket(g_Ticket)) return(false);
   double posVol = PositionGetDouble(POSITION_VOLUME);
   if(lots >= posVol) lots = posVol;
   lots = NormalizeLots(lots);
   if(lots <= 0.0) return(false);
   bool ok = g_Trade.PositionClosePartial(g_Ticket, lots, ULONG_MAX);
   Print("PartialClose [", tag, "] lots=", lots, " of ", posVol, " ok=", ok);
   return(ok);
  }

void CloseAll(string tag)
  {
   if(g_Ticket != 0 && PositionSelectByTicket(g_Ticket))
     {
      bool ok = g_Trade.PositionClose(g_Ticket, ULONG_MAX);
      Print("CloseAll [", tag, "] ok=", ok);
     }
   ResetState();
  }

//+------------------------------------------------------------------+
//| Open entry                                                       |
//+------------------------------------------------------------------+
void OpenEntry(int direction, double basis)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = (direction == STATE_LONG) ? ask : bid;

   double slDist = MathAbs(entry - basis);
   if(slDist <= 0.0)
     {
      Print("Skip entry: SL distance is zero");
      return;
     }
   double slPoints = slDist / _Point;
   double lots = CalcLot(slPoints);
   if(lots <= 0.0)
     {
      Print("Skip entry: lot rounded to 0 (slPoints=", slPoints, ")");
      return;
     }

   bool ok = false;
   if(direction == STATE_LONG)
      ok = g_Trade.Buy(lots, _Symbol, ask, 0, 0, InpComment + " L");
   else
      ok = g_Trade.Sell(lots, _Symbol, bid, 0, 0, InpComment + " S");

   if(!ok)
     {
      Print("Entry failed: retcode=", g_Trade.ResultRetcode(), " ", g_Trade.ResultComment());
      return;
     }

   g_Ticket          = g_Trade.ResultOrder();
   g_EntryPrice      = g_Trade.ResultPrice();
   if(g_EntryPrice <= 0.0) g_EntryPrice = entry;
   g_StopLoss        = basis;
   g_RiskPoints      = MathAbs(g_EntryPrice - g_StopLoss) / _Point;
   g_OriginalLots    = lots;
   g_TradeState      = direction;
   g_TP1Hit          = false;
   g_BreakEvenActive = false;

   Print("ENTRY ", (direction == STATE_LONG ? "LONG " : "SHORT "),
         "lots=", lots, " entry=", g_EntryPrice,
         " SL(basis)=", g_StopLoss, " R(pts)=", g_RiskPoints);
  }

//+------------------------------------------------------------------+
//| Partial TP processing                                            |
//+------------------------------------------------------------------+
void ProcessPartialTP(double highPrice, double lowPrice)
  {
   if(g_TradeState == STATE_FLAT || g_RiskPoints <= 0.0) return;
   double rPrice = g_RiskPoints * _Point;

   if(g_TradeState == STATE_LONG)
     {
      double tp1 = g_EntryPrice + rPrice;
      double tp2 = g_EntryPrice + 2.0 * rPrice;

      if(InpTP1Enable && !g_TP1Hit && highPrice >= tp1)
        {
         double lots = NormalizeLots(g_OriginalLots * InpTP1Pct / 100.0);
         if(lots > 0.0 && ClosePartial(lots, "TP1 1R"))
           {
            g_TP1Hit = true;
            if(InpBreakEven)
              {
               g_BreakEvenActive = true;
               if(g_StopLoss < g_EntryPrice) g_StopLoss = g_EntryPrice;
              }
           }
         return;
        }

      if(InpTP2Enable && highPrice >= tp2)
        {
         CloseAll("TP2 2R");
         return;
        }
     }
   else if(g_TradeState == STATE_SHORT)
     {
      double tp1 = g_EntryPrice - rPrice;
      double tp2 = g_EntryPrice - 2.0 * rPrice;

      if(InpTP1Enable && !g_TP1Hit && lowPrice <= tp1)
        {
         double lots = NormalizeLots(g_OriginalLots * InpTP1Pct / 100.0);
         if(lots > 0.0 && ClosePartial(lots, "TP1 1R"))
           {
            g_TP1Hit = true;
            if(InpBreakEven)
              {
               g_BreakEvenActive = true;
               if(g_StopLoss > g_EntryPrice) g_StopLoss = g_EntryPrice;
              }
           }
         return;
        }

      if(InpTP2Enable && lowPrice <= tp2)
        {
         CloseAll("TP2 2R");
         return;
        }
     }
  }

//+------------------------------------------------------------------+
//| SL check                                                         |
//+------------------------------------------------------------------+
void CheckSL(double bid, double ask, double closedClose, bool barClosed)
  {
   if(g_TradeState == STATE_FLAT || g_StopLoss <= 0.0) return;

   if(InpSLHitMode == SL_TOUCH)
     {
      if(g_TradeState == STATE_LONG && bid <= g_StopLoss)
         CloseAll("SL touch");
      else if(g_TradeState == STATE_SHORT && ask >= g_StopLoss)
         CloseAll("SL touch");
      return;
     }

   // SL_CLOSE: only act on a freshly closed bar
   if(!barClosed) return;
   if(g_TradeState == STATE_LONG && closedClose < g_StopLoss)
      CloseAll("SL close");
   else if(g_TradeState == STATE_SHORT && closedClose > g_StopLoss)
      CloseAll("SL close");
  }

//+------------------------------------------------------------------+
//| Update SL by trailing the Donchian basis                         |
//+------------------------------------------------------------------+
void UpdateBasisTrail()
  {
   if(g_TradeState == STATE_FLAT) return;
   double basis, upper, lower;
   if(!GetDC(1, basis, upper, lower)) return;

   double newSL = basis;
   if(g_BreakEvenActive)
     {
      if(g_TradeState == STATE_LONG  && newSL < g_EntryPrice) newSL = g_EntryPrice;
      if(g_TradeState == STATE_SHORT && newSL > g_EntryPrice) newSL = g_EntryPrice;
     }
   g_StopLoss = newSL;
  }

//+------------------------------------------------------------------+
//| Entry signal evaluation (called on new bar)                      |
//+------------------------------------------------------------------+
void TryEntry()
  {
   if(g_TradeState != STATE_FLAT) return;

   int needBars = InpDcLength + InpLwtiSlopeBars + 5;
   if(Bars(_Symbol, _Period) < needBars) return;

   double basis1, upper1, lower1;
   double basis2, upper2, lower2;
   if(!GetDC(1, basis1, upper1, lower1)) return;
   if(!GetDC(2, basis2, upper2, lower2)) return;

   double vol1, ma1;
   if(!GetVol(1, vol1, ma1)) return;
   if(ma1 == EMPTY_VALUE) return;

   double lwti1, lwtiN;
   if(!GetLwti(1, lwti1)) return;
   if(!GetLwti(1 + InpLwtiSlopeBars, lwtiN)) return;

   double close1 = iClose(_Symbol, _Period, 1);
   double close2 = iClose(_Symbol, _Period, 2);
   double open1  = iOpen (_Symbol, _Period, 1);
   double high1  = iHigh (_Symbol, _Period, 1);
   double low1   = iLow  (_Symbol, _Period, 1);

   if(InpMaxCandlePoints > 0)
     {
      double rangePts = (high1 - low1) / _Point;
      if(rangePts > InpMaxCandlePoints)
        {
         // Skip oversized candle
         return;
        }
     }

   bool dcBuyBreak  = (close2 <= upper2) && (close1 > upper1);
   bool dcSellBreak = (close2 >= lower2) && (close1 < lower1);

   bool volUp = (vol1 > ma1) && (close1 > open1);
   bool volDn = (vol1 > ma1) && (close1 < open1);

   bool lwtiUp = (lwti1 > 50.0) && (lwti1 > lwtiN);
   bool lwtiDn = (lwti1 < 50.0) && (lwti1 < lwtiN);

   if(dcBuyBreak && volUp && lwtiUp)
      OpenEntry(STATE_LONG, basis1);
   else if(dcSellBreak && volDn && lwtiDn)
      OpenEntry(STATE_SHORT, basis1);
  }

//+------------------------------------------------------------------+
//| Tick handler                                                     |
//+------------------------------------------------------------------+
void OnTick()
  {
   SyncTradeState();

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double high0 = iHigh(_Symbol, _Period, 0);
   double low0  = iLow (_Symbol, _Period, 0);

   // Intra-bar management
   if(g_TradeState != STATE_FLAT)
     {
      ProcessPartialTP(high0, low0);
      // After partial TP a position may have been fully closed
      if(g_TradeState != STATE_FLAT)
         CheckSL(bid, ask, 0.0, false);
     }

   // New bar?
   datetime curBar = iTime(_Symbol, _Period, 0);
   if(curBar == g_LastBarTime) return;
   g_LastBarTime = curBar;

   // Bar-close work: refresh trailing SL, run SL_CLOSE check, then attempt entries
   if(g_TradeState != STATE_FLAT)
     {
      UpdateBasisTrail();
      double closed = iClose(_Symbol, _Period, 1);
      CheckSL(bid, ask, closed, true);
     }

   if(g_TradeState == STATE_FLAT)
      TryEntry();
  }
//+------------------------------------------------------------------+
