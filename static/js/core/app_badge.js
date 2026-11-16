/**
 * App icon badge — puts a small count on the installed KCC ClassStamp icon.
 *
 * Android launchers draw a dot / number on the home-screen icon when the page
 * calls navigator.setAppBadge(). The count comes from the same endpoint the
 * notification bell already uses, so the icon, the bell and the list can never
 * disagree.
 *
 * Browsers without the Badging API (Firefox, older Safari) simply skip it.
 */
(function () {
  'use strict';

  var unreadUrl = '/api/notifications/unread/';
  var POLL_MS = 60000;
  var timer = null;

  function supported() {
    return typeof navigator !== 'undefined' && typeof navigator.setAppBadge === 'function';
  }

  function apply(count) {
    if (!supported()) { return; }
    try {
      if (count > 0) {
        navigator.setAppBadge(count);
      } else if (typeof navigator.clearAppBadge === 'function') {
        navigator.clearAppBadge();
      } else {
        navigator.setAppBadge(0);
      }
    } catch (error) {
      /* A badge is decoration; never let it break the page. */
    }
  }

  function refresh() {
    if (!supported() || document.hidden) { return; }
    fetch(unreadUrl, {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    })
      .then(function (response) {
        if (!response.ok) { return null; }
        return response.json();
      })
      .then(function (payload) {
        if (!payload) { return; }
        var count = Number(payload.count) || 0;
        apply(count);
        document.body.classList.toggle('has-unread-badge', count > 0);
      })
      .catch(function () { /* offline: keep the last badge */ });
  }

  function start() {
    refresh();
    if (timer) { clearInterval(timer); }
    timer = setInterval(refresh, POLL_MS);

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) { refresh(); }
    });

    // Reading a notification should clear the dot immediately.
    document.addEventListener('click', function (event) {
      var link = event.target.closest && event.target.closest('a[href*="notification"]');
      if (link) { setTimeout(refresh, 700); }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  window.KccAppBadge = { refresh: refresh, apply: apply };
})();
