import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def scan(api_key, secret_key, universe):
    client = StockHistoricalDataClient(api_key, secret_key)
    findings = []

    for batch in chunks(universe, 50):
        bars = client.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=batch,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=450),
            end=datetime.now(),
            feed='sip'
        )).df.reset_index()

        for symbol in batch:
            df = bars[bars['symbol'] == symbol].copy()
            if len(df) < 200:
                continue

            df['200sma'] = df['close'].rolling(200).mean()
            curr = df.iloc[-1]

            # Check each of the last 10 sessions for a 10%+ rise
            qualified = False
            for i in range(1, 11):
                if len(df) < i + 1:
                    break
                past_low = df.iloc[-i - 1]['low']
                curr_high = curr['high']
                if past_low > 0 and (curr_high - past_low) / past_low >= 0.10:
                    qualified = True
                    break

            if not qualified:
                continue

            # Must be within 0.2% of 200 SMA
            pct_from_200 = abs(curr['close'] - curr['200sma']) / curr['200sma'] * 100
            if pct_from_200 > 0.2:
                continue

            findings.append({
                "symbol": symbol,
                "current_price": round(curr['close'], 2),
                "trigger_price": round(curr['close'], 2),
                "metric": round(pct_from_200, 2),
                "metric_label": "% From 200 SMA"
            })

    findings.sort(key=lambda x: x["metric"])
    return findings

def chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]