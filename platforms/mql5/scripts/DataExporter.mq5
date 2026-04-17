//+------------------------------------------------------------------+
//|                                                 DataExporter.mq5 |
//|                                                                  |
//| MQL5 Script - Historical OHLCV Data Exporter                     |
//|                                                                  |
//| Usage:                                                           |
//|   1. Open a chart for the symbol/timeframe you want to export    |
//|   2. Drag this script onto the chart                             |
//|   3. Configure the input parameters in the dialog:               |
//|      - InpSymbol:    Symbol name (blank = current chart symbol)   |
//|      - InpTimeframe: Timeframe enum (0 = current chart TF)       |
//|      - InpStartDate: Start date for export                       |
//|      - InpEndDate:   End date for export                         |
//|      - InpFileName:  Output CSV file name (blank = auto-name)    |
//|   4. The CSV is saved in MQL5/Files/ folder                      |
//|   5. Check the Experts tab for progress and status               |
//+------------------------------------------------------------------+
#property copyright ""
#property link      ""
#property version   "1.00"
#property script_show_inputs

//--- Input parameters
input string             InpSymbol    = "";              // Symbol (blank = current chart)
input ENUM_TIMEFRAMES    InpTimeframe = PERIOD_CURRENT;  // Timeframe (PERIOD_CURRENT = chart TF)
input datetime           InpStartDate = 0;               // Start Date (0 = 5 years ago)
input datetime           InpEndDate   = 0;               // End Date (0 = today)
input string             InpFileName  = "";              // File Name (blank = auto)

//+------------------------------------------------------------------+
//| Return a human-readable timeframe string                         |
//+------------------------------------------------------------------+
string TimeframeToString(ENUM_TIMEFRAMES tf)
  {
   switch(tf)
     {
      case PERIOD_M1:  return "M1";
      case PERIOD_M2:  return "M2";
      case PERIOD_M3:  return "M3";
      case PERIOD_M4:  return "M4";
      case PERIOD_M5:  return "M5";
      case PERIOD_M6:  return "M6";
      case PERIOD_M10: return "M10";
      case PERIOD_M12: return "M12";
      case PERIOD_M15: return "M15";
      case PERIOD_M20: return "M20";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H2:  return "H2";
      case PERIOD_H3:  return "H3";
      case PERIOD_H4:  return "H4";
      case PERIOD_H6:  return "H6";
      case PERIOD_H8:  return "H8";
      case PERIOD_H12: return "H12";
      case PERIOD_D1:  return "D1";
      case PERIOD_W1:  return "W1";
      case PERIOD_MN1: return "MN1";
      default:         return "UNK";
     }
  }

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
  {
//--- Resolve symbol
   string symbol = InpSymbol;
   if(symbol == "" || symbol == NULL)
      symbol = Symbol();

//--- Validate symbol
   if(!SymbolSelect(symbol, true))
     {
      PrintFormat("Error: Symbol '%s' not found or cannot be selected.", symbol);
      return;
     }

//--- Resolve timeframe
   ENUM_TIMEFRAMES timeframe = InpTimeframe;
   if(timeframe == PERIOD_CURRENT)
      timeframe = Period();

//--- Resolve dates
   datetime startDate = InpStartDate;
   datetime endDate   = InpEndDate;

   if(startDate == 0)
     {
      MqlDateTime now;
      TimeCurrent(now);
      now.year -= 5;
      startDate = StructToTime(now);
     }

   if(endDate == 0)
      endDate = TimeCurrent();

//--- Validate date range
   if(startDate >= endDate)
     {
      Print("Error: Start date must be before end date.");
      return;
     }

//--- Resolve file name
   string fileName = InpFileName;
   if(fileName == "" || fileName == NULL)
      fileName = "DataExport_" + symbol + "_" + TimeframeToString(timeframe) + ".csv";

//--- Print export configuration
   PrintFormat("=== Data Exporter ===");
   PrintFormat("Symbol:    %s", symbol);
   PrintFormat("Timeframe: %s", TimeframeToString(timeframe));
   PrintFormat("From:      %s", TimeToString(startDate, TIME_DATE));
   PrintFormat("To:        %s", TimeToString(endDate, TIME_DATE));
   PrintFormat("File:      %s", fileName);

//--- Request historical data
   MqlRates rates[];
   ArraySetAsSeries(rates, false);

   int copied = CopyRates(symbol, timeframe, startDate, endDate, rates);

   if(copied <= 0)
     {
      int err = GetLastError();
      PrintFormat("Error: CopyRates failed. Copied=%d, Error=%d (%s)",
                  copied, err, ErrorDescription(err));
      return;
     }

   PrintFormat("Retrieved %d bars. Writing to file...", copied);

//--- Open file for writing
   int fileHandle = FileOpen(fileName, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');

   if(fileHandle == INVALID_HANDLE)
     {
      int err = GetLastError();
      PrintFormat("Error: Cannot open file '%s'. Error=%d (%s)",
                  fileName, err, ErrorDescription(err));
      return;
     }

//--- Write CSV header
   FileWrite(fileHandle, "Date", "Time", "Open", "High", "Low", "Close", "Volume");

//--- Write data rows with progress reporting
   int progressStep = MathMax(copied / 10, 1);

   for(int i = 0; i < copied; i++)
     {
      string dateStr = TimeToString(rates[i].time, TIME_DATE);
      string timeStr = TimeToString(rates[i].time, TIME_MINUTES);

      FileWrite(fileHandle,
                dateStr,
                timeStr,
                DoubleToString(rates[i].open, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
                DoubleToString(rates[i].high, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
                DoubleToString(rates[i].low, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
                DoubleToString(rates[i].close, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
                IntegerToString(rates[i].tick_volume));

      //--- Print progress every ~10%
      if((i + 1) % progressStep == 0 || i == copied - 1)
         PrintFormat("Progress: %d / %d bars (%.0f%%)",
                     i + 1, copied, (double)(i + 1) / copied * 100.0);
     }

//--- Close file
   FileClose(fileHandle);

   PrintFormat("=== Export complete: %d bars written to %s ===", copied, fileName);
  }

//+------------------------------------------------------------------+
//| Return human-readable error description                          |
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
      case 4101:  return "Wrong chart ID";
      case 4103:  return "Cannot open chart";
      case 4301:  return "Unknown symbol";
      case 4302:  return "Symbol not selected in MarketWatch";
      case 4401:  return "Cannot open file";
      case 4402:  return "Wrong file name";
      case 4403:  return "Too long file name";
      case 4404:  return "Cannot open file";
      case 4405:  return "Text file buffer allocation error";
      case 4406:  return "Cannot delete file";
      case 4407:  return "Invalid file handle";
      case 4408:  return "Wrong file handle number";
      case 4409:  return "File must be opened with FILE_WRITE flag";
      case 5004:  return "Not enough memory for the rate array";
      case 5011:  return "Invalid or empty timeframe";
      case 5012:  return "Too many requested bars";
      case 5013:  return "Requested data not ready";
      default:    return "Error code " + IntegerToString(errorCode);
     }
  }
//+------------------------------------------------------------------+
