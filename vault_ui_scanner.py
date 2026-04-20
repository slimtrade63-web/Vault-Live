import streamlit as st
import pandas as pd
from pytickersymbols import PyTickerSymbols
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta

# --- Page Setup ---
st.set_page_config(page_title="Vault v78.2", layout="wide")

st.markdown("""
    <style>
    .stButton>button {
        width: 100%; height: 70px; font-weight: bold; font-family: 'Consolas', monospace;
        font-size: 15px; border-radius: 8px; border: 2px solid #1f538d;
        background-color: #0e1117; color: white;
    }
    .stButton>button:hover { background-color: #1f538d; border-color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

# --- Clean Universe ---
@st.cache_data(ttl=86400)
def get_universe():
    data = PyTickerSymbols()
    # Grabbing S&P 500 and Nasdaq 100 only for maximum speed/reliability
    sp = [s['symbol'] for s in data.get_sp_500_nyc_yahoo_tickers() if 'symbol' in s]
    nas = [s['symbol'] for s in data.get_nasdaq_100_nyc_yahoo_tickers() if 'symbol' in s]
    return sorted(list(set(sp + nas)))

st.title("🛡️ Institutional Vault v78.2")
st.caption("PAID SIP FEED | INDIVIDUAL SYMBOL RECOVERY")

# --- Auth ---
try:
    client = StockHistoricalDataClient(st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_API_SECRET"])
except:
    st.error("API Keys Missing in Secrets.")
    st.stop()

# --- 4x2 Grid ---
strategies = ["Momentum Buy", "Long Term Momentum", "Trapped Shorts", "Trapped Longs", 
              "Retest Long", "H2 Pullback", "Bull Coil", "Bear Coil"]
selected, cols = None, st.columns(4)
for i, s in enumerate(strategies):
    with cols[i % 4]:
        if st.button(s): selected = s

if selected:
    st.divider()
    universe = get_universe()
    findings = []
    
    status = st.empty()
    progress = st.progress(0)
    
    # We set end to yesterday to ensure no "Today's bar is empty" errors
    end_dt = datetime.now() - timedelta(days=1)
    start_dt = end_dt - timedelta(days=365)
    
    for i, symbol in enumerate(universe):
        progress.progress((i + 1) / len(universe))
        status.info(f"📡 {selected.upper()}: Checking {symbol}...")
        
        try:
            # 1. Fetch raw response
            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
                feed=DataFeed.SIP
            )
            
            response = client.get_stock_bars(request_params)
            
            # 2. THE CRITICAL FIX: Manually verify the data exists in the dictionary
            if not response.data or symbol not in response.data or not response.data[symbol]:
                continue
                
            # 3. Convert only the valid symbol data to DF
            df = pd.DataFrame([vars(bar) for bar in response.data[symbol]])
            
            if df.empty or len(df) < 200:
                continue

            # --- Technicals ---
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

            # --- Simplified Logic Check ---
            match = False
            if selected == "Momentum Buy" and curr['close'] > curr['hi20']:
                dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                if dist <= 0.04: match = True
            
            elif selected == "Long Term Momentum":
                slope = (curr['50sma'] - prev_5['50sma']) / prev_5['50sma']
                if curr['close'] > curr['252sma'] and slope > 0: match = True

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

        except Exception as e:
            # Silently continue on individual errors
            continue

    status.empty()
    progress.empty()
    
    if findings:
        st.success(f"FOUND {len(findings)} MATCHES")
        st.dataframe(pd.DataFrame(findings), use_container_width=True)
    else:
        st.warning(f"No results for {selected}. This usually means the criteria weren't met today.")