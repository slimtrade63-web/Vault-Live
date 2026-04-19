import os
import pandas as pd
import customtkinter as ctk
from tkinter import messagebox
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from datetime import datetime, timedelta

# --- Results Window with Auto-Archiving Logic ---
class ResultsWindow(ctk.CTkToplevel):
    def __init__(self, strategy_name, data, columns):
        super().__init__()
        self.strategy_name = strategy_name
        self.title(f"Vault v76.9 - {self.strategy_name}")
        self.geometry("1250x850")
        
        self.df = pd.DataFrame(data)
        self.columns = columns
        self.sort_states = {col: False for col in columns} 

        # Header Section
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=20)

        self.strategy_label = ctk.CTkLabel(
            self.header_frame, text=f"STRATEGY: {self.strategy_name.upper()}", 
            font=("Consolas", 28, "bold"), text_color="#1f538d"
        )
        self.strategy_label.pack()

        self.hit_count = len(self.df)
        self.counter_label = ctk.CTkLabel(
            self.header_frame, text=f"TOTAL HITS: {self.hit_count}", 
            font=("Consolas", 20, "bold"), text_color="#4CAF50"
        )
        self.counter_label.pack(pady=10)

        # Table UI
        self.table_container = ctk.CTkScrollableFrame(self, fg_color="#1a1a1a")
        self.table_container.pack(fill="both", expand=True, padx=25, pady=10)
        self.render_table()

        # Footer Report Button
        self.report_btn = ctk.CTkButton(
            self, text="GENERATE REPORT", command=self.auto_save_report, 
            fg_color="#1f538d", font=("Consolas", 18, "bold"), height=50, width=300
        )
        self.report_btn.pack(pady=30)

    def sort_column(self, col_name):
        self.sort_states[col_name] = not self.sort_states[col_name]
        if self.df[col_name].dtype == 'object':
            temp = self.df[col_name].astype(str).str.replace('%', '').replace('N/A', '0')
            try:
                num = pd.to_numeric(temp)
                self.df = self.df.iloc[num.sort_values(ascending=self.sort_states[col_name]).index]
            except: self.df = self.df.sort_values(by=col_name, ascending=self.sort_states[col_name])
        else: self.df = self.df.sort_values(by=col_name, ascending=self.sort_states[col_name])
        self.render_table()

    def render_table(self):
        for widget in self.table_container.winfo_children(): widget.destroy()
        h_frame = ctk.CTkFrame(self.table_container, fg_color="#333333", corner_radius=0)
        h_frame.pack(fill="x", pady=(0, 5))
        for i, col in enumerate(self.columns):
            btn = ctk.CTkButton(h_frame, text=f"{col.upper()} ↕", font=("Consolas", 14, "bold"), width=180, fg_color="transparent", command=lambda c=col: self.sort_column(c))
            btn.grid(row=0, column=i, padx=5, pady=10)
        for idx, (_, row) in enumerate(self.df.iterrows()):
            r_color = "#2b2b2b" if idx % 2 == 0 else "#1a1a1a"
            r_frame = ctk.CTkFrame(self.table_container, fg_color=r_color, corner_radius=0)
            r_frame.pack(fill="x")
            for i, col in enumerate(self.columns):
                ctk.CTkLabel(r_frame, text=str(row[col]), font=("Consolas", 14), width=180).grid(row=0, column=i, padx=5, pady=10)

    def auto_save_report(self):
        # Setup Directory relative to current script
        report_dir = os.path.join(os.getcwd(), "Reports")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H-%M-%S")
        filename = f"{self.strategy_name} {timestamp}.txt"
        full_path = os.path.join(report_dir, filename)

        try:
            with open(full_path, 'w') as f:
                f.write("="*75 + "\n")
                f.write(f"VAULT v76.9 INSTITUTIONAL REPORT | {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*75 + "\n")
                f.write(f"STRATEGY: {self.strategy_name}\n")
                f.write(f"TOTAL FINDINGS: {self.hit_count}\n")
                f.write("-" * 75 + "\n\n")

                col_widths = {col: max(self.df[col].astype(str).map(len).max(), len(col)) + 6 for col in self.columns}
                header = "".join([col.upper().ljust(col_widths[col]) for col in self.columns])
                f.write(header + "\n" + "-" * len(header) + "\n")

                for _, row in self.df.iterrows():
                    line = "".join([str(row[col]).ljust(col_widths[col]) for col in self.columns])
                    f.write(line + "\n")

            os.startfile(full_path) # Automatically opens in Notepad
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save file: {e}")

# --- Main Command Center ---
class VaultCommandCenter(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Institutional Vault v76.9")
        self.geometry("650x600")
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_API_SECRET')
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.trading_client = TradingClient(self.api_key, self.secret_key)
        ctk.set_appearance_mode("Dark")
        
        ctk.CTkLabel(self, text="INSTITUTIONAL STRATEGY VAULT", font=("Consolas", 24, "bold")).pack(pady=30)
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(padx=30, pady=10, fill="both", expand=True)
        
        # Strategy List (Consolidated Names)
        strategies = [
            "Momentum Buy", "Long Term Momentum", "Trapped Shorts", 
            "Trapped Longs", "Retest Long", "H2 Pullback", 
            "Bull Coil", "Bear Coil"
        ]
        
        for i, strat in enumerate(strategies):
            btn = ctk.CTkButton(self.button_frame, text=strat, height=65, width=260, font=("Consolas", 15, "bold"), command=lambda s=strat: self.execute_strategy(s))
            btn.grid(row=i//2, column=i%2, padx=15, pady=15)
            
        self.status = ctk.CTkLabel(self, text="SYSTEM READY", font=("Consolas", 12))
        self.status.pack(pady=20)

    def execute_strategy(self, strat):
        self.status.configure(text=f"SCANNING: {strat.upper()}...", text_color="yellow"); self.update()
        try:
            assets = self.trading_client.get_all_assets(GetAssetsRequest(status='active', asset_class='us_equity'))
            tickers = [a.symbol for a in assets if a.tradable and a.marginable][:250]
            findings = []
            bars = self.data_client.get_stock_bars(StockBarsRequest(symbol_or_symbols=tickers, timeframe=TimeFrame.Day, start=datetime.now()-timedelta(days=450))).df.reset_index()
            for symbol in tickers:
                df = bars[bars['symbol'] == symbol].copy()
                if len(df) < 252: continue
                df['8sma'], df['20sma'], df['50sma'], df['200sma'], df['252sma'] = df['close'].rolling(8).mean(), df['close'].rolling(20).mean(), df['close'].rolling(50).mean(), df['close'].rolling(200).mean(), df['close'].rolling(252).mean()
                df['hi20'], df['lo20'], df['hi252'] = df['high'].shift(1).rolling(20).max(), df['low'].shift(1).rolling(20).min(), df['high'].shift(1).rolling(252).max()
                curr = df.iloc[-1]
                
                # Logic Block
                if strat == "Momentum Buy":
                    dist = abs(curr['close'] - curr['8sma']) / curr['8sma']
                    if curr['close'] > curr['hi20'] and dist <= 0.04: findings.append({'Symbol': symbol, 'Trigger': round(curr['hi20'], 2), 'Price': round(curr['close'], 2), 'Dist_8MA': f'{dist:.2%}'})
                elif strat == "Bull Coil":
                    smas = [curr['8sma'], curr['20sma'], curr['200sma']]; tightness = (max(smas) - min(smas)) / min(smas)
                    if (curr['close'] > curr['8sma'] > curr['20sma'] > curr['200sma']) and tightness <= 0.05: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})
                elif strat == "Bear Coil":
                    smas = [curr['8sma'], curr['20sma'], curr['200sma']]; tightness = (max(smas) - min(smas)) / min(smas)
                    if (curr['close'] < curr['8sma'] < curr['20sma'] < curr['200sma']) and tightness <= 0.05: findings.append({'Symbol': symbol, 'Price': round(curr['close'], 2), 'Tightness': f'{tightness:.2%}'})
                elif strat == "Long Term Momentum":
                    slope = (curr['50sma'] - df.iloc[-5]['50sma']) / df.iloc[-5]['50sma']
                    if curr['close'] > curr['252sma'] and slope > 0: findings.append({'Symbol': symbol, '252SMA': round(curr['252sma'], 2), 'Price': round(curr['close'], 2), 'Slope': f'{slope:.2%}'})
                elif strat == "Retest Long":
                    if (df.iloc[-5:]['hi252'].max() == curr['hi252']) and (curr['low'] <= curr['20sma']) and (curr['close'] > curr['20sma']): findings.append({'Symbol': symbol, '20SMA': round(curr['20sma'], 2), 'Price': round(curr['close'], 2), 'Status': 'Bounce'})
                elif strat == "Trapped Shorts":
                    if curr['low'] < curr['lo20'] and curr['close'] > curr['lo20']: findings.append({'Symbol': symbol, '20D_Low': round(curr['lo20'], 2), 'Price': round(curr['close'], 2), 'Action': 'Reclaim'})
            
            if findings: ResultsWindow(strat, findings, list(findings[0].keys()))
            else: messagebox.showinfo("Vault Scan", f"No {strat} setups found.")
        except Exception as e: messagebox.showerror("Error", f"Scan Failed: {str(e)}")
        self.status.configure(text="SYSTEM READY", text_color="white")

if __name__ == "__main__":
    VaultCommandCenter().mainloop()