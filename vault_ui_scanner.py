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
st.set_page_config(page_title="Vault v76.9 Institutional", layout="wide")

# Custom CSS for the Button Grid
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 80px;
        font-weight: bold;
        font-family: 'Consolas', monospace;
        font-size: 18px;
        text-transform: uppercase;
        border-radius: 12px;
        border: 2px solid #1f538d;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Universe Builder (Cached for 24 Hours) ---
@st.cache_data(ttl=86400)
def get_full_institutional_universe():
    stock_data = PyTickerSymbols()
    sp500 = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers()]
    nasdaq = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers()]
    # Russell 2000 is large; we take the first 500 to keep scan times under 2 mins
    russell = [s['symbol'] for s in stock_data.get_stocks_by_index('Russell 2000')][:500]
    
    full_list = list(set(sp500 + nasdaq + russell))
    return sorted(full_list)

st.title("🛡️ Institutional Vault v76.9")
st.subheader("UNIVERSE: S&P 500 | NASDAQ 100 | RUSSELL TOP 500")
st.divider()

# --- Credentials ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
except:
    st.error("🔑 SECURITY ALERT: Alpaca Keys missing in Streamlit Secrets.")
    st.stop()

# --- Strategy Grid ---
strategies = [
    "Momentum Buy", "Long Term Momentum", "Trapped Shorts", 
    "Trapped Longs", "Retest Long", "H2 Pullback", 
    "Bull Coil", "Bear Coil"
]

col1, col2 = st.columns(2)
selected_strat = None

for i, strat in enumerate(strategies):
    with (col1 if i % 2 == 0 else col2):
        if st.button(strat):
            selected_strat = strat

# --- Scanning Engine ---
if selected_strat:
    try:
        universe = get_full_institutional_universe()
        data_client = StockHistoricalDataClient(api_key, secret_key)
        findings = []
        
        progress_text = f"📡 SCANNING {len(universe)} SYMBOLS FOR {selected_strat.upper()}..."
        progress_bar = st.progress(0, text=progress_text)
        
        # Batching for stability (Chunks of 50)
        batch_size = 50
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress_bar.progress(i / len(universe), text=progress_text)
            
            try:
                # Fetching 450 days of data for the 252 SMA and 252 Highs
                bars = data_client.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=datetime.now()-timedelta(days=450)
                )).df.reset_index()
                
                for symbol in batch:
                    df = bars[bars['symbol'] == symbol].copy()
                    if len(df) < 252: continue
                    
                    # --- Technical Core ---
                    df['8sma'] = df['close'].rolling(8).mean()
                    df['20sma'] = df['close'].rolling(20).mean()
                    df['50sma'] = df['close'].rolling(50).mean()
                    df['200sma'] = df['close'].rolling(200).mean()
                    df['252sma'] = df['close'].rolling(252).mean()
                    df['hi20'] = df['high'].shift(1).rolling(20).max()
                    df['lo20'] = df['low'].shift(1).rolling(20).min()
                    df['hi252'] = df['high'].shift(1).rolling(252).max()
                    
                    curr = df.iloc[-1]
                    prev_5 = df.iloc[-5] # Used for slope and retest logic
                    
                    # --- FULL STRATEGY LOGIC ---
                    if selected_strat == "Momentum Buy":
                        dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                        if curr['close'] > curr['hi20'] and dist <= 0.04:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), '8MA_Dist': f'{dist:.2%}'})

                    elif selected_strat == "Long Term Momentum":
                        slope = (curr['50sma'] - prev_5['50sma']) / prev_5['50sma']
                        if curr['close'] > curr['252sma'] and slope > 0:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Slope': f'{slope:.2%}'})

                    elif selected_strat == "Trapped Shorts":
                        if curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Action': 'Reclaim'})

                    elif selected_strat == "Trapped Longs":
                        if curr['high'] > curr['hi20'] and curr['close'] < curr['hi20']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Action': 'Failure'})

                    elif selected_strat == "Retest Long":
                        if (df.iloc[-5:]['hi252'].max() == curr['hi252']) and (curr['low'] <= curr['20sma']) and (curr['close'] > curr['20sma']):
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Status': 'Bounce'})

                    elif selected_strat == "H2 Pullback":
                        if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Setup': 'H2'})

                    elif selected_strat == "Bull Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})

                    elif selected_strat == "Bear Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})

            except: continue # Skip faulty ticker batches

        progress_bar.empty()
        
        if findings:
            st.success(f"STRATEGY: {selected_strat.upper()} | TARGETS: {len(findings)}")
            res_df = pd.DataFrame(findings)
            st.dataframe(res_df, use_container_width=True)
            st.download_button("📥 DOWNLOAD REPORT", res_df.to_csv(index=False), f"{selected_strat}.csv")
        else:
            st.warning(f"No setups found for {selected_strat} in the current universe.")

    except Exception as e:
        st.error(f"SCANNER ERROR: {e}")