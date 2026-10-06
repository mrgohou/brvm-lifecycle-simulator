const STAGE_LABELS = {
  DEMARRAGE: "Démarrage",
  CROISSANCE: "Croissance",
  MATURITE: "Maturité",
  DECLIN: "Déclin",
  INDETERMINE: "Indéterminé",
};

const STAGE_CLASSES = {
  DEMARRAGE: "stage-demarrage",
  CROISSANCE: "stage-croissance",
  MATURITE: "stage-maturite",
  DECLIN: "stage-declin",
  INDETERMINE: "stage-indetermine",
};

let currentSymbol = null;
let liveTimer = null;
let priceChart = null;

const el = (id) => document.getElementById(id);

function fmtFCFA(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value) + " FCFA";
}

function fmtPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function showError(message) {
  const panel = el("errorPanel");
  panel.textContent = message;
  panel.hidden = false;
}

function clearError() {
  el("errorPanel").hidden = true;
  el("errorPanel").textContent = "";
}

function setPeriodFromDays(days) {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - days);
  el("startDate").value = start.toISOString().slice(0, 10);
  el("endDate").value = end.toISOString().slice(0, 10);
}

async function loadCompanies() {
  const { data } = await Api.getCompanies();
  const select = el("symbolSelect");
  select.innerHTML = "";
  data
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((company) => {
      const option = document.createElement("option");
      option.value = company.symbol;
      option.textContent = `${company.name} (${company.symbol})`;
      select.appendChild(option);
    });
  if (data.length > 0) {
    currentSymbol = data.find((c) => c.symbol === "SNTS.sn")?.symbol || data[0].symbol;
    select.value = currentSymbol;
  }
}

async function refreshLiveQuote() {
  if (!currentSymbol) return;
  try {
    const [quote, lifecycle] = await Promise.all([
      Api.getQuote(currentSymbol),
      Api.getLifecycle(currentSymbol),
    ]);

    el("companyName").textContent = quote.name || currentSymbol;
    el("currentPrice").textContent = fmtFCFA(quote.price);

    const changeEl = el("currentChange");
    changeEl.textContent = fmtPercent(quote.change_percent);
    changeEl.className = "change " + (quote.change_percent >= 0 ? "up" : "down");

    el("freshnessNote").textContent =
      `Source : ${quote.source} — cours différé ~15 min. Dernière actualisation : ${new Date().toLocaleTimeString("fr-FR")}`;

    const badge = el("lifecycleBadge");
    badge.textContent = STAGE_LABELS[lifecycle.stage] || lifecycle.stage;
    badge.className = "badge " + (STAGE_CLASSES[lifecycle.stage] || "");

    el("lifecycleRationale").textContent = lifecycle.rationale || "";

    clearError();
  } catch (err) {
    showError(`Impossible de récupérer le cours en direct : ${err.message}`);
  }
}

function renderChart(history) {
  const ctx = el("priceChart").getContext("2d");
  const labels = history.map((h) => h.date);
  const closes = history.map((h) => h.close);

  if (priceChart) {
    priceChart.destroy();
  }
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Cours de clôture (FCFA)",
          data: closes,
          borderColor: "#1d6f42",
          backgroundColor: "rgba(29, 111, 66, 0.08)",
          fill: true,
          tension: 0.15,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { maxTicksLimit: 10 } },
        y: { beginAtZero: false },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderResult(result) {
  const { period_result: p } = result;
  const grid = el("resultGrid");
  grid.innerHTML = "";

  const rows = [
    ["Date de début", p.start_date],
    ["Date de fin", p.end_date],
    ["Prix initial", fmtFCFA(p.initial_price)],
    ["Prix final", fmtFCFA(p.final_price)],
    ["Montant investi", fmtFCFA(p.initial_amount)],
    ["Dividendes perçus", fmtFCFA(p.dividends_received)],
    ["Valeur finale", fmtFCFA(p.final_value)],
    ["Gain / Perte", fmtFCFA(p.net_gain_or_loss)],
    ["Performance sur la période", fmtPercent(p.performance_percent)],
    ["Performance annualisée", p.annualized_percent !== null ? fmtPercent(p.annualized_percent) : "—"],
  ];

  rows.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "result-item";
    item.innerHTML = `<span class="label">${label}</span><span class="value">${value}</span>`;
    grid.appendChild(item);
  });

  el("resultPanel").hidden = false;
}

async function runSimulation() {
  clearError();
  const symbol = el("symbolSelect").value;
  const start = el("startDate").value;
  const end = el("endDate").value;
  const amount = parseFloat(el("amountInput").value);
  const includeDividends = el("includeDividends").checked;

  if (!start || !end) {
    showError("Choisissez une date de début et une date de fin.");
    return;
  }

  currentSymbol = symbol;
  el("runButton").disabled = true;
  el("runButton").textContent = "Calcul en cours…";

  try {
    const [history, simulation] = await Promise.all([
      Api.getHistory(symbol, start, end),
      Api.simulate(symbol, start, end, amount, includeDividends),
    ]);

    if (history.data.length < 2) {
      showError(
        "Historique insuffisant sur cette période pour cette valeur (source sikafinance.com limitée)."
      );
    } else {
      renderChart(history.data);
    }
    renderResult(simulation);
    await refreshLiveQuote();
  } catch (err) {
    showError(err.message);
  } finally {
    el("runButton").disabled = false;
    el("runButton").textContent = "Calculer la rentabilité";
  }
}

function initPeriodPresets() {
  const buttons = Array.from(el("periodPresets").querySelectorAll("button"));
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      setPeriodFromDays(parseInt(button.dataset.days, 10));
    });
  });
}

async function init() {
  initPeriodPresets();
  setPeriodFromDays(365);

  try {
    await loadCompanies();
  } catch (err) {
    showError(`Impossible de charger la liste des valeurs : ${err.message}`);
    return;
  }

  el("symbolSelect").addEventListener("change", (e) => {
    currentSymbol = e.target.value;
    refreshLiveQuote();
  });
  el("runButton").addEventListener("click", runSimulation);

  await refreshLiveQuote();
  liveTimer = setInterval(refreshLiveQuote, 45000);
}

document.addEventListener("DOMContentLoaded", init);
