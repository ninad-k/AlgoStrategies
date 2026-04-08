//+------------------------------------------------------------------+
//|                                      MultiTF_Dashboard_EA.mq5   |
//|                                         AlgoStrategies           |
//|                                                                  |
//|  Multi-Timeframe Dashboard: EMA, Ichimoku (Tenkan/Kijun),        |
//|  Bollinger Bands — W1 / D1 / H4 / H1                            |
//|  Includes CSV export matching the dashboard layout.              |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property link      ""
#property version   "1.20"
#property description "Multi-TF Dashboard: EMA200/500/1000, Ichimoku Tenkan+Kijun, BB Middle/Upper/Lower"

//============================================================
//  INPUTS
//============================================================
input group "=== General ==="
input bool   InpUsePrevCandle   = true; // Candle Data: true=Previous Closed Candle, false=Current Price
input int    InpDisplayDigits   = 0;    // Price Display Decimals (0 = integers like 2910)

input group "=== EMA Settings ==="
input int    InpEMA1Period      = 200;  // EMA 1 Period
input int    InpEMA2Period      = 500;  // EMA 2 Period
input int    InpEMA3Period      = 1000; // EMA 3 Period

input group "=== Ichimoku Settings ==="
input int    InpTenkan          = 9;    // Tenkan-sen Period
input int    InpKijun           = 26;   // Kijun-sen Period
input int    InpSenkou          = 52;   // Senkou Span B Period

input group "=== Bollinger Bands Settings ==="
input int    InpBBPeriod        = 20;   // BB Period
input double InpBBDeviation     = 2.0;  // BB Deviation
input int    InpBBShift         = 0;    // BB Shift

input group "=== Dashboard Position ==="
input int    InpDashX           = 20;   // X Position (pixels from left)
input int    InpDashY           = 30;   // Y Position (pixels from top)
input int    InpFontSize        = 9;    // Base Font Size

input group "=== Chart Level Lines ==="
input bool   InpPlotLines       = true;  // Plot price-level H-lines on chart (current TF)
input color  InpColorW1         = clrGold;        // W1 line colour
input color  InpColorD1         = clrDodgerBlue;  // D1 line colour
input color  InpColorH4         = clrOrange;      // H4 line colour
input color  InpColorH1         = clrLimeGreen;   // H1 line colour
input int    InpLineWidth       = 1;     // Line width (1-5)

input group "=== Chart Indicator Overlays ==="
input bool   InpPlotIndicators  = true;  // Plot EMA curves + BB bands + Ichimoku on chart

input group "=== Export Settings ==="
input string InpExportFolder    = "";    // Save folder (blank = MQL5\Files\, e.g. "Reports\Gold")

//============================================================
//  CONSTANTS & GLOBALS
//============================================================
#define PREFIX  "MTFD_"
#define ROWS    8
#define COLS    4

// Timeframe array
ENUM_TIMEFRAMES g_TF[COLS]   = {PERIOD_W1, PERIOD_D1, PERIOD_H4, PERIOD_H1};
string          g_TFLabel[COLS] = {"W1", "D1", "H4", "H1"};

// Row labels (set in OnInit using input periods)
string g_RowLabel[ROWS];

// Indicator handles [timeframe index]
int g_hEMA1[COLS], g_hEMA2[COLS], g_hEMA3[COLS];
int g_hIchi[COLS];
int g_hBB[COLS];

// Shared value cache filled by FetchValues(), read by DashUpdate() and ExportExcel()
double g_Vals[ROWS][COLS];

// Resolved candle shift (0 = current price, 1 = previous closed)
// Computed once in OnInit / re-used everywhere
int g_Shift = 1;

// Per-TF line colours (indexed by COLS order: W1/D1/H4/H1)
color g_TFColor[COLS];

// Line style per row-group  (EMA=SOLID, Ichimoku=DASH, BB=DOT)
ENUM_LINE_STYLE g_LineStyle[ROWS] = {
   STYLE_SOLID, STYLE_SOLID, STYLE_SOLID,   // EMA 0-2
   STYLE_DASH,  STYLE_DASH,                 // Ichimoku 3-4
   STYLE_DOT,   STYLE_DOT,   STYLE_DOT      // BB 5-7
};

// Tracks short-names of chart indicator overlays we added so we can remove them cleanly
string g_IndNames[5];   // max 5 overlays: EMA1, EMA2, EMA3, Ichimoku, BB
int    g_IndCount   = 0;
int    g_ChartActTF = -1; // which TF's overlays are currently on the chart (-1 = none)

// Layout dimensions
int g_CW  = 110;   // data column width
int g_CH  = 22;    // cell height
int g_LW  = 160;   // label column width
int g_TH  = 28;    // title bar height
int g_HH  = 26;    // header row height

//============================================================
//  INIT
//============================================================
int OnInit()
{
   // Build row labels from actual input values
   g_RowLabel[0] = "EMA " + (string)InpEMA1Period;
   g_RowLabel[1] = "EMA " + (string)InpEMA2Period;
   g_RowLabel[2] = "EMA " + (string)InpEMA3Period;
   g_RowLabel[3] = "Tenkan Sen Line";
   g_RowLabel[4] = "Kijun Sen Line";
   g_RowLabel[5] = "Middle BB";
   g_RowLabel[6] = "Upper BB";
   g_RowLabel[7] = "Lower BB";

   // Create indicator handles for each timeframe
   for(int t = 0; t < COLS; t++)
   {
      g_hEMA1[t] = iMA(_Symbol, g_TF[t], InpEMA1Period,  0, MODE_EMA, PRICE_CLOSE);
      g_hEMA2[t] = iMA(_Symbol, g_TF[t], InpEMA2Period,  0, MODE_EMA, PRICE_CLOSE);
      g_hEMA3[t] = iMA(_Symbol, g_TF[t], InpEMA3Period,  0, MODE_EMA, PRICE_CLOSE);
      g_hIchi[t] = iIchimoku(_Symbol, g_TF[t], InpTenkan, InpKijun, InpSenkou);
      g_hBB[t]   = iBands(_Symbol, g_TF[t], InpBBPeriod, InpBBShift, InpBBDeviation, PRICE_CLOSE);

      if(g_hEMA1[t] == INVALID_HANDLE || g_hEMA2[t] == INVALID_HANDLE ||
         g_hEMA3[t] == INVALID_HANDLE || g_hIchi[t] == INVALID_HANDLE ||
         g_hBB[t]   == INVALID_HANDLE)
      {
         Alert("MultiTF Dashboard: Failed to create indicator handle for TF=", g_TFLabel[t]);
         return INIT_FAILED;
      }
   }

   // Resolve candle shift from bool input
   g_Shift = InpUsePrevCandle ? 1 : 0;

   // Populate TF colour array from inputs
   g_TFColor[0] = InpColorW1;
   g_TFColor[1] = InpColorD1;
   g_TFColor[2] = InpColorH4;
   g_TFColor[3] = InpColorH1;

   // Build the visual dashboard
   DashCreate();
   DashUpdate();        // also calls PlotLines() internally

   // Refresh every 5 seconds so dashboard stays current even without ticks
   EventSetTimer(5);

   return INIT_SUCCEEDED;
}

//============================================================
//  DEINIT
//============================================================
void OnDeinit(const int reason)
{
   EventKillTimer();
   RemoveIndicatorsFromChart(); // remove BB / Ichimoku / EMA overlays
   DeleteLines();               // remove H-level lines
   ObjectsDeleteAll(0, PREFIX); // remove dashboard panel objects
   for(int t = 0; t < COLS; t++)
   {
      IndicatorRelease(g_hEMA1[t]);
      IndicatorRelease(g_hEMA2[t]);
      IndicatorRelease(g_hEMA3[t]);
      IndicatorRelease(g_hIchi[t]);
      IndicatorRelease(g_hBB[t]);
   }
   ChartRedraw();
}

//============================================================
//  TICK & TIMER
//============================================================
void OnTick()   { DashUpdate(); }
void OnTimer()  { DashUpdate(); }

//============================================================
//  CHART EVENT — Download button click
//============================================================
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK && sparam == PREFIX + "BTN_DL")
   {
      ExportExcel();
      // Release button pressed state
      ObjectSetInteger(0, PREFIX + "BTN_DL", OBJPROP_STATE, false);
      ChartRedraw();
   }
}

//============================================================
//  FETCH VALUES — fills global g_Vals[ROWS][COLS]
//  Returns true if at least one value was retrieved.
//============================================================
bool FetchValues(int shift)
{
   bool   ok  = false;
   double buf[];   // dynamic — required for CopyBuffer

   for(int t = 0; t < COLS; t++)
   {
      // EMA 1
      g_Vals[0][t] = (CopyBuffer(g_hEMA1[t], 0, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // EMA 2
      g_Vals[1][t] = (CopyBuffer(g_hEMA2[t], 0, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // EMA 3
      g_Vals[2][t] = (CopyBuffer(g_hEMA3[t], 0, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // Ichimoku buffer 0 = Tenkan-sen
      g_Vals[3][t] = (CopyBuffer(g_hIchi[t], 0, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // Ichimoku buffer 1 = Kijun-sen
      g_Vals[4][t] = (CopyBuffer(g_hIchi[t], 1, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // BB buffer 0 = Middle
      g_Vals[5][t] = (CopyBuffer(g_hBB[t],   0, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // BB buffer 1 = Upper
      g_Vals[6][t] = (CopyBuffer(g_hBB[t],   1, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;
      // BB buffer 2 = Lower
      g_Vals[7][t] = (CopyBuffer(g_hBB[t],   2, shift, 1, buf) > 0) ? buf[0] : EMPTY_VALUE;

      for(int r = 0; r < ROWS; r++)
         if(g_Vals[r][t] != EMPTY_VALUE) ok = true;
   }
   return ok;
}

//============================================================
//  FORMAT VALUE
//============================================================
string FmtVal(double v)
{
   if(v == EMPTY_VALUE || v <= 0.0) return "N/A";
   return DoubleToString(v, InpDisplayDigits);
}

//============================================================
//  CREATE DASHBOARD OBJECTS
//============================================================
void DashCreate()
{
   int x  = InpDashX;
   int y  = InpDashY;
   int fs = InpFontSize;

   int totalW = g_LW + COLS * g_CW + 2;
   int totalH = g_TH + g_HH + ROWS * g_CH + 58;

   //--- Outer background shadow
   RectMake(PREFIX+"SHADOW", x+3, y+3, totalW+2, totalH+2, C'8,8,20', C'8,8,20', 0);
   //--- Main background
   RectMake(PREFIX+"BG",     x,   y,   totalW,   totalH,   C'16,16,38', C'70,70,140', 2);

   //--- Title bar
   RectMake(PREFIX+"TITLE_BG", x, y, totalW, g_TH, C'28,28,68', C'70,70,140', 1);
   LblMake(PREFIX+"TITLE", x + totalW/2, y + g_TH/2,
           _Symbol + "  |  Multi-Timeframe Indicator Dashboard",
           clrWhite, fs+1, true, ANCHOR_CENTER);

   //--- Column header row
   int hy = y + g_TH;
   RectMake(PREFIX+"HDR0_BG", x, hy, g_LW, g_HH, C'38,38,88', C'70,70,140', 1);
   LblMake(PREFIX+"HDR0", x + g_LW/2, hy + g_HH/2, "Condition", clrYellow, fs, true, ANCHOR_CENTER);

   for(int c = 0; c < COLS; c++)
   {
      int cx = x + g_LW + c * g_CW;
      RectMake(PREFIX+"HDR"+string(c+1)+"_BG", cx, hy, g_CW, g_HH, C'38,38,88', C'70,70,140', 1);
      LblMake(PREFIX+"HDR"+string(c+1), cx + g_CW/2, hy + g_HH/2,
              g_TFLabel[c] + " [Price]", clrYellow, fs, true, ANCHOR_CENTER);
   }

   //--- Data rows
   // Row group colours: EMA (rows 0-2) = dark olive, Ichimoku (3-4) = dark navy, BB (5-7) = dark maroon
   color grpBG[ROWS] = {
      C'22,38,18', C'22,38,18', C'22,38,18',   // EMA rows
      C'18,22,48', C'18,22,48',                 // Ichimoku rows
      C'42,18,18', C'42,18,18', C'42,18,18'    // BB rows
   };
   color altBG[ROWS] = {
      C'28,46,22', C'22,38,18', C'28,46,22',
      C'22,28,58', C'18,22,48',
      C'52,22,22', C'42,18,18', C'52,22,22'
   };

   for(int r = 0; r < ROWS; r++)
   {
      int ry  = y + g_TH + g_HH + r * g_CH;
      color bg = (r % 2 == 0) ? altBG[r] : grpBG[r];

      // Left: row label cell
      RectMake(PREFIX+"RLBG"+string(r), x,     ry, g_LW, g_CH, bg, C'55,55,110', 1);
      LblMake(PREFIX+"RLBL"+string(r),  x + 8, ry + g_CH/2,
              g_RowLabel[r], clrWhite, fs, false, ANCHOR_LEFT);

      // Right: data cells
      for(int c = 0; c < COLS; c++)
      {
         int cx = x + g_LW + c * g_CW;
         RectMake(PREFIX+"CBGR"+string(r)+"C"+string(c), cx, ry, g_CW, g_CH, bg, C'55,55,110', 1);
         LblMake(PREFIX+"CELR"+string(r)+"C"+string(c), cx + g_CW/2, ry + g_CH/2,
                 "---", clrLightYellow, fs, false, ANCHOR_CENTER);
      }
   }

   //--- Download button
   int btnY    = y + g_TH + g_HH + ROWS * g_CH + 8;
   int btnW    = 160;
   int btnH    = 26;
   int btnX    = x + (totalW - btnW) / 2;
   BtnMake(PREFIX+"BTN_DL", btnX, btnY, btnW, btnH, "  Download Excel  ", C'0,130,0', clrWhite, fs);

   //--- Candle info label
   LblMake(PREFIX+"CINFO", x + totalW/2, btnY + btnH + 6,
           CandleInfoText(), clrGray, fs - 1, false, ANCHOR_UPPER);

   ChartRedraw();
}

//============================================================
//  UPDATE DASHBOARD VALUES
//============================================================
void DashUpdate()
{
   FetchValues(g_Shift);
   PlotLines();

   for(int r = 0; r < ROWS; r++)
      for(int c = 0; c < COLS; c++)
         ObjectSetString(0, PREFIX+"CELR"+string(r)+"C"+string(c), OBJPROP_TEXT, FmtVal(g_Vals[r][c]));

   // Refresh candle info text
   ObjectSetString(0, PREFIX+"CINFO", OBJPROP_TEXT, CandleInfoText());
   ChartRedraw();
}

//============================================================
//  CANDLE INFO TEXT
//============================================================
string CandleInfoText()
{
   return InpUsePrevCandle
          ? "Displaying: Previous Close Candle"
          : "Displaying: Current Price";
}

//============================================================
//  CHART OVERLAY HELPERS
//  Naming: LPREFIX + "R<row>T<tf>"  for H-lines
//============================================================
#define LPREFIX  "MTFD_LINE_"

// Short label for H-line text
string LineLabelShort(int r, int t)
{
   string rowTag[ROWS] = {"EMA1","EMA2","EMA3","Tenkan","Kijun","MidBB","UpperBB","LowerBB"};
   return g_TFLabel[t] + "-" + rowTag[r];
}

// Returns g_TF[] index matching the current chart period, -1 if not found
int CurrentTFIndex()
{
   for(int t = 0; t < COLS; t++)
      if(g_TF[t] == _Period) return t;
   return -1;
}

//------------------------------------------------------------
//  Add actual indicator overlays (EMA curves, BB bands,
//  full Ichimoku cloud) to the main chart window.
//  Tracks added short-names so they can be cleanly removed.
//------------------------------------------------------------
void AddIndicatorsToChart(int tfIdx)
{
   RemoveIndicatorsFromChart(); // remove any previous overlays first

   int handles[5];
   handles[0] = g_hEMA1[tfIdx];
   handles[1] = g_hEMA2[tfIdx];
   handles[2] = g_hEMA3[tfIdx];
   handles[3] = g_hIchi[tfIdx]; // full Ichimoku: Tenkan, Kijun, Kumo cloud, Chikou
   handles[4] = g_hBB[tfIdx];   // Bollinger Bands: upper, middle, lower

   g_IndCount = 0;
   for(int i = 0; i < 5; i++)
   {
      if(handles[i] == INVALID_HANDLE) continue;

      int before = ChartIndicatorsTotal(0, 0);
      if(ChartIndicatorAdd(0, 0, handles[i]))
      {
         int after = ChartIndicatorsTotal(0, 0);
         if(after > before) // a new entry appeared → capture its name
            g_IndNames[g_IndCount++] = ChartIndicatorName(0, 0, after - 1);
      }
   }
   g_ChartActTF = tfIdx;
   ChartRedraw();
}

//------------------------------------------------------------
//  Remove every indicator overlay we added via AddIndicatorsToChart
//------------------------------------------------------------
void RemoveIndicatorsFromChart()
{
   for(int i = 0; i < g_IndCount; i++)
      if(g_IndNames[i] != "")
         ChartIndicatorDelete(0, 0, g_IndNames[i]);

   g_IndCount   = 0;
   g_ChartActTF = -1;
   for(int i = 0; i < 5; i++) g_IndNames[i] = "";
   ChartRedraw();
}

//------------------------------------------------------------
//  Draw / update H-lines at current-value price levels
//------------------------------------------------------------
void PlotLines()
{
   int activeTF = CurrentTFIndex();

   // ── H-lines toggle ─────────────────────────────────────
   if(!InpPlotLines)
   {
      DeleteLines(); // remove all H-lines immediately
   }
   else if(activeTF != -1)
   {
      // Remove H-lines for TFs other than the current chart TF
      for(int t = 0; t < COLS; t++)
         if(t != activeTF) DeleteTFLines(t);

      // Draw / update H-lines for the active TF
      for(int r = 0; r < ROWS; r++)
      {
         double val = g_Vals[r][activeTF];
         if(val == EMPTY_VALUE || val <= 0.0) continue;

         string name  = LPREFIX + "R" + string(r) + "T" + string(activeTF);
         string label = LineLabelShort(r, activeTF) + " " + FmtVal(val);

         if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_HLINE, 0, 0, val);

         ObjectSetDouble(0,  name, OBJPROP_PRICE,      val);
         ObjectSetInteger(0, name, OBJPROP_COLOR,      g_TFColor[activeTF]);
         ObjectSetInteger(0, name, OBJPROP_STYLE,      g_LineStyle[r]);
         ObjectSetInteger(0, name, OBJPROP_WIDTH,      InpLineWidth);
         ObjectSetString(0,  name, OBJPROP_TEXT,       label);
         ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, name, OBJPROP_BACK,       true);
         ObjectSetInteger(0, name, OBJPROP_HIDDEN,     false);
         ObjectSetInteger(0, name, OBJPROP_RAY,        true);
         ObjectSetString(0,  name, OBJPROP_TOOLTIP,    "\n");
      }
   }
   else
      DeleteLines(); // chart TF not in W1/D1/H4/H1 list — nothing to draw

   // ── Indicator overlays toggle ──────────────────────────
   if(!InpPlotIndicators)
   {
      RemoveIndicatorsFromChart(); // remove EMA / BB / Ichimoku overlays immediately
   }
   else if(activeTF != -1)
   {
      // Only re-add when TF changed — avoids duplicate overlays on every tick
      if(g_ChartActTF != activeTF)
         AddIndicatorsToChart(activeTF);
   }
   else
      RemoveIndicatorsFromChart(); // chart TF not supported — clean up

   ChartRedraw();
}

// Delete H-lines for one TF column
void DeleteTFLines(int t)
{
   for(int r = 0; r < ROWS; r++)
   {
      string name = LPREFIX + "R" + string(r) + "T" + string(t);
      if(ObjectFind(0, name) >= 0)
         ObjectDelete(0, name);
   }
}

// Delete ALL H-lines (does NOT remove indicator overlays)
void DeleteLines()
{
   for(int t = 0; t < COLS; t++)
      DeleteTFLines(t);
}

//============================================================
//  EXCEL XML HELPERS
//  Writes a single <Cell> in SpreadsheetML format.
//  sType  : "String" or "Number"
//  styleID: one of the style IDs defined in the Workbook Styles
//============================================================
void XLCell(int fh, const string sType, const string value, const string styleID)
{
   FileWriteString(fh, "    <Cell ss:StyleID=\"" + styleID + "\">" +
                       "<Data ss:Type=\"" + sType + "\">" + value + "</Data>" +
                       "</Cell>\r\n");
}

// Merged title cell spanning all 8 columns
void XLTitleCell(int fh, const string value, const string styleID)
{
   FileWriteString(fh, "    <Cell ss:MergeAcross=\"7\" ss:StyleID=\"" + styleID + "\">" +
                       "<Data ss:Type=\"String\">" + value + "</Data>" +
                       "</Cell>\r\n");
}

void XLRowOpen(int fh,  int height) { FileWriteString(fh, "   <Row ss:Height=\"" + string(height) + "\">\r\n"); }
void XLRowClose(int fh)             { FileWriteString(fh, "   </Row>\r\n"); }

//============================================================
//  EXPORT TO EXCEL  (.xls — Excel 2003 SpreadsheetML XML)
//  Opens natively in Excel / LibreOffice Calc.
//============================================================
void ExportExcel()
{
   if(!FetchValues(g_Shift))
   {
      Alert("Dashboard Export: No data available yet. Please wait for indicators to load.");
      return;
   }

   // ── Resolve export folder & filename ─────────────────────
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   // Build subfolder path (relative to MQL5\Files\)
   // Normalise: trim trailing slashes, replace forward-slashes with backslashes
   string folder = InpExportFolder;
   StringTrimRight(folder);
   StringTrimLeft(folder);
   StringReplace(folder, "/", "\\");
   // Remove any trailing backslash
   while(StringLen(folder) > 0 &&
         StringGetCharacter(folder, StringLen(folder) - 1) == '\\')
      folder = StringSubstr(folder, 0, StringLen(folder) - 1);

   // Create subfolder if one was specified (FolderCreate is safe to call even if it exists)
   if(folder != "")
      FolderCreate(folder);

   // Compose the full relative path used by FileOpen (rooted at MQL5\Files\)
   string fileOnly = StringFormat("%s_Dashboard_%04d%02d%02d_%02d%02d.xls",
                                  _Symbol, dt.year, dt.mon, dt.day, dt.hour, dt.min);
   string fname    = (folder != "") ? folder + "\\" + fileOnly : fileOnly;

   int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
   {
      Alert("Dashboard Export: Cannot create file '", fname,
            "'. Error=", GetLastError(),
            "\nCheck that the folder path is valid and contains no illegal characters.");
      return;
   }

   // ── XML + Workbook header ─────────────────────────────────
   FileWriteString(fh, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\r\n");
   FileWriteString(fh, "<?mso-application progid=\"Excel.Sheet\"?>\r\n");
   FileWriteString(fh, "<Workbook xmlns=\"urn:schemas-microsoft-com:office:spreadsheet\"\r\n");
   FileWriteString(fh, " xmlns:ss=\"urn:schemas-microsoft-com:office:spreadsheet\"\r\n");
   FileWriteString(fh, " xmlns:x=\"urn:schemas-microsoft-com:office:excel\">\r\n");

   // ── Styles ───────────────────────────────────────────────
   // Shared border snippet (reused in each style)
   string bdr = "<Borders>"
                "<Border ss:Position=\"Bottom\" ss:LineStyle=\"Continuous\" ss:Weight=\"1\" ss:Color=\"#888888\"/>"
                "<Border ss:Position=\"Left\"   ss:LineStyle=\"Continuous\" ss:Weight=\"1\" ss:Color=\"#888888\"/>"
                "<Border ss:Position=\"Right\"  ss:LineStyle=\"Continuous\" ss:Weight=\"1\" ss:Color=\"#888888\"/>"
                "<Border ss:Position=\"Top\"    ss:LineStyle=\"Continuous\" ss:Weight=\"1\" ss:Color=\"#888888\"/>"
                "</Borders>";

   string thickBdr = "<Borders>"
                     "<Border ss:Position=\"Bottom\" ss:LineStyle=\"Continuous\" ss:Weight=\"2\" ss:Color=\"#444444\"/>"
                     "<Border ss:Position=\"Left\"   ss:LineStyle=\"Continuous\" ss:Weight=\"2\" ss:Color=\"#444444\"/>"
                     "<Border ss:Position=\"Right\"  ss:LineStyle=\"Continuous\" ss:Weight=\"2\" ss:Color=\"#444444\"/>"
                     "<Border ss:Position=\"Top\"    ss:LineStyle=\"Continuous\" ss:Weight=\"2\" ss:Color=\"#444444\"/>"
                     "</Borders>";

   FileWriteString(fh, "<Styles>\r\n");

   // sTitle — merged title bar
   FileWriteString(fh, " <Style ss:ID=\"sTitle\">"
      "<Alignment ss:Horizontal=\"Center\" ss:Vertical=\"Center\" ss:WrapText=\"0\"/>"
      "<Font ss:Bold=\"1\" ss:Size=\"13\" ss:Color=\"#FFFFFF\"/>"
      "<Interior ss:Color=\"#1A1A3E\" ss:Pattern=\"Solid\"/>" + thickBdr +
      "</Style>\r\n");

   // sMeta — metadata label (left col)
   FileWriteString(fh, " <Style ss:ID=\"sMeta\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Bold=\"1\" ss:Size=\"9\" ss:Color=\"#333333\"/>"
      "<Interior ss:Color=\"#EDEDF5\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");

   // sMetaV — metadata value (right cols)
   FileWriteString(fh, " <Style ss:ID=\"sMetaV\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#333333\"/>"
      "<Interior ss:Color=\"#EDEDF5\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");

   // sHdrCond — "Condition" column header
   FileWriteString(fh, " <Style ss:ID=\"sHdrCond\">"
      "<Alignment ss:Horizontal=\"Center\" ss:Vertical=\"Center\"/>"
      "<Font ss:Bold=\"1\" ss:Size=\"10\" ss:Color=\"#FFFF00\"/>"
      "<Interior ss:Color=\"#262660\" ss:Pattern=\"Solid\"/>" + thickBdr +
      "</Style>\r\n");

   // sHdrTF — timeframe column headers
   FileWriteString(fh, " <Style ss:ID=\"sHdrTF\">"
      "<Alignment ss:Horizontal=\"Center\" ss:Vertical=\"Center\"/>"
      "<Font ss:Bold=\"1\" ss:Size=\"10\" ss:Color=\"#FFFF00\"/>"
      "<Interior ss:Color=\"#262660\" ss:Pattern=\"Solid\"/>" + thickBdr +
      "</Style>\r\n");

   // sHdrSr — Sr.No / Date / Instrument headers
   FileWriteString(fh, " <Style ss:ID=\"sHdrSr\">"
      "<Alignment ss:Horizontal=\"Center\" ss:Vertical=\"Center\"/>"
      "<Font ss:Bold=\"1\" ss:Size=\"10\" ss:Color=\"#FFFF00\"/>"
      "<Interior ss:Color=\"#262660\" ss:Pattern=\"Solid\"/>" + thickBdr +
      "</Style>\r\n");

   // Row group styles (label col = left-align, price col = right-align)
   // EMA  rows — pale green
   FileWriteString(fh, " <Style ss:ID=\"sEMAL\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#1A3A0A\"/>"
      "<Interior ss:Color=\"#DFF2D0\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sEMAV\">"
      "<Alignment ss:Horizontal=\"Right\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#1A3A0A\"/>"
      "<Interior ss:Color=\"#DFF2D0\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   // Alt EMA row — slightly darker green
   FileWriteString(fh, " <Style ss:ID=\"sEMALA\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#1A3A0A\"/>"
      "<Interior ss:Color=\"#CBEAD8\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sEMAVA\">"
      "<Alignment ss:Horizontal=\"Right\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#1A3A0A\"/>"
      "<Interior ss:Color=\"#CBEAD8\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");

   // Ichimoku rows — pale blue
   FileWriteString(fh, " <Style ss:ID=\"sIchiL\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#0A1A4A\"/>"
      "<Interior ss:Color=\"#D0DCF2\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sIchiV\">"
      "<Alignment ss:Horizontal=\"Right\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#0A1A4A\"/>"
      "<Interior ss:Color=\"#D0DCF2\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sIchiLA\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#0A1A4A\"/>"
      "<Interior ss:Color=\"#BDD0EF\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sIchiVA\">"
      "<Alignment ss:Horizontal=\"Right\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#0A1A4A\"/>"
      "<Interior ss:Color=\"#BDD0EF\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");

   // BB rows — pale red
   FileWriteString(fh, " <Style ss:ID=\"sBBL\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#4A0A0A\"/>"
      "<Interior ss:Color=\"#F2D0D0\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sBBV\">"
      "<Alignment ss:Horizontal=\"Right\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#4A0A0A\"/>"
      "<Interior ss:Color=\"#F2D0D0\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sBBLA\">"
      "<Alignment ss:Horizontal=\"Left\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#4A0A0A\"/>"
      "<Interior ss:Color=\"#EFB8B8\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");
   FileWriteString(fh, " <Style ss:ID=\"sBBVA\">"
      "<Alignment ss:Horizontal=\"Right\" ss:Vertical=\"Center\"/>"
      "<Font ss:Size=\"9\" ss:Color=\"#4A0A0A\"/>"
      "<Interior ss:Color=\"#EFB8B8\" ss:Pattern=\"Solid\"/>" + bdr +
      "</Style>\r\n");

   FileWriteString(fh, "</Styles>\r\n");

   // ── Worksheet ─────────────────────────────────────────────
   FileWriteString(fh, "<Worksheet ss:Name=\"Dashboard\">\r\n");
   FileWriteString(fh, " <Table ss:DefaultRowHeight=\"20\">\r\n");

   // Column widths: Sr.No | Date | Instrument | Condition | W1 | D1 | H4 | H1
   FileWriteString(fh, "  <Column ss:Width=\"45\"/>\r\n");   // Sr. No.
   FileWriteString(fh, "  <Column ss:Width=\"85\"/>\r\n");   // Date
   FileWriteString(fh, "  <Column ss:Width=\"110\"/>\r\n");  // Instrument
   FileWriteString(fh, "  <Column ss:Width=\"150\"/>\r\n");  // Condition
   FileWriteString(fh, "  <Column ss:Width=\"100\"/>\r\n");  // W1
   FileWriteString(fh, "  <Column ss:Width=\"100\"/>\r\n");  // D1
   FileWriteString(fh, "  <Column ss:Width=\"100\"/>\r\n");  // H4
   FileWriteString(fh, "  <Column ss:Width=\"100\"/>\r\n");  // H1

   // ── Row 1: Title (merged across all 8 cols) ───────────────
   XLRowOpen(fh, 32);
   XLTitleCell(fh, _Symbol + "  |  Multi-Timeframe Indicator Dashboard", "sTitle");
   XLRowClose(fh);

   // ── Row 2: Instrument ─────────────────────────────────────
   string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
   XLRowOpen(fh, 18);
   XLCell(fh, "String", "Instrument",  "sMeta");
   XLCell(fh, "String", _Symbol,       "sMetaV");
   XLCell(fh, "String", "",            "sMetaV");
   XLCell(fh, "String", "",            "sMetaV");
   XLCell(fh, "String", "",            "sMetaV");
   XLCell(fh, "String", "",            "sMetaV");
   XLCell(fh, "String", "",            "sMetaV");
   XLCell(fh, "String", "",            "sMetaV");
   XLRowClose(fh);

   // ── Row 3: Candle Data ────────────────────────────────────
   XLRowOpen(fh, 18);
   XLCell(fh, "String", "Candle Data",   "sMeta");
   XLCell(fh, "String", CandleInfoText(),"sMetaV");
   XLCell(fh, "String", "",              "sMetaV");
   XLCell(fh, "String", "",              "sMetaV");
   XLCell(fh, "String", "",              "sMetaV");
   XLCell(fh, "String", "",              "sMetaV");
   XLCell(fh, "String", "",              "sMetaV");
   XLCell(fh, "String", "",              "sMetaV");
   XLRowClose(fh);

   // ── Row 4: Generated ─────────────────────────────────────
   XLRowOpen(fh, 18);
   XLCell(fh, "String", "Generated", "sMeta");
   XLCell(fh, "String", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), "sMetaV");
   XLCell(fh, "String", "", "sMetaV");
   XLCell(fh, "String", "", "sMetaV");
   XLCell(fh, "String", "", "sMetaV");
   XLCell(fh, "String", "", "sMetaV");
   XLCell(fh, "String", "", "sMetaV");
   XLCell(fh, "String", "", "sMetaV");
   XLRowClose(fh);

   // ── Row 5: blank spacer ───────────────────────────────────
   XLRowOpen(fh, 8);
   for(int i = 0; i < 8; i++) XLCell(fh, "String", "", "sMetaV");
   XLRowClose(fh);

   // ── Row 6: Column headers ─────────────────────────────────
   XLRowOpen(fh, 26);
   XLCell(fh, "String", "Sr. No.",     "sHdrSr");
   XLCell(fh, "String", "Date",        "sHdrSr");
   XLCell(fh, "String", "Instrument",  "sHdrSr");
   XLCell(fh, "String", "Condition",   "sHdrCond");
   XLCell(fh, "String", "W1 [Price]",  "sHdrTF");
   XLCell(fh, "String", "D1 [Price]",  "sHdrTF");
   XLCell(fh, "String", "H4 [Price]",  "sHdrTF");
   XLCell(fh, "String", "H1 [Price]",  "sHdrTF");
   XLRowClose(fh);

   // ── Rows 7-14: Data  ─────────────────────────────────────
   // Style maps per row: [labelStyle, valueStyle]
   // Rows 0-2 = EMA, rows 3-4 = Ichimoku, rows 5-7 = BB
   string styleLbl[ROWS] = {"sEMAL","sEMALA","sEMAL","sIchiL","sIchiLA","sBBL","sBBLA","sBBL"};
   string styleVal[ROWS] = {"sEMAV","sEMAVA","sEMAV","sIchiV","sIchiVA","sBBV","sBBVA","sBBV"};

   for(int r = 0; r < ROWS; r++)
   {
      XLRowOpen(fh, 20);
      XLCell(fh, "Number", string(r + 1),   styleVal[r]);
      XLCell(fh, "String", dateStr,          styleLbl[r]);
      XLCell(fh, "String", _Symbol,          styleLbl[r]);
      XLCell(fh, "String", g_RowLabel[r],    styleLbl[r]);
      XLCell(fh, "String", FmtVal(g_Vals[r][0]), styleVal[r]);
      XLCell(fh, "String", FmtVal(g_Vals[r][1]), styleVal[r]);
      XLCell(fh, "String", FmtVal(g_Vals[r][2]), styleVal[r]);
      XLCell(fh, "String", FmtVal(g_Vals[r][3]), styleVal[r]);
      XLRowClose(fh);
   }

   // ── Close XML ────────────────────────────────────────────
   FileWriteString(fh, " </Table>\r\n");
   FileWriteString(fh, "</Worksheet>\r\n");
   FileWriteString(fh, "</Workbook>\r\n");

   FileClose(fh);

   string rootDir  = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\";
   string fullPath = rootDir + fname;
   string msg = "Excel exported successfully!"
                "\nFile : " + fileOnly +
                "\nPath : " + fullPath;
   Alert(msg);
   Print("MultiTF Dashboard Export (Excel): ", fullPath);
}

//============================================================
//  OBJECT HELPERS
//============================================================

void RectMake(const string name, int x, int y, int w, int h,
              color bg, color border, int bw)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER,       CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,    x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,    y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE,        w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,        h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,      bg);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, border);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE,  BORDER_FLAT);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,        bw);
   ObjectSetInteger(0, name, OBJPROP_BACK,         false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,   false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,       true);
}

void LblMake(const string name, int x, int y, const string text,
             color clr, int fs, bool bold, ENUM_ANCHOR_POINT anchor)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER,     CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,  x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,  y);
   ObjectSetString(0,  name, OBJPROP_TEXT,       text);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,   fs);
   ObjectSetString(0,  name, OBJPROP_FONT,       bold ? "Arial Bold" : "Arial");
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,     anchor);
   ObjectSetInteger(0, name, OBJPROP_BACK,       false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
}

void BtnMake(const string name, int x, int y, int w, int h,
             const string text, color bg, color clr, int fs)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER,       CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,    x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,    y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE,        w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,        h);
   ObjectSetString(0,  name, OBJPROP_TEXT,         text);
   ObjectSetInteger(0, name, OBJPROP_COLOR,        clr);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,      bg);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, C'0,80,0');
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,     fs);
   ObjectSetString(0,  name, OBJPROP_FONT,         "Arial Bold");
   ObjectSetInteger(0, name, OBJPROP_BACK,         false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,   false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,       true);
   ObjectSetInteger(0, name, OBJPROP_STATE,        false);
}
//+------------------------------------------------------------------+
