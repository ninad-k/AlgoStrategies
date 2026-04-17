//+------------------------------------------------------------------+
//|                                                         VWAP.mqh |
//|                  Volume Weighted Average Price (Session-based)    |
//|                  Resets at each new trading session               |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property strict

class CVWAP
{
private:
    double m_vwap;
    double m_cumulativeTPV;   // Cumulative (Typical Price * Volume)
    double m_cumulativeVol;   // Cumulative Volume
    datetime m_sessionStart;
    int m_sessionStartHour;
    int m_sessionStartMinute;

public:
    CVWAP() : m_vwap(0), m_cumulativeTPV(0), m_cumulativeVol(0),
              m_sessionStart(0), m_sessionStartHour(9), m_sessionStartMinute(15) {}

    //--- Set session start time (default: 9:15 IST for NSE)
    void SetSessionStart(int hour, int minute)
    {
        m_sessionStartHour = hour;
        m_sessionStartMinute = minute;
    }

    //--- Calculate VWAP from session start to current bar
    bool Calculate(const string symbol, const ENUM_TIMEFRAMES period)
    {
        MqlRates rates[];
        ArraySetAsSeries(rates, true);

        // Get today's date
        datetime currentTime = TimeCurrent();
        MqlDateTime dt;
        TimeToStruct(currentTime, dt);

        // Session start for today
        dt.hour = m_sessionStartHour;
        dt.min  = m_sessionStartMinute;
        dt.sec  = 0;
        datetime todaySessionStart = StructToTime(dt);

        // If current time is before session start, use previous day
        if(currentTime < todaySessionStart)
        {
            todaySessionStart -= 86400; // Go back one day
        }

        // Check if we need to reset (new session)
        if(todaySessionStart != m_sessionStart)
        {
            Reset();
            m_sessionStart = todaySessionStart;
        }

        // Copy bars from session start
        int bars = CopyRates(symbol, period, todaySessionStart, currentTime, rates);
        if(bars < 1)
            return false;

        // Recalculate from scratch each time for accuracy
        m_cumulativeTPV = 0;
        m_cumulativeVol = 0;

        for(int i = bars - 1; i >= 0; i--)
        {
            double typicalPrice = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
            double volume = (double)rates[i].tick_volume;

            if(volume <= 0) volume = 1; // Avoid division by zero

            m_cumulativeTPV += typicalPrice * volume;
            m_cumulativeVol += volume;
        }

        if(m_cumulativeVol > 0)
            m_vwap = m_cumulativeTPV / m_cumulativeVol;

        return true;
    }

    //--- Reset for new session
    void Reset()
    {
        m_cumulativeTPV = 0;
        m_cumulativeVol = 0;
        m_vwap = 0;
        m_sessionStart = 0;
    }

    //--- Getters
    double Value() const { return m_vwap; }

    //--- Check if price is above/below VWAP
    bool IsAboveVWAP(double price) const { return price > m_vwap; }
    bool IsBelowVWAP(double price) const { return price < m_vwap; }
};
