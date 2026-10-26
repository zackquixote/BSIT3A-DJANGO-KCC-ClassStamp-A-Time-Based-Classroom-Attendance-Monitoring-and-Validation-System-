/* KCC ClassStamp — Student: Offline Badge Issuer (S-07) */
(function (window) {
  'use strict';

  var countdownTimer = null;

  function getEl(id) { return document.getElementById(id); }

  function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || '';
  }

  function toast(type, message) {
    if (typeof window.toast === 'function') { window.toast(type, message); return; }
    if (window.App && typeof window.App.toast === 'function') { window.App.toast(type, message); }
  }

  function startCountdown(expiresAtIso) {
    if (countdownTimer) clearInterval(countdownTimer);
    var expiryEl = getEl('offlineBadgeExpiry');

    function tick() {
      var target = new Date(expiresAtIso).getTime();
      var diff = target - Date.now();
      if (diff <= 0) {
        clearInterval(countdownTimer);
        if (expiryEl) expiryEl.textContent = 'Badge expired — generate a new one.';
        var img = getEl('offlineQrImage');
        if (img) img.style.filter = 'grayscale(1) opacity(0.5)';
        return;
      }
      var hours = Math.floor(diff / 3600000);
      var mins = Math.floor((diff % 3600000) / 60000);
      if (expiryEl) {
        expiryEl.textContent = 'Valid for ' + hours + 'h ' + (mins < 10 ? '0' : '') + mins + 'm — expires ' +
          new Date(expiresAtIso).toLocaleString();
      }
    }
    tick();
    countdownTimer = setInterval(tick, 30000);
  }

  function issueOfflineBadge(url) {
    var btn = getEl('offlineBadgeIssueBtn');
    var errEl = getEl('offlineBadgeError');
    var resultEl = getEl('offlineBadgeResult');
    if (btn) btn.disabled = true;
    if (errEl) errEl.textContent = '';

    fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCSRF()
      }
    })
    .then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    })
    .then(function (result) {
      if (btn) btn.disabled = false;
      if (!result.data.ok) {
        throw new Error(result.data.error || 'Unable to issue offline badge.');
      }
      var img = getEl('offlineQrImage');
      if (img) {
        img.src = result.data.qr_data_uri;
        img.style.filter = '';
      }
      if (resultEl) resultEl.style.display = 'block';
      startCountdown(result.data.expires_at);
      toast('success', 'Offline badge issued — valid for 48 hours, single use.');
    })
    .catch(function (err) {
      if (btn) btn.disabled = false;
      var message = err && err.message ? err.message : 'Network error while issuing badge.';
      if (errEl) errEl.textContent = message;
      if (err && err.message) toast('error', message);
    });
  }

  function init() {
    var root = getEl('qrBadgeRoot');
    var btn = getEl('offlineBadgeIssueBtn');
    if (!root || !btn) return;

    var url = root.getAttribute('data-offline-url');
    btn.addEventListener('click', function () {
      issueOfflineBadge(url);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
