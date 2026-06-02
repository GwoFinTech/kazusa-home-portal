/* ── kazusa home portal — shared utilities ── */
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function apiFetch(url, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET' && window.csrfToken) {
    opts.headers = { ...(opts.headers || {}), 'X-CSRF-Token': window.csrfToken };
  }
  return fetch(url, opts);
}
