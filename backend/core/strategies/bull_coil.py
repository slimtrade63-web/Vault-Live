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

            df['8sma'] = df['close'].rolling(8).mean()
            df['20sma'] = df['close'].rolling(20).mean()
            df['200sma'] = df['close'].rolling(200).mean()

            curr = df.iloc[-1]

            # Price above 8 SMA, 8 above 20, 20 above 200
            if not (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']):
                continue

            # All SMAs within 5% of each other
            sma_max = max(curr['8sma'], curr['20sma'], curr['200sma'])
            sma_min = min(curr['8sma'], curr['20sma'], curr['200sma'])
            compression = (sma_max - sma_min) / sma_min * 100

            if compression > 5.0:
                continue

            findings.append({
                "symbol": symbol,
                "current_price": round(curr['close'], 2),
                "trigger_price": round(curr['close'], 2),
                "metric": round(compression, 2),
                "metric_label": "MA Compression %"
            })

    findings.sort(key=lambda x: x["metric"])
    return findings

def chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]