/* KCC ClassStamp — Core: User Session Inactivity Watchdog */
(function (window) {
  'use strict';

  window.App = window.App || {};

  /* ── User Session Inactivity Watchdog ────────────────────────── */
  function initSessionInactivityGuard() {
    // Only monitor on authenticated pages (sidebar present)
    if (!document.getElementById('sidebar') && !document.querySelector('.sidebar')) return;

    var IDLE_WARN_MS = 28 * 60 * 1000;
    var COUNTDOWN_SEC = 120;
    var idleTimer = null;
    var countdownInterval = null;
    var warningActive = false;

    function resetIdleTimer() {
      if (warningActive) return;
      clearTimeout(idleTimer);
      idleTimer = setTimeout(showInactivityWarning, IDLE_WARN_MS);
    }

    function showInactivityWarning() {
      warningActive = true;
      var remaining = COUNTDOWN_SEC;

      var modal = document.getElementById('sessionInactivityModal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'sessionInactivityModal';
        modal.className = 'modal';
        modal.setAttribute('role', 'alertdialog');
        modal.setAttribute('aria-modal', 'true');
        modal.innerHTML =
          '<div class="modal-dialog modal-dialog--sm confirm-dialog">' +
          '  <div class="confirm-dialog-header" style="display: flex; gap: 14px; align-items: flex-start; padding: 22px 24px 14px;">' +
          '    <div class="confirm-dialog-icon confirm-dialog-icon--warning">' +
          '      <i class="fas fa-clock-rotate-left"></i>' +
          '    </div>' +
          '    <div style="flex: 1;">' +
          '      <h4 style="margin: 0 0 6px; font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">Session Timeout Warning</h4>' +
          '      <p style="margin: 0; font-size: 0.875rem; color: var(--text-muted); line-height: 1.45;">' +
          '        You have been inactive. For your account security on campus computers, your session will expire in ' +
          '        <strong id="sessionCountdownDisplay" style="color: #fbbf24; font-size: 1rem;">' + COUNTDOWN_SEC + '</strong> seconds.' +
          '      </p>' +
          '    </div>' +
          '  </div>' +
          '  <div class="modal-footer" style="padding: 14px 24px; display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--glass-border);">' +
          '    <a href="/logout/" class="btn btn-outline btn-sm">Log Out Now</a>' +
          '    <button type="button" id="sessionStayLoggedInBtn" class="btn btn-primary btn-sm"><i class="fas fa-lock-open mr-1"></i> Stay Signed In</button>' +
          '  </div>' +
          '</div>';
        document.body.appendChild(modal);
      }

      var displayEl = modal.querySelector('#sessionCountdownDisplay');
      var stayBtn = modal.querySelector('#sessionStayLoggedInBtn');

      if (typeof window.openModal === 'function') {
        window.openModal('sessionInactivityModal');
      } else if (window.App && window.App.openModal) {
        window.App.openModal('sessionInactivityModal');
      }

      if (stayBtn) stayBtn.focus();

      countdownInterval = setInterval(function () {
        remaining--;
        if (displayEl) displayEl.textContent = remaining;
        if (remaining <= 0) {
          clearInterval(countdownInterval);
          window.location.href = '/logout/';
        }
      }, 1000);

      function onStayLoggedIn() {
        clearInterval(countdownInterval);
        warningActive = false;
        if (typeof window.closeModal === 'function') {
          window.closeModal('sessionInactivityModal');
        } else if (window.App && window.App.closeModal) {
          window.App.closeModal('sessionInactivityModal');
        }
        // Ping keepalive to refresh backend Django session activity
        fetch('/session/keepalive/', { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .catch(function () {});
        if (window.App && window.App.toast) {
          window.App.toast('success', 'Your session has been extended.', 3000);
        }
        resetIdleTimer();
      }

      if (stayBtn) {
        stayBtn.onclick = onStayLoggedIn;
      }
    }

    ['mousemove', 'keydown', 'touchstart', 'scroll', 'click'].forEach(function (evt) {
      window.addEventListener(evt, resetIdleTimer, { passive: true });
    });

    resetIdleTimer();
  }

  window.App.initSessionInactivityGuard = initSessionInactivityGuard;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSessionInactivityGuard);
  } else {
    initSessionInactivityGuard();
  }
})(window);
