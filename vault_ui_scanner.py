import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

# --- Page Setup ---
st.set_page_config(page_title="Vault Restored", layout="wide")

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

# --- RESTORED: Universe Function with Safety Check ---
@st.cache_data(ttl=86400)
def get_universe():
    data = PyTickerSymbols()
    # Added "if 'symbol' in s" to prevent the TypeError you're seeing
    sp = [s['symbol'] for s in data.get_sp_500_nyc_yahoo_tickers() if s is not None and 'symbol' in s]
    nas = [s['symbol'] for s in data.get_nasdaq_100_nyc_yahoo_tickers() if s is not None and 'symbol' in s]
    return sorted(list(set(sp + nas)))

st.title("🛡️ Institutional Vault v78.8")
st.caption("STABLE RESTORATION | DATA-SAFETY PATCH")
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

# --- Scanning Engine ---
if selected:
    st.divider()
    universe = get_universe()
    findings = []
    
    status = st.empty()
    progress = st.progress(0)
    
    start_dt = datetime.now() - timedelta(days=365)
    
    for i, symbol in enumerate(universe):
        progress.progress((i + 1) / len(universe))
        status.info(f"🔍 Analyzing {symbol}...")
        
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt
            )
            df = client.get_stock_bars(req).df
            
            if df is None or df.empty: continue
            
            if 'symbol' in df.index.names:
                df = df.xs(symbol)
                
            if len(df) < 200: continue

            # --- Technical Indicators ---
            df['8sma'] = df['close'].rolling(8).mean()
            df['20sma'] = df['close'].rolling(20).mean()
            df['50sma'] = df['close'].rolling(50).mean()
            df['200sma'] = df['close'].rolling(200).mean()
            df['252sma'] = df['close'].rolling(252).mean()
            df['hi20'] = df['high'].shift(1).rolling(20).max()
            df['lo20'] = df['low'].shift(1).rolling(20).min()
            df['hi252'] = df['high'].shift(1).rolling(252).max()
            
            c = df.iloc[-1]
            p5 = df.iloc[-5]

            # --- Strategy Logic ---
            match = False
            if selected == "Momentum Buy" and c['close'] > c['hi20']:
                if (abs(c['close'] - c['8sma']) / c['8sma']) <= 0.04: match = True
            elif selected == "Long Term Momentum" and c['close'] > c['252sma'] and (c['50sma'] > p5['50sma']):
                match = True
            elif selected == "Trapped Shorts" and c['low'] < c['lo20'] and c['close'] > c['lo20']:
                match = True
            elif selected == "Trapped Longs" and c['high'] > c['hi20'] and c['close'] < c['hi20']:
                match = True
            elif selected == "Retest Long":
                if (df.iloc[-10:]['high'].max() >= c['hi252']) and c['low'] <= c['20sma'] and c['close'] > c['20sma']:
                    match = True
            elif selected == "H2 Pullback" and c['close'] > c['200sma'] and c['close'] < c['20sma'] and c['low'] > c['50sma']:
                match = True
            elif selected == "Bull Coil":
                smas = [c['8sma'], c['20sma'], c['200sma']]
                if (c['close'] > c['8sma'] > c['20sma'] > c['200sma']) and (max(smas)-min(smas))/min(smas) <= 0.05:
                    match = True
            elif selected == "Bear Coil":
                smas = [c['8sma'], c['20sma'], c['200sma']]
                if (c['close'] < c['8sma'] < c['20sma'] < c['200sma']) and (max(smas)-min(smas))/min(smas) <= 0.05:
                    match = True

            if match:
                findings.append({'Symbol': symbol, 'Price': round(float(c['close']), 2)})

        except Exception:
            continue

    status.empty()
    progress.empty()
    
    if findings:
        st.success(f"COMPLETE: Found {len(findings)} results")
        st.dataframe(pd.DataFrame(findings), use_container_width=True)
    else:
        st.warning(f"No results found for {selected}.")