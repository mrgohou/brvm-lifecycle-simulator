const API_BASE = window.location.origin;

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Erreur API (${res.status})`);
  }
  return res.json();
}

const Api = {
  getCompanies: () => apiGet("/api/companies"),
  getQuote: (symbol) => apiGet(`/api/quote/${encodeURIComponent(symbol)}`),
  getLifecycle: (symbol) => apiGet(`/api/lifecycle/${encodeURIComponent(symbol)}`),
  getHistory: (symbol, start, end) =>
    apiGet(`/api/history/${encodeURIComponent(symbol)}?start=${start}&end=${end}`),
  simulate: (symbol, start, end, amount, includeDividends) =>
    apiGet(
      `/api/simulate/${encodeURIComponent(symbol)}?start=${start}&end=${end}` +
        `&amount=${amount}&include_dividends=${includeDividends}`
    ),
};
