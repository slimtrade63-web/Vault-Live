import streamlit as st
import pandas as pd
import os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Vault v76.9 Institutional", layout="wide")

st.title("🛡️ Institutional Vault v76.9")
st.markdown("---")

# --- Sidebar: Credentials ---
st.sidebar.header("🔑 Authentication")
api_key = st.sidebar.text_input("Alpaca API Key", value=os.getenv('ALPACA_API_KEY', ""), type="password")
secret_key = st.sidebar.text_input("Alpaca API Secret", value=os.getenv('ALPACA_API_SECRET', ""), type="password")

# --- Strategy Selection ---
st.sidebar.header("📡 Strategy Command")
strategies = [
    "Momentum Buy", "Long Term Momentum", "Trapped Shorts", 
    "Trapped Longs", "Retest Long", "H2 Pullback", 
    "Bull Coil", "Bear Coil"
]
selected_strat = st.sidebar.selectbox("Select Strategy to Scan", strategies)
run_scan = st.sidebar.button("🚀 RUN INSTITUTIONAL SCAN")

# --- Logic Processing ---
if run_scan:
    if not api_key or not secret_key:
        st.error("Please enter your Alpaca API Keys in the sidebar.")
    else:
        try:
            with st.spinner(f"Scanning 250 assets for {selected_strat}..."):
                # Initialize Clients
                data_client = StockHistoricalDataClient(api_key, secret_key)
                trading_client = TradingClient(api_key, secret_key)
                
                # Fetch Assets
                assets = trading_client.get_all_assets(GetAssetsRequest(status='active', asset_class='us_equity'))
                tickers = [a.symbol for a in assets if a.tradable and a.marginable][:250]
                
                # Fetch Data
                bars = data_client.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=tickers, 
                    timeframe=TimeFrame.Day, 
                    start=datetime.now()-timedelta(days=450)
                )).df.reset_index()
                
                findings = []
                
                for symbol in tickers:
                    df = bars[bars['symbol'] == symbol].copy()
                    if len(df) < 252: continue
                    
                    # Technicals
                    df['8sma'] = df['close'].rolling(8).mean()
                    df['20sma'] = df['close'].rolling(20).mean()
                    df['50sma'] = df['close'].rolling(50).mean()
                    df['200sma'] = df['close'].rolling(200).mean()
                    df['252sma'] = df['close'].rolling(252).mean()
                    df['hi20'] = df['high'].shift(1).rolling(20).max()
                    df['lo20'] = df['low'].shift(1).rolling(20).min()
                    df['hi252'] = df['high'].shift(1).rolling(252).max()
                    
                    curr = df.iloc[-1]
                    
                    # Strategy Logic
                    if selected_strat == "Momentum Buy":
                        dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                        if curr['close'] > curr['hi20'] and dist <= 0.04:
                            findings.append({'Symbol': symbol, 'Trigger': round(curr['hi20'], 2), 'Price': round(curr['close'], 2), 'Dist_8MA': f'{dist:.2%}'})
                    
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
                    
                    elif selected_strat == "Long Term Momentum":
                        slope = (curr['50sma'] - df.iloc[-5]['50sma']) / df.iloc[-5]['50sma']
                        if curr['close'] > curr['252sma'] and slope > 0:
                            findings.append({'Symbol': symbol, '252SMA': round(curr['252sma'], 2), 'Price': round(curr['close'], 2), 'Slope': f'{slope:.2%}'})
                    
                    elif selected_strat == "Retest Long":
                        if (df.iloc[-5:]['hi252'].max() == curr['hi252']) and (curr['low'] <= curr['20sma']) and (curr['close'] > curr['20sma']):
                            findings.append({'Symbol': symbol, '20SMA': round(curr['20sma'], 2), 'Price': round(curr['close'], 2), 'Status': 'Bounce'})
                    
                    elif selected_strat == "Trapped Shorts":
                        if curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']:
                            findings.append({'Symbol': symbol, '20D_Low': round(curr['lo20'], 2), 'Price': round(curr['close'], 2), 'Action': 'Reclaim'})

                # --- Display Results ---
                if findings:
                    st.success(f"Strategy {selected_strat} found {len(findings)} hits!")
                    result_df = pd.DataFrame(findings)
                    st.dataframe(result_df, use_container_width=True)
                    
                    # Download CSV (Replaces the text report)
                    csv = result_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 DOWNLOAD REPORT (CSV)", data=csv, file_name=f"{selected_strat}_report.csv", mime='text/csv')
                else:
                    st.warning(f"No {selected_strat} setups found currently.")

        except Exception as e:
            st.error(f"Scan Failed: {str(e)}")
else:
    st.info("👈 Set your keys and select a strategy in the sidebar to begin.")