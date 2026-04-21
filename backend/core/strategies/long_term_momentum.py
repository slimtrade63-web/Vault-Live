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
            start=datetime.now() - timedelta(days=550),
            end=datetime.now(),
            feed='sip'
        )).df.reset_index()

        for symbol in batch:
            df = bars[bars['symbol'] == symbol].copy()
            if len(df) < 252:
                continue

            df['8sma'] = df['close'].rolling(8).mean()
            df['avg_vol'] = df['volume'].rolling(50).mean()
            df['avg_body'] = (df['close'] - df['open']).abs().rolling(50).mean()

            curr = df.iloc[-1]

            # Creek line: highest high over 252 bars excluding current
            creek_line = df['high'].iloc[-253:-1].max()

            # JAC: high volume wide body bar in last 10 bars excluding current
            recent = df.iloc[-11:-1]
            avg_vol = curr['avg_vol']
            avg_body = curr['avg_body']

            recently_jumped = any(
                (row['volume'] > avg_vol and abs(row['close'] - row['open']) > avg_body)
                for _, row in recent.iterrows()
            )

            if not recently_jumped:
                continue

            # BUEC: retreating volume and testing the creek
            is_retreating = curr['volume'] < avg_vol
            testing_creek = curr['low'] <= creek_line * 1.01 and curr['close'] >= creek_line * 0.99

            if not (is_retreating and testing_creek):
                continue

            # Rank by proximity to 8 SMA
            pct_from_8sma = abs(curr['close'] - curr['8sma']) / curr['8sma'] * 100

            findings.append({
                "symbol": symbol,
                "current_price": round(curr['close'], 2),
                "trigger_price": round(creek_line, 2),
                "metric": round(pct_from_8sma, 2),
                "metric_label": "% From 8 SMA"
            })

    findings.sort(key=lambda x: x["metric"])
    return findings

def chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]