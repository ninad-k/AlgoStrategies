//+------------------------------------------------------------------+
//|                                                  PivotPoints.mqh |
//|                         Traditional Pivot Points (Daily)         |
//|                         Pivot = (H + L + C) / 3                  |
//|                         R1 = 2*P - L,  S1 = 2*P - H             |
//|                         R2 = P + (H-L), S2 = P - (H-L)          |
//|                         R3 = H + 2*(P-L), S3 = L - 2*(H-P)      |
//+------------------------------------------------------------------+
#property copyright "AlgoStrategies"
#property strict

class CPivotPoints
{
private:
    double m_pivot;
    double m_r1, m_r2, m_r3;
    double m_s1, m_s2, m_s3;
    double m_prevHigh, m_prevLow, m_prevClose;
    datetime m_lastCalcDate;

public:
    CPivotPoints() : m_pivot(0), m_r1(0), m_r2(0), m_r3(0),
                     m_s1(0), m_s2(0), m_s3(0),
                     m_prevHigh(0), m_prevLow(0), m_prevClose(0),
                     m_lastCalcDate(0) {}

    //--- Calculate pivot levels from previous day's OHLC
    bool Calculate(const string symbol, const ENUM_TIMEFRAMES period = PERIOD_D1)
    {
        MqlRates daily[];
        ArraySetAsSeries(daily, true);

        int copied = CopyRates(symbol, period, 1, 1, daily);
        if(copied < 1)
            return false;

        datetime currentDate = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
        if(m_lastCalcDate == currentDate)
            return true; // Already calculated for today

        m_prevHigh  = daily[0].high;
        m_prevLow   = daily[0].low;
        m_prevClose = daily[0].close;

        m_pivot = (m_prevHigh + m_prevLow + m_prevClose) / 3.0;

        m_r1 = 2.0 * m_pivot - m_prevLow;
        m_s1 = 2.0 * m_pivot - m_prevHigh;

        m_r2 = m_pivot + (m_prevHigh - m_prevLow);
        m_s2 = m_pivot - (m_prevHigh - m_prevLow);

        m_r3 = m_prevHigh + 2.0 * (m_pivot - m_prevLow);
        m_s3 = m_prevLow - 2.0 * (m_prevHigh - m_pivot);

        m_lastCalcDate = currentDate;
        return true;
    }

    //--- Force recalculation (for new session)
    void Reset() { m_lastCalcDate = 0; }

    //--- Getters
    double Pivot() const { return m_pivot; }
    double R1()    const { return m_r1; }
    double R2()    const { return m_r2; }
    double R3()    const { return m_r3; }
    double S1()    const { return m_s1; }
    double S2()    const { return m_s2; }
    double S3()    const { return m_s3; }

    //--- Check if price is above/below pivot
    bool IsAbovePivot(double price) const { return price > m_pivot; }
    bool IsBelowPivot(double price) const { return price < m_pivot; }
};
