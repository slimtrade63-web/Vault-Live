from core.regime import compute_regime, compute_sector_strength
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.universe import get_full_universe
from core.strategies import trapped_longs, trapped_shorts, momentum_buy, bull_coil, bear_coil, bull_reversion, bear_reversion, long_term_momentum
import os

app = FastAPI(title="Vault v80 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_API_SECRET")

@app.get("/")
def root():
    return {"message": "Vault API is running."}

@app.get("/scan/trapped_longs")
def run_trapped_longs():
    universe = get_full_universe()
    results = trapped_longs.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Trapped Longs", "results": results}

@app.get("/scan/trapped_shorts")
def run_trapped_shorts():
    universe = get_full_universe()
    results = trapped_shorts.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Trapped Shorts", "results": results}

@app.get("/scan/momentum_buy")
def run_momentum_buy():
    universe = get_full_universe()
    results = momentum_buy.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Momentum Buy", "results": results}
@app.get("/scan/bull_coil")
def run_bull_coil():
    universe = get_full_universe()
    results = bull_coil.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Bull Coil", "results": results}

@app.get("/scan/bear_coil")
def run_bear_coil():
    universe = get_full_universe()
    results = bear_coil.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Bear Coil", "results": results}

@app.get("/scan/bull_reversion")
def run_bull_reversion():
    universe = get_full_universe()
    results = bull_reversion.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Bull Reversion", "results": results}

@app.get("/scan/bear_reversion")
def run_bear_reversion():
    universe = get_full_universe()
    results = bear_reversion.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Bear Reversion", "results": results}

@app.get("/scan/long_term_momentum")
def run_long_term_momentum():
    universe = get_full_universe()
    results = long_term_momentum.scan(API_KEY, SECRET_KEY, universe)
    return {"strategy": "Long Term Momentum", "results": results}

@app.get("/regime")
def get_regime():
    return compute_regime(API_KEY, SECRET_KEY)

@app.get("/sectors")
def get_sectors():
    return compute_sector_strength(API_KEY, SECRET_KEY)