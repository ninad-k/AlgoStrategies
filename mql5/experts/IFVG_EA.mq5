//+------------------------------------------------------------------+
//|                                              IFVG_EA.mq5         |
//|                                  Copyright 2026, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property link      "https://www.mql5.com"
#property version   "1.01"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+
CTrade obj_Trade;                                                  //--- Trade object
#define FVG_Prefix "IFVG REC "                                     //--- FVG prefix

// Normal FVGs
#define CLR_UP clrGreen                                            // Green for normal up (Bullish FVG)
#define CLR_DOWN clrRed                                            // Red for normal down (Bearish FVG)
// Mitigated FVGs
#define CLR_MIT_UP clrPurple                                       // Purple for mitigated up (Mitigated Bullish FVG)
#define CLR_MIT_DOWN clrOrange                                     // Orange for mitigated down (Mitigated Bearish FVG)
// Inverted FVGs
#define CLR_INV_UP clrRed                                          // Red for inverted up (Bearish IFVG)
#define CLR_INV_DOWN clrGreen                                      // Green for inverted down (Bullish IFVG)

//+------------------------------------------------------------------+
//| Enums                                                            |
//+------------------------------------------------------------------+
enum TradeMode {                                                   // Define trade mode enum
   TradeOnce,                                                      // Trade Once
   LimitedTrades,                                                  // Limited Trades
   UnlimitedTrades                                                 // Unlimited Trades
};

enum FVGState {                                                    // Define FVG state enum
   Normal,                                                         // Normal
   Mitigated,                                                      // Mitigated
   Inverted                                                        // Inverted
};

enum TrailingTypeEnum {                                            // Define enum for trailing stop types
   Trailing_None  = 0,                                             // None
   Trailing_Points = 2                                             // By Points
};

enum LotMode {                                                     // Lot mode enum
   FixedLot,                                                       // Fixed Lot
   DynamicLot                                                      // Dynamic (Risk %)
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
sinput string separator0 = "--- Lot Settings ---";
input LotMode lotMode           = DynamicLot;                      // Lot Mode
input double fixedLot           = 1.0;                             // Fixed Lot Size
input double riskPercent        = 1.0;                             // Risk % of Balance (Dynamic)

sinput string separator = "--- IFVG Strategy Settings ---";
input int    sl_pts             = 500;                             // Stop Loss Points
input int    tp_pts             = 10000;                           // Take Profit Points
input int    minPts             = 100;                             // Minimum Gap Size in Points
input int    FVG_Rec_Ext_Bars   = 30;                              // FVG Extension Bars
input bool   prt                = true;                            // Print Statements
input long   magic_number       = 123456789;                       // Magic Number
input bool   ignoreOverlaps     = true;                            // Ignore new FVGs that overlap existing ones
input TradeMode tradeMode       = LimitedTrades;                   // Mode for trading FVGs
input int    maxTradesPerFVG    = 1;                               // Maximum trades per FVG (if LimitedTrades)
input int    maxFVGs            = 50;                              // Maximum FVGs to track in array
input TrailingTypeEnum TrailingType = Trailing_Points;             // Trailing Stop Type
input double Trailing_Stop_Pips = 30.0;                            // Trailing Stop in Pips
input double Min_Profit_To_Trail_Pips = 10.0;                      // Min Profit to Start Trailing in Pips

//+------------------------------------------------------------------+
//| Structure for FVG zone information                               |
//+------------------------------------------------------------------+
struct FVGZone {                                                   // Define FVG zone structure
   string   name;                                                  //--- Zone name
   datetime startTime;                                             //--- Start time
   datetime origEndTime;                                           //--- Original end time
   datetime mitTime;                                               //--- Mitigation time
   bool     signal;                                                //--- Signal flag
   bool     inverted;                                              //--- Inverted flag
   bool     mit;                                                   //--- Mitigated flag
   bool     ret;                                                   //--- Retraced flag
   bool     origUp;                                                //--- Original up flag
   int      tradeCount;                                            //--- Trade count
   FVGState state;                                                 //--- State
   bool     newSignal;                                             //--- New signal flag
};
FVGZone fvgs[];                                                    //--- FVG zones array

//+------------------------------------------------------------------+
//| Calculate lot size                                               |
//+------------------------------------------------------------------+
double CalcLot(double slPoints) {
   if (lotMode == FixedLot) return fixedLot;                       //--- Return fixed

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);            //--- Get balance
   double riskMoney = balance * riskPercent / 100.0;               //--- Calc risk money
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE); //--- Get tick value
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);  //--- Get tick size
   if (tickValue == 0 || tickSize == 0) return fixedLot;           //--- Safety fallback

   double slMoney = (slPoints * _Point / tickSize) * tickValue;    //--- SL cost per 1 lot
   if (slMoney == 0) return fixedLot;                              //--- Safety fallback

   double lot = NormalizeDouble(riskMoney / slMoney, 2);           //--- Calc lot
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);   //--- Get min lot
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);   //--- Get max lot
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP); //--- Get step
   if (lot < minLot) lot = minLot;                                 //--- Clamp min
   if (lot > maxLot) lot = maxLot;                                 //--- Clamp max
   lot = MathFloor(lot / stepLot) * stepLot;                       //--- Round to step
   return NormalizeDouble(lot, 2);                                 //--- Return lot
}

//+------------------------------------------------------------------+
//| Get color based on state and direction                           |
//+------------------------------------------------------------------+
color GetFVGColor(bool isUp, FVGState currentState) {
   if (currentState == Normal) return isUp ? CLR_UP : CLR_DOWN;    //--- Return normal color
   if (currentState == Mitigated) return isUp ? CLR_MIT_UP : CLR_MIT_DOWN; //--- Return mitigated color
   if (currentState == Inverted) return isUp ? CLR_INV_UP : CLR_INV_DOWN; //--- Return inverted color
   return clrNONE;                                                 //--- Return none
}

//+------------------------------------------------------------------+
//| Print FVGs for debugging                                         |
//+------------------------------------------------------------------+
void PrintFVGs() {
   if (!prt) return;                                               //--- Return if no print
   Print("Current FVGs count: ", ArraySize(fvgs));                 //--- Print count
   for (int i = 0; i < ArraySize(fvgs); i++) {                     //--- Iterate FVGs
      Print("FVG ", i, ": ", fvgs[i].name, " state=", EnumToString(fvgs[i].state), " mit=", fvgs[i].mit, " ret=", fvgs[i].ret, " inverted=", fvgs[i].inverted, " tradeCount=", fvgs[i].tradeCount, " newSignal=", fvgs[i].newSignal, " endTime=", TimeToString(fvgs[i].origEndTime)); //--- Print details
   }
}

//+------------------------------------------------------------------+
//| Create label                                                     |
//+------------------------------------------------------------------+
void UpdateLabelText(string lblName, string zoneName) {
   string text = "";                                               //--- Init text
   int tradeCnt = 0;                                               //--- Init count
   FVGState state = Normal;                                        //--- Init state
   bool origUp = false;                                            //--- Init orig up
   for (int idx = 0; idx < ArraySize(fvgs); idx++) {               //--- Iterate FVGs
      if (fvgs[idx].name == zoneName) {                            //--- Check match
         tradeCnt = fvgs[idx].tradeCount;                          //--- Get count
         state = fvgs[idx].state;                                  //--- Get state
         origUp = fvgs[idx].origUp;                                //--- Get orig up
         break;                                                    //--- Break loop
      }
   }
   if (state == Normal) {                                          //--- Check normal
      text = origUp ? "Bullish FVG" : "Bearish FVG";               //--- Set text
   } else if (state == Mitigated) {                                //--- Check mitigated
      text = origUp ? "Mitigated Bullish FVG" : "Mitigated Bearish FVG"; //--- Set text
   } else if (state == Inverted) {                                 //--- Check inverted
      text = origUp ? "Bearish IFVG" : "Bullish IFVG";             //--- Set text
   }
   if (tradeCnt > 0) {                                             //--- Check traded
      text += " (Traded " + IntegerToString(tradeCnt) + "x)";      //--- Add traded
   }
   ObjectSetString(0, lblName, OBJPROP_TEXT, text);                //--- Set text
}

void CreateLabel(string zoneName, datetime time, double price) {
   string lblName = zoneName + "_Label";                           //--- Label name
   ObjectCreate(0, lblName, OBJ_TEXT, 0, time, price);             //--- Create text
   ObjectSetInteger(0, lblName, OBJPROP_ANCHOR, ANCHOR_CENTER);    //--- Set anchor
   ObjectSetInteger(0, lblName, OBJPROP_COLOR, clrBlack);          //--- Set color
   UpdateLabelText(lblName, zoneName);                             //--- Update text
}

void UpdateLabel(string zoneName, datetime time, double price) {
   string lblName = zoneName + "_Label";                           //--- Label name
   if (ObjectFind(0, lblName) >= 0) {                              //--- Check exists
      ObjectSetInteger(0, lblName, OBJPROP_TIME, 0, time);         //--- Set time
      ObjectSetDouble(0, lblName, OBJPROP_PRICE, 0, price);        //--- Set price
      UpdateLabelText(lblName, zoneName);                          //--- Update text
   }
}

//+------------------------------------------------------------------+
//| Create Rectangle                                                 |
//+------------------------------------------------------------------+
void CreateRec(string objName, datetime time1, double price1, datetime time2, double price2, color clr) {
   ObjectCreate(0, objName, OBJ_RECTANGLE, 0, time1, price1, time2, price2); //--- Create rectangle
   ObjectSetInteger(0, objName, OBJPROP_FILL, true);               //--- Set fill
   ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);               //--- Set color
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);              //--- Set foreground
   datetime midTime = time1 + (time2 - time1) / 2;                 //--- Calc mid time
   double midPrice = (price1 + price2) / 2;                        //--- Calc mid price
   CreateLabel(objName, midTime, midPrice);                        //--- Create label
   ChartRedraw(0);                                                 //--- Redraw chart
}

void UpdateRec(string objName, datetime time1, double price1, datetime time2, double price2, color clr) {
   if (ObjectFind(0, objName) >= 0) {                              //--- Check exists
      ObjectSetInteger(0, objName, OBJPROP_TIME, 0, time1);        //--- Set time1
      ObjectSetDouble(0, objName, OBJPROP_PRICE, 0, price1);       //--- Set price1
      ObjectSetInteger(0, objName, OBJPROP_TIME, 1, time2);        //--- Set time2
      ObjectSetDouble(0, objName, OBJPROP_PRICE, 1, price2);       //--- Set price2
      ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);            //--- Set color
      datetime midTime = time1 + (time2 - time1) / 2;              //--- Calc mid time
      double midPrice = (price1 + price2) / 2;                     //--- Calc mid price
      UpdateLabel(objName, midTime, midPrice);                     //--- Update label
      ChartRedraw(0);                                              //--- Redraw chart
   }
}

//+------------------------------------------------------------------+
//| Draw mitigation icon                                             |
//+------------------------------------------------------------------+
void DrawMitIcon(string fvgNAME, datetime mitTime, double fvgHigh, double fvgLow, bool isUp) {
   string iconName = fvgNAME + "_MitIcon";                         //--- Icon name
   double iconPrice = isUp ? fvgLow : fvgHigh;                     //--- Icon price
   ObjectCreate(0, iconName, OBJ_ARROW, 0, mitTime, iconPrice);    //--- Create arrow
   ObjectSetInteger(0, iconName, OBJPROP_ARROWCODE, 251);          //--- Set code
   ObjectSetInteger(0, iconName, OBJPROP_COLOR, clrBlue);          //--- Set color
   ObjectSetInteger(0, iconName, OBJPROP_ANCHOR, isUp ? ANCHOR_TOP : ANCHOR_BOTTOM); //--- Set anchor
   ChartRedraw(0);                                                 //--- Redraw chart
}

//+------------------------------------------------------------------+
//| Process historical mitigation, retracement, signal for an FVG    |
//+------------------------------------------------------------------+
void ProcessHistoricalState(int idx) {
   string fvgNAME = fvgs[idx].name;                                //--- Get name
   datetime timeSTART = fvgs[idx].startTime;                       //--- Get start time
   datetime endTime = fvgs[idx].origEndTime;                       //--- Get end time
   double fvgLow = MathMin(ObjectGetDouble(0, fvgNAME, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgNAME, OBJPROP_PRICE, 1)); //--- Calc low
   double fvgHigh = MathMax(ObjectGetDouble(0, fvgNAME, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgNAME, OBJPROP_PRICE, 1)); //--- Calc high
   int fvgBar = iBarShift(_Symbol, _Period, timeSTART);            //--- Get bar
   if (fvgBar < 0) return;                                         //--- Return invalid
   bool isMit = false, isRet = false, isSig = false;               //--- Init flags
   datetime mitTime = 0;                                           //--- Init mit time
   int mitK = -1, sigK = -1;                                       //--- Init indices
   for (int k = fvgBar - 1; k >= 0; k--) {                         //--- Iterate bars
      double barLow = iLow(_Symbol, _Period, k);                   //--- Get bar low
      double barHigh = iHigh(_Symbol, _Period, k);                 //--- Get bar high
      double barClose = iClose(_Symbol, _Period, k);               //--- Get bar close
      if (!isMit) {                                                //--- Check not mit
         bool breakFar = (fvgs[idx].origUp && barLow < fvgLow) || (!fvgs[idx].origUp && barHigh > fvgHigh); //--- Check break far
         if (breakFar) {                                           //--- Break far
            isMit = true;                                          //--- Set mit
            mitK = k;                                              //--- Set mit k
            mitTime = iTime(_Symbol, _Period, k);                  //--- Set mit time
            if (prt) Print("Historical Mitigated: ", fvgNAME, " at bar ", k, " time=", TimeToString(mitTime)); //--- Log mitigated
         }
      }
      if (isMit && !isRet) {                                       //--- Check mit and not ret
         bool inside = (barHigh > fvgLow && barLow < fvgHigh);     //--- Check inside
         if (inside) {                                             //--- Inside
            isRet = true;                                          //--- Set ret
            if (prt) Print("Historical Retraced: ", fvgNAME, " at bar ", k); //--- Log retraced
         }
      }
      if (isMit && isRet && !isSig) {                              //--- Check mit ret not sig
         bool signal = (fvgs[idx].origUp && barClose < fvgLow) || (!fvgs[idx].origUp && barClose > fvgHigh); //--- Check signal
         if (signal) {                                             //--- Signal
            if (k + 1 < iBars(_Symbol, _Period)) {                 //--- Check prev bar
               double prevClose = iClose(_Symbol, _Period, k + 1); //--- Get prev close
               bool prevInside = (prevClose > fvgLow && prevClose < fvgHigh); //--- Check prev inside
               if (prevInside) {                                   //--- Prev inside
                  isSig = true;                                    //--- Set sig
                  sigK = k;                                        //--- Set sig k
                  if (prt) Print("Historical Signal/Inverted: ", fvgNAME, " at bar ", k, " time=", TimeToString(iTime(_Symbol, _Period, k))); //--- Log signal
               }
            }
         }
      }
   }
   fvgs[idx].mit = isMit;                                          //--- Set mit
   fvgs[idx].ret = isRet;                                          //--- Set ret
   fvgs[idx].inverted = isSig;                                     //--- Set inverted
   fvgs[idx].signal = isSig;                                       //--- Set signal
   fvgs[idx].mitTime = mitTime;                                    //--- Set mit time
   fvgs[idx].state = isSig ? Inverted : (isMit ? Mitigated : Normal); //--- Set state
   fvgs[idx].newSignal = false;                                    //--- Set no new signal
   color currentClr = GetFVGColor(fvgs[idx].origUp, fvgs[idx].state); //--- Get color
   UpdateRec(fvgs[idx].name, fvgs[idx].startTime, fvgLow, fvgs[idx].origEndTime, fvgHigh, currentClr); //--- Update rec
   if (mitTime > 0) DrawMitIcon(fvgs[idx].name, mitTime, fvgHigh, fvgLow, fvgs[idx].origUp); //--- Draw mit icon
}

//+------------------------------------------------------------------+
//| Detect new FVGs on recent bars                                   |
//+------------------------------------------------------------------+
void DetectFVGs() {
   for (int i = 3; i >= 1; i--) {                                 //--- Iterate recent bars
      double low0 = iLow(_Symbol, _Period, i);                    //--- Get low0
      double high2 = iHigh(_Symbol, _Period, i + 2);              //--- Get high2
      double gap_L0_H2 = NormalizeDouble((low0 - high2) / _Point, _Digits); //--- Calc gap L0 H2
      double high0 = iHigh(_Symbol, _Period, i);                  //--- Get high0
      double low2 = iLow(_Symbol, _Period, i + 2);                //--- Get low2
      double gap_H0_L2 = NormalizeDouble((low2 - high0) / _Point, _Digits); //--- Calc gap H0 L2

      bool FVG_UP = low0 > high2 && gap_L0_H2 > minPts;           //--- Check up FVG
      bool FVG_DOWN = low2 > high0 && gap_H0_L2 > minPts;         //--- Check down FVG

      if (FVG_UP || FVG_DOWN) {                                   //--- Check FVG
         datetime time1 = iTime(_Symbol, _Period, i + 1);         //--- Get time1
         double price1 = FVG_UP ? high2 : high0;                  //--- Set price1
         double price2 = FVG_UP ? low0 : low2;                    //--- Set price2
         double newLow = MathMin(price1, price2);                 //--- Calc new low
         double newHigh = MathMax(price1, price2);                //--- Calc new high
         bool overlaps = false;                                   //--- Init overlaps

         if (ignoreOverlaps) {                                    //--- Check ignore overlaps
            for (int ex = 0; ex < ArraySize(fvgs); ex++) {        //--- Iterate existing
               double exLow = MathMin(ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 1)); //--- Calc ex low
               double exHigh = MathMax(ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 1)); //--- Calc ex high
               if (MathMax(newLow, exLow) < MathMin(newHigh, exHigh)) { //--- Check overlap
                  overlaps = true;                                //--- Set overlaps
                  if (prt) Print("Detect: Skipping overlapping FVG at ", TimeToString(time1)); //--- Log skip
                  break;                                          //--- Break loop
               }
            }
         }
         if (overlaps) continue;                                  //--- Continue if overlaps

         string fvgNAME = FVG_Prefix + "(" + TimeToString(time1) + ")"; //--- FVG name
         if (ObjectFind(0, fvgNAME) >= 0) continue;               //--- Skip duplicate

         color fvgClr = FVG_UP ? CLR_UP : CLR_DOWN;               //--- Set color
         datetime endTime = time1 + PeriodSeconds(_Period) * FVG_Rec_Ext_Bars; //--- Calc end time
         CreateRec(fvgNAME, time1, price1, endTime, price2, fvgClr); //--- Create rec

         int size = ArraySize(fvgs);                              //--- Get size
         if (size >= maxFVGs) {                                   //--- Check max
            if (prt) Print("Detect: Max FVGs reached, removing oldest."); //--- Log max
            ArrayRemove(fvgs, 0, 1);                              //--- Remove oldest
         }

         ArrayResize(fvgs, size + 1);                             //--- Resize array
         fvgs[size].name = fvgNAME;                               //--- Set name
         fvgs[size].startTime = time1;                            //--- Set start time
         fvgs[size].origEndTime = endTime;                        //--- Set end time
         fvgs[size].mitTime = 0;                                  //--- Set mit time
         fvgs[size].signal = false;                               //--- Set signal
         fvgs[size].inverted = false;                             //--- Set inverted
         fvgs[size].mit = false;                                  //--- Set mit
         fvgs[size].ret = false;                                  //--- Set ret
         fvgs[size].origUp = FVG_UP;                              //--- Set orig up
         fvgs[size].tradeCount = 0;                               //--- Set trade count
         fvgs[size].state = Normal;                               //--- Set state
         fvgs[size].newSignal = false;                            //--- Set new signal
         if (prt) Print("New FVG added to storage: ", fvgNAME, " origUp=", FVG_UP, " endTime=", TimeToString(endTime)); //--- Log added
      }
   }
}

//+------------------------------------------------------------------+
//| Update states for all FVGs                                       |
//+------------------------------------------------------------------+
void UpdateFVGs() {
   double prevClose = iClose(_Symbol, _Period, 1);                //--- Get prev close
   double prevLow = iLow(_Symbol, _Period, 1);                    //--- Get prev low
   double prevHigh = iHigh(_Symbol, _Period, 1);                  //--- Get prev high
   double bar2Close = iClose(_Symbol, _Period, 2);                //--- Get bar2 close
   datetime curBarTime = iTime(_Symbol, _Period, 1);              //--- Get prev bar time

   for (int j = ArraySize(fvgs) - 1; j >= 0; j--) {               //--- Iterate reverse
      if (ObjectFind(0, fvgs[j].name) < 0) {                      //--- Check no object
         if (prt) Print("Update: Removed non-existent FVG from storage: ", fvgs[j].name); //--- Log removed
         ArrayRemove(fvgs, j, 1);                                 //--- Remove from array
         continue;                                                //--- Continue
      }

      double fvgLow = MathMin(ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 1)); //--- Calc low
      double fvgHigh = MathMax(ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 1)); //--- Calc high

      if (!fvgs[j].mit) {                                         //--- Check not mit
         bool breakFar = (fvgs[j].origUp && prevLow < fvgLow) || (!fvgs[j].origUp && prevHigh > fvgHigh); //--- Check break far
         if (breakFar) {                                          //--- Break far
            fvgs[j].mit = true;                                   //--- Set mit
            fvgs[j].mitTime = curBarTime;                         //--- Set mit time
            fvgs[j].state = Mitigated;                            //--- Set state
            if (prt) Print("Mitigated FVG: ", fvgs[j].name, " at time=", TimeToString(curBarTime)); //--- Log mitigated
            color mitClr = GetFVGColor(fvgs[j].origUp, fvgs[j].state); //--- Get color
            UpdateRec(fvgs[j].name, fvgs[j].startTime, fvgLow, fvgs[j].origEndTime, fvgHigh, mitClr); //--- Update rec
            DrawMitIcon(fvgs[j].name, curBarTime, fvgHigh, fvgLow, fvgs[j].origUp); //--- Draw icon
         }
      }

      if (fvgs[j].mit && !fvgs[j].ret) {                          //--- Check mit not ret
         bool inside = (prevHigh > fvgLow && prevLow < fvgHigh);  //--- Check inside
         if (inside) {                                            //--- Inside
            fvgs[j].ret = true;                                   //--- Set ret
            if (prt) Print("Retraced into FVG: ", fvgs[j].name);  //--- Log retraced
         }
      }

      if (fvgs[j].mit && fvgs[j].ret) {                           //--- Check mit ret
         bool signal = (fvgs[j].origUp && prevClose < fvgLow) || (!fvgs[j].origUp && prevClose > fvgHigh); //--- Check signal
         bool prevInside = (bar2Close > fvgLow && bar2Close < fvgHigh); //--- Check prev inside
         if (signal && curBarTime != fvgs[j].mitTime && prevInside) { //--- Check signal conditions
            fvgs[j].newSignal = true;                             //--- Set new signal
            if (!fvgs[j].inverted) {                              //--- Check not inverted
               fvgs[j].inverted = true;                           //--- Set inverted
               fvgs[j].state = Inverted;                          //--- Set state
               if (prt) Print("Signal/Inverted FVG: ", fvgs[j].name, " at time=", TimeToString(curBarTime)); //--- Log signal
               color sigClr = GetFVGColor(fvgs[j].origUp, fvgs[j].state); //--- Get color
               UpdateRec(fvgs[j].name, fvgs[j].startTime, fvgLow, fvgs[j].origEndTime, fvgHigh, sigClr); //--- Update rec
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Trade on FVGs with signals                                       |
//+------------------------------------------------------------------+
void TradeOnFVGs() {
   double Ask = NormalizeDouble(SymbolInfoDouble(_Symbol, SYMBOL_ASK), _Digits); //--- Get ask
   double Bid = NormalizeDouble(SymbolInfoDouble(_Symbol, SYMBOL_BID), _Digits); //--- Get bid
   for (int j = 0; j < ArraySize(fvgs); j++) {                    //--- Iterate FVGs
      if (!fvgs[j].newSignal || fvgs[j].mitTime == 0) continue;   //--- Skip no signal or no mit
      if (tradeMode == TradeOnce && fvgs[j].tradeCount >= 1) {    //--- Check once and traded
         fvgs[j].newSignal = false;                               //--- Reset signal
         continue;                                                //--- Continue
      }
      if (tradeMode == LimitedTrades && fvgs[j].tradeCount >= maxTradesPerFVG) { //--- Check limited and max
         fvgs[j].newSignal = false;                               //--- Reset signal
         continue;                                                //--- Continue
      }

      double fvgLow = MathMin(ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 1)); //--- Calc low
      double fvgHigh = MathMax(ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[j].name, OBJPROP_PRICE, 1)); //--- Calc high

      if (!fvgs[j].origUp) {                                      //--- Check orig down: Bullish IFVG, Buy
         //--- Calc actual SL distance in points for dynamic lot
         double slDistance = (Ask - fvgLow) / _Point + sl_pts;    //--- Entry to fvgLow + sl_pts buffer
         double lot = CalcLot(slDistance);                         //--- Calc lot based on actual SL distance
         if (prt) Print("BULLISH IFVG TRADE SIGNAL For ", fvgs[j].name, " at ", Bid, " lot=", lot); //--- Log buy signal
         double SL_Buy = NormalizeDouble(fvgLow - sl_pts * _Point, _Digits); //--- Calc buy SL
         double TP_Buy = NormalizeDouble(Ask + tp_pts * _Point, _Digits); //--- Calc buy TP
         obj_Trade.Buy(lot, _Symbol, Ask, SL_Buy, TP_Buy, "IFVG Buy"); //--- Open buy
      } else {                                                    //--- Orig up: Bearish IFVG, Sell
         //--- Calc actual SL distance in points for dynamic lot
         double slDistance = (fvgHigh - Bid) / _Point + sl_pts;   //--- Entry to fvgHigh + sl_pts buffer
         double lot = CalcLot(slDistance);                         //--- Calc lot based on actual SL distance
         if (prt) Print("BEARISH IFVG TRADE SIGNAL For ", fvgs[j].name, " at ", Ask, " lot=", lot); //--- Log sell signal
         double SL_Sell = NormalizeDouble(fvgHigh + sl_pts * _Point, _Digits); //--- Calc sell SL
         double TP_Sell = NormalizeDouble(Bid - tp_pts * _Point, _Digits); //--- Calc sell TP
         obj_Trade.Sell(lot, _Symbol, Bid, SL_Sell, TP_Sell, "IFVG Sell"); //--- Open sell
      }
      fvgs[j].tradeCount++;                                       //--- Increment count
      fvgs[j].newSignal = false;                                  //--- Reset signal
      fvgs[j].ret = false;                                        //--- Reset ret
      if (prt) Print("Trade executed on ", fvgs[j].name, ", tradeCount now=", fvgs[j].tradeCount); //--- Log executed
      double midPrice = (fvgLow + fvgHigh) / 2;                   //--- Calc mid price
      datetime midTime = fvgs[j].startTime + (fvgs[j].origEndTime - fvgs[j].startTime) / 2; //--- Calc mid time
      UpdateLabel(fvgs[j].name, midTime, midPrice);               //--- Update label
   }
}

//+------------------------------------------------------------------+
//| Apply Points Trailing Stop                                       |
//+------------------------------------------------------------------+
void ApplyPointsTrailing() {
   double point = _Point;                                         //--- Get point value
   for (int i = PositionsTotal() - 1; i >= 0; i--) {              //--- Iterate positions reverse
      if (PositionGetTicket(i) > 0) {                             //--- Check valid ticket
         if (PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic_number) { //--- Check symbol and magic
            double sl = PositionGetDouble(POSITION_SL);           //--- Get SL
            double tp = PositionGetDouble(POSITION_TP);           //--- Get TP
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN); //--- Get open price
            ulong ticket = PositionGetInteger(POSITION_TICKET);   //--- Get ticket

            if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) { //--- Check buy
               double newSL = NormalizeDouble(SymbolInfoDouble(_Symbol, SYMBOL_BID) - Trailing_Stop_Pips * point, _Digits); //--- Calc new SL
               if (newSL > sl && SymbolInfoDouble(_Symbol, SYMBOL_BID) - openPrice > Min_Profit_To_Trail_Pips * point) { //--- Check conditions
                  obj_Trade.PositionModify(ticket, newSL, tp);    //--- Modify position
               }
            } else if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL) { //--- Check sell
               double newSL = NormalizeDouble(SymbolInfoDouble(_Symbol, SYMBOL_ASK) + Trailing_Stop_Pips * point, _Digits); //--- Calc new SL
               if (newSL < sl && openPrice - SymbolInfoDouble(_Symbol, SYMBOL_ASK) > Min_Profit_To_Trail_Pips * point) { //--- Check conditions
                  obj_Trade.PositionModify(ticket, newSL, tp);    //--- Modify position
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
   obj_Trade.SetExpertMagicNumber(magic_number);                  //--- Set magic number
   ObjectsDeleteAll(0, FVG_Prefix);                               //--- Delete FVG objects
   ArrayResize(fvgs, 0);                                          //--- Reset array
   if (prt) Print("Initializing: Deleted all existing FVG objects and reset array."); //--- Log init

   int visibleBars = (int)ChartGetInteger(0, CHART_VISIBLE_BARS); //--- Get visible bars
   // Detect historical FVGs from older to newer
   for (int i = visibleBars - 3; i >= 0; i--) {                   //--- Iterate bars
      double low0 = iLow(_Symbol, _Period, i);                    //--- Get low0
      double high2 = iHigh(_Symbol, _Period, i + 2);              //--- Get high2
      double gap_L0_H2 = NormalizeDouble((low0 - high2) / _Point, _Digits); //--- Calc gap L0 H2
      double high0 = iHigh(_Symbol, _Period, i);                  //--- Get high0
      double low2 = iLow(_Symbol, _Period, i + 2);                //--- Get low2
      double gap_H0_L2 = NormalizeDouble((low2 - high0) / _Point, _Digits); //--- Calc gap H0 L2

      bool FVG_UP = low0 > high2 && gap_L0_H2 > minPts;           //--- Check up FVG
      bool FVG_DOWN = low2 > high0 && gap_H0_L2 > minPts;         //--- Check down FVG

      if (FVG_UP || FVG_DOWN) {                                   //--- Check FVG
         datetime time1 = iTime(_Symbol, _Period, i + 1);         //--- Get time1
         double price1 = FVG_UP ? high2 : high0;                  //--- Set price1
         double price2 = FVG_UP ? low0 : low2;                    //--- Set price2
         double newLow = MathMin(price1, price2);                 //--- Calc new low
         double newHigh = MathMax(price1, price2);                //--- Calc new high
         bool overlaps = false;                                   //--- Init overlaps

         if (ignoreOverlaps) {                                    //--- Check ignore overlaps
            for (int ex = 0; ex < ArraySize(fvgs); ex++) {        //--- Iterate existing
               double exLow = MathMin(ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 1)); //--- Calc ex low
               double exHigh = MathMax(ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 0), ObjectGetDouble(0, fvgs[ex].name, OBJPROP_PRICE, 1)); //--- Calc ex high
               if (MathMax(newLow, exLow) < MathMin(newHigh, exHigh)) { //--- Check overlap
                  overlaps = true;                                //--- Set overlaps
                  break;                                          //--- Break loop
               }
            }
         }

         if (overlaps) continue;                                  //--- Continue if overlaps

         string fvgNAME = FVG_Prefix + "(" + TimeToString(time1) + ")"; //--- FVG name
         color fvgClr = FVG_UP ? CLR_UP : CLR_DOWN;               //--- Set color
         CreateRec(fvgNAME, time1, price1, time1 + PeriodSeconds(_Period) * FVG_Rec_Ext_Bars, price2, fvgClr); //--- Create rec

         int size = ArraySize(fvgs);                              //--- Get size
         if (size >= maxFVGs) {                                   //--- Check max
            ArrayRemove(fvgs, 0, 1);                              //--- Remove oldest
         }

         ArrayResize(fvgs, size + 1);                             //--- Resize array
         fvgs[size].name = fvgNAME;                               //--- Set name
         fvgs[size].startTime = time1;                            //--- Set start time
         fvgs[size].origEndTime = time1 + PeriodSeconds(_Period) * FVG_Rec_Ext_Bars; //--- Set end time
         fvgs[size].mitTime = 0;                                  //--- Set mit time
         fvgs[size].signal = false;                               //--- Set signal
         fvgs[size].inverted = false;                             //--- Set inverted
         fvgs[size].mit = false;                                  //--- Set mit
         fvgs[size].ret = false;                                  //--- Set ret
         fvgs[size].origUp = FVG_UP;                              //--- Set orig up
         fvgs[size].tradeCount = 0;                               //--- Set trade count
         fvgs[size].state = Normal;                               //--- Set state
         fvgs[size].newSignal = false;                            //--- Set new signal
      }
   }

   // Process historical states
   for (int j = 0; j < ArraySize(fvgs); j++) {                    //--- Iterate FVGs
      ProcessHistoricalState(j);                                  //--- Process state
   }
   return(INIT_SUCCEEDED);                                        //--- Return success
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   for (int i = 0; i < ArraySize(fvgs); i++) {                    //--- Iterate FVGs
      ObjectDelete(0, fvgs[i].name);                              //--- Delete name
      ObjectDelete(0, fvgs[i].name + "_Label");                   //--- Delete label
      ObjectDelete(0, fvgs[i].name + "_MitIcon");                 //--- Delete mit icon
   }
   ArrayResize(fvgs, 0);                                          //--- Reset array
   ChartRedraw(0);                                                //--- Redraw chart
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
   static datetime lastBarTime = 0;                               //--- Last bar time
   datetime curBarTime = iTime(_Symbol, _Period, 0);              //--- Current bar time
   bool newBar = (curBarTime != lastBarTime);                     //--- Check new bar

   if (newBar) {                                                  //--- If new bar
      lastBarTime = curBarTime;                                   //--- Update last time
      DetectFVGs();                                               //--- Detect FVGs
      UpdateFVGs();                                               //--- Update FVGs
      TradeOnFVGs();                                              //--- Check trades
   }

   if (TrailingType == Trailing_Points && PositionsTotal() > 0) { //--- Check trailing
      ApplyPointsTrailing();                                      //--- Apply trailing
   }
}
//+------------------------------------------------------------------+
