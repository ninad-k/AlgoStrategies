//+------------------------------------------------------------------+
//| PineConnector_EA.mq5                                              |
//| ZMQ Bridge EA — receives execution commands from Rust engine      |
//| via ZeroMQ and executes trades in MetaTrader 5.                   |
//|                                                                    |
//| Requires: mql-zmq library (https://github.com/dingmaotu/mql-zmq) |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property version   "1.00"
#property strict

#include <Zmq/Zmq.mqh>
#include <Trade/Trade.mqh>

//--- Input parameters
input string   InpCmdAddr       = "tcp://127.0.0.1:5556";  // ZMQ PULL address (commands from Rust)
input string   InpResultAddr    = "tcp://127.0.0.1:5557";  // ZMQ PUSH address (results to Python)
input string   InpRustResultAddr = "tcp://127.0.0.1:5559"; // ZMQ PUSH address (results to Rust)
input int      InpMagicNumber   = 123456;                   // Magic number filter
input int      InpSlippage      = 20;                       // Max slippage in points

//--- Global objects
Context  g_context("PineConnector");
Socket   g_cmdSocket(g_context, ZMQ_PULL);
Socket   g_resultSocket(g_context, ZMQ_PUSH);
Socket   g_rustResultSocket(g_context, ZMQ_PUSH);
CTrade   g_trade;

//+------------------------------------------------------------------+
int OnInit()
{
    g_trade.SetExpertMagicNumber(InpMagicNumber);
    g_trade.SetDeviationInPoints(InpSlippage);
    g_trade.SetTypeFilling(ORDER_FILLING_IOC);

    // Bind PULL socket for commands
    if(!g_cmdSocket.bind(InpCmdAddr))
    {
        PrintFormat("ERROR: Failed to bind PULL on %s", InpCmdAddr);
        return INIT_FAILED;
    }
    g_cmdSocket.setReceiveHighWaterMark(1000);
    g_cmdSocket.setLinger(1000);

    // Connect PUSH socket for results to Python
    if(!g_resultSocket.connect(InpResultAddr))
    {
        PrintFormat("ERROR: Failed to connect PUSH to %s", InpResultAddr);
        return INIT_FAILED;
    }
    g_resultSocket.setSendHighWaterMark(1000);
    g_resultSocket.setLinger(1000);

    // Connect PUSH socket for results to Rust
    if(!g_rustResultSocket.connect(InpRustResultAddr))
    {
        PrintFormat("ERROR: Failed to connect PUSH (Rust) to %s", InpRustResultAddr);
        return INIT_FAILED;
    }
    g_rustResultSocket.setSendHighWaterMark(1000);
    g_rustResultSocket.setLinger(1000);

    PrintFormat("PineConnector EA initialized | CMD: %s | RESULT: %s | RUST: %s",
                InpCmdAddr, InpResultAddr, InpRustResultAddr);

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    g_cmdSocket.unbind(InpCmdAddr);
    g_resultSocket.disconnect(InpResultAddr);
    g_rustResultSocket.disconnect(InpRustResultAddr);
    Print("PineConnector EA deinitialized");
}

//+------------------------------------------------------------------+
void OnTick()
{
    // Non-blocking receive
    ZmqMsg msg;
    if(!g_cmdSocket.recv(msg, ZMQ_DONTWAIT))
        return;

    string jsonStr = msg.getData();
    if(StringLen(jsonStr) == 0)
        return;

    // Parse command JSON
    string commandId = JsonGetString(jsonStr, "command_id");
    string signalId  = JsonGetString(jsonStr, "signal_id");
    string action    = JsonGetString(jsonStr, "action");
    string symbol    = JsonGetString(jsonStr, "symbol");
    string orderType = JsonGetString(jsonStr, "order_type");
    double lot       = JsonGetDouble(jsonStr, "lot");
    double price     = JsonGetDouble(jsonStr, "price");
    double sl        = JsonGetDouble(jsonStr, "sl");
    double tp        = JsonGetDouble(jsonStr, "tp");
    long   ticket    = JsonGetLong(jsonStr, "ticket");
    string comment   = JsonGetString(jsonStr, "comment");
    int    magic     = (int)JsonGetLong(jsonStr, "magic");

    PrintFormat("CMD: %s %s %s lot=%.2f sl=%.5f tp=%.5f ticket=%d",
                action, orderType, symbol, lot, sl, tp, ticket);

    string result = "";

    if(action == "place_order")
        result = PlaceOrder(commandId, signalId, symbol, orderType, lot, price, sl, tp, comment, magic);
    else if(action == "close_order")
        result = CloseOrder(commandId, signalId, symbol, lot, ticket, comment, magic);
    else if(action == "modify_order")
        result = ModifyOrder(commandId, signalId, ticket, sl, tp);
    else
        result = BuildResult(commandId, signalId, false, 0, 0, 0, -1, "Unknown action: " + action);

    // Send result to both Python and Rust
    ZmqMsg resultMsg(result);
    g_resultSocket.send(resultMsg);

    ZmqMsg rustMsg(result);
    g_rustResultSocket.send(rustMsg);
}

//+------------------------------------------------------------------+
string PlaceOrder(string cmdId, string sigId, string symbol, string orderType,
                  double lot, double price, double sl, double tp, string comment, int magic)
{
    g_trade.SetExpertMagicNumber(magic > 0 ? magic : InpMagicNumber);

    // Normalize lot
    double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    lot = MathMax(minLot, MathMin(maxLot, NormalizeDouble(lot / lotStep, 0) * lotStep));

    bool success = false;

    if(orderType == "market_buy")
        success = g_trade.Buy(lot, symbol, 0, sl, tp, comment);
    else if(orderType == "market_sell")
        success = g_trade.Sell(lot, symbol, 0, sl, tp, comment);
    else if(orderType == "buy_limit")
        success = g_trade.BuyLimit(lot, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
    else if(orderType == "sell_limit")
        success = g_trade.SellLimit(lot, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
    else if(orderType == "buy_stop")
        success = g_trade.BuyStop(lot, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
    else if(orderType == "sell_stop")
        success = g_trade.SellStop(lot, price, symbol, sl, tp, ORDER_TIME_GTC, 0, comment);
    else
        return BuildResult(cmdId, sigId, false, 0, 0, 0, -1, "Unknown order type: " + orderType);

    if(success)
    {
        MqlTradeResult tradeResult;
        g_trade.Result(tradeResult);
        PrintFormat("Order placed: ticket=%d price=%.5f vol=%.2f",
                    tradeResult.order, tradeResult.price, tradeResult.volume);
        return BuildResult(cmdId, sigId, true, (long)tradeResult.order,
                           tradeResult.price, tradeResult.volume, 0, "");
    }
    else
    {
        uint retcode = g_trade.ResultRetcode();
        string retcomment = g_trade.ResultComment();
        PrintFormat("Order failed: code=%d msg=%s", retcode, retcomment);
        return BuildResult(cmdId, sigId, false, 0, 0, 0, (int)retcode, retcomment);
    }
}

//+------------------------------------------------------------------+
string CloseOrder(string cmdId, string sigId, string symbol,
                  double lot, long ticket, string comment, int magic)
{
    if(ticket <= 0)
        return BuildResult(cmdId, sigId, false, 0, 0, 0, -1, "Invalid ticket");

    if(!PositionSelectByTicket(ticket))
        return BuildResult(cmdId, sigId, false, 0, 0, 0, -1, "Position not found: " + IntegerToString(ticket));

    double posVol = PositionGetDouble(POSITION_VOLUME);
    double closeVol = (lot > 0 && lot < posVol) ? lot : posVol;

    // Normalize close volume
    double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    closeVol = NormalizeDouble(closeVol / lotStep, 0) * lotStep;

    bool success;
    if(MathAbs(closeVol - posVol) < lotStep)
        success = g_trade.PositionClose(ticket, InpSlippage);
    else
        success = g_trade.PositionClosePartial(ticket, closeVol, InpSlippage);

    if(success)
    {
        MqlTradeResult tradeResult;
        g_trade.Result(tradeResult);
        PrintFormat("Position closed: ticket=%d vol=%.2f price=%.5f",
                    ticket, closeVol, tradeResult.price);
        return BuildResult(cmdId, sigId, true, ticket, tradeResult.price, closeVol, 0, "");
    }
    else
    {
        uint retcode = g_trade.ResultRetcode();
        return BuildResult(cmdId, sigId, false, ticket, 0, 0, (int)retcode, g_trade.ResultComment());
    }
}

//+------------------------------------------------------------------+
string ModifyOrder(string cmdId, string sigId, long ticket, double sl, double tp)
{
    if(ticket <= 0)
        return BuildResult(cmdId, sigId, false, 0, 0, 0, -1, "Invalid ticket for modify");

    if(!PositionSelectByTicket(ticket))
        return BuildResult(cmdId, sigId, false, 0, 0, 0, -1, "Position not found: " + IntegerToString(ticket));

    bool success = g_trade.PositionModify(ticket, sl, tp);

    if(success)
    {
        PrintFormat("Position modified: ticket=%d sl=%.5f tp=%.5f", ticket, sl, tp);
        return BuildResult(cmdId, sigId, true, ticket, 0, 0, 0, "");
    }
    else
    {
        uint retcode = g_trade.ResultRetcode();
        return BuildResult(cmdId, sigId, false, ticket, 0, 0, (int)retcode, g_trade.ResultComment());
    }
}

//+------------------------------------------------------------------+
string BuildResult(string cmdId, string sigId, bool success,
                   long ticket, double execPrice, double execLot,
                   int errCode, string errMsg)
{
    string ts = TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS);
    StringReplace(ts, ".", "-");

    return StringFormat(
        "{\"command_id\":\"%s\",\"signal_id\":\"%s\",\"success\":%s,"
        "\"ticket\":%d,\"executed_price\":%.5f,\"executed_lot\":%.2f,"
        "\"error_code\":%d,\"error_message\":\"%s\",\"timestamp\":\"%sZ\"}",
        cmdId, sigId, (success ? "true" : "false"),
        ticket, execPrice, execLot,
        errCode, errMsg, ts
    );
}

//+------------------------------------------------------------------+
// Simple JSON string extraction helpers
//+------------------------------------------------------------------+
string JsonGetString(string json, string key)
{
    string search = "\"" + key + "\":\"";
    int pos = StringFind(json, search);
    if(pos == -1) return "";
    pos += StringLen(search);
    int endPos = StringFind(json, "\"", pos);
    if(endPos == -1) return "";
    return StringSubstr(json, pos, endPos - pos);
}

double JsonGetDouble(string json, string key)
{
    string search = "\"" + key + "\":";
    int pos = StringFind(json, search);
    if(pos == -1) return 0;
    pos += StringLen(search);
    string remaining = StringSubstr(json, pos, 30);
    // Find end of number (comma, brace, or end)
    int end = 0;
    for(int i = 0; i < StringLen(remaining); i++)
    {
        ushort ch = StringGetCharacter(remaining, i);
        if(ch == ',' || ch == '}' || ch == ' ' || ch == '\n')
        {
            end = i;
            break;
        }
        end = i + 1;
    }
    return StringToDouble(StringSubstr(remaining, 0, end));
}

long JsonGetLong(string json, string key)
{
    string search = "\"" + key + "\":";
    int pos = StringFind(json, search);
    if(pos == -1) return 0;
    pos += StringLen(search);
    string remaining = StringSubstr(json, pos, 30);
    int end = 0;
    for(int i = 0; i < StringLen(remaining); i++)
    {
        ushort ch = StringGetCharacter(remaining, i);
        if(ch == ',' || ch == '}' || ch == ' ' || ch == '\n')
        {
            end = i;
            break;
        }
        end = i + 1;
    }
    return StringToInteger(StringSubstr(remaining, 0, end));
}
//+------------------------------------------------------------------+
