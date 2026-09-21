/* Shared helpers for all DBSafe pages. */
(function () {
  const body = document.body;
  const DBSafe = window.DBSafe = {
    role: body.dataset.role || '',
    username: body.dataset.username || '',
    csrf: body.dataset.csrf || '',
    isAdmin() { return this.role === 'admin'; },
  };

  DBSafe.esc = function (value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, c =>
      ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  };

  DBSafe.api = async function (path, opts) {
    opts = opts || {};
    const method = (opts.method || 'GET').toUpperCase();
    const headers = {'Accept': 'application/json'};
    const init = {method, headers, credentials: 'same-origin'};
    if (opts.body !== undefined && opts.body !== null) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    if (method !== 'GET') headers['X-CSRF-Token'] = DBSafe.csrf;
    const res = await fetch(path, init);
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (res.status === 401 && !location.pathname.startsWith('/login') && path !== '/api/auth/login') {
      location.href = '/login';
      throw new Error('Session expired. Please sign in again.');
    }
    if (!res.ok) throw new Error((data && data.error) || ('Request failed (' + res.status + ')'));
    return data;
  };

  DBSafe.toast = function (message, type) {
    const box = document.getElementById('toasts');
    if (!box) return;
    const el = document.createElement('div');
    el.className = 'alert alert-' + (type || 'info') + ' alert-dismissible';
    el.textContent = message;
    const close = document.createElement('button');
    close.type = 'button'; close.className = 'btn-close';
    close.addEventListener('click', () => el.remove());
    el.appendChild(close);
    box.appendChild(el);
    setTimeout(() => el.remove(), 6000);
  };

  DBSafe.fmtBytes = function (n) {
    n = Number(n) || 0;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)) + ' ' + units[i];
  };

  DBSafe.badge = function (status) {
    const map = {success: 'success', valid: 'success', ok: 'success', failed: 'danger', invalid: 'danger',
      running: 'warning text-dark', missing: 'secondary', not_verified: 'secondary', skipped: 'secondary'};
    const label = String(status || '').replace('_', ' ');
    return '<span class="badge bg-' + (map[status] || 'secondary') + '">' + DBSafe.esc(label) + '</span>';
  };

  /* Poll url until isDone(data) is true. Resolves with the final data. */
  DBSafe.waitFor = async function (url, isDone, intervalMs, maxMs) {
    const start = Date.now();
    for (;;) {
      const data = await DBSafe.api(url);
      if (isDone(data)) return data;
      if (Date.now() - start > (maxMs || 6 * 3600 * 1000)) throw new Error('Timed out waiting for the operation');
      await new Promise(r => setTimeout(r, intervalMs || 1500));
    }
  };

  const logout = document.getElementById('logout-btn');
  if (logout) logout.addEventListener('click', async () => {
    try { await DBSafe.api('/api/auth/logout', {method: 'POST', body: {}}); } catch (e) { /* ignore */ }
    location.href = '/login';
  });
})();
