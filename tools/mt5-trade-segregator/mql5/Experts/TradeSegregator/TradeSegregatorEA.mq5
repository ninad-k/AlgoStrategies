//+------------------------------------------------------------------+
//| TradeSegregatorEA.mq5 — export history + rule-based categories   |
//+------------------------------------------------------------------+
#property copyright "TradeSegregator"
#property version   "1.00"
#property strict

#include <TradeSegregator/RuleEngine.mqh>
#include <TradeSegregator/DealHelpers.mqh>

input datetime InpFrom = 0;
input datetime InpTo   = 0;
input string   InpRulesFile = "rules-for-ea.csv";
input string   InpOutputPrefix = "trade_segregator";
input bool     InpExportOnInit = true;
input int      InpTimerSeconds = 0;

CRuleEngine g_engine;

bool RunExport(void)
  {
   if(!g_engine.LoadFromCsvFile(InpRulesFile))
     {
      Print("TradeSegregatorEA: rules not loaded — place ",InpRulesFile," in MQL5/Files");
      return false;
     }

   datetime from_t=InpFrom;
   datetime to_t=InpTo;
   if(from_t==0)
      from_t=TimeCurrent()-86400*365;
   if(to_t==0)
      to_t=TimeCurrent();

   TsDealRow rows[];
   if(!TsCollectHistory(from_t,to_t,rows))
      return false;

   const int n=ArraySize(rows);
   string j="{";
   j+="\"schemaVersion\":1,";
   j+="\"source\":\"MT5_EA\",";
   j+="\"uncategorizedId\":\""+g_engine.UncategorizedId()+"\",";
   j+="\"exported\":\""+TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS)+"\",";
   j+="\"deals\":[";

   string csv="ticket;symbol;magic;volume;profit;swap;commission;deal_time;deal_type;entry;position_id;duration_minutes;category_id;category_label\r\n";

   for(int i=0;i<n;i++)
     {
      string cid,clabel;
      g_engine.AssignCategory(rows[i].profit,
                             rows[i].volume,
                             rows[i].magic,
                             rows[i].duration_minutes,
                             rows[i].deal_type,
                             rows[i].entry,
                             cid,
                             clabel);

      if(i>0)
         j+=",";
      j+="{";
      j+="\"ticket\":"+(string)rows[i].ticket+",";
      j+="\"symbol\":\""+TsJsonEscape(rows[i].symbol)+"\",";
      j+="\"magic\":"+(string)rows[i].magic+",";
      j+="\"volume\":"+DoubleToString(rows[i].volume,8)+",";
      j+="\"profit\":"+DoubleToString(rows[i].profit,8)+",";
      j+="\"swap\":"+DoubleToString(rows[i].swap,8)+",";
      j+="\"commission\":"+DoubleToString(rows[i].commission,8)+",";
      j+="\"dealTime\":\""+TimeToString(rows[i].deal_time,TIME_DATE|TIME_SECONDS)+"\",";
      j+="\"dealType\":"+(string)rows[i].deal_type+",";
      j+="\"entry\":"+(string)rows[i].entry+",";
      j+="\"positionId\":"+(string)rows[i].position_id+",";
      j+="\"durationMinutes\":"+DoubleToString(rows[i].duration_minutes,4)+",";
      j+="\"categoryId\":\""+TsJsonEscape(cid)+"\",";
      j+="\"categoryLabel\":\""+TsJsonEscape(clabel)+"\",";
      j+="\"manualCategoryId\":\"\",";
      j+="\"manualCategoryLabel\":\"\"";
      j+="}";

      csv+=(string)rows[i].ticket+";";
      csv+=rows[i].symbol+";";
      csv+=(string)rows[i].magic+";";
      csv+=DoubleToString(rows[i].volume,8)+";";
      csv+=DoubleToString(rows[i].profit,8)+";";
      csv+=DoubleToString(rows[i].swap,8)+";";
      csv+=DoubleToString(rows[i].commission,8)+";";
      csv+=TimeToString(rows[i].deal_time,TIME_DATE|TIME_SECONDS)+";";
      csv+=(string)rows[i].deal_type+";";
      csv+=(string)rows[i].entry+";";
      csv+=(string)rows[i].position_id+";";
      csv+=DoubleToString(rows[i].duration_minutes,4)+";";
      csv+=cid+";";
      csv+=clabel+"\r\n";
     }

   j+="]}";

   string json_name=InpOutputPrefix+"_deals.json";
   string csv_name=InpOutputPrefix+"_deals.csv";

   int hj=FileOpen(json_name,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(hj==INVALID_HANDLE)
     {
      Print("TradeSegregatorEA: cannot write ",json_name," err=",GetLastError());
      return false;
     }
   FileWriteString(hj,j);
   FileClose(hj);

   int hc=FileOpen(csv_name,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(hc==INVALID_HANDLE)
     {
      Print("TradeSegregatorEA: cannot write ",csv_name," err=",GetLastError());
      return false;
     }
   FileWriteString(hc,csv);
   FileClose(hc);

   Print("TradeSegregatorEA: wrote ",n," deals to ",json_name," and ",csv_name);
   return true;
  }

int OnInit(void)
  {
   if(InpTimerSeconds>0)
      EventSetTimer(InpTimerSeconds);
   if(InpExportOnInit)
      RunExport();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer(void)
  {
   RunExport();
  }

void OnTick(void)
  {
  }
