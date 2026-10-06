"""API du simulateur d'évaluation d'action BRVM (cycle de vie + rentabilité)."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from lifecycle.classifier import classify
from providers.sika_provider import SikaFinanceProvider
from simulation.engine import compute_performance, instant_performance
from storage import history_store

app = FastAPI(title="Simulateur BRVM — Cycle de vie & Rentabilité")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

provider = SikaFinanceProvider()

# Cache mémoire très simple pour éviter de re-scraper à chaque appel rapproché.
_quote_cache: dict[str, tuple[float, dict]] = {}
QUOTE_TTL_SECONDS = 60


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Date invalide (attendu YYYY-MM-DD): {value}") from exc


def get_history_with_cache(symbol: str, start: date, end: date) -> list[dict]:
    start_s, end_s = start.isoformat(), end.isoformat()
    cached = history_store.get_cached_range(symbol, start_s, end_s)
    margin = timedelta(days=5)
    covers_start = bool(cached) and _parse_date(cached[0]["date"]) <= start + margin
    covers_end = bool(cached) and _parse_date(cached[-1]["date"]) >= end - margin
    if cached and covers_start and covers_end:
        return cached

    fresh_rows = provider.get_history(symbol, start, end)
    for row in fresh_rows:
        row["symbol"] = symbol
    history_store.upsert_prices(symbol, fresh_rows)
    return history_store.get_cached_range(symbol, start_s, end_s)


def get_quote_cached(symbol: str) -> dict:
    now = time.time()
    cached = _quote_cache.get(symbol)
    if cached and (now - cached[0]) < QUOTE_TTL_SECONDS:
        return cached[1]

    quote = provider.get_quote(symbol)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Valeur inconnue ou page indisponible: {symbol}")
    _quote_cache[symbol] = (now, quote)
    return quote


@app.get("/api/companies")
def api_companies():
    return {"count": len(provider.get_companies()), "data": provider.get_companies()}


@app.get("/api/quote/{symbol}")
def api_quote(symbol: str):
    return get_quote_cached(symbol)


@app.get("/api/lifecycle/{symbol}")
def api_lifecycle(symbol: str):
    quote = get_quote_cached(symbol)
    return {"symbol": symbol, **classify(quote)}


@app.get("/api/history/{symbol}")
def api_history(
    symbol: str,
    start: str = Query(..., description="Date de début YYYY-MM-DD"),
    end: str = Query(..., description="Date de fin YYYY-MM-DD"),
):
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date >= end_date:
        raise HTTPException(status_code=400, detail="La date de début doit précéder la date de fin.")
    rows = get_history_with_cache(symbol, start_date, end_date)
    return {"symbol": symbol, "start": start, "end": end, "count": len(rows), "data": rows}


@app.get("/api/simulate/{symbol}")
def api_simulate(
    symbol: str,
    start: str = Query(...),
    end: str = Query(...),
    amount: float = Query(..., gt=0, description="Montant initial investi (FCFA)"),
    include_dividends: bool = Query(True),
):
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    history = get_history_with_cache(symbol, start_date, end_date)
    quote = get_quote_cached(symbol)

    try:
        result = compute_performance(
            history=history,
            start_date=start,
            end_date=end,
            initial_amount=amount,
            dividends=quote.get("dividends"),
            include_dividends=include_dividends,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "symbol": symbol,
        "period_result": result,
        "instant": instant_performance(quote),
    }


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
