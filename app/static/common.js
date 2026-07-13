/* ── kazusa home portal — shared utilities ── */
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function apiFetch(url, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET' && window.csrfToken) {
    opts.headers = { ...(opts.headers || {}), 'X-CSRF-Token': window.csrfToken };
  }
  return fetch(url, opts);
}

/* Lucide is loaded before this file on every static page. Keep dynamic icons
   declarative so re-rendered content remains consistent with the static UI. */
function icon(name, className = '', label = '') {
  const safeName = String(name).replace(/[^a-z0-9-]/g, '');
  const safeClass = String(className).replace(/[^a-z0-9_ -]/g, '');
  const accessible = label ? `role="img" aria-label="${esc(label)}"` : 'aria-hidden="true"';
  return `<i data-lucide="${safeName}" class="lucide-icon ${safeClass}" ${accessible}></i>`;
}
function refreshIcons() {
  window.lucide?.createIcons();
}

/* ── Theme toggle (3-state: auto → light → dark → auto) ── */
(function() {
  const ICONS = { auto: 'monitor', light: 'sun', dark: 'moon' };
  const TITLES = { auto: '跟随系统', light: '浅色模式', dark: '深色模式' };
  const ORDER = ['auto', 'light', 'dark'];

  function applyTheme(value) {
    const root = document.documentElement;
    if (value === 'auto') {
      root.removeAttribute('data-theme');
      localStorage.removeItem('theme');
    } else {
      root.setAttribute('data-theme', value);
      localStorage.setItem('theme', value);
    }
    // Update meta theme-color
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      const isDark = value === 'dark' || (value === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      meta.setAttribute('content', isDark ? '#0a0a0a' : '#fafafa');
    }
  }

  function currentTheme() {
    return localStorage.getItem('theme') || 'auto';
  }

  function createToggle() {
    const btn = document.createElement('button');
    btn.className = 'theme-toggle';
    btn.onclick = function() {
      const cur = currentTheme();
      const next = ORDER[(ORDER.indexOf(cur) + 1) % ORDER.length];
      applyTheme(next);
      btn.innerHTML = icon(ICONS[next]);
      refreshIcons();
      btn.title = TITLES[next];
    };
    const cur = currentTheme();
    btn.innerHTML = icon(ICONS[cur]);
    btn.title = TITLES[cur];
    document.body.appendChild(btn);
    refreshIcons();

    // Update button when system preference changes (only matters in auto mode)
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (currentTheme() === 'auto') {
        applyTheme('auto');
        btn.textContent = ICONS.auto;
        btn.title = TITLES.auto;
      }
    });
  }

  // Apply stored theme immediately
  applyTheme(currentTheme());

  // Create toggle button when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createToggle);
  } else {
    createToggle();
  }
})();
