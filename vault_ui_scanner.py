import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Setup ---
st.set_page_config(page_title="Vault v77.3 Institutional", layout="wide")

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

# --- Universe (Fixed Extraction) ---
@st.cache_data(ttl=86400)
def get_institutional_universe():
    stock_data = PyTickerSymbols()
    sp = [s['symbol'] for s in stock_data.get_sp_500_nyc_yahoo_tickers() if 'symbol' in s]
    nas = [s['symbol'] for s in stock_data.get_nasdaq_100_nyc_yahoo_tickers() if 'symbol' in s]
    rus = [s['symbol'] if isinstance(s, dict) else s for s in stock_data.get_stocks_by_index('Russell 2000')][:500]
    return [str(t).replace('.', '-') for t in sorted(list(set(sp + nas + rus)))]

st.title("🛡️ Institutional Vault v77.3")
st.caption("PAID TIER ACTIVE | S&P 500, NASDAQ 100, RUSSELL TOP 500")
st.divider()

# --- Auth ---
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_API_SECRET"]
except:
    st.error("🔑 Keys missing in Streamlit Secrets.")
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
        client = StockHistoricalDataClient(api_key, secret_key)
        findings = []
        
        status = st.empty()
        status.info(f"📡 SIP SCANNING {len(universe)} SYMBOLS...")
        
        # Pulling 400 days for 252-day math
        start_dt = datetime.now() - timedelta(days=400)
        
        # Batching for reliability (Paid Tier handles 100-200 easily)
        batch_size = 100
        progress_bar = st.progress(0)
        
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i+batch_size]
            progress_bar.progress(i / len(universe))
            
            try:
                # REQUESTING SIP DATA
                raw_data = client.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=start_dt,
                    feed=DataFeed.SIP # PAID FEED
                )).df
                
                if raw_data.empty: continue

                # NEW: Robust data extraction from multi-index
                unique_symbols = raw_data.index.get_level_values('symbol').unique()
                
                for symbol in unique_symbols:
                    df = raw_data.xs(symbol).copy()
                    
                    # Ensure we have enough bars for the math
                    if len(df) < 252: continue
                    
                    # Calculations
                    df['8sma'] = df['close'].rolling(8).mean()
                    df['20sma'] = df['close'].rolling(20).mean()
                    df['50sma'] = df['close'].rolling(50).mean()
                    df['200sma'] = df['close'].rolling(200).mean()
                    df['252sma'] = df['close'].rolling(252).mean()
                    df['hi20'] = df['high'].shift(1).rolling(20).max()
                    df['lo20'] = df['low'].shift(1).rolling(20).min()
                    df['hi252'] = df['high'].shift(1).rolling(252).max()
                    
                    curr, prev_5 = df.iloc[-1], df.iloc[-5]
                    
                    # STRATEGY BLOCKS (Logic Preserved Exactly)
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
                        recent_high = df.iloc[-10:]['high'].max() >= curr['hi252']
                        if recent_high and curr['low'] <= curr['20sma'] and curr['close'] > curr['20sma']:
                            findings.append({'Symbol': symbol, 'Price': curr['close']})

                    elif selected_strat == "H2 Pullback":
                        if curr['close'] > curr['200sma'] and curr['close'] < curr['20sma'] and curr['low'] > curr['50sma']:
                            findings.append({'Symbol': symbol, 'Price': curr['close']})

                    elif selected_strat == "Bull Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': curr['close'], 'Tightness': f'{tightness:.2%}'})

                    elif selected_strat == "Bear Coil":
                        smas = [curr['8sma'], curr['20sma'], curr['200sma']]
                        tightness = (max(smas) - min(smas)) / min(smas)
                        if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05:
                            findings.append({'Symbol': symbol, 'Price': curr['close'], 'Tightness': f'{tightness:.2%}'})

            except: continue

        status.empty()
        progress_bar.empty()
        
        if findings:
            st.success(f"FOUND {len(findings)} MATCHES")
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.warning(f"Strategy {selected_strat} returned 0 results. Try 'Long Term Momentum' to verify connectivity.")

    except Exception as e:
        st.error(f"SCANNER ERROR: {e}")