/**
 * Dashboard JavaScript — Tailwind Catalyst UI + Multi-Protocol Strategy Edition
 */

// ── Auth guard ────────────────────────────────────────────────────────────────
if (!API.isLoggedIn()) {
  window.location.href = '/login/';
}

// ── State ─────────────────────────────────────────────────────────────────────
let monitors = [];
let wsConnection = null;

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadUserProfile();
  await loadMonitors();
  connectWebSocket();

  // Add monitor form submit
  const form = document.getElementById('add-monitor-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      await createMonitor();
    });
  }
});

// ── Monitor Type Change Handler ───────────────────────────────────────────────
function onMonitorTypeChange() {
  const type = document.getElementById('m-type').value;
  const urlLabel = document.getElementById('m-url-label');
  const urlInput = document.getElementById('m-url');

  document.getElementById('fields-http').style.display = (type === 'http') ? 'block' : 'none';
  document.getElementById('fields-keyword').style.display = (type === 'keyword') ? 'block' : 'none';
  document.getElementById('fields-tcp').style.display = (type === 'tcp') ? 'block' : 'none';
  document.getElementById('fields-ssl').style.display = (type === 'ssl') ? 'block' : 'none';
  document.getElementById('fields-domain').style.display = (type === 'domain') ? 'block' : 'none';

  if (type === 'tcp') {
    urlLabel.textContent = 'Hostname / IP Address';
    urlInput.placeholder = '127.0.0.1 or redis.internal.net';
  } else if (type === 'domain') {
    urlLabel.textContent = 'Domain Name';
    urlInput.placeholder = 'example.com or my-startup.io';
  } else if (type === 'ssl') {
    urlLabel.textContent = 'Domain / Hostname (HTTPS)';
    urlInput.placeholder = 'https://example.com or api.stripe.com';
  } else {
    urlLabel.textContent = 'Target Endpoint URL';
    urlInput.placeholder = 'https://api.example.com/health';
  }
}

// ── User profile ──────────────────────────────────────────────────────────────
async function loadUserProfile() {
  try {
    const user = await API.request('GET', '/auth/me/');
    const displayName = user.full_name || user.email.split('@')[0];
    const initial = (user.full_name || user.email)[0].toUpperCase();
    
    const nameEl = document.getElementById('user-name');
    const emailEl = document.getElementById('user-email');
    const avatarEl = document.getElementById('user-avatar');
    
    if (nameEl) nameEl.textContent = displayName;
    if (emailEl) emailEl.textContent = user.email;
    if (avatarEl) avatarEl.textContent = initial;
  } catch (e) {
    /* Non-critical error */
  }
}

// ── Monitors ──────────────────────────────────────────────────────────────────
async function loadMonitors() {
  const grid = document.getElementById('monitors-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="skeleton" style="height:140px;border-radius:14px"></div>'.repeat(3);

  try {
    const data = await API.monitors.list();
    monitors = data.results || data;
    renderMonitors();
    updateStats();
  } catch (e) {
    Toast.error('Failed to load monitors');
    grid.innerHTML = '<p style="color:var(--text-secondary);grid-column:1/-1;text-align:center;padding:32px">Failed to load monitors. Check server connection.</p>';
  }
}

function renderMonitors() {
  const grid = document.getElementById('monitors-grid');
  if (!grid) return;

  if (!monitors.length) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:64px 24px;border:1px dashed var(--border-strong);border-radius:var(--radius-xl);background:rgba(255,255,255,0.01)">
        <div style="width:48px;height:48px;border-radius:var(--radius-md);background:var(--card);border:1px solid var(--border);margin:0 auto 16px auto;display:flex;align-items:center;justify-content:center;color:var(--text-muted)">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/>
          </svg>
        </div>
        <div style="font-family:var(--font-display);font-size:1.1rem;font-weight:600;color:var(--text-primary);margin-bottom:6px">No monitors configured yet</div>
        <div style="font-size:0.875rem;color:var(--text-muted);max-width:380px;margin:0 auto 20px auto">Add your first endpoint, SSL cert, or TCP service to start receiving instant uptime telemetry.</div>
        <button class="btn btn-primary" onclick="openAddMonitorModal()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" x2="12" y1="5" y2="19"/><line x1="5" x2="19" y1="12" y2="12"/>
          </svg>
          Add Your First Monitor
        </button>
      </div>`;
    return;
  }

  grid.innerHTML = monitors.map(m => monitorCardHTML(m)).join('');
}

function monitorCardHTML(monitor) {
  const status = monitor.current_status || 'unknown';
  const type = monitor.monitor_type || 'http';
  const uptime = monitor.uptime_24h != null ? `${monitor.uptime_24h}%` : '100%';
  const interval = intervalLabel(monitor.interval);
  const lastCheck = monitor.last_checked_at
    ? timeAgo(new Date(monitor.last_checked_at))
    : 'Pending';

  const statusLabel = {
    'up': 'Operational',
    'down': 'Degraded',
    'paused': 'Paused',
    'unknown': 'Checking'
  }[status] || status;

  const typeLabels = {
    'http': 'HTTP(s)',
    'keyword': 'Keyword',
    'ssl': 'SSL Cert',
    'tcp': 'TCP Port',
    'domain': 'Domain'
  };
  const typeBadge = `<span style="font-size:0.65rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;padding:2px 6px;border-radius:var(--radius-sm);background:rgba(255,255,255,0.06);color:var(--text-secondary);border:1px solid var(--border)">${typeLabels[type] || type}</span>`;

  const regionFlags = {
    'eu-central': '🇪🇺 EU',
    'us-east': '🇺🇸 US',
    'ap-southeast': '🇸🇬 AP'
  };
  const configuredRegions = (monitor.regions && monitor.regions.length > 0) ? monitor.regions : ['eu-central'];
  const regionsBadges = configuredRegions.map(r => `<span style="font-size:0.65rem;padding:2px 5px;border-radius:var(--radius-sm);background:rgba(255,255,255,0.03);color:var(--text-muted);border:1px solid var(--border-subtle)">${regionFlags[r] || r}</span>`).join(' ');

  return `
    <div class="monitor-card" id="card-${monitor.id}" data-id="${monitor.id}">
      <div class="monitor-header">
        <div class="monitor-identity">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">
            <div class="monitor-name">${escHtml(monitor.name)}</div>
            ${typeBadge}
            <div style="display:flex;gap:4px">${regionsBadges}</div>
          </div>
          <a class="monitor-url" href="${type === 'tcp' ? '#' : escHtml(monitor.url)}" target="_blank" rel="noopener">
            ${escHtml(monitor.url)}${monitor.tcp_port ? `:${monitor.tcp_port}` : ''}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" x2="21" y1="14" y2="3"/>
            </svg>
          </a>
        </div>
        <span class="status-badge ${status}">
          <span class="status-dot"></span>
          ${statusLabel}
        </span>
      </div>

      <!-- Catalyst Uptime Segment Bar (24 hour blocks) -->
      <div>
        <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-muted);margin-bottom:6px">
          <span>24h telemetry</span>
          <span style="font-family:var(--font-mono);font-weight:600;color:var(--text-primary)">${uptime} uptime</span>
        </div>
        <div class="uptime-bar-container" id="uptime-bar-${monitor.id}" title="${uptime} uptime (24h)">
          ${generateUptimeSegments(status)}
        </div>
      </div>

      <!-- Monitor Meta Telemetry -->
      <div class="monitor-meta">
        <span class="meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          ${interval}
        </span>
        <span class="meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          ${lastCheck}
        </span>
        ${monitor.is_public && monitor.public_slug ? `
          <a class="meta-item" href="/status/${escHtml(monitor.public_slug)}/" target="_blank" style="color:var(--accent-hover)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="2" x2="22" y1="12" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
            Public Status
          </a>
        ` : ''}
      </div>

      <!-- Card Action Buttons -->
      <div class="monitor-actions">
        ${monitor.is_active
          ? `<button class="btn btn-secondary" style="flex:1" onclick="pauseMonitor(${monitor.id},event)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect width="4" height="16" x="6" y="4"/><rect width="4" height="16" x="14" y="4"/>
              </svg>
              Pause
            </button>`
          : `<button class="btn btn-secondary" style="flex:1" onclick="resumeMonitor(${monitor.id},event)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Resume
            </button>`}
        <button class="btn btn-danger" onclick="deleteMonitor(${monitor.id},event)" title="Delete monitor">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>
    </div>`;
}

function generateUptimeSegments(status) {
  const segmentCount = 28;
  const segments = [];
  for (let i = 0; i < segmentCount; i++) {
    const isLatest = i === segmentCount - 1;
    let cls = '';
    if (status === 'down' && isLatest) {
      cls = 'down';
    } else if (status === 'paused') {
      cls = 'no-data';
    }
    segments.push(`<div class="uptime-segment ${cls}"></div>`);
  }
  return segments.join('');
}

function updateStats() {
  const total = monitors.length;
  const up = monitors.filter(m => m.current_status === 'up').length;
  const down = monitors.filter(m => m.current_status === 'down').length;
  const uptimes = monitors.map(m => m.uptime_24h).filter(u => u != null);
  const avgUptime = uptimes.length
    ? (uptimes.reduce((a, b) => a + b, 0) / uptimes.length).toFixed(1) + '%'
    : (total > 0 ? '100%' : '—');

  const totalEl = document.getElementById('stat-total');
  const upEl = document.getElementById('stat-up');
  const downEl = document.getElementById('stat-down');
  const avgEl = document.getElementById('stat-avg-uptime');
  const badgeEl = document.getElementById('nav-badge-monitors');

  if (totalEl) totalEl.textContent = total;
  if (upEl) upEl.textContent = up;
  if (downEl) downEl.textContent = down;
  if (avgEl) avgEl.textContent = avgUptime;
  if (badgeEl) badgeEl.textContent = total;
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWebSocket() {
  const token = localStorage.getItem('access_token');
  if (!token) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/dashboard/?token=${token}`;

  wsConnection = new WebSocket(wsUrl);

  wsConnection.onopen = () => {
    setWsStatus('Real-time telemetry connected', true);
  };

  wsConnection.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'monitor_status_update') {
      updateMonitorCard(data);
    }
  };

  wsConnection.onclose = (event) => {
    setWsStatus('Telemetry disconnected', false);
    if (event.code !== 4001) {
      setTimeout(connectWebSocket, 5000);
    }
  };

  wsConnection.onerror = () => {
    setWsStatus('Telemetry connection error', false);
  };
}

function setWsStatus(text, isLive) {
  const dot = document.getElementById('ws-dot');
  const label = document.getElementById('ws-status');
  if (dot) {
    dot.className = isLive ? 'pulse-dot live' : 'pulse-dot disconnected';
  }
  if (label) {
    label.textContent = text;
  }
}

function updateMonitorCard(data) {
  const { monitor_id, status, response_time_ms, http_code, checked_at } = data;

  const monitor = monitors.find(m => m.id === monitor_id);
  if (monitor) {
    monitor.current_status = status;
    monitor.last_checked_at = checked_at;
  }

  const card = document.getElementById(`card-${monitor_id}`);
  if (!card) return;

  const badge = card.querySelector('.status-badge');
  const statusLabel = {
    'up': 'Operational',
    'down': 'Degraded',
    'paused': 'Paused',
    'unknown': 'Checking'
  }[status] || status;

  if (badge) {
    badge.className = `status-badge ${status}`;
    badge.innerHTML = `<span class="status-dot"></span> ${statusLabel}`;
  }

  card.style.borderColor = status === 'up' ? 'var(--emerald-border)' : 'var(--rose-border)';
  setTimeout(() => { card.style.borderColor = ''; }, 2000);

  updateStats();
}

// ── Monitor CRUD ──────────────────────────────────────────────────────────────
async function createMonitor() {
  const type = document.getElementById('m-type').value;
  const regionCheckboxes = document.querySelectorAll('input[name="m-region"]:checked');
  const selectedRegions = Array.from(regionCheckboxes).map(cb => cb.value);
  const quorum = parseInt(document.getElementById('m-quorum').value || 1);

  const payload = {
    name: document.getElementById('m-name').value,
    monitor_type: type,
    url: document.getElementById('m-url').value,
    method: document.getElementById('m-method').value,
    regions: selectedRegions.length > 0 ? selectedRegions : ['eu-central'],
    quorum_threshold: quorum,
    expected_status_code: parseInt(document.getElementById('m-status').value || 200),
    interval: parseInt(document.getElementById('m-interval').value),
    timeout: parseInt(document.getElementById('m-timeout').value),
    is_public: document.getElementById('m-public').checked,
  };

  if (type === 'keyword') {
    payload.keyword = document.getElementById('m-keyword').value;
    payload.keyword_should_exist = document.getElementById('m-keyword-exist').checked;
  } else if (type === 'tcp') {
    payload.tcp_port = parseInt(document.getElementById('m-port').value || 80);
  } else if (type === 'ssl') {
    payload.ssl_threshold_days = parseInt(document.getElementById('m-ssl-days').value || 14);
  } else if (type === 'domain') {
    payload.domain_threshold_days = parseInt(document.getElementById('m-domain-days').value || 30);
  }

  try {
    const monitor = await API.monitors.create(payload);
    monitors.unshift(monitor);
    renderMonitors();
    updateStats();
    closeModal('add-monitor-modal');
    Toast.success(`Monitor "${monitor.name}" created successfully.`);
    document.getElementById('add-monitor-form').reset();
    onMonitorTypeChange();
  } catch (e) {
    Toast.error(e.message || 'Failed to create monitor');
  }
}

async function pauseMonitor(id, event) {
  if (event) event.stopPropagation();
  try {
    await API.monitors.pause(id);
    const m = monitors.find(m => m.id === id);
    if (m) { m.is_active = false; m.current_status = 'paused'; }
    renderMonitors();
    Toast.info('Monitor monitoring paused.');
  } catch (e) { Toast.error(e.message); }
}

async function resumeMonitor(id, event) {
  if (event) event.stopPropagation();
  try {
    await API.monitors.resume(id);
    const m = monitors.find(m => m.id === id);
    if (m) { m.is_active = true; m.current_status = 'unknown'; }
    renderMonitors();
    Toast.success('Monitor monitoring resumed.');
  } catch (e) { Toast.error(e.message); }
}

async function deleteMonitor(id, event) {
  if (event) event.stopPropagation();
  if (!confirm('Are you sure you want to delete this monitor? Telemetry history will be erased.')) return;
  try {
    await API.monitors.delete(id);
    monitors = monitors.filter(m => m.id !== id);
    renderMonitors();
    updateStats();
    Toast.success('Monitor removed.');
  } catch (e) { Toast.error(e.message); }
}

// ── Section Switcher ──────────────────────────────────────────────────────────
function showSection(name) {
  document.querySelectorAll('[id^="section-"]').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  
  const target = document.getElementById(`section-${name}`);
  if (target) target.style.display = '';
  
  if (window.event && window.event.currentTarget) {
    window.event.currentTarget.classList.add('active');
  }
}

// ── Modals ────────────────────────────────────────────────────────────────────
function openAddMonitorModal() {
  const modal = document.getElementById('add-monitor-modal');
  if (modal) {
    modal.style.display = 'flex';
    onMonitorTypeChange();
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'none';
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function intervalLabel(seconds) {
  if (seconds < 60) return `${seconds}s interval`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m interval`;
  return `${Math.floor(seconds / 3600)}h interval`;
}

function timeAgo(date) {
  const diff = Math.floor((Date.now() - date) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function openAddChannelModal() {
  Toast.info('Notification channel webhooks and integrations coming in next release.');
}
