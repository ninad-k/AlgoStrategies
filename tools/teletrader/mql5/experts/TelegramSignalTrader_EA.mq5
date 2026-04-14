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
#property version   "2.10"
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

input group "== Notifications =="
input bool   InpNotifyTelegram = true;   // Send trade updates to Telegram?

input group "== API Settings =="
input string InpAPIUrl        = "http://127.0.0.1:8100"; // TeleTrader API URL
input int    InpPollIntervalSec = 5;     // Poll interval (seconds)

//--- Global variables
CPendingOrderManager g_orderMgr;
int    g_lastSeq = 0;
datetime g_lastPollTime = 0;
bool   g_apiConnected = false;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("[INIT] ====================================");
    Print("[INIT] TeleTrader EA v2.1 starting...");

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

    // Log configuration
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
    PrintFormat("[INIT] Telegram notifications: %s", InpNotifyTelegram ? "ON" : "OFF");
    PrintFormat("[INIT] Magic: %d, Poll interval: %d sec", InpMagicNumber, InpPollIntervalSec);
    PrintFormat("[INIT] API: %s", InpAPIUrl);
    PrintFormat("[INIT] Account balance: %.2f %s", AccountInfoDouble(ACCOUNT_BALANCE),
                AccountInfoString(ACCOUNT_CURRENCY));

    // Test API connectivity
    g_apiConnected = _TestAPIConnection();
    if(!g_apiConnected)
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

    // Show initial dashboard
    _UpdateDashboard();

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Comment(""); // Clear chart dashboard
    PrintFormat("[DEINIT] TeleTrader EA stopped. Reason code: %d", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
    // Manage existing positions on every tick
    g_orderMgr.ManagePositions();

    // Send any queued notifications
    _DrainNotifications();

    // Report any queued trade events to API
    _DrainTradeEvents();

    // Update chart dashboard
    _UpdateDashboard();

    // Poll API at configured interval
    datetime now = TimeCurrent();
    if(now - g_lastPollTime < InpPollIntervalSec)
        return;
    g_lastPollTime = now;

    _PollForSignals();
}

//+------------------------------------------------------------------+
//| Trade transaction handler                                         |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
    g_orderMgr.OnTransaction(trans, request, result);
}

//+------------------------------------------------------------------+
//| Update chart dashboard via Comment()                              |
//+------------------------------------------------------------------+
void _UpdateDashboard()
{
    string dash = g_orderMgr.GetDashboardText(g_apiConnected, g_lastPollTime, g_lastSeq);
    Comment(dash);
}

//+------------------------------------------------------------------+
//| Drain notification queue and send to Telegram                     |
//+------------------------------------------------------------------+
void _DrainNotifications()
{
    if(!InpNotifyTelegram) return;
    if(!g_orderMgr.HasNotifications()) return;

    // Send up to 3 notifications per tick to avoid blocking
    int sent = 0;
    while(g_orderMgr.HasNotifications() && sent < 3)
    {
        string msg = g_orderMgr.PopNotification();
        if(msg != "")
        {
            _SendTelegramNotification(msg);
            sent++;
        }
    }
}

//+------------------------------------------------------------------+
//| Send notification via TeleTrader API -> Telegram                  |
//+------------------------------------------------------------------+
void _SendTelegramNotification(const string &message)
{
    string url = InpAPIUrl + "/api/v1/notify";
    string headers = "Content-Type: application/json\r\n";

    // Build JSON: {"message": "..."}
    // Escape quotes and newlines in the message
    string escaped = message;
    StringReplace(escaped, "\\", "\\\\");
    StringReplace(escaped, "\"", "\\\"");
    StringReplace(escaped, "\n", "\\n");

    string jsonBody = "{\"message\": \"" + escaped + "\"}";
    char postData[];
    StringToCharArray(jsonBody, postData, 0, WHOLE_ARRAY, CP_UTF8);
    // Remove null terminator that StringToCharArray adds
    ArrayResize(postData, ArraySize(postData) - 1);

    char resultData[];
    string resultHeaders;

    int res = WebRequest("POST", url, headers, 3000, postData, resultData, resultHeaders);

    if(res == 200)
        PrintFormat("[NOTIFY] Telegram notification sent (%d chars)", StringLen(message));
    else
        PrintFormat("[NOTIFY] Failed to send notification (HTTP %d)", res);
}

//+------------------------------------------------------------------+
//| Drain trade event queue and POST to API                           |
//+------------------------------------------------------------------+
void _DrainTradeEvents()
{
    if(!g_orderMgr.HasTradeEvents()) return;

    // Send up to 3 events per tick to avoid blocking
    int sent = 0;
    TradeEvent evt;
    while(g_orderMgr.HasTradeEvents() && sent < 3)
    {
        if(g_orderMgr.PopTradeEvent(evt))
        {
            _ReportTradeEvent(evt.signalId, evt.eventType, evt.symbol,
                              evt.direction, evt.lots, evt.price, evt.pnl,
                              evt.source, evt.details);
            sent++;
        }
    }
}

//+------------------------------------------------------------------+
//| Report a single trade event to API                                |
//+------------------------------------------------------------------+
void _ReportTradeEvent(const string &signalId, const string &eventType,
                       const string &symbol, const string &direction,
                       double lots, double price, double pnl,
                       const string &source, const string &details)
{
    string url = InpAPIUrl + "/api/v1/trade/update";
    string headers = "Content-Type: application/json\r\n";

    // Escape strings for JSON
    string escDetails = details;
    StringReplace(escDetails, "\\", "\\\\");
    StringReplace(escDetails, "\"", "\\\"");

    string jsonBody = StringFormat(
        "{\"signal_id\":\"%s\",\"event_type\":\"%s\",\"symbol\":\"%s\","
        "\"direction\":\"%s\",\"lots\":%.4f,\"price\":%.5f,\"pnl\":%.2f,"
        "\"source\":\"%s\",\"details\":\"%s\"}",
        signalId, eventType, symbol, direction, lots, price, pnl, source, escDetails
    );

    char postData[];
    StringToCharArray(jsonBody, postData, 0, WHOLE_ARRAY, CP_UTF8);
    ArrayResize(postData, ArraySize(postData) - 1);

    char resultData[];
    string resultHeaders;

    int res = WebRequest("POST", url, headers, 3000, postData, resultData, resultHeaders);

    if(res == 201)
        PrintFormat("[TRADE_EVENT] Reported: %s %s %s (pnl=%.2f)", eventType, symbol, direction, pnl);
    else
        PrintFormat("[TRADE_EVENT] Failed to report %s (HTTP %d)", eventType, res);
}

//+------------------------------------------------------------------+
//| Calculate lot size based on mode and signal                       |
//+------------------------------------------------------------------+
double _CalculateLotSize(const string &symbol, double signalLots, double slDistance)
{
    double finalLots = InpLotSize;

    if(InpUseSignalLot && signalLots > 0)
    {
        finalLots = signalLots;
        PrintFormat("[LOT] Using signal lot size: %.2f", finalLots);
    }
    else if(InpLotMode == LOT_MODE_RISK)
    {
        double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
        double riskAmount = balance * InpRiskPercent / 100.0;
        double tickSize   = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
        double tickValue  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);

        if(tickSize > 0 && tickValue > 0 && slDistance > 0)
        {
            double slTicks    = slDistance / tickSize;
            double riskPerLot = slTicks * tickValue;
            finalLots         = riskAmount / riskPerLot;

            PrintFormat("[LOT] Risk calc: balance=%.2f, risk%%=%.1f%%, riskAmount=%.2f",
                        balance, InpRiskPercent, riskAmount);
            PrintFormat("[LOT] Risk calc: slDist=%.5f, tickSize=%.5f, tickValue=%.2f",
                        slDistance, tickSize, tickValue);
            PrintFormat("[LOT] Risk calc: slTicks=%.1f, riskPerLot=%.2f, rawLots=%.4f",
                        slTicks, riskPerLot, finalLots);
        }
        else
        {
            PrintFormat("[LOT] WARNING: Cannot calculate risk lots. Using fixed: %.2f", InpLotSize);
            finalLots = InpLotSize;
        }
    }
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
//| Check if symbol exists in Market Watch                            |
//+------------------------------------------------------------------+
bool _ValidateSymbol(const string &symbol)
{
    // Try to select the symbol in Market Watch
    if(SymbolSelect(symbol, true))
    {
        // Verify it has valid tick data
        double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
        if(bid > 0)
            return true;
    }
    return false;
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

    int res = WebRequest("GET", url, headers, 5000, postData, resultData, resultHeaders);

    if(res != 200)
    {
        g_apiConnected = false;
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

    g_apiConnected = true;
    string json = CharArrayToString(resultData);
    _ProcessSignalsJSON(json);
}

//+------------------------------------------------------------------+
//| Parse signals JSON and place pending orders                       |
//+------------------------------------------------------------------+
void _ProcessSignalsJSON(const string &json)
{
    int arrStart = StringFind(json, "\"signals\"");
    if(arrStart < 0) return;

    arrStart = StringFind(json, "[", arrStart);
    if(arrStart < 0) return;

    int arrEnd = _FindMatchingBracket(json, arrStart, '[', ']');
    if(arrEnd < 0) return;

    string arrContent = StringSubstr(json, arrStart + 1, arrEnd - arrStart - 1);
    StringTrimLeft(arrContent);
    StringTrimRight(arrContent);
    if(StringLen(arrContent) == 0)
        return;

    int searchPos = 0;
    while(searchPos < StringLen(arrContent))
    {
        int objStart = StringFind(arrContent, "{", searchPos);
        if(objStart < 0) break;

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
    return -1;
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

    // Validate basic fields
    if(signalId == "" || symbol == "" || direction == "" || entryPrice == 0)
    {
        PrintFormat("[SIGNAL] ERROR: Invalid signal JSON (id=%s, sym=%s, dir=%s, entry=%.5f)",
                    signalId, symbol, direction, entryPrice);
        return;
    }

    // Check if already processed
    if(g_orderMgr.HasSignal(signalId))
        return;

    // Validate symbol exists in MT5
    if(!_ValidateSymbol(symbol))
    {
        PrintFormat("[SIGNAL] ERROR: Symbol '%s' not found in Market Watch", symbol);

        if(InpNotifyTelegram)
        {
            _SendTelegramNotification(StringFormat(
                "<b>Symbol Not Found</b>\n"
                "Symbol <b>%s</b> is not available in Market Watch.\n"
                "Signal: %s %s @ %.5f\n"
                "Source: %s\n\n"
                "Please check the symbol name in your broker's MT5.",
                symbol, direction, orderType, entryPrice, source
            ));
        }
        // Report symbol_not_found trade event
        _ReportTradeEvent(signalId, "symbol_not_found", symbol, direction, 0, entryPrice, 0, source,
                          "Symbol not found in Market Watch");
        return;
    }

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
        entryPrice, stopLoss, tp1, tp2, tp3, lots, source
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

    int colonPos = StringFind(json, ":", pos + StringLen(searchKey));
    if(colonPos < 0) return "";

    int quoteStart = StringFind(json, "\"", colonPos + 1);
    if(quoteStart < 0) return "";

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

    int numStart = colonPos + 1;
    while(numStart < StringLen(json))
    {
        ushort ch = StringGetCharacter(json, numStart);
        if(ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r')
            break;
        numStart++;
    }

    if(StringSubstr(json, numStart, 4) == "null")
        return 0;

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
