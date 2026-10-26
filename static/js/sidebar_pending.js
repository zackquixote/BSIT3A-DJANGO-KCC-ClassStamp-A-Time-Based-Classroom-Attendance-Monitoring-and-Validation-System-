// ==============================================================================
// KCC CLASSSTAMP - SIDEBAR LIVE COUNTER POLLER (A-05)
// ==============================================================================
// Keeps the Account Validation and Security Alerts sidebar badges fresh on
// every admin page by polling /api/admin/pending-count/ every 45 seconds.
// The admin dashboard controller already handles this via SSE + its own
// poller, so this script stands down there to avoid duplicate requests.
// ==============================================================================
(function () {
  'use strict';

  var pendingBadge = document.getElementById('sidebarPendingBadge');
  var anomalyBadge = document.getElementById('sidebarAnomalyBadge');
  if (!pendingBadge && !anomalyBadge) return;
  if (document.getElementById('admin-dashboard-boot')) return;

  var url = pendingBadge ? pendingBadge.getAttribute('data-pending-count-url') : '';
  if (!url) return;

  function applyCount(el, count) {
    if (!el) return;
    if (count > 0) {
      el.textContent = count > 99 ? '99+' : String(count);
      el.style.display = '';
    } else {
      el.style.display = 'none';
    }
  }

  function poll() {
    fetch(url, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (typeof data.pending_count === 'number') applyCount(pendingBadge, data.pending_count);
        if (typeof data.open_anomaly_count === 'number') applyCount(anomalyBadge, data.open_anomaly_count);
      })
      .catch(function () { /* silent — next tick retries */ });
  }

  poll();
  setInterval(poll, 45000);
})();
