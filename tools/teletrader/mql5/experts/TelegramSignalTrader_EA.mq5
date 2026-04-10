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
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include "../include/PendingOrderManager.mqh"

//--- Input parameters
input group "== Trade Settings =="
input double InpLotSize       = 0.01;    // Lot size per signal
input int    InpMagicNumber   = 20260410; // Magic number

input group "== Partial Profit Booking =="
input double InpTP1Pct        = 30;      // TP1 close % (default 30%)
input double InpTP2Pct        = 50;      // TP2 close % (default 50%)
input double InpTP3Pct        = 10;      // TP3 close % (default 10%)
input double InpResidualPct   = 10;      // Residual % for trailing (default 10%)

input group "== Trailing Stop =="
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
    // Validate TP percentages
    double totalPct = InpTP1Pct + InpTP2Pct + InpTP3Pct + InpResidualPct;
    if(MathAbs(totalPct - 100.0) > 0.01)
    {
        PrintFormat("ERROR: TP percentages must sum to 100%%. Got %.1f%%", totalPct);
        return INIT_PARAMETERS_INCORRECT;
    }

    // Initialize order manager
    g_orderMgr.Init(InpMagicNumber);
    g_orderMgr.SetTPConfig(InpTP1Pct, InpTP2Pct, InpTP3Pct, InpResidualPct);
    g_orderMgr.SetTrailingPoints(InpTrailingPoints);

    // Test API connectivity
    if(!_TestAPIConnection())
    {
        Print("WARNING: Could not reach TeleTrader API at ", InpAPIUrl);
        Print("EA will keep retrying on each poll cycle.");
    }
    else
    {
        Print("TeleTrader EA initialized. API connected at ", InpAPIUrl);
    }

    PrintFormat("Config: TP1=%.0f%% TP2=%.0f%% TP3=%.0f%% Residual=%.0f%% Trail=%.0f pts",
                InpTP1Pct, InpTP2Pct, InpTP3Pct, InpResidualPct, InpTrailingPoints);

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("TeleTrader EA stopped. Reason: ", reason);
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
                Print("Add '", InpAPIUrl, "' to Tools → Options → Expert Advisors → Allow WebRequest");
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
    // Expected format:
    // {"signals":[{"signalId":"abc","seq":1,"symbol":"XAUUSD","direction":"buy",
    //   "orderType":"buy_stop","entryPrice":4756.0,"stopLoss":4736.0,
    //   "takeProfits":[4760.0,4764.0,4785.0],"parsedAtUtc":"..."},...]}"

    // Find the signals array
    int arrStart = StringFind(json, "\"signals\"");
    if(arrStart < 0) return;

    arrStart = StringFind(json, "[", arrStart);
    if(arrStart < 0) return;

    int arrEnd = StringFind(json, "]", arrStart);
    if(arrEnd < 0) return;

    string arrContent = StringSubstr(json, arrStart + 1, arrEnd - arrStart - 1);
    if(StringLen(StringTrimRight(StringTrimLeft(arrContent))) == 0)
        return; // empty array

    // Split by "},{" to get individual signal objects
    // First, find each { ... } block
    int searchPos = 0;
    while(searchPos < StringLen(arrContent))
    {
        int objStart = StringFind(arrContent, "{", searchPos);
        if(objStart < 0) break;

        int objEnd = StringFind(arrContent, "}", objStart);
        if(objEnd < 0) break;

        string signalJson = StringSubstr(arrContent, objStart, objEnd - objStart + 1);
        _ProcessSingleSignal(signalJson);

        searchPos = objEnd + 1;
    }
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

    // Update cursor
    if(seq > g_lastSeq)
        g_lastSeq = seq;

    // Validate
    if(signalId == "" || symbol == "" || direction == "" || entryPrice == 0)
    {
        Print("Invalid signal JSON: ", signalJson);
        return;
    }

    // Check if already processed
    if(g_orderMgr.HasSignal(signalId))
        return;

    // Extract take profits array
    double tp1 = 0, tp2 = 0, tp3 = 0;
    _ExtractTakeProfits(signalJson, tp1, tp2, tp3);

    int dir = (direction == "buy") ? 1 : -1;

    PrintFormat("New signal: %s %s %s @ %.5f SL=%.5f TP=[%.5f, %.5f, %.5f]",
                symbol, direction, orderType, entryPrice, stopLoss, tp1, tp2, tp3);

    // Place the pending order
    bool ok = g_orderMgr.PlaceOrder(
        signalId, symbol, dir, orderType,
        entryPrice, stopLoss, tp1, tp2, tp3, InpLotSize
    );

    if(ok)
        PrintFormat("Pending order placed for signal %s", signalId);
    else
        PrintFormat("Failed to place order for signal %s", signalId);
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

    if(count >= 1) tp1 = StringToDouble(StringTrimLeft(StringTrimRight(parts[0])));
    if(count >= 2) tp2 = StringToDouble(StringTrimLeft(StringTrimRight(parts[1])));
    if(count >= 3) tp3 = StringToDouble(StringTrimLeft(StringTrimRight(parts[2])));
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
