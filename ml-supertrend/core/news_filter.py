# News Filter
# Author: Ninad
#
# Economic calendar integration to avoid trading around high-impact news events.
# Currency-to-symbol mapping determines which pairs are affected by each event.

import requests
from datetime import datetime, timedelta


class NewsFilter:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.high_impact_events = []
        self.last_update = None

    def update_calendar(self):
        """Refresh the event list from the calendar API (at most once per hour)."""
        if self.last_update and (datetime.now() - self.last_update) < timedelta(hours=1):
            return
        try:
            # TODO: integrate with a real economic calendar API
            self.last_update = datetime.now()
        except Exception:
            pass

    def is_news_time(self, symbol: str, minutes_before: int = 30, minutes_after: int = 30) -> bool:
        """Return True if a high-impact event affecting this symbol is within the buffer window."""
        current_time = datetime.now()
        for event in self.high_impact_events:
            if self.affects_symbol(event, symbol):
                event_time = event['datetime']
                if (event_time - timedelta(minutes=minutes_before)
                        <= current_time
                        <= event_time + timedelta(minutes=minutes_after)):
                    return True
        return False

    def affects_symbol(self, event: dict, symbol: str) -> bool:
        """Check whether an event's currency is a component of the given symbol."""
        currency_map = {
            'USD': ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'NZDUSD', 'USDCAD'],
            'EUR': ['EURUSD', 'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD'],
            'GBP': ['GBPUSD', 'EURGBP', 'GBPJPY', 'GBPCHF'],
            'JPY': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY'],
            'CHF': ['USDCHF', 'EURCHF', 'GBPCHF'],
            'AUD': ['AUDUSD', 'EURAUD', 'AUDJPY'],
            'NZD': ['NZDUSD'],
            'CAD': ['USDCAD'],
        }
        event_currency = event.get('currency', '')
        return symbol in currency_map.get(event_currency, [])
