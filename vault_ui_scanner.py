import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Vault v77.0 Institutional", layout="wide")

# Custom CSS for the 4x2 Button Grid
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 75px;
        font-weight: bold;
        font-family: 'Consolas', monospace;
        font-size: 16px;
        text-transform: uppercase;
        border-radius: 10px;
        border: 2px solid #1f538d;
        background-color: #0e1117;
        color: white;
    }
    .stButton>button:hover {
        background-color: #1f538d;
        border-color: #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Hardened Universe Builder (Fixes String Index Error) ---
@st.cache_data(ttl=86400)
def get_full_institutional_universe():
    stock_data = PyTickerSymbols()
    
    # Clean extraction for S&P 500
    sp500_raw = stock_data.get_sp_500_nyc_yahoo_tickers()
    sp500 = [s['symbol'] for s in sp500_raw if isinstance(s, dict) and 'symbol' in s]
    
    # Clean extraction for Nasdaq 100
    nasdaq_raw = stock_data.get_nasdaq_100_nyc_yahoo_tickers()
    nasdaq = [s['symbol'] for s in nasdaq_raw if isinstance(s, dict) and 'symbol' in s]
    
    # Clean extraction for Russell 2000 (Top 500)
    russell_raw = stock_data.get_stocks_by_index('Russell 2000')
    russell = []
    for s in russell_raw:
        if isinstance(s, dict) and 'symbol' in s:
            russell.append(s['symbol'])
        elif isinstance(s, str):
            russell.append(s)
            
    # Combine, Deduplicate, and Format for Alpaca (Replace . with -)
    full_list = list(set(sp500 + nasdaq + russell[:500]))
    return [str(t).replace('.', '-') for t in sorted(full_list)]

st.title("🛡️ Institutional Vault v77.0")
st.caption("Universe: S&P 500 | NASDAQ 100 | RUSSELL TOP 500")
st.divider()

# --- Credentials ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
except:
    st.error("🔑 SECURITY ALERT: Alpaca Keys missing in Streamlit Secrets.")
    st.stop()

# --- 4x2 STRATEGY GRID ---
strategies = [
    "Momentum Buy", "Long Term Momentum", "Trapped Shorts", "Trapped Longs", 
    "Retest Long", "H2 Pullback", "Bull Coil", "Bear Coil"
]

selected_strat = None
cols = st.columns(4)

for i, strat in enumerate(strategies):
    with cols[i % 4]:
        if st.button(strat):
            selected_strat = strat

# --- Scanning Engine ---
if selected_strat:
    st.divider()
    try:
        universe = get_full_institutional_universe()
        data_client = StockHistoricalDataClient(api_key, secret_key)
        findings = []
        
        progress_bar = st.progress(0, text=f"📡 SCANNING {len(universe)} SYMBOLS...")
        
        batch_size = 50
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress_bar.progress(i / len(universe), text=f"Processing {i}/{len(universe)} symbols...")
            
            try:
                bars = data_client.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=datetime.now()-timedelta(days=450)
                )).df.reset_index()
                
                for symbol in batch:
                    df = bars[bars['symbol'] == symbol].copy()
                    if len(df) < 252: continue
                    
                    # Technical Core
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
                    
                    # Strategy Decision Logic
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

            except: continue

        progress_bar.empty()
        
        if findings:
            st.success(f"SCAN COMPLETE: {len(findings)} TARGETS FOUND")
            res_df = pd.DataFrame(findings)
            st.dataframe(res_df, use_container_width=True)
            st.download_button("📥 DOWNLOAD REPORT", res_df.to_csv(index=False), f"Vault_{selected_strat}.csv")
        else:
            st.warning(f"NO SETUPS CURRENTLY FOUND FOR {selected_strat.upper()}.")

    except Exception as e:
        st.error(f"SYSTEM ERROR: {e}")