"""
Fournisseur de données BRVM basé sur sikafinance.com.

Source choisie car elle expose, sans authentification :
- une fiche par valeur avec un cours quasi temps réel (différé ~15 min)
- des variations sur périodes fixes (1 semaine / 1 mois / 1er janvier / 1 an / 3 ans / 5 ans)
- un historique de dividendes sur 5 ans
- un export CSV de l'historique quotidien (open/high/low/close/volume), limité à 31 jours par requête

Aucune donnée de marché n'est inventée ici : si une information n'est pas présente
sur la page source, la valeur correspondante reste `None` plutôt que d'être estimée.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.sikafinance.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 BRVMLifecycleSimulator/1.0"
)

# Identité des valeurs BRVM (symbole sikafinance, nom, code pays).
# Liste constituée à partir du sélecteur de valeurs de sikafinance.com (octobre 2026).
# Ce sont des informations d'identification publiques, pas des données de performance.
COMPANIES: list[dict] = [
    {"symbol": "SDSC.ci", "name": "Africa Global Logistics", "country": "CI"},
    {"symbol": "BOAB.bj", "name": "Bank Of Africa Bénin", "country": "BJ"},
    {"symbol": "BOABF.bf", "name": "Bank Of Africa Burkina Faso", "country": "BF"},
    {"symbol": "BOAC.ci", "name": "Bank Of Africa Côte d'Ivoire", "country": "CI"},
    {"symbol": "BOAM.ml", "name": "Bank Of Africa Mali", "country": "ML"},
    {"symbol": "BOAN.ne", "name": "Bank Of Africa Niger", "country": "NE"},
    {"symbol": "BOAS.sn", "name": "Bank Of Africa Sénégal", "country": "SN"},
    {"symbol": "BICB.bj", "name": "Banque Internationale pour le Commerce du Bénin", "country": "BJ"},
    {"symbol": "BNBC.ci", "name": "Bernabé", "country": "CI"},
    {"symbol": "BICC.ci", "name": "BICICI", "country": "CI"},
    {"symbol": "BBGC.ci", "name": "Bridge Bank Group Côte d'Ivoire", "country": "CI"},
    {"symbol": "CFAC.ci", "name": "CFAO CI", "country": "CI"},
    {"symbol": "CIEC.ci", "name": "CIE CI", "country": "CI"},
    {"symbol": "CBIBF.bf", "name": "Coris Bank International BF", "country": "BF"},
    {"symbol": "SEMC.ci", "name": "Crown Siem", "country": "CI"},
    {"symbol": "ECOC.ci", "name": "Ecobank CI", "country": "CI"},
    {"symbol": "SIVC.ci", "name": "Erium", "country": "CI"},
    {"symbol": "ETIT.tg", "name": "ETI TG", "country": "TG"},
    {"symbol": "FTSC.ci", "name": "Filtisac CI", "country": "CI"},
    {"symbol": "LNBB.bj", "name": "Loterie Nationale du Bénin", "country": "BJ"},
    {"symbol": "SVOC.ci", "name": "Movis CI", "country": "CI"},
    {"symbol": "NEIC.ci", "name": "NEI-CEDA CI", "country": "CI"},
    {"symbol": "NTLC.ci", "name": "Nestlé CI", "country": "CI"},
    {"symbol": "NSBC.ci", "name": "NSIA Banque", "country": "CI"},
    {"symbol": "ONTBF.bf", "name": "Onatel BF", "country": "BF"},
    {"symbol": "ORGT.tg", "name": "Oragroup Togo", "country": "TG"},
    {"symbol": "ORAC.ci", "name": "Orange CI", "country": "CI"},
    {"symbol": "PALC.ci", "name": "Palmci", "country": "CI"},
    {"symbol": "SAFC.ci", "name": "Safca CI", "country": "CI"},
    {"symbol": "SPHC.ci", "name": "SAPH CI", "country": "CI"},
    {"symbol": "ABJC.ci", "name": "Servair Abidjan CI", "country": "CI"},
    {"symbol": "STAC.ci", "name": "Setao CI", "country": "CI"},
    {"symbol": "SGBC.ci", "name": "SGBCI", "country": "CI"},
    {"symbol": "CABC.ci", "name": "Sicable CI", "country": "CI"},
    {"symbol": "SICC.ci", "name": "Sicor", "country": "CI"},
    {"symbol": "STBC.ci", "name": "Sitab", "country": "CI"},
    {"symbol": "SMBC.ci", "name": "SMB CI", "country": "CI"},
    {"symbol": "SIBC.ci", "name": "Société Ivoirienne de Banque CI", "country": "CI"},
    {"symbol": "SDCC.ci", "name": "Sodeci", "country": "CI"},
    {"symbol": "SOGC.ci", "name": "SOGB", "country": "CI"},
    {"symbol": "SLBC.ci", "name": "Solibra CI", "country": "CI"},
    {"symbol": "SNTS.sn", "name": "Sonatel", "country": "SN"},
    {"symbol": "SCRC.ci", "name": "Sucrivoire", "country": "CI"},
    {"symbol": "TTLC.ci", "name": "Total CI", "country": "CI"},
    {"symbol": "TTLS.sn", "name": "Total Sénégal", "country": "SN"},
    {"symbol": "PRSC.ci", "name": "Tractafric Motors CI", "country": "CI"},
    {"symbol": "UNLC.ci", "name": "Unilever CI", "country": "CI"},
    {"symbol": "UNXC.ci", "name": "Uniwax CI", "country": "CI"},
    {"symbol": "SHEC.ci", "name": "Vivo Energy CI", "country": "CI"},
]

_COMPANY_BY_SYMBOL = {c["symbol"]: c for c in COMPANIES}


def _parse_number(text: Optional[str]) -> Optional[float]:
    """Convertit '45 000', '1,21%', '4 500 000 MXOF' (etc.) en float, ou None."""
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace(" ", "")
    cleaned = re.sub(r"[^0-9,.\-]", "", cleaned)
    cleaned = cleaned.replace(",", ".")
    if cleaned in ("", "-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


class SikaFinanceProvider:
    """Cotations, historique et dividendes BRVM via scraping de sikafinance.com."""

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 20):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})
        self.timeout = timeout

    def get_companies(self) -> list[dict]:
        return list(COMPANIES)

    def get_company(self, symbol: str) -> Optional[dict]:
        return _COMPANY_BY_SYMBOL.get(symbol)

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Cours actuel + variations sur périodes fixes + dividendes récents."""
        url = f"{BASE_URL}/marches/cotation_{symbol}"
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        company = self.get_company(symbol)
        if company is None:
            name_el = soup.select_one("h1")
            company = {"symbol": symbol, "name": name_el.text.strip() if name_el else symbol, "country": None}

        price_el = soup.select_one(".cot1u")
        price = _parse_number(price_el.contents[0]) if price_el and price_el.contents else None

        change_el = soup.select_one(".cot1u .quote_up, .cot1u .quote_down")
        change_percent = _parse_number(change_el.text) if change_el else None
        if change_el is not None and "quote_down" in change_el.get("class", []) and change_percent is not None:
            change_percent = -abs(change_percent)

        details: dict[str, Optional[float]] = {}
        for row in soup.select(".cot1v table tr"):
            cells = row.select("td")
            if len(cells) == 2:
                label = cells[0].text.strip().lower()
                value = _parse_number(cells[1].text)
                details[label] = value

        variations: dict[str, dict] = {}
        for row in soup.select("table.tableVar tr"):
            cells = row.select("td")
            if len(cells) == 4:
                period_label = cells[0].text.strip()
                variations[period_label] = {
                    "high": _parse_number(cells[1].text),
                    "low": _parse_number(cells[2].text),
                    "change_percent": _parse_number(cells[3].text),
                }

        dividends = []
        for row in soup.select("div.section-vote table.tableVar tbody tr"):
            cells = row.select("td")
            if len(cells) == 3:
                dividends.append(
                    {
                        "year": cells[0].text.strip(),
                        "amount": _parse_number(cells[1].text),
                        "yield_percent": _parse_number(cells[2].text),
                    }
                )

        return {
            "symbol": symbol,
            "name": company["name"],
            "country": company.get("country"),
            "price": price,
            "change_percent": change_percent,
            "volume": details.get("volume (titres)"),
            "open": details.get("ouverture"),
            "high": details.get("plus haut"),
            "low": details.get("plus bas"),
            "previous_close": details.get("clôture veille"),
            "source": "sikafinance.com",
            "freshness": "delayed_15min",
            "variations": variations,
            "dividends": dividends,
        }

    def get_history(self, symbol: str, start_date: date, end_date: date) -> list[dict]:
        """Historique quotidien OHLCV via l'export CSV (fenêtres de 31 jours max)."""
        rows: list[dict] = []
        window_start = start_date
        while window_start <= end_date:
            window_end = min(window_start + timedelta(days=30), end_date)
            rows.extend(self._download_csv_window(symbol, window_start, window_end))
            window_start = window_end + timedelta(days=1)
        rows.sort(key=lambda r: r["date"])
        return rows

    def _download_csv_window(self, symbol: str, start_date: date, end_date: date) -> list[dict]:
        url = f"{BASE_URL}/marches/download/{symbol}"
        payload = {"dtFrom": start_date.isoformat(), "dtTo": end_date.isoformat()}
        resp = self.session.post(url, data=payload, timeout=self.timeout)
        if resp.status_code != 200:
            return []

        content = resp.content.decode("utf-8-sig", errors="ignore")
        if "<html" in content.lower():
            # Le site a renvoyé une page HTML au lieu d'un CSV (session expirée,
            # nom de champ de formulaire changé, etc.) : on ne fabrique pas de
            # données, on remonte une liste vide pour cette fenêtre.
            return []

        delimiter = ";" if content.count(";") > content.count(",") else ","
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        parsed: list[dict] = []
        for line in reader:
            if not line or len(line) < 6:
                continue
            try:
                day_value = self._parse_csv_date(line)
            except ValueError:
                continue  # ligne d'en-tête ou format inattendu, on l'ignore
            try:
                parsed.append(
                    {
                        "symbol": symbol,
                        "date": day_value.isoformat(),
                        "open": _parse_number(line[-5]),
                        "high": _parse_number(line[-4]),
                        "low": _parse_number(line[-3]),
                        "close": _parse_number(line[-2]),
                        "volume": _parse_number(line[-1]),
                    }
                )
            except IndexError:
                continue
        return parsed

    @staticmethod
    def _parse_csv_date(line: list[str]) -> date:
        for field in line:
            field = field.strip()
            for fmt_sep in ("/", "-"):
                if fmt_sep in field and len(field) >= 8:
                    parts = field.split(fmt_sep)
                    if len(parts) == 3:
                        try:
                            nums = [int(p) for p in parts]
                        except ValueError:
                            continue
                        if nums[0] > 31:  # YYYY-MM-DD
                            return date(nums[0], nums[1], nums[2])
                        if nums[2] > 31:  # DD/MM/YYYY
                            return date(nums[2], nums[1], nums[0])
        raise ValueError(f"Aucune date reconnaissable dans la ligne CSV: {line}")
