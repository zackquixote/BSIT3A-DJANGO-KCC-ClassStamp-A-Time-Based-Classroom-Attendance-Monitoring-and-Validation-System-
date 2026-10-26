// ==============================================================================
// KCC CLASSSTAMP - STUDENT ROTATING QR BADGE CONTROLLER
// ==============================================================================
// Fetches the current TOTP token/QR image from the server, counts down the
// 30-second validity window, and refreshes automatically. Server renders the
// PNG so no client-side QR library is required.
// ==============================================================================
(function () {
  'use strict';

  var root = document.getElementById('qrBadgeRoot');
  if (!root) return;

  var tokenUrl = root.getAttribute('data-token-url');
  var img = document.getElementById('qrImage');
  var loading = document.getElementById('qrLoading');
  var countdownEl = document.getElementById('qrCountdown');
  var progressEl = document.getElementById('qrProgress');
  var statusEl = document.getElementById('qrStatus');
  var refreshBtn = document.getElementById('qrRefreshBtn');

  var interval = 30;
  var remaining = 0;
  var fetching = false;
  var lastPayload = null;

  function render() {
    if (countdownEl) {
      countdownEl.textContent = remaining > 0 ? remaining + 's' : '—';
    }
    if (progressEl) {
      var pct = interval > 0 ? Math.max(0, Math.min(100, (remaining / interval) * 100)) : 0;
      progressEl.style.width = pct + '%';
    }
  }

  function showError(message) {
    if (statusEl) statusEl.textContent = message;
    if (loading) {
      loading.style.display = 'flex';
      loading.innerHTML = '';
      var icon = document.createElement('i');
      icon.className = 'fas fa-triangle-exclamation';
      loading.appendChild(icon);
      loading.appendChild(document.createTextNode(' ' + message));
    }
  }

  function loadToken(force) {
    if (fetching) return;
    fetching = true;
    fetch(tokenUrl, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
      cache: 'no-store'
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          throw new Error(result.data.error || 'Unable to load QR badge.');
        }
        var data = result.data;
        if (data.qr_data_uri && (force || data.payload !== lastPayload)) {
          img.src = data.qr_data_uri;
          lastPayload = data.payload;
          if (loading) loading.style.display = 'none';
        }
        interval = data.interval || 30;
        remaining = (data.seconds_remaining != null) ? data.seconds_remaining : interval;
        if (statusEl) statusEl.textContent = 'Synced ' + (data.server_time || '');
        render();
      })
      .catch(function (err) {
        showError(err.message || 'Badge unavailable');
      })
      .then(function () {
        fetching = false;
      });
  }

  function tick() {
    if (remaining > 0) remaining -= 1;
    render();
    if (remaining <= 0) loadToken(true);
  }

  setInterval(tick, 1000);

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) loadToken(true);
  });

  if (refreshBtn) {
    refreshBtn.addEventListener('click', function () { loadToken(true); });
  }

  loadToken(true);
})();
