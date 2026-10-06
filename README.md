# Simulateur d'évaluation d'action BRVM — Cycle de vie & Rentabilité

Simulateur web qui évalue une action cotée à la **BRVM** (Bourse Régionale des
Valeurs Mobilières, UEMOA) en fonction du **cycle de vie** de l'entreprise
(démarrage / croissance / maturité / déclin) et de sa performance réelle sur
une **période choisie par l'utilisateur**, avec un cours et une rentabilité
affichés en quasi temps réel.

## Ce que ça fait

- Cours actuel (différé ~15 min) d'une valeur BRVM, rafraîchi automatiquement.
- Classification indicative du stade de cycle de vie de l'entreprise, à partir
  de signaux réels (variation du cours sur 1/3/5 ans, tendance des dividendes)
  — jamais de chiffres inventés : si une donnée manque, le stade est
  "Indéterminé" plutôt qu'une estimation forcée.
- Simulateur de rentabilité : montant investi, période libre ou préréglée
  (1 semaine à 5 ans), avec ou sans réinvestissement des dividendes reçus.
- Graphique du cours sur la période choisie.

## D'où viennent les données

Toutes les données viennent de **sikafinance.com**, en lecture seule et sans
compte :
- `GET /marches/cotation_{SYMBOLE}` : cours du jour, variations sur périodes
  fixes, historique de dividendes.
- `POST /marches/download/{SYMBOLE}` : export CSV des cours quotidiens
  (open/high/low/close/volume), limité à 31 jours par appel côté site — le
  backend enchaîne donc plusieurs appels pour couvrir une période plus longue.

Ces appels sont mis en cache (cours : 60s en mémoire ; historique : archive
locale SQLite dans `backend/data/history.sqlite3`) pour limiter la charge sur
le site source et faire grandir l'historique réellement disponible au fil du
temps. Si une période demandée n'est pas couvrable (ancienneté de la valeur,
site source indisponible), l'application l'indique explicitement — elle ne
fabrique jamais de cours.

Usage strictement pédagogique : **ceci n'est pas un conseil d'investissement**.
Vérifiez les conditions d'utilisation de sikafinance.com avant tout usage
intensif ou commercial de ce scraper.

## Installation

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Ouvrez ensuite http://localhost:8000 — le frontend est servi directement par
le backend (pas de build JS nécessaire).

## Collecte quotidienne (optionnel)

Pour que l'archive locale grandisse même sans consultation active :

```bash
python3 scripts/collect_daily.py
```

À planifier une fois par jour ouvré (cron, Tâches planifiées Windows, etc.).

## Tests

```bash
cd backend
pip install pytest
python3 -m pytest tests/ -v
```

## Structure

```
backend/
├── app.py                     # API FastAPI + cache + service du frontend
├── providers/sika_provider.py # Scraping sikafinance.com (cotation + CSV)
├── lifecycle/classifier.py    # Classification heuristique du cycle de vie
├── simulation/engine.py       # Calcul de rentabilité sur une période
├── storage/history_store.py   # Archive locale SQLite
└── tests/                     # Tests unitaires (moteur de simulation)
frontend/                      # HTML/CSS/JS (Chart.js via CDN), pas de build
scripts/collect_daily.py       # Snapshot quotidien planifiable
```

## Limites connues

- L'historique réel par action ne remonte que jusqu'à ce que sikafinance.com
  peut effectivement fournir (export limité à 31 jours par appel) et ce que
  l'application aura elle-même archivé au fil du temps.
- La classification du cycle de vie est une heuristique basée sur le cours et
  les dividendes, pas sur un compte de résultat complet (chiffre d'affaires,
  résultat net), car ces données ne sont pas disponibles gratuitement et de
  façon fiable pour la BRVM.
- Le scraping dépend de la structure actuelle des pages sikafinance.com ; si
  le site change de structure, les sélecteurs dans `sika_provider.py` devront
  être ajustés.
