// Simple client-side code to load alerts.json and render a list with search/filter
const DATA_PATH = 'assets/data/alerts.json';
let alerts = [];

const severityMap = {
  critical: { label: 'Critical', color: 'danger', icon: 'fa-fire' },
  high: { label: 'High', color: 'danger', icon: 'fa-triangle-exclamation' },
  error: { label: 'Error', color: 'danger', icon: 'fa-triangle-exclamation' },
  warning: { label: 'Warning', color: 'warning', icon: 'fa-triangle-exclamation' },
  info: { label: 'Info', color: 'info', icon: 'fa-info-circle' },
  low: { label: 'Low', color: 'secondary', icon: 'fa-circle-info' },
};

function fmtTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch (e) {
    return iso;
  }
}

function severityBadge(s) {
  const k = (s || 'info').toLowerCase();
  const meta = severityMap[k] || severityMap['info'];
  return `<span class="badge bg-${meta.color} badge-severity"><i class="fa-solid ${meta.icon} me-1"></i>${meta.label}</span>`;
}

function renderList(items) {
  const container = document.getElementById('alertsContainer');
  if (!items.length) {
    container.innerHTML = '<div class="text-center py-8 text-muted">No alerts match your filter.</div>';
    return;
  }

  const html = items.map(a => {
    return `
      <div class="card mb-3 alert-card">
        <div class="card-body d-flex justify-content-between align-items-start">
          <div class="me-3" style="min-width: 220px; max-width: 320px;">
            <div class="d-flex align-items-center mb-2">
              <h6 class="mb-0 me-2">${a.service}</h6>
              ${severityBadge(a.severity)}
            </div>
            <div class="small-muted">${fmtTime(a.timestamp)} • ${a.region} • ${a.host}</div>
          </div>
          <div class="flex-grow-1">
            <p class="mb-1">${a.message}</p>
            <div class="text-muted small">Fingerprint: <code>${(a.fingerprint||'—')}</code></div>
          </div>
          <div class="ms-3 text-end" style="min-width:140px;">
            <button class="btn btn-outline-primary btn-sm" onclick='showDetails(${JSON.stringify(a)})'>Details</button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = html;
}

function showDetails(a) {
  const body = `
    <div><strong>Service:</strong> ${a.service}</div>
    <div><strong>Severity:</strong> ${a.severity}</div>
    <div><strong>Time:</strong> ${fmtTime(a.timestamp)}</div>
    <div><strong>Host:</strong> ${a.host}</div>
    <div><strong>Region:</strong> ${a.region}</div>
    <div class="mt-2"><strong>Message:</strong><div class="small-muted">${a.message}</div></div>
  `;
  const modal = new bootstrap.Modal(document.createElement('div'));
  // Use a quick DOM-based modal
  const el = document.createElement('div');
  el.className = 'modal fade';
  el.tabIndex = -1;
  el.innerHTML = `
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Alert details</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          ${body}
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(el);
  const m = new bootstrap.Modal(el);
  el.addEventListener('hidden.bs.modal', () => el.remove());
  m.show();
}

function applyFilters() {
  const q = (document.getElementById('searchInput').value || '').toLowerCase().trim();
  const severity = document.getElementById('severityFilter').value;
  let filtered = alerts.slice();
  if (severity && severity !== 'all') {
    filtered = filtered.filter(a => (a.severity||'').toLowerCase() === severity);
  }
  if (q) {
    filtered = filtered.filter(a => {
      return (a.message||'').toLowerCase().includes(q) || (a.service||'').toLowerCase().includes(q) || (a.host||'').toLowerCase().includes(q);
    });
  }
  // sort by timestamp desc
  filtered.sort((a,b) => new Date(b.timestamp) - new Date(a.timestamp));
  renderList(filtered);
  document.getElementById('summary').innerText = `${filtered.length} / ${alerts.length} shown`;
}

async function loadData() {
  try {
    const resp = await fetch(DATA_PATH, {cache: 'no-store'});
    const data = await resp.json();
    // add fingerprint placeholder where missing to demonstrate
    alerts = (data.alerts || []).map(a => ({ ...a, fingerprint: a.fingerprint || '' }));
    applyFilters();
  } catch (e) {
    document.getElementById('alertsContainer').innerHTML = `<div class="alert alert-danger">Failed to load data: ${e.message}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadData();
  document.getElementById('searchInput').addEventListener('input', () => applyFilters());
  document.getElementById('severityFilter').addEventListener('change', () => applyFilters());
  document.getElementById('refreshBtn').addEventListener('click', () => loadData());
});
