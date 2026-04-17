//+------------------------------------------------------------------+
//| TradeHistoryExporter_EA.mq5                                       |
//| Copyright 2025-2026, Ninad Kulkarni                               |
//| MT5 Multi-Account P&L Dashboard - Trade History Export EA         |
//+------------------------------------------------------------------+
#property copyright "Ninad Kulkarni"
#property version   "1.00"
#property description "Exports complete trade history to CSV for P&L Dashboard"
#property description "Runs daily on timer + supports manual trigger via chart button"

//--- Input Parameters
input group              "=== Export Settings ==="
input datetime           InpStartDate        = D'2020.01.01';     // Start Date
input datetime           InpEndDate          = 0;                  // End Date (0 = now)
input string             InpExportPath       = "PnlDashboard";    // Subfolder in MQL5/Files/
input bool               InpIncludeOpen      = true;               // Include Open Positions
input bool               InpAutoExport       = true;               // Enable Daily Auto-Export
input int                InpExportHour       = 23;                 // Auto-Export Hour (server time)
input int                InpExportMinute     = 0;                  // Auto-Export Minute
input bool               InpCalcMFEMAE       = true;               // Calculate MFE/MAE (slower)

//--- Global variables
static bool    g_exportedToday = false;
static int     g_lastExportDay = 0;
string         g_btnName       = "btnExportNow";

//--- Trade record struct for deal pairing
struct TradeRecord
{
   ulong    positionId;
   int      orderType;       // 0=buy, 1=sell
   string   symbol;
   long     magic;
   double   volume;
   double   entryPrice;
   double   exitPrice;
   double   sl;
   double   tp;
   datetime entryTime;
   datetime exitTime;
   double   profitLoss;
   double   commission;
   double   swap;
   string   comment;
   long     accountLogin;
   string   accountServer;
   string   accountName;
   string   accountCurrency;
   double   holdingMinutes;
   double   mfe;
   double   mae;
   ulong    dealEntryTicket;
   ulong    dealExitTicket;
   bool     isOpen;
};

//--- Entry deal storage for pairing
struct EntryDeal
{
   ulong    positionId;
   ulong    dealTicket;
   int      type;          // DEAL_TYPE_BUY or DEAL_TYPE_SELL
   string   symbol;
   long     magic;
   double   volume;
   double   price;
   double   sl;
   double   tp;
   datetime time;
   string   comment;
};

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpAutoExport)
      EventSetTimer(60);  // Check every 60 seconds

   // Create manual export button
   CreateExportButton();

   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   string server = AccountInfoString(ACCOUNT_SERVER);
   PrintFormat("TradeHistoryExporter initialized. Account: %d @ %s", login, server);
   PrintFormat("Auto-export: %s at %02d:%02d server time",
               InpAutoExport ? "ON" : "OFF", InpExportHour, InpExportMinute);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectDelete(0, g_btnName);
   ObjectDelete(0, g_btnName + "_label");
}

//+------------------------------------------------------------------+
//| Timer function - checks if export time has arrived                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(!InpAutoExport) return;

   MqlDateTime dt;
   TimeCurrent(dt);

   // Reset flag on new day
   if(dt.day_of_year != g_lastExportDay)
   {
      g_exportedToday = false;
      g_lastExportDay = dt.day_of_year;
   }

   // Check if it's export time
   if(!g_exportedToday && dt.hour == InpExportHour && dt.min == InpExportMinute)
   {
      PrintFormat("Auto-export triggered at %02d:%02d", dt.hour, dt.min);
      ExportTradeHistory();
      g_exportedToday = true;
   }
}

//+------------------------------------------------------------------+
//| Chart event handler for manual trigger button                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK && sparam == g_btnName)
   {
      Print("Manual export triggered via button");
      ExportTradeHistory();
      // Reset button state
      ObjectSetInteger(0, g_btnName, OBJPROP_STATE, false);
   }
}

//+------------------------------------------------------------------+
//| OnTick - required for EA but not used                              |
//+------------------------------------------------------------------+
void OnTick()
{
   // EA runs on timer, not on tick
}

//+------------------------------------------------------------------+
//| Create the manual export button on chart                           |
//+------------------------------------------------------------------+
void CreateExportButton()
{
   ObjectCreate(0, g_btnName, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, g_btnName, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
   ObjectSetInteger(0, g_btnName, OBJPROP_XDISTANCE, 150);
   ObjectSetInteger(0, g_btnName, OBJPROP_YDISTANCE, 30);
   ObjectSetInteger(0, g_btnName, OBJPROP_XSIZE, 140);
   ObjectSetInteger(0, g_btnName, OBJPROP_YSIZE, 30);
   ObjectSetString(0, g_btnName, OBJPROP_TEXT, "Export History");
   ObjectSetInteger(0, g_btnName, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, g_btnName, OBJPROP_BGCOLOR, clrDodgerBlue);
   ObjectSetInteger(0, g_btnName, OBJPROP_BORDER_COLOR, clrDodgerBlue);
   ObjectSetInteger(0, g_btnName, OBJPROP_FONTSIZE, 10);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Main export function                                               |
//+------------------------------------------------------------------+
void ExportTradeHistory()
{
   datetime startDt = (InpStartDate == 0) ? D'2020.01.01' : InpStartDate;
   datetime endDt   = (InpEndDate == 0)   ? TimeCurrent()  : InpEndDate;

   // Account metadata
   long    accLogin    = AccountInfoInteger(ACCOUNT_LOGIN);
   string  accServer   = AccountInfoString(ACCOUNT_SERVER);
   string  accName     = AccountInfoString(ACCOUNT_NAME);
   string  accCurrency = AccountInfoString(ACCOUNT_CURRENCY);

   PrintFormat("Exporting trade history for account %d (%s to %s)...",
               accLogin, TimeToString(startDt, TIME_DATE), TimeToString(endDt, TIME_DATE));

   //--- Step 1: Select history
   if(!HistorySelect(startDt, endDt))
   {
      PrintFormat("ERROR: HistorySelect failed. Error=%d (%s)", GetLastError(), ErrorDescription(GetLastError()));
      return;
   }

   int totalDeals = HistoryDealsTotal();
   PrintFormat("Found %d deals in history", totalDeals);

   if(totalDeals == 0)
   {
      Print("No deals found in the selected period.");
      return;
   }

   //--- Step 2: Collect entry deals for pairing
   EntryDeal entryDeals[];
   int entryCount = 0;

   // First pass: collect all entry deals
   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);

      // Skip balance operations, commissions, etc.
      if(dealType != DEAL_TYPE_BUY && dealType != DEAL_TYPE_SELL) continue;

      if(entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT)
      {
         int idx = ArrayResize(entryDeals, entryCount + 1) - 1;
         entryDeals[idx].positionId = (ulong)HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
         entryDeals[idx].dealTicket = ticket;
         entryDeals[idx].type       = (int)dealType;
         entryDeals[idx].symbol     = HistoryDealGetString(ticket, DEAL_SYMBOL);
         entryDeals[idx].magic      = HistoryDealGetInteger(ticket, DEAL_MAGIC);
         entryDeals[idx].volume     = HistoryDealGetDouble(ticket, DEAL_VOLUME);
         entryDeals[idx].price      = HistoryDealGetDouble(ticket, DEAL_PRICE);
         entryDeals[idx].sl         = HistoryDealGetDouble(ticket, DEAL_SL);
         entryDeals[idx].tp         = HistoryDealGetDouble(ticket, DEAL_TP);
         entryDeals[idx].time       = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         entryDeals[idx].comment    = HistoryDealGetString(ticket, DEAL_COMMENT);
         entryCount++;
      }
   }

   //--- Step 3: Pair entry+exit deals into TradeRecords
   TradeRecord records[];
   int recordCount = 0;

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);

      if(dealType != DEAL_TYPE_BUY && dealType != DEAL_TYPE_SELL) continue;

      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
      {
         ulong posId = (ulong)HistoryDealGetInteger(ticket, DEAL_POSITION_ID);

         // Find matching entry deal
         int entryIdx = FindEntryDeal(entryDeals, entryCount, posId);
         if(entryIdx < 0) continue;  // orphaned exit, skip

         int idx = ArrayResize(records, recordCount + 1) - 1;
         records[idx].positionId     = posId;
         records[idx].orderType      = entryDeals[entryIdx].type == DEAL_TYPE_BUY ? 0 : 1;
         records[idx].symbol         = entryDeals[entryIdx].symbol;
         records[idx].magic          = entryDeals[entryIdx].magic;
         records[idx].volume         = HistoryDealGetDouble(ticket, DEAL_VOLUME);
         records[idx].entryPrice     = entryDeals[entryIdx].price;
         records[idx].exitPrice      = HistoryDealGetDouble(ticket, DEAL_PRICE);
         records[idx].sl             = entryDeals[entryIdx].sl;
         records[idx].tp             = entryDeals[entryIdx].tp;
         records[idx].entryTime      = entryDeals[entryIdx].time;
         records[idx].exitTime       = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         records[idx].profitLoss     = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         records[idx].commission     = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         records[idx].swap           = HistoryDealGetDouble(ticket, DEAL_SWAP);
         records[idx].comment        = entryDeals[entryIdx].comment;
         records[idx].accountLogin   = accLogin;
         records[idx].accountServer  = accServer;
         records[idx].accountName    = accName;
         records[idx].accountCurrency= accCurrency;
         records[idx].dealEntryTicket= entryDeals[entryIdx].dealTicket;
         records[idx].dealExitTicket = ticket;
         records[idx].isOpen         = false;

         // Holding time
         if(records[idx].exitTime > records[idx].entryTime)
            records[idx].holdingMinutes = (double)(records[idx].exitTime - records[idx].entryTime) / 60.0;

         // MFE/MAE
         if(InpCalcMFEMAE)
            CalculateMFEMAE(records[idx]);

         recordCount++;
      }
   }

   //--- Step 4: Include open positions
   if(InpIncludeOpen)
   {
      int posTotal = PositionsTotal();
      for(int i = 0; i < posTotal; i++)
      {
         ulong posTicket = PositionGetTicket(i);
         if(posTicket == 0) continue;

         int idx = ArrayResize(records, recordCount + 1) - 1;
         records[idx].positionId     = posTicket;
         records[idx].orderType      = (int)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 0 : 1;
         records[idx].symbol         = PositionGetString(POSITION_SYMBOL);
         records[idx].magic          = PositionGetInteger(POSITION_MAGIC);
         records[idx].volume         = PositionGetDouble(POSITION_VOLUME);
         records[idx].entryPrice     = PositionGetDouble(POSITION_PRICE_OPEN);
         records[idx].exitPrice      = 0;
         records[idx].sl             = PositionGetDouble(POSITION_SL);
         records[idx].tp             = PositionGetDouble(POSITION_TP);
         records[idx].entryTime      = (datetime)PositionGetInteger(POSITION_TIME);
         records[idx].exitTime       = 0;
         records[idx].profitLoss     = PositionGetDouble(POSITION_PROFIT);
         records[idx].commission     = PositionGetDouble(POSITION_COMMISSION);
         records[idx].swap           = PositionGetDouble(POSITION_SWAP);
         records[idx].comment        = PositionGetString(POSITION_COMMENT) + " [OPEN]";
         records[idx].accountLogin   = accLogin;
         records[idx].accountServer  = accServer;
         records[idx].accountName    = accName;
         records[idx].accountCurrency= accCurrency;
         records[idx].dealEntryTicket= posTicket;
         records[idx].dealExitTicket = 0;
         records[idx].isOpen         = true;
         records[idx].holdingMinutes = (double)(TimeCurrent() - records[idx].entryTime) / 60.0;
         records[idx].mfe            = 0;
         records[idx].mae            = 0;
         recordCount++;
      }
   }

   PrintFormat("Paired %d trade records", recordCount);

   //--- Step 5: Write CSV
   if(recordCount == 0)
   {
      Print("No trade records to export.");
      return;
   }

   string dateStr = TimeToString(TimeCurrent(), TIME_DATE);
   StringReplace(dateStr, ".", "_");
   string fileName = InpExportPath + "/TradeHistory_" + IntegerToString(accLogin) + "_" + dateStr + ".csv";

   int fileHandle = FileOpen(fileName, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(fileHandle == INVALID_HANDLE)
   {
      PrintFormat("ERROR: Cannot open file %s. Error=%d (%s)", fileName, GetLastError(), ErrorDescription(GetLastError()));
      return;
   }

   // Header
   FileWrite(fileHandle,
      "Ticket", "OrderType", "Symbol", "MagicNumber", "Volume",
      "EntryPrice", "ExitPrice", "SL", "TP",
      "EntryTime", "ExitTime", "ProfitLoss", "Commission", "Swap", "OrderComment",
      "AccountLogin", "AccountServer", "AccountName", "AccountCurrency",
      "HoldingTimeMinutes", "MFE", "MAE", "DealEntryTicket", "DealExitTicket", "IsOpen");

   // Data rows
   int progressStep = MathMax(1, recordCount / 10);
   for(int i = 0; i < recordCount; i++)
   {
      if(i % progressStep == 0)
         PrintFormat("Writing... %d%%", (int)(100.0 * i / recordCount));

      int digits = (int)SymbolInfoInteger(records[i].symbol, SYMBOL_DIGITS);
      if(digits <= 0) digits = 5;

      FileWrite(fileHandle,
         IntegerToString((long)records[i].positionId),
         records[i].orderType == 0 ? "buy" : "sell",
         records[i].symbol,
         IntegerToString(records[i].magic),
         DoubleToString(records[i].volume, 2),
         DoubleToString(records[i].entryPrice, digits),
         records[i].exitPrice > 0 ? DoubleToString(records[i].exitPrice, digits) : "0",
         DoubleToString(records[i].sl, digits),
         DoubleToString(records[i].tp, digits),
         TimeToString(records[i].entryTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
         records[i].exitTime > 0 ? TimeToString(records[i].exitTime, TIME_DATE | TIME_MINUTES | TIME_SECONDS) : "",
         DoubleToString(records[i].profitLoss, 2),
         DoubleToString(records[i].commission, 2),
         DoubleToString(records[i].swap, 2),
         records[i].comment,
         IntegerToString(records[i].accountLogin),
         records[i].accountServer,
         records[i].accountName,
         records[i].accountCurrency,
         DoubleToString(records[i].holdingMinutes, 1),
         DoubleToString(records[i].mfe, digits),
         DoubleToString(records[i].mae, digits),
         IntegerToString((long)records[i].dealEntryTicket),
         IntegerToString((long)records[i].dealExitTicket),
         records[i].isOpen ? "1" : "0");
   }

   FileClose(fileHandle);
   PrintFormat("SUCCESS: Exported %d records to %s", recordCount, fileName);
}

//+------------------------------------------------------------------+
//| Find entry deal by position ID                                     |
//+------------------------------------------------------------------+
int FindEntryDeal(EntryDeal &entries[], int count, ulong positionId)
{
   for(int i = 0; i < count; i++)
   {
      if(entries[i].positionId == positionId)
         return i;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Calculate MFE/MAE using M1 bars between entry and exit             |
//+------------------------------------------------------------------+
void CalculateMFEMAE(TradeRecord &record)
{
   record.mfe = 0;
   record.mae = 0;

   if(record.entryTime == 0 || record.exitTime == 0) return;
   if(record.exitTime <= record.entryTime) return;

   MqlRates rates[];
   int copied = CopyRates(record.symbol, PERIOD_M1, record.entryTime, record.exitTime, rates);
   if(copied <= 0) return;

   double maxHigh = rates[0].high;
   double minLow  = rates[0].low;

   for(int i = 1; i < copied; i++)
   {
      if(rates[i].high > maxHigh) maxHigh = rates[i].high;
      if(rates[i].low  < minLow)  minLow  = rates[i].low;
   }

   if(record.orderType == 0) // Buy
   {
      record.mfe = maxHigh - record.entryPrice;
      record.mae = record.entryPrice - minLow;
   }
   else // Sell
   {
      record.mfe = record.entryPrice - minLow;
      record.mae = maxHigh - record.entryPrice;
   }
}

//+------------------------------------------------------------------+
//| Error description helper (matches DataExporter.mq5 pattern)        |
//+------------------------------------------------------------------+
string ErrorDescription(int errorCode)
{
   switch(errorCode)
   {
      case 0:     return "No error";
      case 4001:  return "Unexpected internal error";
      case 4002:  return "Wrong internal parameter";
      case 4003:  return "Invalid parameter";
      case 4004:  return "Not enough memory";
      case 5001:  return "Too many opened files";
      case 5002:  return "Wrong file name";
      case 5003:  return "Too long file name";
      case 5004:  return "Cannot open file";
      case 5005:  return "Text file buffer allocation error";
      case 5006:  return "Cannot delete file";
      case 5007:  return "Invalid file handle";
      case 5008:  return "Wrong file handle number";
      case 5009:  return "File must be opened with FILE_WRITE flag";
      case 5010:  return "File must be opened with FILE_READ flag";
      case 5011:  return "File must be opened as binary";
      case 5012:  return "File must be opened as text";
      case 5013:  return "Wrong data type for file reading";
      case 4301:  return "Unknown symbol";
      case 4302:  return "Symbol not selected in Market Watch";
      default:    return "Error " + IntegerToString(errorCode);
   }
}
//+------------------------------------------------------------------+
