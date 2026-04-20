import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Vault v77.5 Institutional", layout="wide")

# Custom CSS for the 4x2 Button Grid
st.markdown("""
    <style>
    .stButton>button {
        width: 100%; height: 75px; font-weight: bold; font-family: 'Consolas', monospace;
        font-size: 16px; text-transform: uppercase; border-radius: 10px;
        border: 2px solid #1f538d; background-color: #0e1117; color: white;
    }
    .stButton>button:hover { background-color: #1f538d; border-color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

# --- Universe Builder ---
@st.cache_data(ttl=86400)
def get_institutional_universe():
    stock_data = PyTickerSymbols()
    # Pulling from S&P 500, Nasdaq 100, and Top 500 of Russell 2000
    sp = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers() if 'symbol' in s]
    nas = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers() if 'symbol' in s]
    rus_raw = stock_data.get_stocks_by_index('Russell 2000')
    rus = [s['symbol'] if isinstance(s, dict) else s for s in rus_raw][:500]
    
    full_list = list(set(sp + nas + rus))
    return [str(t).replace('.', '-') for t in sorted(full_list) if t]

st.title("🛡️ Institutional Vault v77.5")
st.caption("PAID SIP FEED ACTIVE | FULL INDEX SCAN")
st.divider()

# --- Auth ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
except:
    st.error("🔑 Keys missing in Streamlit Secrets.")
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
        universe = get_institutional_universe()
        client = StockHistoricalDataClient(api_key, secret_key)
        findings = []
        
        status = st.empty()
        status.info(f"📡 SIP SCANNING {len(universe)} SYMBOLS FOR {selected_strat.upper()}...")
        
        # Pull 400 days to ensure we have exactly 252+ trading bars
        start_dt = datetime.now() - timedelta(days=400)
        
        # Process in batches of 100 for maximum reliability on Paid Tier
        batch_size = 100
        progress_bar = st.progress(0)
        
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress_bar.progress(i / len(universe))
            
            try:
                # API CALL
                request_params = StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=start_dt,
                    feed=DataFeed.SIP  # Using your Paid Tier SIP Feed
                )
                raw_data = client.get_stock_bars(request_params).df
                
                if raw_data.empty:
                    continue

                # Get the unique symbols that actually returned data in this batch
                symbols_in_data = raw_data.index.get_level_values('symbol').unique()
                
                for symbol in symbols_in_data:
                    df = raw_data.xs(symbol).copy()
                    
                    if len(df) < 252:
                        continue
                    
                    # --- Indicators ---
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
                    
                    # --- Strategy Logic ---
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
                        recent_high = (df.iloc[-10:]['high'].max() >= curr['hi252'])
                        if recent_high and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Type': 'Retest'})

                    elif selected_strat == "H2 Pullback":
                        if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                            findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2)})

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

            except Exception as e:
                # Log specific batch errors to console for you to see in "Manage App"
                print(f"Batch Error: {e}")
                continue

        status.empty()
        progress_bar.empty()
        
        if findings:
            st.success(f"SUCCESS: {len(findings)} MATCHES FOUND")
            res_df = pd.DataFrame(findings)
            st.dataframe(res_df, use_container_width=True)
            st.download_button("📥 DOWNLOAD CSV", res_df.to_csv(index=False), f"{selected_strat}.csv")
        else:
            st.warning(f"No results for {selected_strat}. Verify market is open or criteria are met.")

    except Exception as e:
        st.error(f"SCANNER FATAL ERROR: {e}")