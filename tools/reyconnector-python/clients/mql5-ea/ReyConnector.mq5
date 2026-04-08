//+------------------------------------------------------------------+
//| ReyConnector.mq5 — EA skeleton (Rey Capital)                      |
//| Same as tools/reyconnector — Python stack uses same terminal side.|
//+------------------------------------------------------------------+
#property copyright "Rey Capital"
#property link      "https://reycapital.example"
#property version   "1.000"
#property description "ReyConnector bridge — connection handshake and order execution (expand per roadmap)."

input string InpConnectionId = "conn-demo-001"; // Connection ID (from portal when available)

int OnInit()
  {
   Print("ReyConnector EA initialized. ConnectionId=", InpConnectionId);
   // TODO: outbound TLS session to ReyConnector gateway (see reyconnector-python gateway app).
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   Print("ReyConnector EA stopped. reason=", reason);
  }

void OnTick()
  {
  }
