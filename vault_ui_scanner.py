import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

# --- Page Setup ---
st.set_page_config(page_title="Vault Restored", layout="wide")

# CSS for the 4x2 Strategy Grid
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

# --- Universe Logic ---
@st.cache_data(ttl=86400)
def get_universe():
    stock_data = PyTickerSymbols()
    # Grabbing the list of tickers exactly how we did in the original working version
    sp = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers()]
    nas = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers()]
    return sorted(list(set(sp + nas)))

st.title("🛡️ Institutional Vault (Restored)")
st.caption("Using original stable retrieval logic")
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
    
    # 365 days of data for calculation stability
    start_dt = datetime.now() - timedelta(days=365)
    
    for i, symbol in enumerate(universe):
        progress.progress((i + 1) / len(universe))
        status.info(f"🔍 Analyzing {symbol}...")
        
        try:
            # The Simple Retrieval that worked:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt
            )
            # Fetch data and immediate .df conversion
            df = client.get_stock_bars(req).df
            
            if df is None or df.empty: continue
            
            # Remove multi-index if present
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
            
            curr = df.iloc[-1]
            prev_5 = df.iloc[-5]

            # --- Strategy Logic (Restored) ---
            match = False
            if selected == "Momentum Buy" and curr['close'] > curr['hi20']:
                if (abs(curr['close'] - curr['8sma']) / curr['8sma']) <= 0.04: match = True
            
            elif selected == "Long Term Momentum":
                if curr['close'] > curr['252sma'] and curr['50sma'] > prev_5['50sma']: match = True

            elif selected == "Trapped Shorts" and curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                match = True

            elif selected == "Trapped Longs" and curr['high'] > curr['hi20'] and curr['close'] < curr['hi20']:
                match = True

            elif selected == "Retest Long":
                if (df.iloc[-10:]['high'].max() >= curr['hi252']) and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']:
                    match = True

            elif selected == "H2 Pullback":
                if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                    match = True

            elif selected == "Bull Coil":
                smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and (max(smas)-min(smas))/min(smas) <= 0.05:
                    match = True

            elif selected == "Bear Coil":
                smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and (max(smas)-min(smas))/min(smas) <= 0.05:
                    match = True

            if match:
                findings.append({'Symbol': symbol, 'Price': round(float(curr['close']), 2)})

        except Exception:
            # If one symbol fails, just keep moving like the old version did
            continue

    status.empty()
    progress.empty()
    
    if findings:
        st.success(f"COMPLETE: Found {len(findings)} results")
        st.dataframe(pd.DataFrame(findings), use_container_width=True)
    else:
        st.warning(f"Scan complete. No matches found for {selected}.")