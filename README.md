# README.md

# Crypto Trading Agent (minimal scaffold)

This repo is a minimal, runnable crypto trading agent scaffold.
It supports:
- paper mode (default) — simulated fills, safe
- live mode — uses CCXT to place orders (only if you set MODE=live and provide keys)
- FastAPI endpoints for a dashboard or frontend (Lovable)
- Supabase persistence via REST

IMPORTANT ENV VARS (exact names)
- MODE = "paper" or "live"
- SUPABASE_URL
- SUPABASE_KEY
- EXCHANGE_BINANCE_KEY
- EXCHANGE_BINANCE_SECRET
- EXCHANGE_COINBASE_KEY
- EXCHANGE_COINBASE_SECRET
- TELEGRAM_BOT_TOKEN (optional)
- TELEGRAM_CHAT_ID (optional)
- MAX_POSITION_USD (optional, default 5000)
- MAX_DAILY_LOSS_PCT (optional, default 5)

Quick start (local, paper mode)
1. Copy files into a folder.
2. Create a virtualenv, install deps:
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
3. Fill .env (copy .env.example) with MODE=paper and SUPABASE_URL/SUPABASE_KEY (you can create a free Supabase project).
4. Run:
   uvicorn main:app --host 0.0.0.0 --port 8000
5. Visit http://127.0.0.1:8000/docs for the API docs.

Deploy (Render)
- Push repo to GitHub.
- Create a Render Web Service, connect to repo.
- Set build command: pip install -r requirements.txt
- Set start command: uvicorn main:app --host 0.0.0.0 --port $PORT
- Add env vars in Render settings (use the exact names above). Start with MODE=paper.

Supabase SQL
- See db/schema.sql. Run it in Supabase SQL Editor to create trades, positions, logs, settings.

Lovable
- Use the API base URL `https://<your-render-url>` in Lovable.
- Lovable will call endpoints:
  GET /status
  GET /positions
  GET /pnl
  POST /trade
  POST /control

Safety notes
- Always use trading-only API keys with no withdrawal permissions.
- Keep MODE=paper until you confirm behavior for 48+ hours under real market conditions.
- Use MAX_POSITION_USD to cap exposure.

