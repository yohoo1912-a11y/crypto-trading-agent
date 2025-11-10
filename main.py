# main.py
import os
import time
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from strategy.sma import SMAStrategy
from exchangers.ccxt_client import ExchangeManager
import httpx
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

MODE = os.getenv("MODE", "paper")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MAX_POSITION_USD = float(os.getenv("MAX_POSITION_USD", "5000"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "5"))

app = FastAPI(title="Crypto Trading Agent")

# control flags
control = {"running": True, "killed": False, "last_error": None, "start_time": time.time()}

exchange_manager = ExchangeManager(mode=MODE, supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)

strategy = SMAStrategy(exchange_manager=exchange_manager, symbol="BTC/USDT", timeframe="1m")

class TradeRequest(BaseModel):
    symbol: str
    side: str
    amount: float

class ControlRequest(BaseModel):
    action: str

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(strategy_loop())

async def strategy_loop():
    while True:
        try:
            if control["killed"]:
                logger.info("Strategy killed. Sleeping 60s.")
                await asyncio.sleep(60)
                continue
            if control["running"]:
                await strategy.run_once()
            await asyncio.sleep(60)  # run every minute
        except Exception as e:
            logger.exception("Error in strategy loop")
            control["last_error"] = str(e)
            await asyncio.sleep(5)

@app.get("/status")
async def status():
    return {
        "uptime": int(time.time() - control["start_time"]),
        "mode": MODE,
        "connected_exchanges": list(exchange_manager.connected()),
        "last_error": control["last_error"],
    }

@app.get("/positions")
async def get_positions():
    return exchange_manager.list_positions()

@app.get("/pnl")
async def get_pnl():
    # crude: return last 24h P&L aggregated from trades table via supabase if configured
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"error": "SUPABASE not configured", "realized": 0, "unrealized": 0}
    q = f"{SUPABASE_URL}/rest/v1/trades?select=price,amount,side,timestamp&order=timestamp.desc&limit=1000"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(q, headers=headers)
        if r.status_code != 200:
            return {"error": "failed to query supabase", "status_code": r.status_code}
        trades = r.json()
    # naive P&L calc (for demo): sum sells - buys
    realized = 0.0
    for t in trades:
        if t["side"] == "sell":
            realized += float(t["price"]) * float(t["amount"])
        else:
            realized -= float(t["price"]) * float(t["amount"])
    return {"realized": realized, "unrealized": 0}

@app.post("/trade")
async def manual_trade(req: TradeRequest):
    if control["killed"]:
        raise HTTPException(status_code=400, detail="Trading is killed")
    if MODE == "live" and (not os.getenv("EXCHANGE_BINANCE_KEY") and not os.getenv("EXCHANGE_COINBASE_KEY")):
        raise HTTPException(status_code=400, detail="No exchange keys configured for live mode")
    # simple exposure check
    if MAX_POSITION_USD and req.amount * 1 > MAX_POSITION_USD:
        raise HTTPException(status_code=400, detail="Amount exceeds MAX_POSITION_USD")
    res = await exchange_manager.create_order(symbol=req.symbol, side=req.side, amount=req.amount)
    return res

@app.post("/control")
async def control_action(req: ControlRequest):
    a = req.action.lower()
    if a == "pause":
        control["running"] = False
    elif a == "resume":
        control["running"] = True
    elif a == "kill":
        control["killed"] = True
        control["running"] = False
    else:
        raise HTTPException(status_code=400, detail="Unknown action")
    return {"running": control["running"], "killed": control["killed"]}
