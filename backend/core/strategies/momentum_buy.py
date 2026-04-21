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
            start=datetime.now() - timedelta(days=90),
            end=datetime.now(),
            feed='sip',
        )).df.reset_index()

        for symbol in batch:
            df = bars[bars['symbol'] == symbol].copy()
            if len(df) < 22:
                continue

            df['8sma'] = df['close'].rolling(8).mean()
            df['avg_volume'] = df['volume'].rolling(20).mean()
            df['hi20'] = df['high'].shift(1).rolling(20).max()

            curr = df.iloc[-1]

            # Minimum average daily volume
            if curr['avg_volume'] < 500000:
                continue

            # Must be making a 20-day high
            if curr['high'] <= curr['hi20']:
                continue

            # Must be within 4% of the 8 SMA
            pct_dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
            if pct_dist > 0.04:
                continue

            rank = round((1 - pct_dist) * 100, 2)

            findings.append({
    "symbol": symbol,
    "current_price": round(curr['close'], 2),
    "trigger_price": round(curr['hi20'], 2),
    "metric": round(pct_dist * 100, 2),
    "metric_label": "% From 8 SMA"
})

    findings.sort(key=lambda x: x["metric"])
    return findings

def chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]