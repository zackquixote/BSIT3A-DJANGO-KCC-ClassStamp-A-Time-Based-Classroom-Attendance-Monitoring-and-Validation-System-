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

  // A dropped request surfaces as TypeError("Failed to fetch") and a non-JSON
  // reply as SyntaxError("Unexpected token '<'"); neither is actionable, so
  // those get the plain message while server-written errors pass through.
  function friendlyMessage(err, fallback) {
    if (err && (err.name === 'TypeError' || err.name === 'SyntaxError')) return fallback;
    return (err && err.message) || fallback;
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
      var message = friendlyMessage(err, 'Could not reach the server — check your connection and try again.');
      if (errEl) errEl.textContent = message;
      toast('error', message);
    });
  }

  // A data: URI is already in memory, so the file can be rebuilt without a
  // second network call.
  function dataUriToFile(dataUri, filename) {
    var binary = window.atob((dataUri.split(',')[1] || ''));
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) { bytes[i] = binary.charCodeAt(i); }
    return new window.File([bytes], filename, { type: 'image/png' });
  }

  function saveBadge() {
    var img = getEl('offlineQrImage');
    var hint = getEl('offlineBadgeSaveHint');
    if (!img || !img.src || img.src.indexOf('data:image') !== 0) {
      if (hint) { hint.textContent = 'Generate a badge first.'; }
      return;
    }
    var filename = 'classstamp-offline-badge.png';

    // Phones: the share sheet carries "Save image" / "Save to Photos", which is
    // the only route into the gallery on iOS (the download attribute is ignored
    // by Safari).
    if (window.navigator.canShare && window.File) {
      try {
        var file = dataUriToFile(img.src, filename);
        if (window.navigator.canShare({ files: [file] })) {
          window.navigator.share({ files: [file], title: 'KCC ClassStamp offline badge' })
            .then(function () {
              if (hint) { hint.textContent = 'Choose "Save image" in the share sheet.'; }
            })
            .catch(function () { /* cancelled — keep the badge on screen */ });
          return;
        }
      } catch (error) { /* fall through to a plain download */ }
    }

    var link = document.createElement('a');
    link.href = img.src;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    if (hint) { hint.textContent = 'Saved to Downloads — open it in Photos/Gallery.'; }
  }

  function init() {
    var root = getEl('qrBadgeRoot');
    var btn = getEl('offlineBadgeIssueBtn');
    if (!root || !btn) return;

    var url = root.getAttribute('data-offline-url');
    btn.addEventListener('click', function () {
      issueOfflineBadge(url);
    });

    var saveBtn = getEl('offlineBadgeSaveBtn');
    if (saveBtn) {
      saveBtn.addEventListener('click', saveBadge);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
