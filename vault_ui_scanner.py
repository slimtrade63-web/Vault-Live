import streamlit as st
import pandas as pd
import os
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Vault v77 Institutional", layout="wide")

# Custom CSS for the 4x2 Button Grid
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 70px;
        font-weight: bold;
        font-family: 'Consolas', monospace;
        font-size: 15px;
        text-transform: uppercase;
        border-radius: 8px;
        border: 2px solid #1f538d;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Universe Builder (Cached) ---
@st.cache_data(ttl=86400)
def get_full_institutional_universe():
    stock_data = PyTickerSymbols()
    sp500 = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers()]
    nasdaq = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers()]
    russell = [s['symbol'] for s in stock_data.get_stocks_by_index('Russell 2000')][:500]
    return sorted(list(set(sp500 + nasdaq + russell)))

st.title("🛡️ Institutional Vault v76.9")
st.divider()

# --- Credentials ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
except:
    st.error("🔑 Keys missing in Streamlit Secrets.")
    st.stop()

# --- REARRANGED STRATEGY GRID (4 over 4) ---
strategies = [
    "Momentum Buy", "Long Term Momentum", "Trapped Shorts", "Trapped Longs", 
    "Retest Long", "H2 Pullback", "Bull Coil", "Bear Coil"
]

selected_strat = None

# Create 4 columns
cols = st.columns(4)

# Fill the columns (first 4 in row 1, next 4 in row 2)
for i, strat in enumerate(strategies):
    with cols[i % 4]:
        if st.button(strat):
            selected_strat = strat

st.divider()

# --- Scanning Engine ---
if selected_strat:
    try:
        universe = get_full_institutional_universe()
        data_client = StockHistoricalDataClient(api_key, secret_key)
        findings = []
        
        progress_text = f"📡 SCANNING {len(universe)} SYMBOLS: {selected_strat.upper()}..."
        progress_bar = st.progress(0, text=progress_text)
        
        batch_size = 50
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress_bar.progress(i / len(universe), text=progress_text)
            
            try:
                bars = data_client.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=datetime.now()-timedelta(days=450)
                )).df.reset_index()
                
                for symbol in batch:
                    df = bars[bars['symbol'] == symbol].copy()
                    if len(df) < 252: continue
                    
                    # Technical Calculations
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
                    
                    # Logic implementation (Momentum Buy, Coil, etc.)
                    if selected_strat == "Momentum Buy":
                        dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                        if curr['close'] > curr['hi20'] and dist <= 0.04:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), '8MA_Dist': f'{dist:.2%}'})
                    
                    elif selected_strat == "Bull Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})
                    
                    # ... [Include other strategy logic here as per previous version] ...

            except: continue

        progress_bar.empty()
        
        if findings:
            st.success(f"TARGETS FOUND: {len(findings)}")
            res_df = pd.DataFrame(findings)
            st.dataframe(res_df, use_container_width=True)
            st.download_button("📥 DOWNLOAD REPORT", res_df.to_csv(index=False), f"{selected_strat}.csv")
        else:
            st.warning(f"No setups found for {selected_strat}.")

    except Exception as e:
        st.error(f"SCANNER ERROR: {e}")