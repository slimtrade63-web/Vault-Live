import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(page_title="Vault v77.6 Institutional", layout="wide")

# CSS for 4x2 Grid
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

# --- Universe ---
@st.cache_data(ttl=86400)
def get_institutional_universe():
    stock_data = PyTickerSymbols()
    sp = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers() if 'symbol' in s]
    nas = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers() if 'symbol' in s]
    rus_raw = stock_data.get_stocks_by_index('Russell 2000')
    rus = [s['symbol'] if isinstance(s, dict) else s for s in rus_raw][:500]
    return [str(t).replace('.', '-') for t in sorted(list(set(sp + nas + rus))) if t]

st.title("🛡️ Institutional Vault v77.6")
st.caption("ADAPTIVE DATA FEED ENABLED | FULL INDEX SCAN")
st.divider()

# --- Auth ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
    client = StockHistoricalDataClient(api_key, secret_key)
except Exception as e:
    st.error(f"Credentials Error: {e}")
    st.stop()

# --- 4x2 STRATEGY GRID ---
strategies = ["Momentum Buy", "Long Term Momentum", "Trapped Shorts", "Trapped Longs", 
              "Retest Long", "H2 Pullback", "Bull Coil", "Bear Coil"]

selected_strat = None
cols = st.columns(4)
for i, strat in enumerate(strategies):
    with cols[i % 4]:
        if st.button(strat): selected_strat = strat

# --- Scanning Engine ---
if selected_strat:
    st.divider()
    try:
        universe = get_institutional_universe()
        findings = []
        
        # --- FEED AUTO-DETECTION ---
        # We try SIP first (for your Paid Account). If it returns nothing, we fallback to IEX.
        test_bar = client.get_stock_bars(StockBarsRequest(symbol_or_symbols=["AAPL"], timeframe=TimeFrame.Day, start=datetime.now()-timedelta(days=5), feed=DataFeed.SIP)).df
        active_feed = DataFeed.SIP if not test_bar.empty else DataFeed.IEX
        
        status_box = st.empty()
        status_box.info(f"📡 FEED: {active_feed} | SCANNING {len(universe)} SYMBOLS...")
        
        # Use 350 days to ensure we cover holidays/weekends for the 252 SMA
        start_dt = datetime.now() - timedelta(days=350)
        
        batch_size = 100
        progress_bar = st.progress(0)
        
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress_bar.progress(i / len(universe))
            
            try:
                # Optimized Data Request
                bars = client.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=batch, timeframe=TimeFrame.Day, 
                    start=start_dt, feed=active_feed
                )).df
                
                if bars.empty: continue

                # Process returned symbols
                for symbol in bars.index.get_level_values('symbol').unique():
                    df = bars.xs(symbol).copy()
                    if len(df) < 200: continue # Slightly relaxed to ensure hits
                    
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
                    
                    # Strategy Logic
                    if selected_strat == "Momentum Buy" and curr['close'] > curr['hi20']:
                        dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                        if dist <= 0.04: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), '8MA_Dist': f'{dist:.2%}'})
                    
                    elif selected_strat == "Long Term Momentum":
                        slope = (curr['50sma'] - prev_5['50sma']) / prev_5['50sma']
                        if curr['close'] > curr['252sma'] and slope > 0: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Slope': f'{slope:.2%}'})

                    elif selected_strat == "Trapped Shorts" and curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                        findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Trapped Longs" and curr['high'] > curr['hi20'] and curr['close'] < curr['hi20']:
                        findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Retest Long":
                        at_high = (df.iloc[-10:]['high'].max() >= curr['hi252'])
                        if at_high and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "H2 Pullback":
                        if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

                    elif selected_strat == "Bull Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})

                    elif selected_strat == "Bear Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})
            except: continue

        status_box.empty()
        progress_bar.empty()
        
        if findings:
            st.success(f"SUCCESS: {len(findings)} MATCHES FOUND")
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.warning(f"No results found for {selected_strat}. (Feed: {active_feed})")

    except Exception as e:
        st.error(f"Critical Failure: {e}")