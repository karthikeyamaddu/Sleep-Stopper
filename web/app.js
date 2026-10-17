// State
let isRunning = false;
let currentInterval = 60;
let nextPingIn = 60;

// DOM Elements - Header & Global
const globalStatusBadge = document.getElementById('global-status-badge');
const statusBadgeText = document.getElementById('status-badge-text');
const powerSourceBadge = document.getElementById('power-source-badge');
const powerSourceText = document.getElementById('power-source-text');

// Controls
const radarRing = document.getElementById('radar-ring');
const countdownDisplay = document.getElementById('countdown-display');
const countdownSub = document.getElementById('countdown-sub');
const intervalInput = document.getElementById('interval-input');
const intervalHint = document.getElementById('interval-hint');
const toggleBtn = document.getElementById('toggle-btn');
const btnIcon = document.getElementById('btn-icon');
const btnText = document.getElementById('btn-text');
const clearHistoryBtn = document.getElementById('clear-history-btn');

// Safe Mode Toggles
const togglePowerApi = document.getElementById('toggle-power-api');
const toggleF15 = document.getElementById('toggle-f15');
const toggleMouse = document.getElementById('toggle-mouse');

// Current Session Live (Resets on Stop)
const statCurrentDuration = document.getElementById('stat-current-duration');
const statCurrentStatusNote = document.getElementById('stat-current-status-note');
const statCurrentPings = document.getElementById('stat-current-pings');
const statLastPing = document.getElementById('stat-last-ping');

// Background Lifetime Usage
const statLifetimeTime = document.getElementById('stat-lifetime-time');
const statHistoryCount = document.getElementById('stat-history-count');
const statLifetimePings = document.getElementById('stat-lifetime-pings');

// History Table
const historyBadge = document.getElementById('history-badge');
const historyTable = document.getElementById('history-table');
const historyTableBody = document.getElementById('history-table-body');
const emptyHistoryState = document.getElementById('empty-history-state');

// Resource Monitors
const meterProcCpu = document.getElementById('meter-proc-cpu');
const barProcCpu = document.getElementById('bar-proc-cpu');
const meterProcRam = document.getElementById('meter-proc-ram');
const barProcRam = document.getElementById('bar-proc-ram');
const meterSysCpu = document.getElementById('meter-sys-cpu');
const barSysCpu = document.getElementById('bar-sys-cpu');
const meterSysRam = document.getElementById('meter-sys-ram');
const barSysRam = document.getElementById('bar-sys-ram');

// Logs
const logsFeed = document.getElementById('logs-feed');

// Duration Formatter (HH:MM:SS)
function formatDuration(totalSeconds) {
  const sec = Math.floor(totalSeconds || 0);
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function formatShortDuration(totalSeconds) {
  const sec = Math.floor(totalSeconds || 0);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

// Preset Buttons
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const sec = parseInt(btn.dataset.sec, 10);
    intervalInput.value = sec;
    intervalHint.textContent = `Triggers every ${sec}s`;
  });
});

intervalInput.addEventListener('input', () => {
  const val = parseInt(intervalInput.value, 10) || 60;
  intervalHint.textContent = `Triggers every ${val}s`;
  document.querySelectorAll('.preset-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.sec, 10) === val);
  });
});

// Render Archived History Table
function renderHistory(historyList) {
  if (!historyList || historyList.length === 0) {
    historyTable.style.display = 'none';
    emptyHistoryState.style.display = 'block';
    historyBadge.textContent = '0 Archived';
    return;
  }

  historyTable.style.display = 'table';
  emptyHistoryState.style.display = 'none';
  historyBadge.textContent = `${historyList.length} Archived`;

  historyTableBody.innerHTML = historyList
    .map(
      item => `
      <tr>
        <td><span class="session-tag">#${item.id}</span></td>
        <td>${escapeHtml(item.date || '')}</td>
        <td>${escapeHtml(item.start_time || '')}</td>
        <td>${escapeHtml(item.stop_time || '')}</td>
        <td><span class="dur-tag">${formatShortDuration(item.duration_seconds)}</span></td>
        <td>${item.pings}</td>
        <td>${item.interval}s</td>
      </tr>`
    )
    .join('');
}

// UI Updater from backend response
function updateUI(status) {
  isRunning = status.running;
  currentInterval = status.interval;
  nextPingIn = status.next_ping_in;

  // Active / Idle State
  if (isRunning) {
    globalStatusBadge.classList.add('active');
    statusBadgeText.textContent = 'ACTIVE • KEEP-AWAKE ON';
    radarRing.classList.add('active');
    toggleBtn.classList.add('active');
    btnIcon.textContent = '⏹';
    btnText.textContent = 'STOP & ARCHIVE SESSION';
    countdownDisplay.innerHTML = `${nextPingIn}<span class="unit">s</span>`;
    countdownSub.textContent = `Pinging every ${currentInterval}s`;

    statCurrentDuration.textContent = formatDuration(status.current_session_seconds);
    statCurrentStatusNote.textContent = `Active • Started at ping #${status.current_session_pings}`;
    statCurrentStatusNote.style.color = '#10b981';
  } else {
    globalStatusBadge.classList.remove('active');
    statusBadgeText.textContent = 'IDLE / STOPPED';
    radarRing.classList.remove('active');
    toggleBtn.classList.remove('active');
    btnIcon.textContent = '▶';
    btnText.textContent = 'START SLEEP STOPPER';
    countdownDisplay.innerHTML = `${intervalInput.value}<span class="unit">s</span>`;
    countdownSub.textContent = 'Engine on standby';

    // On STOP: Current session stats are initial / zero
    statCurrentDuration.textContent = '00:00:00';
    statCurrentStatusNote.textContent = 'Status: Stopped (Reset to 0)';
    statCurrentStatusNote.style.color = '#94a3b8';
  }

  // Current session pings (0 when stopped)
  statCurrentPings.textContent = status.current_session_pings;
  statLastPing.textContent = status.last_ping_time ? `Last: ${status.last_ping_time}` : 'Last: None';

  // Lifetime Background Usage (keeps accumulating)
  statLifetimeTime.textContent = formatDuration(status.lifetime_active_seconds);
  statHistoryCount.textContent = status.completed_sessions_count;
  statLifetimePings.textContent = `Total Pings: ${status.lifetime_pings}`;

  // Session History List
  renderHistory(status.history);

  // Resource Usage (Baseline Benchmark for Phase 2)
  const procCpu = status.process_cpu_percent || 0;
  meterProcCpu.textContent = `${procCpu.toFixed(2)}%`;
  barProcCpu.style.width = `${Math.min(100, Math.max(2, procCpu * 15))}%`;

  const procRam = status.process_memory_mb || 0;
  meterProcRam.textContent = `${procRam.toFixed(1)} MB`;
  barProcRam.style.width = `${Math.min(100, Math.max(5, (procRam / 150) * 100))}%`;

  const sysCpu = status.system_cpu_percent || 0;
  meterSysCpu.textContent = `${sysCpu.toFixed(1)}%`;
  barSysCpu.style.width = `${Math.min(100, sysCpu)}%`;

  const sysRam = status.system_memory_percent || 0;
  meterSysRam.textContent = `${sysRam.toFixed(1)}%`;
  barSysRam.style.width = `${Math.min(100, sysRam)}%`;

  // Battery & Power info
  if (status.battery) {
    if (status.battery.power_plugged) {
      powerSourceBadge.style.color = '#10b981';
      powerSourceText.textContent = `AC Plugged (${status.battery.percent}%)`;
    } else {
      powerSourceBadge.style.color = '#f59e0b';
      powerSourceText.textContent = `Battery (${status.battery.percent}%)`;
    }
  } else {
    powerSourceText.textContent = 'AC Powered';
  }

  // Activity Logs
  if (status.logs && Array.isArray(status.logs)) {
    const wasAtBottom = logsFeed.scrollHeight - logsFeed.scrollTop <= logsFeed.clientHeight + 20;
    logsFeed.innerHTML = status.logs
      .map(
        l => `
      <div class="log-entry ${l.level || 'info'}">
        <span class="log-time">[${l.time}]</span>
        <span class="log-msg">${escapeHtml(l.message)}</span>
      </div>`
      )
      .join('');
    if (wasAtBottom) {
      logsFeed.scrollTop = logsFeed.scrollHeight;
    }
  }
}

function escapeHtml(str) {
  return String(str).replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

// Fetch Status from Backend
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      updateUI(data);
    }
  } catch (err) {
    statusBadgeText.textContent = 'DISCONNECTED';
    globalStatusBadge.classList.remove('active');
  }
}

// Toggle Start / Stop
async function handleToggle() {
  toggleBtn.disabled = true;
  try {
    if (!isRunning) {
      const interval = parseInt(intervalInput.value, 10) || 60;
      const res = await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          interval: interval,
          use_mouse: toggleMouse.checked,
          use_f15: toggleF15.checked,
          use_power_api: togglePowerApi.checked
        })
      });
      const data = await res.json();
      if (data.status) updateUI(data.status);
    } else {
      const res = await fetch('/api/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (data.status) updateUI(data.status);
    }
  } catch (err) {
    console.error('Action failed:', err);
  } finally {
    toggleBtn.disabled = false;
  }
}

toggleBtn.addEventListener('click', handleToggle);

// Clear History Button
clearHistoryBtn.addEventListener('click', async () => {
  if (confirm('Clear all session history records and reset lifetime usage counters?')) {
    try {
      const res = await fetch('/api/clear_history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (data.status) updateUI(data.status);
    } catch (err) {
      console.error('Clear history failed:', err);
    }
  }
});

// Real-time Poll Loop
fetchStatus();
setInterval(fetchStatus, 1000);
