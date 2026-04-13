//+------------------------------------------------------------------+
//|                                           SmartRenkoLikeStep.mq5 |
//|   Renko-like step line engine (non-repainting, bar-close based)  |
//|   Exposes buffers: RenkoStep, Direction(-1/0/1), BrickSize       |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#property indicator_chart_window
#property indicator_buffers 3
#property indicator_plots   1

//--- Plot 1: Renko step line (visual approximation)
#property indicator_label1  "Renko Step"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrLime
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

//--- Inputs
input group "=== ASSET ==="
input bool   InpAutoDetectAsset = true;          // Asset Selection Mode (Auto-Detect)
input string InpManualAsset     = "XAUUSD/GOLD"; // Manual Asset Pick (label only)

input group "=== BRICK SIZE ==="
enum BrickCalcMode
{
   BRICK_ATR = 0,
   BRICK_PERCENT = 1,
   BRICK_FIXED = 2
};
input BrickCalcMode InpBrickCalc      = BRICK_ATR;  // Brick Size Calculation
input int           InpATRLen         = 14;         // ATR Length
input double        InpATRMult        = 1.0;        // ATR Mult
input double        InpCustomPct      = 1.0;        // Custom % (if Percentage selected)
input double        InpFixedBoxPoints = 50.0;       // Fixed Box Size (Points)
input double        InpRoundingStep   = 0.0;        // Rounding Step (0 = tick size)

input group "=== ENGINE ==="
input bool InpAllowMultiBrick = true;  // Allow Multi-Brick Jumps
input bool InpInitRoundFirst  = false; // Initialization: round first close to brick

//--- Buffers
double RenkoBuffer[];
double DirBuffer[];
double BrickBuffer[];

//--- Handles
int atrHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
string DetectAssetLabel()
{
   string s = _Symbol;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0 || StringFind(s, "GOLD") >= 0) return "XAUUSD/GOLD";
   if(StringFind(s, "XAG") >= 0 || StringFind(s, "SILVER") >= 0) return "XAGUSD/SILVER";
   if(StringFind(s, "BTC") >= 0) return "BTCUSD";
   if(StringFind(s, "USOIL") >= 0 || StringFind(s, "WTI") >= 0 || StringFind(s, "CRUDE") >= 0) return "US Oil";
   if(StringFind(s, "NG") >= 0 || StringFind(s, "NATGAS") >= 0) return "Natural Gas";
   return "Custom";
}

double GetTickSize()
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts > 0) return ts;
   return _Point;
}

double RoundToStep(const double value, const double step)
{
   if(step <= 0.0) return value;
   return MathRound(value / step) * step;
}

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, RenkoBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, DirBuffer,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(2, BrickBuffer, INDICATOR_CALCULATIONS);

   ArraySetAsSeries(RenkoBuffer, true);
   ArraySetAsSeries(DirBuffer, true);
   ArraySetAsSeries(BrickBuffer, true);
   ArrayInitialize(RenkoBuffer, EMPTY_VALUE);
   ArrayInitialize(DirBuffer, 0.0);
   ArrayInitialize(BrickBuffer, 0.0);

   atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpATRLen);
   if(atrHandle == INVALID_HANDLE)
   {
      Print("SmartRenkoLikeStep: failed to create ATR handle. err=", GetLastError());
      return INIT_FAILED;
   }

   string assetLabel = InpAutoDetectAsset ? DetectAssetLabel() : InpManualAsset;
   IndicatorSetString(INDICATOR_SHORTNAME, "SmartRenkoLikeStep(" + assetLabel + ")");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(rates_total < 3)
      return 0;

   ArraySetAsSeries(close, true);

   //--- Get ATR values (series)
   double atr[];
   ArraySetAsSeries(atr, true);
   int copied = CopyBuffer(atrHandle, 0, 0, rates_total, atr);
   if(copied <= 0)
      return 0;

   const double tickSize = GetTickSize();
   const double step = (InpRoundingStep > 0.0) ? InpRoundingStep : tickSize;

   // Stateful series: must compute from oldest to newest.
   // With series arrays (index 0 = newest), oldest index is rates_total-1.
   int start = (prev_calculated == 0) ? rates_total - 1 : rates_total - prev_calculated;
   if(start > rates_total - 1) start = rates_total - 1;

   // Ensure we back up by one so state connects correctly
   if(prev_calculated > 0)
      start = MathMin(start + 1, rates_total - 1);

   for(int i = start; i >= 0; i--)
   {
      //--- Compute brick size for this bar
      double brickRaw = 0.0;
      if(InpBrickCalc == BRICK_ATR)
      {
         brickRaw = atr[i] * InpATRMult;
      }
      else if(InpBrickCalc == BRICK_PERCENT)
      {
         brickRaw = close[i] * (InpCustomPct / 100.0);
      }
      else // BRICK_FIXED
      {
         brickRaw = InpFixedBoxPoints;
      }

      double brick = RoundToStep(brickRaw, step);
      if(brick < tickSize) brick = tickSize;

      BrickBuffer[i] = brick;

      //--- Initialize renko on oldest bar
      if(i == rates_total - 1)
      {
         double initRenko = close[i];
         if(InpInitRoundFirst)
            initRenko = RoundToStep(initRenko, brick);

         RenkoBuffer[i] = initRenko;
         DirBuffer[i]   = 0.0;
         continue;
      }

      double prevRenko = RenkoBuffer[i + 1];
      double prevDir   = DirBuffer[i + 1];

      double upMove = close[i] - prevRenko;
      double dnMove = prevRenko - close[i];

      double renko = prevRenko;
      double dir   = prevDir;

      if(upMove >= brick)
      {
         int bricks = 1;
         if(InpAllowMultiBrick)
            bricks = (int)MathFloor(upMove / brick);
         renko = prevRenko + bricks * brick;
         dir = 1.0;
      }
      else if(dnMove >= brick)
      {
         int bricks = 1;
         if(InpAllowMultiBrick)
            bricks = (int)MathFloor(dnMove / brick);
         renko = prevRenko - bricks * brick;
         dir = -1.0;
      }

      RenkoBuffer[i] = renko;
      DirBuffer[i]   = dir;
   }

   // MT5 expects EMPTY_VALUE for uninitialized buffer regions; ensure not used.
   return rates_total;
}
//+------------------------------------------------------------------+
