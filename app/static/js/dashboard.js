document.addEventListener('DOMContentLoaded', async () => {
  const $ = id => document.getElementById(id);
  try {
    const d = await DBSafe.api('/api/dashboard');
    $('s-databases').textContent = d.databases;
    $('s-success').textContent = d.successful_backups;
    $('s-failed').textContent = d.failed_backups;
    $('s-storage').textContent = DBSafe.fmtBytes(d.total_storage);
    $('s-scheduled').textContent = d.scheduled_backups;
    $('recent').innerHTML = d.recent.length ? d.recent.map(b => `<tr>
      <td><a href="/backups/${b.id}">${DBSafe.esc(b.backup_id)}</a></td>
      <td>${DBSafe.esc(b.connection_name || b.database_name)}</td>
      <td>${DBSafe.esc(b.created_at)}</td><td>${DBSafe.esc(b.stored_size_human)}</td>
      <td>${DBSafe.badge(b.status)}</td></tr>`).join('')
      : '<tr><td colspan="5" class="text-muted">No backups yet.</td></tr>';
  } catch (e) { DBSafe.toast(e.message, 'danger'); }
});
