#!/usr/bin/env python3
"""
Snapshot quotidien : récupère le cours du jour de chaque valeur BRVM et
l'ajoute à l'archive locale (SQLite). Destiné à être lancé une fois par jour
ouvré via une tâche planifiée (cron / Planificateur de tâches Windows), pour
que l'historique réellement disponible grandisse au fil du temps, en plus de
ce que l'export CSV de sikafinance.com peut déjà fournir rétroactivement.

Usage: python scripts/collect_daily.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from providers.sika_provider import SikaFinanceProvider  # noqa: E402
from storage import history_store  # noqa: E402


def main() -> None:
    provider = SikaFinanceProvider()
    today = date.today().isoformat()
    total = 0
    failures = []

    for company in provider.get_companies():
        symbol = company["symbol"]
        quote = provider.get_quote(symbol)
        if quote is None or quote.get("price") is None:
            failures.append(symbol)
            continue

        row = {
            "symbol": symbol,
            "date": today,
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("price"),
            "volume": quote.get("volume"),
        }
        history_store.upsert_prices(symbol, [row])
        total += 1

    print(f"[{today}] {total} valeurs enregistrées, {len(failures)} échec(s).")
    if failures:
        print("Échecs:", ", ".join(failures))


if __name__ == "__main__":
    main()
