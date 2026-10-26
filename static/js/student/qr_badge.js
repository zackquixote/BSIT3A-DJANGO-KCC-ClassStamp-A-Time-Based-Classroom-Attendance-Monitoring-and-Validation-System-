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
  var ringWrap = document.getElementById('qrRingWrap');
  var ringProgress = document.getElementById('qrRingProgress');
  var statusEl = document.getElementById('qrStatus');
  var refreshBtn = document.getElementById('qrRefreshBtn');

  var interval = 30;
  var remaining = 0;
  var fetching = false;
  var lastPayload = null;

  var RING_RADIUS = 52;
  var RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

  function render() {
    if (countdownEl) {
      countdownEl.textContent = remaining > 0 ? remaining : '—';
    }
    if (ringProgress) {
      var pct = interval > 0 ? Math.max(0, Math.min(1, remaining / interval)) : 0;
      ringProgress.style.strokeDasharray = RING_CIRCUMFERENCE.toFixed(2);
      ringProgress.style.strokeDashoffset = (RING_CIRCUMFERENCE * (1 - pct)).toFixed(2);
    }
  }

  // Pulse the ring when a fresh 30-second token cycle begins
  function pulseRing() {
    if (!ringWrap) return;
    ringWrap.classList.remove('is-pulsing');
    void ringWrap.offsetWidth; // reflow to restart the animation
    ringWrap.classList.add('is-pulsing');
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
          var rotated = lastPayload !== null && data.payload !== lastPayload;
          lastPayload = data.payload;
          if (loading) loading.style.display = 'none';
          if (rotated) pulseRing();
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
