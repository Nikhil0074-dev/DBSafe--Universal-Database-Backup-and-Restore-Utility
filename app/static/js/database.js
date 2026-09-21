document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id);
  if ($('db-list')) initList(); else if ($('db-form')) initForm();

  /* ---- list page ---- */
  async function initList() {
    const body = $('db-list');
    async function load() {
      try {
        const d = await DBSafe.api('/api/databases');
        body.innerHTML = d.items.length ? d.items.map(c => `<tr data-id="${c.id}">
          <td>${DBSafe.esc(c.name)}</td><td>${DBSafe.esc(c.database_type)}</td>
          <td>${c.host ? DBSafe.esc(c.host + ':' + c.port) : '<span class="text-muted">local file</span>'}</td>
          <td class="truncate" title="${DBSafe.esc(c.database_name)}">${DBSafe.esc(c.database_name)}</td>
          <td class="status-cell"><span class="badge bg-secondary">not tested</span></td>
          <td class="text-end text-nowrap">
            <button class="btn btn-sm btn-outline-secondary" data-act="test">Test</button>
            ${DBSafe.isAdmin() ? `<a class="btn btn-sm btn-outline-secondary" href="/databases/${c.id}/edit">Edit</a>
            <button class="btn btn-sm btn-outline-danger" data-act="delete">Delete</button>` : ''}
          </td></tr>`).join('')
          : '<tr><td colspan="6" class="text-muted">No databases yet.</td></tr>';
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
    }
    body.addEventListener('click', async ev => {
      const btn = ev.target.closest('button[data-act]');
      if (!btn) return;
      const row = btn.closest('tr'); const id = row.dataset.id;
      if (btn.dataset.act === 'test') {
        const cell = row.querySelector('.status-cell');
        cell.innerHTML = '<span class="badge bg-warning text-dark">testing…</span>';
        try {
          const r = await DBSafe.api(`/api/databases/${id}/test`, {method: 'POST', body: {}});
          cell.innerHTML = r.ok ? '<span class="badge bg-success">Connected</span>'
            : `<span class="badge bg-danger" title="${DBSafe.esc(r.message)}">Disconnected</span>`;
          DBSafe.toast(r.ok ? `Connection successful (${r.server || ''})` : 'Connection failed: ' + r.message, r.ok ? 'success' : 'danger');
        } catch (e) { cell.innerHTML = '<span class="badge bg-danger">error</span>'; DBSafe.toast(e.message, 'danger'); }
      } else if (btn.dataset.act === 'delete') {
        if (!confirm('Delete this connection and its schedules? Existing backups are kept.')) return;
        try { await DBSafe.api('/api/databases/' + id, {method: 'DELETE'}); DBSafe.toast('Connection deleted', 'success'); load(); }
        catch (e) { DBSafe.toast(e.message, 'danger'); }
      }
    });
    load();
  }

  /* ---- add / edit form ---- */
  async function initForm() {
    const editId = $('db-form').dataset.connectionId;
    const ports = {mysql: 3306, postgresql: 5432, mongodb: 27017};
    function syncType() {
      const t = $('f-type').value, sqlite = t === 'sqlite';
      $('server-fields').hidden = sqlite;
      $('auth-source-field').hidden = t !== 'mongodb';
      $('sqlite-hint').classList.toggle('d-none', !sqlite);
      $('db-label').textContent = sqlite ? 'Database file path' : 'Database';
      if (!editId && ports[t]) $('f-port').value = ports[t];
    }
    $('f-type').addEventListener('change', syncType);

    if (editId) {
      $('pw-hint').classList.remove('d-none');
      try {
        const c = await DBSafe.api('/api/databases/' + editId);
        $('f-name').value = c.name; $('f-type').value = c.database_type;
        $('f-host').value = c.host || 'localhost'; $('f-port').value = c.port || '';
        $('f-username').value = c.username || ''; $('f-database').value = c.database_name;
        $('f-auth').value = (c.extra && c.extra.auth_source) || '';
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
    }
    syncType();

    function payload() {
      const p = {name: $('f-name').value, database_type: $('f-type').value, database_name: $('f-database').value};
      if (p.database_type !== 'sqlite') {
        p.host = $('f-host').value; p.port = $('f-port').value; p.username = $('f-username').value;
        p.password = $('f-password').value;
        if (p.database_type === 'mongodb' && $('f-auth').value) p.extra = {auth_source: $('f-auth').value};
      }
      return p;
    }

    $('test-btn').addEventListener('click', async () => {
      const box = $('test-result');
      box.className = 'alert alert-secondary'; box.textContent = 'Testing…';
      try {
        const body = payload(); if (editId) body.connection_id = Number(editId);
        const r = await DBSafe.api('/api/databases/test', {method: 'POST', body});
        box.className = 'alert alert-' + (r.ok ? 'success' : 'danger');
        box.textContent = r.ok ? `✓ Connection successful — ${r.server || ''} ${r.database ? '· ' + r.database : ''}`
          : `✗ Connection failed — ${r.message}`;
      } catch (e) { box.className = 'alert alert-danger'; box.textContent = e.message; }
    });

    $('save-btn').addEventListener('click', async () => {
      try {
        await DBSafe.api(editId ? '/api/databases/' + editId : '/api/databases',
          {method: editId ? 'PUT' : 'POST', body: payload()});
        location.href = '/databases';
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
    });
  }
});
