"""Calcul de rentabilité sur une période définie par l'utilisateur."""

from __future__ import annotations

from datetime import date, datetime


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def compute_performance(
    history: list[dict],
    start_date: str,
    end_date: str,
    initial_amount: float,
    dividends: list[dict] | None = None,
    include_dividends: bool = True,
) -> dict:
    """
    history: liste de {date: 'YYYY-MM-DD', close: float, ...} triée par date croissante.
    dividends: liste de {year: str, amount: float, yield_percent: float}, optionnel.

    Si l'historique ne couvre pas la période demandée, l'erreur est explicite
    plutôt que de renvoyer un résultat calculé sur une période différente en silence.
    """
    if not history:
        raise ValueError("Aucune donnée historique disponible pour cette valeur.")

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start >= end:
        raise ValueError("La date de début doit être antérieure à la date de fin.")

    in_range = [h for h in history if start.isoformat() <= h["date"] <= end.isoformat()]
    if len(in_range) < 2:
        raise ValueError(
            "Historique insuffisant sur la période demandée "
            f"({len(in_range)} point(s) trouvé(s) entre {start_date} et {end_date})."
        )

    first_point = in_range[0]
    last_point = in_range[-1]
    initial_price = first_point["close"]
    final_price = last_point["close"]

    if not initial_price or initial_price <= 0:
        raise ValueError("Prix de départ invalide ou nul sur la période demandée.")

    shares_bought = initial_amount / initial_price

    dividends_received = 0.0
    if include_dividends and dividends:
        years_in_range = {d["date"][:4] if "date" in d else None for d in in_range}
        for div in dividends:
            div_year = str(div.get("year", ""))
            if div_year in years_in_range and div.get("amount"):
                dividends_received += div["amount"] * shares_bought

    gross_value = shares_bought * final_price
    final_value = gross_value + dividends_received
    net_gain_or_loss = final_value - initial_amount
    performance_percent = (net_gain_or_loss / initial_amount) * 100

    days = (end - start).days or 1
    years = days / 365.25
    if years > 0 and (final_value / initial_amount) > 0:
        annualized_percent = ((final_value / initial_amount) ** (1 / years) - 1) * 100
    else:
        annualized_percent = None

    return {
        "start_date": first_point["date"],
        "end_date": last_point["date"],
        "initial_amount": initial_amount,
        "initial_price": initial_price,
        "final_price": final_price,
        "shares_bought": shares_bought,
        "dividends_received": dividends_received,
        "final_value": final_value,
        "net_gain_or_loss": net_gain_or_loss,
        "performance_percent": performance_percent,
        "annualized_percent": annualized_percent,
        "points_used": len(in_range),
    }


def instant_performance(quote: dict) -> dict:
    """Rentabilité 'instantanée' = variation du jour à partir d'une cotation."""
    return {
        "symbol": quote.get("symbol"),
        "price": quote.get("price"),
        "change_percent": quote.get("change_percent"),
        "as_of": quote.get("source"),
        "freshness": quote.get("freshness"),
    }
