import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Setup ---
st.set_page_config(page_title="Vault v78.1", layout="wide")

# CSS: 4x2 Grid
st.markdown("""
    <style>
    .stButton>button {
        width: 100%; height: 75px; font-weight: bold; font-family: 'Consolas', monospace;
        font-size: 16px; border-radius: 10px; border: 2px solid #1f538d;
        background-color: #0e1117; color: white;
    }
    .stButton>button:hover { background-color: #1f538d; border-color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

# --- Simple Universe Builder ---
@st.cache_data(ttl=86400)
def get_universe():
    data = PyTickerSymbols()
    sp = [s['symbol'] for s in data.get_sp_500_nyc_yahoo_tickers() if isinstance(s, dict)]
    nas = [s['symbol'] for s in data.get_nasdaq_100_nyc_yahoo_tickers() if isinstance(s, dict)]
    return sorted(list(set(sp + nas)))

st.title("🛡️ Institutional Vault v78.1")
st.caption("DIRECT DATA RETRIEVAL | PAID SIP FEED")
st.divider()

# --- Auth ---
try:
    client = StockHistoricalDataClient(st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_API_SECRET"])
except:
    st.error("API Keys Missing.")
    st.stop()

# --- 4x2 Grid ---
strategies = ["Momentum Buy", "Long Term Momentum", "Trapped Shorts", "Trapped Longs", 
              "Retest Long", "H2 Pullback", "Bull Coil", "Bear Coil"]
selected, cols = None, st.columns(4)
for i, s in enumerate(strategies):
    with cols[i % 4]:
        if st.button(s): selected = s

# --- The "Reliable" Scanning Engine ---
if selected:
    st.divider()
    universe = get_universe()
    findings = []
    
    status = st.empty()
    progress = st.progress(0)
    
    # We use a 365-day lookback for clean MA calculations
    start_dt = datetime.now() - timedelta(days=365)
    
    for i, symbol in enumerate(universe):
        progress.progress((i + 1) / len(universe))
        status.info(f"🔍 Analyzing {symbol} ({i+1}/{len(universe)})")
        
        try:
            # DIRECT SINGLE-SYMBOL REQUEST (No complex batching)
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                feed=DataFeed.SIP
            )
            df = client.get_stock_bars(req).df
            
            # Ensure we have data and it's not just an error string
            if df is None or df.empty: continue
            
            # Settle the data structure
            if 'symbol' in df.index.names:
                df = df.xs(symbol)
            
            if len(df) < 200: continue

            # --- Technicals ---
            df['8sma'] = df['close'].rolling(8).mean()
            df['20sma'] = df['close'].rolling(20).mean()
            df['50sma'] = df['close'].rolling(50).mean()
            df['200sma'] = df['close'].rolling(200).mean()
            df['252sma'] = df['close'].rolling(252).mean()
            df['hi20'] = df['high'].shift(1).rolling(20).max()
            df['lo20'] = df['low'].shift(1).rolling(20).min()
            df['hi252'] = df['high'].shift(1).rolling(252).max()
            
            curr, prev_5 = df.iloc[-1], df.iloc[-5]

            # --- Strategy Logic ---
            if selected == "Momentum Buy" and curr['close'] > curr['hi20']:
                dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                if dist <= 0.04: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

            elif selected == "Long Term Momentum":
                slope = (curr['50sma'] - prev_5['50sma']) / prev_5['50sma']
                if curr['close'] > curr['252sma'] and slope > 0:
                    findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

            elif selected == "Trapped Shorts" and curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

            elif selected == "Trapped Longs" and curr['high'] > curr['hi20'] and curr['close'] < curr['hi20']:
                findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

            elif selected == "Retest Long":
                at_high = (df.iloc[-10:]['high'].max() >= curr['hi252'])
                if at_high and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']:
                    findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

            elif selected == "H2 Pullback":
                if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                    findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

            elif selected == "Bull Coil":
                smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                tightness = (max(smas) - min(smas)) / min(smas)
                if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05:
                    findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tight': f'{tightness:.2%}'})

            elif selected == "Bear Coil":
                smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                tightness = (max(smas) - min(smas)) / min(smas)
                if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05:
                    findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tight': f'{tightness:.2%}'})

        except Exception:
            continue

    status.empty()
    progress.empty()
    
    if findings:
        st.success(f"FOUND {len(findings)} MATCHES")
        st.dataframe(pd.DataFrame(findings), use_container_width=True)
    else:
        st.warning(f"No results for {selected} right now.")