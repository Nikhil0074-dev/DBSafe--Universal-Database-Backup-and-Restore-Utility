document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id);

  function syncFrequency() {
    const f = $('s-frequency') && $('s-frequency').value;
    if (!f) return;
    $('s-dow-box').classList.toggle('d-none', f !== 'weekly');
    $('s-dom-box').classList.toggle('d-none', f !== 'monthly');
    $('s-cron-box').classList.toggle('d-none', f !== 'custom');
    $('s-time').disabled = f === 'custom';
  }

  async function loadConnections() {
    if (!$('s-connection')) return;
    try {
      const d = await DBSafe.api('/api/databases');
      $('s-connection').innerHTML = d.items.map(c => `<option value="${c.id}">${DBSafe.esc(c.name)}</option>`).join('')
        || '<option value="">No databases configured</option>';
    } catch (e) { DBSafe.toast(e.message, 'danger'); }
  }

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  function describe(s) {
    switch (s.frequency) {
      case 'hourly': return 'Hourly at :' + s.schedule_time.split(':')[1];
      case 'every_6_hours': return 'Every 6 hours at :' + s.schedule_time.split(':')[1];
      case 'daily': return 'Daily at ' + s.schedule_time;
      case 'weekly': return `Weekly ${days[s.day_of_week]} ${s.schedule_time}`;
      case 'monthly': return `Monthly day ${s.day_of_month} at ${s.schedule_time}`;
      default: return 'Cron: ' + s.cron_expression;
    }
  }
  function retention(s) {
    const parts = [];
    if (s.retention_days) parts.push(s.retention_days + ' d');
    if (s.keep_daily) parts.push(s.keep_daily + ' daily');
    if (s.keep_weekly) parts.push(s.keep_weekly + ' weekly');
    if (s.keep_monthly) parts.push(s.keep_monthly + ' monthly');
    return parts.join(' + ') || 'keep all';
  }

  async function load() {
    try {
      const d = await DBSafe.api('/api/schedules');
      const admin = DBSafe.isAdmin();
      $('s-list').innerHTML = d.items.length ? d.items.map(s => `<tr>
        <td>${DBSafe.esc(s.connection_name || '(deleted)')}</td><td>${DBSafe.esc(describe(s))}</td>
        <td class="small">${DBSafe.esc(s.backup_type)} · ${DBSafe.esc(s.compression)}${s.encryption ? ' · 🔒' : ''}</td>
        <td class="small">${DBSafe.esc(retention(s))}</td>
        <td class="text-nowrap small">${DBSafe.esc(s.next_run || '–')}</td>
        <td class="small">${s.last_run_at ? DBSafe.esc(s.last_run_at) + ' ' + DBSafe.badge(s.last_status) : '–'}</td>
        <td>${s.enabled ? '<span class="badge bg-success">on</span>' : '<span class="badge bg-secondary">off</span>'}</td>
        <td class="text-end text-nowrap">${admin ? `
          <button class="btn btn-sm btn-outline-secondary" data-act="run" data-id="${s.id}">Run now</button>
          <button class="btn btn-sm btn-outline-secondary" data-act="toggle" data-id="${s.id}" data-enabled="${s.enabled ? 1 : 0}">${s.enabled ? 'Disable' : 'Enable'}</button>
          <button class="btn btn-sm btn-outline-danger" data-act="delete" data-id="${s.id}">Delete</button>` : ''}</td></tr>`).join('')
        : '<tr><td colspan="8" class="text-muted">No schedules yet.</td></tr>';
    } catch (e) { DBSafe.toast(e.message, 'danger'); }
  }

  async function create() {
    const num = id => Number($(id).value || 0);
    const body = {connection_id: Number($('s-connection').value), frequency: $('s-frequency').value,
      schedule_time: $('s-time').value || '02:00', day_of_week: num('s-dow'), day_of_month: num('s-dom') || 1,
      cron_expression: $('s-cron').value.trim() || null, compression: $('s-compression').value,
      retention_days: num('s-retention'), keep_daily: num('s-daily'), keep_weekly: num('s-weekly'),
      keep_monthly: num('s-monthly'), encryption: $('s-encrypt').checked, verify: $('s-verify').checked};
    try { await DBSafe.api('/api/schedules', {method: 'POST', body}); DBSafe.toast('Schedule created', 'success'); load(); }
    catch (e) { DBSafe.toast(e.message, 'danger'); }
  }

  $('s-list').addEventListener('click', async ev => {
    const b = ev.target.closest('button[data-act]');
    if (!b) return;
    const id = b.dataset.id;
    try {
      if (b.dataset.act === 'run') { await DBSafe.api(`/api/schedules/${id}/run`, {method: 'POST', body: {}}); DBSafe.toast('Backup started — see Backups', 'info'); }
      else if (b.dataset.act === 'toggle') { await DBSafe.api('/api/schedules/' + id, {method: 'PUT', body: {enabled: b.dataset.enabled !== '1'}}); load(); }
      else if (b.dataset.act === 'delete') { if (!confirm('Delete this schedule?')) return; await DBSafe.api('/api/schedules/' + id, {method: 'DELETE'}); load(); }
    } catch (e) { DBSafe.toast(e.message, 'danger'); }
  });

  if ($('s-create')) {
    $('s-frequency').addEventListener('change', syncFrequency);
    $('s-create').addEventListener('click', create);
    syncFrequency();
  }
  loadConnections(); load();
});
