"""Archive locale (SQLite) des cours BRVM collectés, pour limiter les appels
réseau et faire grandir l'historique réellement disponible au fil du temps."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.sqlite3"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    return conn


def upsert_prices(symbol: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = _connect()
    with conn:
        conn.executemany(
            """
            INSERT INTO prices (symbol, date, open, high, low, close, volume)
            VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
            ON CONFLICT(symbol, date) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
            """,
            rows,
        )
    conn.close()
    return len(rows)


def get_cached_range(symbol: str, start_date: str, end_date: str) -> list[dict]:
    conn = _connect()
    cur = conn.execute(
        """
        SELECT date, open, high, low, close, volume FROM prices
        WHERE symbol = ? AND date BETWEEN ? AND ?
        ORDER BY date ASC
        """,
        (symbol, start_date, end_date),
    )
    rows = [
        {"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]}
        for r in cur.fetchall()
    ]
    conn.close()
    return rows


def get_cached_dates(symbol: str, start_date: str, end_date: str) -> set[str]:
    return {r["date"] for r in get_cached_range(symbol, start_date, end_date)}
