"""
Classification heuristique du stade de cycle de vie d'une valeur BRVM.

Aucun compte de résultat détaillé (chiffre d'affaires, résultat net) n'est
disponible gratuitement et de façon fiable pour la BRVM : la classification
s'appuie donc uniquement sur des signaux réellement observables sur
sikafinance.com (variation du cours sur 1 an / 3 ans / 5 ans, historique de
dividendes). C'est une estimation indicative, pas un diagnostic financier :
elle est toujours renvoyée avec les signaux qui l'ont produite et un niveau
de confiance, pour rester transparente plutôt que de donner une fausse
impression de précision.
"""

from __future__ import annotations

STAGES = ["DEMARRAGE", "CROISSANCE", "MATURITE", "DECLIN", "INDETERMINE"]


def _variation(variations: dict, label: str) -> float | None:
    entry = variations.get(label)
    return entry.get("change_percent") if entry else None


def _dividend_trend(dividends: list[dict]) -> str | None:
    """'hausse' / 'stable' / 'baisse' sur les dividendes les plus récents, ou None."""
    amounts = [d["amount"] for d in dividends if d.get("amount") is not None]
    if len(amounts) < 2:
        return None
    # dividends est trié du plus récent au plus ancien sur la page source
    recent, older = amounts[0], amounts[-1]
    if older == 0:
        return None
    change = (recent - older) / older
    if change > 0.05:
        return "hausse"
    if change < -0.05:
        return "baisse"
    return "stable"


def classify(quote: dict) -> dict:
    """
    quote: dictionnaire renvoyé par SikaFinanceProvider.get_quote (clés
    'variations' et 'dividends' utilisées ici).
    Retourne {stage, confidence, signals, rationale}.
    """
    variations = quote.get("variations", {}) or {}
    dividends = quote.get("dividends", []) or []

    var_1an = _variation(variations, "1 an")
    var_3ans = _variation(variations, "3 ans")
    var_5ans = _variation(variations, "5 ans")
    div_trend = _dividend_trend(dividends)
    div_yield = dividends[0]["yield_percent"] if dividends and dividends[0].get("yield_percent") is not None else None

    signals = {
        "variation_1_an_pct": var_1an,
        "variation_3_ans_pct": var_3ans,
        "variation_5_ans_pct": var_5ans,
        "tendance_dividende": div_trend,
        "rendement_dividende_pct": div_yield,
    }

    if var_3ans is None and var_5ans is None:
        return {
            "stage": "INDETERMINE",
            "confidence": "faible",
            "signals": signals,
            "rationale": "Historique de variation insuffisant (valeur récemment cotée ou données indisponibles).",
        }

    reference_variation = var_3ans if var_3ans is not None else var_5ans

    if reference_variation is not None and reference_variation < -15 and (var_1an or 0) < 0:
        return {
            "stage": "DECLIN",
            "confidence": "moyenne",
            "signals": signals,
            "rationale": "Cours en baisse marquée sur 3-5 ans, tendance toujours négative sur la dernière année.",
        }

    if reference_variation is not None and reference_variation > 40:
        return {
            "stage": "CROISSANCE",
            "confidence": "moyenne",
            "signals": signals,
            "rationale": "Forte appréciation du cours sur 3-5 ans (>40%), signe d'une dynamique de croissance.",
        }

    if div_yield is not None and div_yield >= 5 and div_trend in ("stable", "hausse"):
        return {
            "stage": "MATURITE",
            "confidence": "moyenne" if div_trend == "stable" else "faible",
            "signals": signals,
            "rationale": "Rendement de dividende élevé et stable/en hausse, cours sans forte tendance directionnelle.",
        }

    if reference_variation is not None and -15 <= reference_variation <= 40:
        return {
            "stage": "MATURITE",
            "confidence": "faible",
            "signals": signals,
            "rationale": "Variation de cours modérée sur 3-5 ans, sans signal de dividende déterminant.",
        }

    return {
        "stage": "INDETERMINE",
        "confidence": "faible",
        "signals": signals,
        "rationale": "Signaux insuffisants ou contradictoires pour trancher entre les stades.",
    }
