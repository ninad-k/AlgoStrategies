//+------------------------------------------------------------------+
//| DealHelpers.mqh — history export + position duration estimates   |
//+------------------------------------------------------------------+
#property copyright "TradeSegregator"
#property strict

struct TsDealRow
  {
   ulong             ticket;
   string            symbol;
   long              magic;
   double            volume;
   double            profit;
   double            swap;
   double            commission;
   datetime          deal_time;
   long              deal_type;
   long              entry;
   ulong             position_id;
   double            duration_minutes;
  };

bool TsCollectHistory(const datetime from_time,const datetime to_time,TsDealRow &rows[])
  {
   ArrayResize(rows,0);
   if(!HistorySelect(from_time,to_time))
     {
      Print("TradeSegregator: HistorySelect failed");
      return false;
     }

   int total=(int)HistoryDealsTotal();
   if(total<=0)
      return true;

   // First pass: collect raw deals
   TsDealRow tmp[];
   ArrayResize(tmp,total);
   int n=0;
   for(int i=0;i<total;i++)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0)
         continue;
      TsDealRow r;
      r.ticket=ticket;
      r.symbol=HistoryDealGetString(ticket,DEAL_SYMBOL);
      r.magic=(long)HistoryDealGetInteger(ticket,DEAL_MAGIC);
      r.volume=HistoryDealGetDouble(ticket,DEAL_VOLUME);
      r.profit=HistoryDealGetDouble(ticket,DEAL_PROFIT);
      r.swap=HistoryDealGetDouble(ticket,DEAL_SWAP);
      r.commission=HistoryDealGetDouble(ticket,DEAL_COMMISSION);
      r.deal_time=(datetime)HistoryDealGetInteger(ticket,DEAL_TIME);
      r.deal_type=(long)HistoryDealGetInteger(ticket,DEAL_TYPE);
      r.entry=(long)HistoryDealGetInteger(ticket,DEAL_ENTRY);
      r.position_id=(ulong)HistoryDealGetInteger(ticket,DEAL_POSITION_ID);
      r.duration_minutes=0;
      tmp[n++]=r;
     }

   // Build min/max time per position_id
   datetime tmin[];
   datetime tmax[];
   ulong pids[];
   int pc=0;

   for(int i=0;i<n;i++)
     {
      ulong pid=tmp[i].position_id;
      if(pid==0)
         continue;
      int ix=-1;
      for(int k=0;k<pc;k++)
        {
         if(pids[k]==pid)
           {
            ix=k;
            break;
           }
        }
      if(ix<0)
        {
         ArrayResize(pids,pc+1);
         ArrayResize(tmin,pc+1);
         ArrayResize(tmax,pc+1);
         pids[pc]=pid;
         tmin[pc]=tmp[i].deal_time;
         tmax[pc]=tmp[i].deal_time;
         pc++;
        }
      else
        {
         if(tmp[i].deal_time<tmin[ix])
            tmin[ix]=tmp[i].deal_time;
         if(tmp[i].deal_time>tmax[ix])
            tmax[ix]=tmp[i].deal_time;
        }
     }

   for(int i=0;i<n;i++)
     {
      ulong pid=tmp[i].position_id;
      double dur=0;
      if(pid!=0)
        {
         for(int k=0;k<pc;k++)
           {
            if(pids[k]==pid)
              {
               double secs=(double)(tmax[k]-tmin[k]);
               dur=secs/60.0;
               break;
              }
           }
        }
      tmp[i].duration_minutes=dur;
     }

   ArrayResize(rows,n);
   for(int i=0;i<n;i++)
      rows[i]=tmp[i];
   return true;
  }

string TsJsonEscape(const string s)
  {
   string r=s;
   StringReplace(r,"\\","\\\\");
   StringReplace(r,"\"","\\\"");
   StringReplace(r,"\r","");
   StringReplace(r,"\n","\\n");
   return r;
  }
