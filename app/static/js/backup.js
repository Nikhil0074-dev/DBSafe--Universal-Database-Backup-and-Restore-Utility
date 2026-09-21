document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id);
  if ($('history')) initList(); else if ($('details')) initDetails();

  /* ---------------- backups list + create ---------------- */
  function initList() {
    const state = {page: 1, per: 15, total: 0};

    async function loadConnections() {
      try {
        const d = await DBSafe.api('/api/databases');
        $('b-connection').innerHTML = d.items.length
          ? d.items.map(c => `<option value="${c.id}">${DBSafe.esc(c.name)} (${DBSafe.esc(c.database_type)})</option>`).join('')
          : '<option value="">No databases configured</option>';
        loadTables();
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
    }

    async function loadTables() {
      const selective = $('b-type').value === 'selective';
      $('tables-box').classList.toggle('d-none', !selective);
      if (!selective || !$('b-connection').value) return;
      $('tables-list').textContent = 'Loading tables…';
      try {
        const d = await DBSafe.api(`/api/databases/${$('b-connection').value}/tables`);
        $('tables-list').innerHTML = d.items.length ? d.items.map(t =>
          `<div class="form-check"><label class="form-check-label"><input class="form-check-input tbl" type="checkbox" value="${DBSafe.esc(t)}" checked> ${DBSafe.esc(t)}</label></div>`).join('')
          : '<span class="text-muted">No tables found.</span>';
      } catch (e) { $('tables-list').textContent = e.message; }
    }

    async function createBackup() {
      const connection = $('b-connection').value;
      if (!connection) return DBSafe.toast('Choose a database first', 'warning');
      const body = {connection_id: Number(connection), backup_type: $('b-type').value,
        compression: $('b-compression').value, encryption: $('b-encrypt').checked, verify: $('b-verify').checked};
      if (body.backup_type === 'selective') body.tables = [...document.querySelectorAll('.tbl:checked')].map(i => i.value);
      if ($('b-destination') && $('b-destination').value.trim()) body.destination = $('b-destination').value.trim();
      $('create-btn').disabled = true; $('create-status').textContent = 'Backup running…';
      try {
        const started = await DBSafe.api('/api/backups', {method: 'POST', body});
        loadHistory();
        const done = await DBSafe.waitFor('/api/backups/' + started.id, b => b.status !== 'running', 1000);
        if (done.status === 'success') DBSafe.toast(`Backup ${done.backup_id} completed`, 'success');
        else DBSafe.toast(`Backup failed: ${done.error_message || 'unknown error'}`, 'danger');
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
      $('create-btn').disabled = false; $('create-status').textContent = '';
      loadHistory();
    }

    async function loadHistory() {
      const [sort, order] = $('h-sort').value.split(':');
      const q = new URLSearchParams({page: state.page, per_page: state.per, sort, order,
        q: $('h-search').value.trim(), status: $('h-status').value});
      try {
        const d = await DBSafe.api('/api/backups?' + q);
        state.total = d.total;
        $('history').innerHTML = d.items.length ? d.items.map(b => `<tr>
          <td><a href="/backups/${b.id}">${DBSafe.esc(b.backup_id)}</a>${b.kind !== 'manual' ? ` <span class="badge bg-info text-dark">${DBSafe.esc(b.kind)}</span>` : ''}</td>
          <td>${DBSafe.esc(b.connection_name || b.database_name)}</td>
          <td class="text-nowrap">${DBSafe.esc(b.created_at)}</td>
          <td>${b.status === 'success' ? DBSafe.esc(b.stored_size_human) : '–'}</td>
          <td class="small">${DBSafe.esc(b.backup_type)}${b.compression_enabled ? ' · ' + DBSafe.esc(b.compression_type) : ''}${b.encryption_enabled ? ' · 🔒' : ''}</td>
          <td>${DBSafe.badge(b.verification_status)}</td>
          <td>${DBSafe.badge(b.status)}${b.error_message ? `<div class="small text-danger truncate" title="${DBSafe.esc(b.error_message)}">${DBSafe.esc(b.error_message)}</div>` : ''}</td>
          <td class="text-end text-nowrap">
            <a class="btn btn-sm btn-outline-secondary" href="/backups/${b.id}">Details</a>
            ${b.status === 'success' ? `<button class="btn btn-sm btn-outline-secondary" data-act="verify" data-id="${b.id}">Verify</button>
            <a class="btn btn-sm btn-outline-primary" href="/restore?backup=${b.id}">Restore</a>` : ''}
            ${DBSafe.isAdmin() && b.status !== 'running' ? `<button class="btn btn-sm btn-outline-danger" data-act="delete" data-id="${b.id}">Delete</button>` : ''}
          </td></tr>`).join('')
          : '<tr><td colspan="8" class="text-muted">No backups found.</td></tr>';
        $('h-count').textContent = `${d.total} backup(s) · page ${state.page}`;
        $('h-prev').disabled = state.page <= 1;
        $('h-next').disabled = state.page * state.per >= d.total;
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
    }

    $('history').addEventListener('click', async ev => {
      const btn = ev.target.closest('button[data-act]');
      if (!btn) return;
      try {
        if (btn.dataset.act === 'verify') {
          const r = await DBSafe.api(`/api/backups/${btn.dataset.id}/verify`, {method: 'POST', body: {deep: true}});
          DBSafe.toast(r.message, r.status === 'valid' ? 'success' : 'danger');
          loadHistory();
        } else if (btn.dataset.act === 'delete') {
          if (!confirm('Permanently delete this backup file?')) return;
          await DBSafe.api('/api/backups/' + btn.dataset.id, {method: 'DELETE'});
          DBSafe.toast('Backup deleted', 'success'); loadHistory();
        }
      } catch (e) { DBSafe.toast(e.message, 'danger'); }
    });

    $('b-type').addEventListener('change', loadTables);
    $('b-connection').addEventListener('change', loadTables);
    $('create-btn').addEventListener('click', createBackup);
    let timer; $('h-search').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { state.page = 1; loadHistory(); }, 300); });
    $('h-status').addEventListener('change', () => { state.page = 1; loadHistory(); });
    $('h-sort').addEventListener('change', () => { state.page = 1; loadHistory(); });
    $('h-prev').addEventListener('click', () => { state.page--; loadHistory(); });
    $('h-next').addEventListener('click', () => { state.page++; loadHistory(); });
    loadConnections(); loadHistory();
  }

  /* ---------------- backup details ---------------- */
  async function initDetails() {
    const id = $('details').dataset.backupId;
    async function load() {
      try {
        const b = await DBSafe.api('/api/backups/' + id);
        $('d-title').innerHTML = `${DBSafe.esc(b.backup_id)} ${DBSafe.badge(b.status)}`;
        const rows = [
          ['Database', b.connection_name || b.database_name], ['Database name', b.database_name],
          ['Type', b.database_type], ['Backup type', b.backup_type + (b.tables.length ? ' (' + b.tables.length + ' tables)' : '')],
          ['Kind', b.kind], ['File name', b.file_name || '–'], ['Created', b.created_at + (b.created_by ? ' by ' + b.created_by : '')],
          ['Duration', b.duration_seconds + ' s'], ['Original size', b.original_size_human],
          ['Compressed size', b.compression_enabled ? `${b.compressed_size_human} (${b.compression_type}, ${b.compression_ratio}% saved)` : 'not compressed'],
          ['Stored size', b.stored_size_human], ['Encryption', b.encryption_enabled ? 'AES-256-GCM' : 'none'],
          ['SHA-256', b.checksum ? `<span class="mono">${DBSafe.esc(b.checksum)}</span>` : '–', true],
          ['Integrity', DBSafe.badge(b.verification_status) + (b.last_verified_at ? ' checked ' + DBSafe.esc(b.last_verified_at) : ''), true],
          ['Tables', b.tables.length ? DBSafe.esc(b.tables.join(', ')) : '–', true],
        ];
        if (b.error_message) rows.push(['Error', `<span class="text-danger">${DBSafe.esc(b.error_message)}</span>`, true]);
        $('d-fields').innerHTML = rows.map(r => `<dt class="col-sm-3">${DBSafe.esc(r[0])}</dt><dd class="col-sm-9">${r[2] ? r[1] : DBSafe.esc(r[1])}</dd>`).join('');
        $('d-restore').href = '/restore?backup=' + b.id;
        $('d-restore').classList.toggle('d-none', b.status !== 'success');
        $('d-verify-btn').classList.toggle('d-none', b.status !== 'success');
        $('d-deep-btn').classList.toggle('d-none', b.status !== 'success');
      } catch (e) { $('d-error').textContent = e.message; $('d-error').classList.remove('d-none'); }
    }
    async function verify(deep) {
      const box = $('d-verify');
      box.className = 'alert alert-secondary'; box.textContent = 'Verifying…';
      try {
        const r = await DBSafe.api(`/api/backups/${id}/verify`, {method: 'POST', body: {deep}});
        box.className = 'alert alert-' + (r.status === 'valid' ? 'success' : 'danger');
        box.textContent = (r.status === 'valid' ? '✓ ' : '⚠ ') + r.message;
        load();
      } catch (e) { box.className = 'alert alert-danger'; box.textContent = e.message; }
    }
    $('d-verify-btn').addEventListener('click', () => verify(false));
    $('d-deep-btn').addEventListener('click', () => verify(true));
    const del = $('d-delete');
    if (del) del.addEventListener('click', async () => {
      if (!confirm('Permanently delete this backup file?')) return;
      try { await DBSafe.api('/api/backups/' + id, {method: 'DELETE'}); location.href = '/backups'; }
      catch (e) { DBSafe.toast(e.message, 'danger'); }
    });
    load();
  }
});
