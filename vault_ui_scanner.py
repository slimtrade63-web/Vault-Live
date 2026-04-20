import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Vault v78.0 Institutional", layout="wide")

# Custom CSS for the 4x2 Grid
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

# --- Hardened Universe Builder ---
@st.cache_data(ttl=86400)
def get_institutional_universe():
    stock_data = PyTickerSymbols()
    # Safely extract symbols without assuming dictionary structure
    sp_raw = stock_data.get_sp_500_nyc_yahoo_tickers()
    sp = [s.get('symbol') for s in sp_raw if isinstance(s, dict) and s.get('symbol')]
    
    nas_raw = stock_data.get_nasdaq_100_nyc_yahoo_tickers()
    nas = [s.get('symbol') for s in nas_raw if isinstance(s, dict) and s.get('symbol')]
    
    # Combined and cleaned
    full_list = list(set(sp + nas))
    return [str(t).replace('.', '-') for t in sorted(full_list)]

st.title("🛡️ Institutional Vault v78.0")
st.caption("PAID TIER | SIP FEED | STABILITY FIXED")
st.divider()

# --- Auth ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
    client = StockHistoricalDataClient(api_key, secret_key)
except Exception as e:
    st.error(f"Credentials Error: {e}")
    st.stop()

# --- 4x2 Strategy Grid ---
strategies = ["Momentum Buy", "Long Term Momentum", "Trapped Shorts", "Trapped Longs", 
              "Retest Long", "H2 Pullback", "Bull Coil", "Bear Coil"]
selected_strat, cols = None, st.columns(4)
for i, strat in enumerate(strategies):
    with cols[i % 4]:
        if st.button(strat): selected_strat = strat

# --- Scanning Engine ---
if selected_strat:
    st.divider()
    try:
        universe = get_institutional_universe()
        findings = []
        status = st.empty()
        status.info(f"📡 Scanning {len(universe)} symbols via SIP feed...")
        
        # Pull 400 days to ensure 252 trading bars are present
        start_dt = datetime.now() - timedelta(days=400)
        
        # Batching to prevent timeout
        batch_size = 50
        progress = st.progress(0)
        
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress.progress(i / len(universe))
            
            try:
                # API CALL
                request = StockBarsRequest(
                    symbol_or_symbols=batch, 
                    timeframe=TimeFrame.Day, 
                    start=start_dt, 
                    feed=DataFeed.SIP # PAID FEED
                )
                response = client.get_stock_bars(request)
                
                # CRITICAL FIX: Check if response has data before calling .df
                if not hasattr(response, 'df') or response.df is None or response.df.empty:
                    continue
                
                # FLATTEN THE DATA: This prevents the "string index" error
                df_all = response.df.reset_index()
                
                for symbol in batch:
                    # Isolate symbol data
                    df = df_all[df_all['symbol'] == symbol].copy()
                    
                    if len(df) < 250: continue
                    
                    # Indicators
                    df['8sma'] = df['close'].rolling(8).mean()
                    df['20sma'] = df['close'].rolling(20).mean()
                    df['50sma'] = df['close'].rolling(50).mean()
                    df['200sma'] = df['close'].rolling(200).mean()
                    df['252sma'] = df['close'].rolling(252).mean()
                    df['hi20'] = df['high'].shift(1).rolling(20).max()
                    df['lo20'] = df['low'].shift(1).rolling(20).min()
                    df['hi252'] = df['high'].shift(1).rolling(252).max()
                    
                    curr, prev_5 = df.iloc[-1], df.iloc[-5]
                    
                    # Logic (Same as your verified strategies)
                    if selected_strat == "Momentum Buy" and curr['close'] > curr['hi20']:
                        dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                        if dist <= 0.04: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})
                    
                    elif selected_strat == "Long Term Momentum":
                        slope = (curr['50sma'] - prev_5['50sma']) / prev_5['50sma']
                        if curr['close'] > curr['252sma'] and slope > 0:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Trapped Shorts" and curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                        findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Trapped Longs" and curr['high'] > curr['hi20'] and curr['close'] < curr['hi20']:
                        findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Retest Long":
                        at_high = (df.iloc[-10:]['high'].max() >= curr['hi252'])
                        if at_high and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "H2 Pullback":
                        if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Bull Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Bear Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})
            except:
                continue

        status.empty()
        if findings:
            st.success(f"SUCCESS: {len(findings)} MATCHES")
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.warning("No matches found. This is normal if the market setup isn't active.")

    except Exception as e:
        st.error(f"CRITICAL ERROR: {e}")