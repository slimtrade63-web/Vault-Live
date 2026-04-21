from pytickersymbols import PyTickerSymbols
import re

def get_full_universe():
    stock_data = PyTickerSymbols()
    sp500 = list(stock_data.get_sp_500_nyc_yahoo_tickers())
    nasdaq = list(stock_data.get_nasdaq_100_nyc_yahoo_tickers())
    russell = [s['symbol'] for s in stock_data.get_stocks_by_index('Russell 2000')][:500]
    full_list = list(set(sp500 + nasdaq + russell))
    # Filter out invalid symbols - keep only standard stock tickers
    full_list = [s for s in full_list if re.match(r'^[A-Z]{1,5}$', s)]
    return sorted(full_list)