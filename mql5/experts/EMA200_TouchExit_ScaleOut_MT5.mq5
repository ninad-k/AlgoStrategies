#property strict
#property version   "1.10"
#property description "EMA200 close-cross entry + 50% at 10 points + 50% at 20 points + EMA touch/opposite-signal exit"

#include <Trade/Trade.mqh>

input int      EmaPeriod       = 200;
input double   Lots            = 0.10;
input ulong    MagicNumber     = 200200;
input int      DeviationPoints = 20;
input int      Target1Points   = 10;
input int      Target2Points   = 20;

CTrade   trade;
int      emaHandle   = INVALID_HANDLE;
datetime lastBarTime = 0;

enum ManagedDirection
{
   DIR_SHORT = -1,
   DIR_NONE  = 0,
   DIR_LONG  = 1,
   DIR_MIXED = 2
};

int OnInit()
{
   if(Target1Points <= 0 || Target2Points <= 0 || Target2Points <= Target1Points)
   {
      Print("Invalid target settings. Use positive values and keep Target2Points > Target1Points.");
      return(INIT_FAILED);
   }

   double halfVolume = 0.0;
   if(!CanSplitVolumeExactly(Lots, halfVolume))
   {
      Print("Lots cannot be split into two equal tradable halves on this symbol. Adjust Lots to a value compatible with the broker's minimum lot and volume step.");
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(DeviationPoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);

   emaHandle = iMA(_Symbol, PERIOD_CURRENT, EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(emaHandle == INVALID_HANDLE)
   {
      Print("Failed to create EMA handle. Error: ", GetLastError());
      return(INIT_FAILED);
   }

   lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(emaHandle != INVALID_HANDLE)
      IndicatorRelease(emaHandle);
}

void OnTick()
{
   if(Bars(_Symbol, PERIOD_CURRENT) < EmaPeriod + 3)
      return;

   EnsureStateForManagedPositions();
   ManageOpenPositions();

   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime != 0 && currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      ProcessNewBarSignal();
   }
}

void ProcessNewBarSignal()
{
   double ema1 = GetEMA(1);
   double ema2 = GetEMA(2);
   if(ema1 == EMPTY_VALUE || ema2 == EMPTY_VALUE)
      return;

   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double close2 = iClose(_Symbol, PERIOD_CURRENT, 2);
   if(close1 == 0.0 || close2 == 0.0)
      return;

   bool longSignal  = (close1 > ema1 && close2 <= ema2);
   bool shortSignal = (close1 < ema1 && close2 >= ema2);

   int direction = GetManagedDirection();
   if(direction == DIR_MIXED)
   {
      CloseAllManagedPositions();
      direction = GetManagedDirection();
   }

   if(longSignal)
   {
      if(direction == DIR_SHORT)
         CloseAllManagedPositions();

      if(GetManagedDirection() == DIR_NONE)
         OpenBuy();
   }
   else if(shortSignal)
   {
      if(direction == DIR_LONG)
         CloseAllManagedPositions();

      if(GetManagedDirection() == DIR_NONE)
         OpenSell();
   }
}

void ManageOpenPositions()
{
   double ema0 = GetEMA(0);
   if(ema0 == EMPTY_VALUE)
      return;

   double bid = 0.0;
   double ask = 0.0;
   if(!SymbolInfoDouble(_Symbol, SYMBOL_BID, bid) || !SymbolInfoDouble(_Symbol, SYMBOL_ASK, ask))
      return;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if((ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      ENUM_POSITION_TYPE type  = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double openPrice         = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentVolume     = PositionGetDouble(POSITION_VOLUME);
      ulong  positionId        = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      double initialVolume     = 0.0;
      int    stage             = 0;

      if(!LoadPositionState(positionId, initialVolume, stage))
      {
         InferAndSavePositionState(currentVolume, positionId, initialVolume, stage);
      }

      bool tp1Hit = false;
      bool tp2Hit = false;

      if(type == POSITION_TYPE_BUY)
      {
         tp1Hit = (bid >= openPrice + Target1Points * _Point);
         tp2Hit = (bid >= openPrice + Target2Points * _Point);
      }
      else if(type == POSITION_TYPE_SELL)
      {
         tp1Hit = (ask <= openPrice - Target1Points * _Point);
         tp2Hit = (ask <= openPrice - Target2Points * _Point);
      }

      if(stage < 1 && tp1Hit)
      {
         double firstCloseVolume = GetFirstTargetCloseVolume(initialVolume);
         if(firstCloseVolume > 0.0 && ClosePositionPartialByTicket(ticket, firstCloseVolume))
         {
            SavePositionState(positionId, initialVolume, 1);

            if(!PositionSelectByTicket(ticket))
            {
               DeletePositionState(positionId);
               continue;
            }

            currentVolume = PositionGetDouble(POSITION_VOLUME);
            stage         = 1;
         }
      }

      if(stage >= 1 && tp2Hit)
      {
         if(ClosePositionByTicket(ticket) && !PositionSelectByTicket(ticket))
            DeletePositionState(positionId);
         continue;
      }

      if(!PositionSelectByTicket(ticket))
      {
         DeletePositionState(positionId);
         continue;
      }

      type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      if(type == POSITION_TYPE_BUY && bid <= ema0)
      {
         if(ClosePositionByTicket(ticket) && !PositionSelectByTicket(ticket))
            DeletePositionState(positionId);
      }
      else if(type == POSITION_TYPE_SELL && ask >= ema0)
      {
         if(ClosePositionByTicket(ticket) && !PositionSelectByTicket(ticket))
            DeletePositionState(positionId);
      }
   }
}

ManagedDirection GetManagedDirection()
{
   bool hasBuy  = false;
   bool hasSell = false;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if((ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      if(type == POSITION_TYPE_BUY)
         hasBuy = true;
      else if(type == POSITION_TYPE_SELL)
         hasSell = true;
   }

   if(hasBuy && hasSell)
      return(DIR_MIXED);
   if(hasBuy)
      return(DIR_LONG);
   if(hasSell)
      return(DIR_SHORT);

   return(DIR_NONE);
}

void CloseAllManagedPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if((ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      ulong positionId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(ClosePositionByTicket(ticket) && !PositionSelectByTicket(ticket))
         DeletePositionState(positionId);
   }
}

bool ClosePositionByTicket(const ulong ticket)
{
   if(!trade.PositionClose(ticket, (ulong)DeviationPoints))
   {
      PrintFormat("PositionClose request failed for ticket %I64u. Retcode=%u %s",
                  ticket,
                  trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
      return(false);
   }

   uint retcode = trade.ResultRetcode();
   if(!TradeRetcodeOk(retcode))
   {
      PrintFormat("PositionClose not executed for ticket %I64u. Retcode=%u %s",
                  ticket,
                  retcode,
                  trade.ResultRetcodeDescription());
      return(false);
   }

   return(true);
}

bool ClosePositionPartialByTicket(const ulong ticket, double volume)
{
   if(!PositionSelectByTicket(ticket))
      return(false);

   double currentVolume = PositionGetDouble(POSITION_VOLUME);
   volume = NormalizeVolume(volume);
   if(volume <= 0.0)
      return(false);

   if(volume >= currentVolume - VolumeEpsilon())
      return(ClosePositionByTicket(ticket));

   long marginMode = AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(marginMode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      if(!trade.PositionClosePartial(ticket, volume, (ulong)DeviationPoints))
      {
         PrintFormat("PositionClosePartial request failed for ticket %I64u. Retcode=%u %s",
                     ticket,
                     trade.ResultRetcode(),
                     trade.ResultRetcodeDescription());
         return(false);
      }

      uint retcode = trade.ResultRetcode();
      if(!TradeRetcodeOk(retcode))
      {
         PrintFormat("PositionClosePartial not executed for ticket %I64u. Retcode=%u %s",
                     ticket,
                     retcode,
                     trade.ResultRetcodeDescription());
         return(false);
      }

      return(true);
   }

   return(SendNettingReduction(ticket, volume));
}

bool SendNettingReduction(const ulong ticket, double volume)
{
   if(!PositionSelectByTicket(ticket))
      return(false);

   string symbol = PositionGetString(POSITION_SYMBOL);
   ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   double price = 0.0;
   if(type == POSITION_TYPE_BUY)
   {
      if(!SymbolInfoDouble(symbol, SYMBOL_BID, price))
         return(false);
   }
   else if(type == POSITION_TYPE_SELL)
   {
      if(!SymbolInfoDouble(symbol, SYMBOL_ASK, price))
         return(false);
   }
   else
   {
      return(false);
   }

   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action       = TRADE_ACTION_DEAL;
   request.symbol       = symbol;
   request.position     = ticket;
   request.magic        = MagicNumber;
   request.volume       = volume;
   request.deviation    = (ulong)DeviationPoints;
   request.type_filling = GetFillingMode(symbol);
   request.type         = (type == POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY);
   request.price        = price;
   request.comment      = "EMA200 partial close";

   if(!OrderSend(request, result))
   {
      PrintFormat("Netting reduction request failed for ticket %I64u. Error=%d", ticket, GetLastError());
      return(false);
   }

   if(!TradeRetcodeOk(result.retcode))
   {
      PrintFormat("Netting reduction not executed for ticket %I64u. Retcode=%u %s",
                  ticket,
                  result.retcode,
                  result.comment);
      return(false);
   }

   return(true);
}

bool OpenBuy()
{
   double volume = NormalizeVolume(Lots);
   bool sent = trade.Buy(volume, _Symbol, 0.0, 0.0, 0.0, "EMA200 cross long");
   uint retcode = trade.ResultRetcode();

   if(!sent || !TradeRetcodeOk(retcode))
   {
      PrintFormat("Buy failed. Retcode=%u %s", retcode, trade.ResultRetcodeDescription());
      return(false);
   }

   EnsureStateForManagedPositions();
   return(true);
}

bool OpenSell()
{
   double volume = NormalizeVolume(Lots);
   bool sent = trade.Sell(volume, _Symbol, 0.0, 0.0, 0.0, "EMA200 cross short");
   uint retcode = trade.ResultRetcode();

   if(!sent || !TradeRetcodeOk(retcode))
   {
      PrintFormat("Sell failed. Retcode=%u %s", retcode, trade.ResultRetcodeDescription());
      return(false);
   }

   EnsureStateForManagedPositions();
   return(true);
}

bool TradeRetcodeOk(const uint retcode)
{
   return(retcode == TRADE_RETCODE_DONE ||
          retcode == TRADE_RETCODE_DONE_PARTIAL ||
          retcode == TRADE_RETCODE_PLACED);
}

double GetEMA(const int shift)
{
   double value[1];
   int copied = CopyBuffer(emaHandle, 0, shift, 1, value);
   if(copied < 1)
      return(EMPTY_VALUE);

   return(value[0]);
}

void EnsureStateForManagedPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      if((ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;

      ulong positionId    = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      double currentVolume = PositionGetDouble(POSITION_VOLUME);
      double initialVolume = 0.0;
      int    stage         = 0;

      if(!LoadPositionState(positionId, initialVolume, stage))
         InferAndSavePositionState(currentVolume, positionId, initialVolume, stage);
   }
}

void InferAndSavePositionState(double currentVolume, ulong positionId, double &initialVolume, int &stage)
{
   double configuredEntry = NormalizeVolume(Lots);
   double exactHalf       = GetFirstTargetCloseVolume(configuredEntry);

   if(MathAbs(currentVolume - configuredEntry) <= VolumeEpsilon())
   {
      initialVolume = configuredEntry;
      stage         = 0;
   }
   else if(exactHalf > 0.0 && MathAbs(currentVolume - exactHalf) <= VolumeEpsilon())
   {
      initialVolume = configuredEntry;
      stage         = 1;
   }
   else
   {
      initialVolume = currentVolume;
      stage         = 0;
   }

   SavePositionState(positionId, initialVolume, stage);
}

bool LoadPositionState(ulong positionId, double &initialVolume, int &stage)
{
   string initKey  = GetStateKey(positionId, "init");
   string stageKey = GetStateKey(positionId, "stage");

   if(!GlobalVariableCheck(initKey) || !GlobalVariableCheck(stageKey))
      return(false);

   initialVolume = GlobalVariableGet(initKey);
   stage         = (int)MathRound(GlobalVariableGet(stageKey));
   return(true);
}

void SavePositionState(ulong positionId, double initialVolume, int stage)
{
   GlobalVariableSet(GetStateKey(positionId, "init"), initialVolume);
   GlobalVariableSet(GetStateKey(positionId, "stage"), stage);
}

void DeletePositionState(ulong positionId)
{
   GlobalVariableDel(GetStateKey(positionId, "init"));
   GlobalVariableDel(GetStateKey(positionId, "stage"));
}

string GetStateKey(ulong positionId, string suffix)
{
   return(StringFormat("EMA200_%s_%I64u_%s", _Symbol, positionId, suffix));
}

double GetFirstTargetCloseVolume(double entryVolume)
{
   return(NormalizeVolume(entryVolume / 2.0));
}

bool CanSplitVolumeExactly(double requestedVolume, double &halfVolume)
{
   double total     = NormalizeVolume(requestedVolume);
   double minVol    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double half      = NormalizeVolume(total / 2.0);
   double remainder = NormalizeVolume(total - half);
   double eps       = VolumeEpsilon();

   if(total <= 0.0 || half <= 0.0 || remainder <= 0.0)
      return(false);
   if(half < minVol - eps || remainder < minVol - eps)
      return(false);
   if(MathAbs(half - remainder) > eps)
      return(false);
   if(MathAbs((half + remainder) - total) > eps)
      return(false);

   halfVolume = half;
   return(true);
}

double NormalizeVolume(double volume)
{
   double minVol  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxVol  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(stepVol <= 0.0)
      stepVol = 0.01;

   volume = MathMax(minVol, MathMin(maxVol, volume));
   volume = MathRound(volume / stepVol) * stepVol;

   int digits = GetVolumeDigits();
   return(NormalizeDouble(volume, digits));
}

double VolumeEpsilon()
{
   double stepVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepVol <= 0.0)
      stepVol = 0.01;

   return(stepVol / 2.0);
}

int GetVolumeDigits()
{
   double stepVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepVol <= 0.0)
      stepVol = 0.01;

   int digits = 0;
   double tmp = stepVol;
   while(digits < 8 && MathRound(tmp) != tmp)
   {
      tmp *= 10.0;
      digits++;
   }

   return(digits);
}

ENUM_ORDER_TYPE_FILLING GetFillingMode(string symbol)
{
   long fillingMode = SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);

   if((fillingMode & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return(ORDER_FILLING_FOK);
   if((fillingMode & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return(ORDER_FILLING_IOC);

   return(ORDER_FILLING_RETURN);
}
