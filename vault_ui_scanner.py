import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(page_title="Vault v77.8", layout="wide")

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

# --- Universe ---
@st.cache_data(ttl=86400)
def get_institutional_universe():
    stock_data = PyTickerSymbols()
    sp = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers()]
    nas = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers()]
    rus = [s['symbol'] if isinstance(s, dict) else s for s in stock_data.get_stocks_by_index('Russell 2000')][:500]
    full_list = list(set(sp + nas + rus))
    return [str(t).replace('.', '-') for t in sorted(full_list) if t]

st.title("🛡️ Institutional Vault v77.8")
st.caption("PAID TIER SIP ENABLED | AGGRESSIVE DATA RECOVERY")
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
        status.info(f"📡 Scanning {len(universe)} symbols using SIP feed...")
        
        # 300 days of data for reliable SMAs
        start_date = datetime.now() - timedelta(days=380)
        
        # Batching for stability
        batch_size = 50 
        progress = st.progress(0)
        
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress.progress(i / len(universe))
            
            try:
                # REQUEST
                req = StockBarsRequest(symbol_or_symbols=batch, timeframe=TimeFrame.Day, start=start_date, feed=DataFeed.SIP)
                raw_df = client.get_stock_bars(req).df
                
                if raw_df.empty: continue
                
                # THE FIX: Reset index so 'symbol' becomes a normal column
                df_flat = raw_df.reset_index()
                
                for symbol in batch:
                    # Filter flat DF for this specific symbol
                    sdf = df_flat[df_flat['symbol'] == symbol].copy()
                    
                    if len(sdf) < 200: continue
                    
                    # Technicals
                    sdf['8sma'] = sdf['close'].rolling(8).mean()
                    sdf['20sma'] = sdf['close'].rolling(20).mean()
                    sdf['50sma'] = sdf['close'].rolling(50).mean()
                    sdf['200sma'] = sdf['close'].rolling(200).mean()
                    sdf['252sma'] = sdf['close'].rolling(252).mean()
                    sdf['hi20'] = sdf['high'].shift(1).rolling(20).max()
                    sdf['lo20'] = sdf['low'].shift(1).rolling(20).min()
                    sdf['hi252'] = sdf['high'].shift(1).rolling(252).max()
                    
                    curr, prev_5 = sdf.iloc[-1], sdf.iloc[-5]
                    
                    # Logic
                    if selected_strat == "Momentum Buy" and curr['close'] > curr['hi20']:
                        dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                        if dist <= 0.04: findings.append({'Symbol': symbol, 'Price': curr['close'], '8MA_Dist': f'{dist:.2%}'})
                    
                    elif selected_strat == "Long Term Momentum":
                        slope = (curr['50sma'] - prev_5['50sma']) / prev_5['50sma']
                        if curr['close'] > curr['252sma'] and slope > 0:
                            findings.append({'Symbol': symbol, 'Price': curr['close'], 'Slope': f'{slope:.2%}'})

                    elif selected_strat == "Trapped Shorts" and curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                        findings.append({'Symbol': symbol, 'Price': curr['close']})

                    elif selected_strat == "Trapped Longs" and curr['high'] > curr['hi20'] and curr['close'] < curr['hi20']:
                        findings.append({'Symbol': symbol, 'Price': curr['close']})

                    elif selected_strat == "Retest Long":
                        recent_high = (sdf.iloc[-10:]['high'].max() >= curr['hi252'])
                        if recent_high and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']:
                            findings.append({'Symbol': symbol, 'Price': curr['close']})

                    elif selected_strat == "H2 Pullback":
                        if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                            findings.append({'Symbol': symbol, 'Price': curr['close']})

                    elif selected_strat == "Bull Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': curr['close'], 'Tight': f'{tightness:.2%}'})

                    elif selected_strat == "Bear Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': curr['close'], 'Tight': f'{tightness:.2%}'})
            except: continue

        status.empty()
        if findings:
            st.success(f"FOUND {len(findings)} TARGETS")
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.warning("No results found. Verify connection/market conditions.")

    except Exception as e:
        st.error(f"Critical: {e}")