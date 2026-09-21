document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id);
  let backups = [], connections = [];

  async function init() {
    try {
      const [b, c] = await Promise.all([
        DBSafe.api('/api/backups?status=success&per_page=200&sort=created_at&order=desc'),
        DBSafe.api('/api/databases')]);
      backups = b.items; connections = c.items;
      $('r-backup').innerHTML = backups.length ? backups.map(x =>
        `<option value="${x.id}">${DBSafe.esc(x.backup_id)} — ${DBSafe.esc(x.connection_name || x.database_name)} — ${DBSafe.esc(x.created_at)} (${DBSafe.esc(x.stored_size_human)})</option>`).join('')
        : '<option value="">No successful backups</option>';
      const wanted = new URLSearchParams(location.search).get('backup');
      if (wanted && backups.some(x => String(x.id) === wanted)) $('r-backup').value = wanted;
      onBackupChange();
    } catch (e) { DBSafe.toast(e.message, 'danger'); }
    loadHistory();
  }

  function currentBackup() { return backups.find(x => String(x.id) === $('r-backup').value); }

  function onBackupChange() {
    const b = currentBackup();
    if (!b) { $('r-info').textContent = ''; $('r-connection').innerHTML = ''; return; }
    $('r-info').innerHTML = `Type: ${DBSafe.esc(b.database_type)} · ${b.encryption_enabled ? '🔒 encrypted · ' : ''}${DBSafe.esc(b.compression_type)} · integrity: ${DBSafe.badge(b.verification_status)}`;
    const compatible = connections.filter(c => c.database_type === b.database_type);
    $('r-connection').innerHTML = compatible.length ? compatible.map(c =>
      `<option value="${c.id}" ${c.id === b.connection_id ? 'selected' : ''}>${DBSafe.esc(c.name)}</option>`).join('')
      : '<option value="">No compatible connection</option>';
    onConnectionChange();
  }

  function onConnectionChange() {
    const c = connections.find(x => String(x.id) === $('r-connection').value);
    $('r-target').value = c ? c.database_name : '';
  }

  async function restore() {
    const b = currentBackup();
    if (!b || !$('r-connection').value) return DBSafe.toast('Choose a backup and a target connection', 'warning');
    if (!$('r-confirm').checked) return DBSafe.toast('Please confirm the restore', 'warning');
    $('r-btn').disabled = true;
    $('r-result').innerHTML = '<div class="alert alert-secondary">Restore running…</div>';
    try {
      const started = await DBSafe.api('/api/restore', {method: 'POST', body: {
        backup_id: b.id, connection_id: Number($('r-connection').value),
        target_database: $('r-target').value.trim(), safety_backup: $('r-safety').checked, confirm: true}});
      const done = await DBSafe.waitFor('/api/restores/' + started.id, r => r.status !== 'running', 1000);
      const steps = ((done.verification_result || {}).steps || []).map(s =>
        `<li>${DBSafe.badge(s.status)} ${DBSafe.esc(s.step)}${s.detail ? ' — <span class="text-muted">' + DBSafe.esc(s.detail) + '</span>' : ''}</li>`).join('');
      $('r-result').innerHTML = `<div class="alert alert-${done.status === 'success' ? 'success' : 'danger'}">
        <strong>${done.status === 'success' ? 'Restore completed' : 'Restore failed'}</strong>
        ${done.error_message ? '<div>' + DBSafe.esc(done.error_message) + '</div>' : ''}
        ${done.safety_backup_code ? '<div>Safety backup: ' + DBSafe.esc(done.safety_backup_code) + '</div>' : ''}
        <ul class="mb-0 mt-2 list-unstyled">${steps}</ul></div>`;
      $('r-confirm').checked = false;
    } catch (e) { $('r-result').innerHTML = `<div class="alert alert-danger">${DBSafe.esc(e.message)}</div>`; }
    $('r-btn').disabled = false;
    loadHistory();
  }

  async function loadHistory() {
    try {
      const d = await DBSafe.api('/api/restores');
      $('r-history').innerHTML = d.items.length ? d.items.map(r => `<tr><td>${r.id}</td>
        <td>${DBSafe.esc(r.backup_code || '')}</td><td class="truncate" title="${DBSafe.esc(r.target_database)}">${DBSafe.esc(r.target_database)}</td>
        <td class="text-nowrap">${DBSafe.esc(r.started_at)}</td><td>${r.duration_seconds}s</td>
        <td>${DBSafe.esc(r.safety_backup_code || '–')}</td><td>${DBSafe.badge(r.status)}</td>
        <td class="small">${DBSafe.esc(r.error_message || '')}</td></tr>`).join('')
        : '<tr><td colspan="8" class="text-muted">No restores yet.</td></tr>';
    } catch (e) { DBSafe.toast(e.message, 'danger'); }
  }

  $('r-backup').addEventListener('change', onBackupChange);
  $('r-connection').addEventListener('change', onConnectionChange);
  $('r-btn').addEventListener('click', restore);
  init();
});
