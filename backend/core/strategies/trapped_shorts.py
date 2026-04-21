import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def scan(api_key, secret_key, universe):
    client = StockHistoricalDataClient(api_key, secret_key)
    findings = []

    for batch in chunks(universe, 50):
        try:
            bars = client.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=450)
            )).df.reset_index()

            for symbol in batch:
                df = bars[bars['symbol'] == symbol]
                if len(df) < 252:
                    continue

                df['20sma'] = df['close'].rolling(20).mean()
                df['lo20'] = df['low'].shift(1).rolling(20).min()
                curr = df.iloc[-1]

                # "Trapped Shorts": price reclaims 20‑bar low
                if curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                    dist = abs(curr['close'] - curr['20sma']) / curr['20sma']
                    rank = round((1 - dist) * 100, 2)
                    findings.append({
                        "symbol": symbol,
                        "current_price": round(curr['close'], 2),
                        "trigger_price": round(curr['hi20'], 2),
                        "metric": round(dist * 100, 2),
                        "metric_label": "% From 20 SMA"
                    })
        except Exception:
            continue

    findings.sort(key=lambda x: x["metric"])
    return findings

def chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]
