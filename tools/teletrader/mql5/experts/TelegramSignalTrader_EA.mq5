//+------------------------------------------------------------------+
//|                                     TelegramSignalTrader_EA.mq5 |
//|              TeleTrader — Telegram signal auto-trader for MT5    |
//+------------------------------------------------------------------+
//| Polls TeleTrader API for parsed Telegram signals and places      |
//| pending orders with partial profit booking + trailing SL.        |
//|                                                                  |
//| Signal flow:                                                     |
//|   Telegram → Bot → Parser → API → THIS EA polls → Orders        |
//+------------------------------------------------------------------+
#property copyright "TeleTrader"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>
#include "../include/PendingOrderManager.mqh"

//--- Lot mode enum
enum ENUM_LOT_MODE
{
    LOT_MODE_FIXED = 0,   // Fixed lot size
    LOT_MODE_RISK  = 1    // Risk % of balance
};

//--- Input parameters
input group "== Lot Sizing =="
input ENUM_LOT_MODE InpLotMode    = LOT_MODE_FIXED;  // Lot calculation mode
input double InpLotSize           = 0.01;             // Fixed lot size
input bool   InpUseSignalLot      = false;            // Accept lot size from signal?
input double InpRiskPercent       = 1.0;              // Risk % of balance (Risk mode)

input group "== Trade Settings =="
input int    InpMagicNumber   = 20260410; // Magic number

input group "== Partial Profit Booking =="
input bool   InpEnablePartialTP = true;  // Enable partial TP management?
input double InpTP1Pct        = 30;      // TP1 close % (default 30%)
input double InpTP2Pct        = 50;      // TP2 close % (default 50%)
input double InpTP3Pct        = 10;      // TP3 close % (default 10%)
input double InpResidualPct   = 10;      // Residual % for trailing (default 10%)

input group "== Trailing Stop =="
input bool   InpEnableTrailing = true;   // Enable trailing stop?
input double InpTrailingPoints = 200;    // Trailing SL distance (points)

input group "== API Settings =="
input string InpAPIUrl        = "http://127.0.0.1:8100"; // TeleTrader API URL
input int    InpPollIntervalSec = 5;     // Poll interval (seconds)

//--- Global variables
CPendingOrderManager g_orderMgr;
int    g_lastSeq = 0;                    // cursor for polling
datetime g_lastPollTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("[INIT] ====================================");
    Print("[INIT] TeleTrader EA v2.0 starting...");

    // Validate TP percentages (only when partial TP is enabled)
    if(InpEnablePartialTP)
    {
        double totalPct = InpTP1Pct + InpTP2Pct + InpTP3Pct + InpResidualPct;
        if(MathAbs(totalPct - 100.0) > 0.01)
        {
            PrintFormat("[INIT] ERROR: TP percentages must sum to 100%%. Got %.1f%%", totalPct);
            return INIT_PARAMETERS_INCORRECT;
        }
    }

    // Initialize order manager
    g_orderMgr.Init(InpMagicNumber);
    g_orderMgr.SetTPConfig(InpTP1Pct, InpTP2Pct, InpTP3Pct, InpResidualPct);
    g_orderMgr.SetTrailingPoints(InpTrailingPoints);
    g_orderMgr.SetPartialTPEnabled(InpEnablePartialTP);
    g_orderMgr.SetTrailingEnabled(InpEnableTrailing);

    // Log lot mode configuration
    if(InpLotMode == LOT_MODE_FIXED)
        PrintFormat("[INIT] Lot mode: FIXED (%.2f lots)", InpLotSize);
    else
        PrintFormat("[INIT] Lot mode: RISK (%.1f%% of balance)", InpRiskPercent);

    PrintFormat("[INIT] Use signal lot: %s", InpUseSignalLot ? "YES (overrides if present)" : "NO");
    PrintFormat("[INIT] Partial TP: %s", InpEnablePartialTP ? "ON" : "OFF (close 100% at TP1)");
    if(InpEnablePartialTP)
        PrintFormat("[INIT] TP config: TP1=%.0f%% TP2=%.0f%% TP3=%.0f%% Residual=%.0f%%",
                    InpTP1Pct, InpTP2Pct, InpTP3Pct, InpResidualPct);
    PrintFormat("[INIT] Trailing: %s%s", InpEnableTrailing ? "ON" : "OFF",
                InpEnableTrailing ? StringFormat(" (%.0f points)", InpTrailingPoints) : "");
    PrintFormat("[INIT] Magic: %d, Poll interval: %d sec", InpMagicNumber, InpPollIntervalSec);
    PrintFormat("[INIT] API: %s", InpAPIUrl);
    PrintFormat("[INIT] Account balance: %.2f %s", AccountInfoDouble(ACCOUNT_BALANCE),
                AccountInfoString(ACCOUNT_CURRENCY));

    // Test API connectivity
    if(!_TestAPIConnection())
    {
        Print("[INIT] WARNING: Could not reach TeleTrader API at ", InpAPIUrl);
        Print("[INIT] EA will keep retrying on each poll cycle.");
    }
    else
    {
        Print("[INIT] API connected successfully.");
    }

    Print("[INIT] TeleTrader EA initialized.");
    Print("[INIT] ====================================");

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    PrintFormat("[DEINIT] TeleTrader EA stopped. Reason code: %d", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
    // Manage existing positions on every tick
    g_orderMgr.ManagePositions();

    // Poll API at configured interval
    datetime now = TimeCurrent();
    if(now - g_lastPollTime < InpPollIntervalSec)
        return;
    g_lastPollTime = now;

    _PollForSignals();
}

//+------------------------------------------------------------------+
//| Trade transaction handler — detect pending order activations      |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
    g_orderMgr.OnTransaction(trans, request, result);
}

//+------------------------------------------------------------------+
//| Calculate lot size based on mode and signal                       |
//+------------------------------------------------------------------+
double _CalculateLotSize(const string &symbol, double signalLots, double slDistance)
{
    double finalLots = InpLotSize; // default

    // Priority 1: If signal lot is present and InpUseSignalLot is enabled
    if(InpUseSignalLot && signalLots > 0)
    {
        finalLots = signalLots;
        PrintFormat("[LOT] Using signal lot size: %.2f", finalLots);
    }
    // Priority 2: Risk-based calculation
    else if(InpLotMode == LOT_MODE_RISK)
    {
        double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
        double riskAmount = balance * InpRiskPercent / 100.0;
        double tickSize   = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
        double tickValue  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
        double point      = SymbolInfoDouble(symbol, SYMBOL_POINT);

        if(tickSize > 0 && tickValue > 0 && slDistance > 0)
        {
            // Convert SL distance in price to ticks, then to money per lot
            double slTicks        = slDistance / tickSize;
            double riskPerLot     = slTicks * tickValue;
            finalLots             = riskAmount / riskPerLot;

            PrintFormat("[LOT] Risk calc: balance=%.2f, risk%%=%.1f%%, riskAmount=%.2f",
                        balance, InpRiskPercent, riskAmount);
            PrintFormat("[LOT] Risk calc: slDist=%.5f, tickSize=%.5f, tickValue=%.2f",
                        slDistance, tickSize, tickValue);
            PrintFormat("[LOT] Risk calc: slTicks=%.1f, riskPerLot=%.2f, rawLots=%.4f",
                        slTicks, riskPerLot, finalLots);
        }
        else
        {
            PrintFormat("[LOT] WARNING: Cannot calculate risk lots (tickSize=%.5f, tickValue=%.2f, slDist=%.5f). Using fixed: %.2f",
                        tickSize, tickValue, slDistance, InpLotSize);
            finalLots = InpLotSize;
        }
    }
    // Priority 3: Fixed lot
    else
    {
        finalLots = InpLotSize;
        PrintFormat("[LOT] Using fixed lot size: %.2f", finalLots);
    }

    // Normalize to broker constraints
    double minLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double maxLot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double stepLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);

    if(stepLot > 0)
        finalLots = MathFloor(finalLots / stepLot) * stepLot;
    if(finalLots < minLot) finalLots = minLot;
    if(finalLots > maxLot) finalLots = maxLot;

    PrintFormat("[LOT] Final lot size: %.2f (min=%.2f, max=%.2f, step=%.2f)",
                finalLots, minLot, maxLot, stepLot);

    return finalLots;
}

//+------------------------------------------------------------------+
//| Poll TeleTrader API for new signals                               |
//+------------------------------------------------------------------+
void _PollForSignals()
{
    string url = InpAPIUrl + "/api/v1/signals?since=" + IntegerToString(g_lastSeq);
    string headers = "Content-Type: application/json\r\n";
    char   postData[];
    char   resultData[];
    string resultHeaders;

    int timeout = 5000; // 5 seconds

    int res = WebRequest("GET", url, headers, timeout, postData, resultData, resultHeaders);

    if(res != 200)
    {
        if(res == -1)
        {
            int err = GetLastError();
            if(err == 4014)
                Print("[POLL] ERROR: Add '", InpAPIUrl, "' to Tools > Options > Expert Advisors > Allow WebRequest");
            else
                PrintFormat("[POLL] ERROR: WebRequest failed, error=%d", err);
        }
        else
        {
            PrintFormat("[POLL] ERROR: API returned HTTP %d", res);
        }
        return;
    }

    string json = CharArrayToString(resultData);

    // Parse the signals array from JSON response
    _ProcessSignalsJSON(json);
}

//+------------------------------------------------------------------+
//| Parse signals JSON and place pending orders                       |
//+------------------------------------------------------------------+
void _ProcessSignalsJSON(const string &json)
{
    // Find the signals array
    int arrStart = StringFind(json, "\"signals\"");
    if(arrStart < 0) return;

    arrStart = StringFind(json, "[", arrStart);
    if(arrStart < 0) return;

    // Find matching ] for the signals array (skip nested [] inside)
    int arrEnd = _FindMatchingBracket(json, arrStart, '[', ']');
    if(arrEnd < 0) return;

    string arrContent = StringSubstr(json, arrStart + 1, arrEnd - arrStart - 1);
    StringTrimLeft(arrContent);
    StringTrimRight(arrContent);
    if(StringLen(arrContent) == 0)
        return; // empty array

    // Find each { ... } signal object, handling nested braces
    int searchPos = 0;
    while(searchPos < StringLen(arrContent))
    {
        int objStart = StringFind(arrContent, "{", searchPos);
        if(objStart < 0) break;

        // Find matching } for this object (skip nested {} inside)
        int objEnd = _FindMatchingBracket(arrContent, objStart, '{', '}');
        if(objEnd < 0) break;

        string signalJson = StringSubstr(arrContent, objStart, objEnd - objStart + 1);
        _ProcessSingleSignal(signalJson);

        searchPos = objEnd + 1;
    }
}

//+------------------------------------------------------------------+
//| Find matching closing bracket, skipping nested pairs              |
//+------------------------------------------------------------------+
int _FindMatchingBracket(const string &text, int openPos, ushort openChar, ushort closeChar)
{
    int depth = 0;
    int len = StringLen(text);
    for(int i = openPos; i < len; i++)
    {
        ushort ch = StringGetCharacter(text, i);
        if(ch == openChar)
            depth++;
        else if(ch == closeChar)
        {
            depth--;
            if(depth == 0)
                return i;
        }
    }
    return -1; // no match found
}

//+------------------------------------------------------------------+
//| Process a single signal JSON object                               |
//+------------------------------------------------------------------+
void _ProcessSingleSignal(const string &signalJson)
{
    string signalId  = _ExtractJsonString(signalJson, "signalId");
    int    seq       = (int)_ExtractJsonNumber(signalJson, "seq");
    string symbol    = _ExtractJsonString(signalJson, "symbol");
    string direction = _ExtractJsonString(signalJson, "direction");
    string orderType = _ExtractJsonString(signalJson, "orderType");
    double entryPrice = _ExtractJsonNumber(signalJson, "entryPrice");
    double stopLoss   = _ExtractJsonNumber(signalJson, "stopLoss");
    string source     = _ExtractJsonString(signalJson, "source");
    double signalLotSize = _ExtractJsonNumber(signalJson, "lotSize");

    // Update cursor
    if(seq > g_lastSeq)
        g_lastSeq = seq;

    // Validate
    if(signalId == "" || symbol == "" || direction == "" || entryPrice == 0)
    {
        PrintFormat("[SIGNAL] ERROR: Invalid signal JSON (id=%s, sym=%s, dir=%s, entry=%.5f)",
                    signalId, symbol, direction, entryPrice);
        return;
    }

    // Check if already processed
    if(g_orderMgr.HasSignal(signalId))
        return;

    // Extract take profits array
    double tp1 = 0, tp2 = 0, tp3 = 0;
    _ExtractTakeProfits(signalJson, tp1, tp2, tp3);

    int dir = (direction == "buy") ? 1 : -1;

    PrintFormat("[SIGNAL] ========== NEW SIGNAL ==========");
    PrintFormat("[SIGNAL] ID: %s  seq: %d  source: %s", signalId, seq, source);
    PrintFormat("[SIGNAL] %s %s %s @ %.5f", symbol, direction, orderType, entryPrice);
    PrintFormat("[SIGNAL] SL=%.5f  TP1=%.5f  TP2=%.5f  TP3=%.5f", stopLoss, tp1, tp2, tp3);
    if(signalLotSize > 0)
        PrintFormat("[SIGNAL] Signal lot size: %.2f", signalLotSize);

    // Calculate lot size
    double slDistance = MathAbs(entryPrice - stopLoss);
    double lots = _CalculateLotSize(symbol, signalLotSize, slDistance);

    // Place the pending order
    bool ok = g_orderMgr.PlaceOrder(
        signalId, symbol, dir, orderType,
        entryPrice, stopLoss, tp1, tp2, tp3, lots
    );

    if(ok)
        PrintFormat("[SIGNAL] Order placed successfully for %s", signalId);
    else
        PrintFormat("[SIGNAL] FAILED to place order for %s", signalId);
}

//+------------------------------------------------------------------+
//| Extract a string value from JSON by key                           |
//+------------------------------------------------------------------+
string _ExtractJsonString(const string &json, const string &key)
{
    string searchKey = "\"" + key + "\"";
    int pos = StringFind(json, searchKey);
    if(pos < 0) return "";

    // Find the colon after the key
    int colonPos = StringFind(json, ":", pos + StringLen(searchKey));
    if(colonPos < 0) return "";

    // Find opening quote
    int quoteStart = StringFind(json, "\"", colonPos + 1);
    if(quoteStart < 0) return "";

    // Find closing quote
    int quoteEnd = StringFind(json, "\"", quoteStart + 1);
    if(quoteEnd < 0) return "";

    return StringSubstr(json, quoteStart + 1, quoteEnd - quoteStart - 1);
}

//+------------------------------------------------------------------+
//| Extract a numeric value from JSON by key                          |
//+------------------------------------------------------------------+
double _ExtractJsonNumber(const string &json, const string &key)
{
    string searchKey = "\"" + key + "\"";
    int pos = StringFind(json, searchKey);
    if(pos < 0) return 0;

    int colonPos = StringFind(json, ":", pos + StringLen(searchKey));
    if(colonPos < 0) return 0;

    // Find the start of the number (skip whitespace)
    int numStart = colonPos + 1;
    while(numStart < StringLen(json))
    {
        ushort ch = StringGetCharacter(json, numStart);
        if(ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r')
            break;
        numStart++;
    }

    // Check for null
    if(StringSubstr(json, numStart, 4) == "null")
        return 0;

    // Read until non-numeric character
    string numStr = "";
    for(int i = numStart; i < StringLen(json); i++)
    {
        ushort ch = StringGetCharacter(json, i);
        if((ch >= '0' && ch <= '9') || ch == '.' || ch == '-')
            numStr += ShortToString(ch);
        else
            break;
    }

    return StringToDouble(numStr);
}

//+------------------------------------------------------------------+
//| Extract take profit array from JSON                               |
//+------------------------------------------------------------------+
void _ExtractTakeProfits(const string &json, double &tp1, double &tp2, double &tp3)
{
    int tpStart = StringFind(json, "\"takeProfits\"");
    if(tpStart < 0) return;

    int arrStart = StringFind(json, "[", tpStart);
    if(arrStart < 0) return;

    int arrEnd = StringFind(json, "]", arrStart);
    if(arrEnd < 0) return;

    string tpContent = StringSubstr(json, arrStart + 1, arrEnd - arrStart - 1);

    // Split by comma
    string parts[];
    int count = StringSplit(tpContent, ',', parts);

    if(count >= 1) { StringTrimLeft(parts[0]); StringTrimRight(parts[0]); tp1 = StringToDouble(parts[0]); }
    if(count >= 2) { StringTrimLeft(parts[1]); StringTrimRight(parts[1]); tp2 = StringToDouble(parts[1]); }
    if(count >= 3) { StringTrimLeft(parts[2]); StringTrimRight(parts[2]); tp3 = StringToDouble(parts[2]); }
}

//+------------------------------------------------------------------+
//| Test API connectivity                                             |
//+------------------------------------------------------------------+
bool _TestAPIConnection()
{
    string url = InpAPIUrl + "/health";
    string headers = "";
    char   postData[];
    char   resultData[];
    string resultHeaders;

    int res = WebRequest("GET", url, headers, 3000, postData, resultData, resultHeaders);
    return (res == 200);
}
