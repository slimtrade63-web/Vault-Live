import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

SECTORS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Disc",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Comm Services",
}

WYCKOFF_PHASES = {
    0: {"name": "Accumulation",  "color": "#2E86AB", "description": "Smart money building positions — potential markup ahead"},
    1: {"name": "Markup",        "color": "#27AE60", "description": "Price trending up — institutional buying confirmed"},
    2: {"name": "Distribution",  "color": "#F0A500", "description": "Smart money distributing — caution advised"},
    3: {"name": "Markdown",      "color": "#C0392B", "description": "Price trending down — defensive posture recommended"},
}


def fetch_bars(client, symbols, days=180):
    """Fetch daily bars for a list of symbols."""
    bars = client.get_stock_bars(StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        feed='sip'
    )).df.reset_index()
    return bars


def compute_regime(api_key, secret_key):
    """Run HMM on SPY + macro inputs to detect current Wyckoff phase."""
    client = StockHistoricalDataClient(api_key, secret_key)

    # Fetch SPY, TLT, VIX proxy (VIXY), XLK, XLU
    symbols = ["SPY", "TLT", "VIXY", "XLK", "XLU"]
    bars = fetch_bars(client, symbols, days=180)

    result = {}
    for sym in symbols:
        df = bars[bars['symbol'] == sym][['timestamp', 'close', 'volume']].copy()
        df = df.sort_values('timestamp').set_index('timestamp')
        result[sym] = df

    # Align on common dates
    spy = result["SPY"]
    tlt = result["TLT"]
    vixy = result["VIXY"]
    xlk = result["XLK"]
    xlu = result["XLU"]

    common = spy.index.intersection(tlt.index).intersection(vixy.index).intersection(xlk.index).intersection(xlu.index)
    if len(common) < 60:
        return None

    spy   = spy.loc[common]
    tlt   = tlt.loc[common]
    vixy  = vixy.loc[common]
    xlk   = xlk.loc[common]
    xlu   = xlu.loc[common]

    # Build feature matrix
    spy_returns  = spy['close'].pct_change()
    spy_vol      = spy['volume'].pct_change()
    vix_level    = vixy['close']
    spy_tlt      = spy['close'] / tlt['close']
    spy_tlt_ret  = spy_tlt.pct_change()
    xlk_xlu      = xlk['close'] / xlu['close']
    xlk_xlu_ret  = xlk_xlu.pct_change()

    features = pd.DataFrame({
        'spy_returns':  spy_returns,
        'spy_vol':      spy_vol,
        'vix':          vix_level,
        'spy_tlt':      spy_tlt_ret,
        'xlk_xlu':      xlk_xlu_ret,
    }).dropna()

    if len(features) < 50:
        return None

    # Scale features
    scaler = StandardScaler()
    X = scaler.fit_transform(features.values)

    # Fit HMM
    model = GaussianHMM(
        n_components=4,
        covariance_type="full",
        n_iter=200,
        random_state=42
    )
    model.fit(X)

    # Predict states
    states = model.predict(X)
    current_state = int(states[-1])

    # Get confidence from state probabilities
    log_probs = model.predict_proba(X)
    current_probs = log_probs[-1]
    confidence = round(float(current_probs[current_state]) * 100, 1)

    # Map HMM states to Wyckoff phases based on mean returns
    state_means = {}
    for s in range(4):
        mask = states == s
        if mask.sum() > 0:
            state_means[s] = float(features['spy_returns'][mask].mean())

    # Sort states by mean return to assign Wyckoff phases
    sorted_states = sorted(state_means.items(), key=lambda x: x[1])
    phase_map = {
        sorted_states[0][0]: 3,  # lowest returns = Markdown
        sorted_states[1][0]: 0,  # second lowest = Accumulation
        sorted_states[2][0]: 2,  # second highest = Distribution
        sorted_states[3][0]: 1,  # highest returns = Markup
    }

    wyckoff_phase = phase_map[current_state]
    phase_info = WYCKOFF_PHASES[wyckoff_phase]

    return {
        "phase": phase_info["name"],
        "color": phase_info["color"],
        "description": phase_info["description"],
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),
    }


def compute_sector_strength(api_key, secret_key):
    """Compute composite strength score for each sector vs SPY."""
    client = StockHistoricalDataClient(api_key, secret_key)

    symbols = list(SECTORS.keys()) + ["SPY"]
    bars = fetch_bars(client, symbols, days=120)

    scores = []

    # Get SPY data for reference
    spy_df = bars[bars['symbol'] == "SPY"][['timestamp', 'close', 'volume']].copy()
    spy_df = spy_df.sort_values('timestamp').set_index('timestamp')

    spy_return_3m = (spy_df['close'].iloc[-1] - spy_df['close'].iloc[-63]) / spy_df['close'].iloc[-63] * 100

    for ticker, name in SECTORS.items():
        df = bars[bars['symbol'] == ticker][['timestamp', 'close', 'volume']].copy()
        df = df.sort_values('timestamp').set_index('timestamp')

        if len(df) < 63:
            continue

        close = df['close']
        volume = df['volume']

        # ── Performance score (40%) — 3-month return relative to SPY
        ret_3m = (close.iloc[-1] - close.iloc[-63]) / close.iloc[-63] * 100
        rel_perf = ret_3m - spy_return_3m

        # ── MA score (40%) — position relative to 8, 20, 200 SMAs
        sma8   = close.rolling(8).mean().iloc[-1]
        sma20  = close.rolling(20).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
        current = close.iloc[-1]

        ma_score = 0
        if current > sma8:   ma_score += 33
        if current > sma20:  ma_score += 33
        if sma200 and current > sma200: ma_score += 34

        # ── Volume score (20%) — is volume expanding on up days?
        recent = df.tail(20).copy()
        recent['up'] = recent['close'].diff() > 0
        up_vol   = recent[recent['up']]['volume'].mean()
        down_vol = recent[~recent['up']]['volume'].mean()
        vol_score = 100 if (up_vol > down_vol) else 0

        # ── Composite score
        composite = (rel_perf * 0.40) + (ma_score * 0.40) + (vol_score * 0.20)

        scores.append({
            "ticker":     ticker,
            "name":       name,
            "ret_3m":     round(ret_3m, 2),
            "rel_perf":   round(rel_perf, 2),
            "ma_score":   round(ma_score, 1),
            "vol_score":  round(vol_score, 1),
            "composite":  round(composite, 2),
            "vs_spy":     "leading" if rel_perf > 1 else ("lagging" if rel_perf < -1 else "inline"),
        })

    # Add SPY as reference
    scores.append({
        "ticker":    "SPY",
        "name":      "S&P 500",
        "ret_3m":    round(spy_return_3m, 2),
        "rel_perf":  0.0,
        "ma_score":  0,
        "vol_score": 0,
        "composite": 0.0,
        "vs_spy":    "reference",
    })

    scores.sort(key=lambda x: x["composite"], reverse=True)
    return scores