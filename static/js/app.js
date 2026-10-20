/* KCC ClassStamp — App JS (Vanilla, no framework) */

(function () {
  'use strict';

  window.App = window.App || {};

  /* ── Unified Modern Toast Notification System ───────────────── */
  window.App.toast = function (type, message, duration) {
    if (!message) return;
    type = type || 'info';

    // Normalize type
    if (type === 'danger') type = 'error';
    if (type === 'warn') type = 'warning';

    // Ensure container exists
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    // Determine icon
    var iconClass = 'fas fa-circle-info';
    if (type === 'success') {
      iconClass = 'fas fa-circle-check';
    } else if (type === 'error') {
      iconClass = 'fas fa-circle-xmark';
    } else if (type === 'warning') {
      iconClass = 'fas fa-triangle-exclamation';
    }

    var toast = document.createElement('div');
    toast.className = 'toast toast--' + type;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');

    var iconEl = document.createElement('i');
    iconEl.className = iconClass + ' toast-icon';
    toast.appendChild(iconEl);

    var contentEl = document.createElement('span');
    contentEl.className = 'toast-content';
    contentEl.textContent = message;
    toast.appendChild(contentEl);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'toast-dismiss';
    closeBtn.setAttribute('aria-label', 'Dismiss notification');
    closeBtn.innerHTML = '&times;';
    toast.appendChild(closeBtn);

    var dismissed = false;
    function dismissToast() {
      if (dismissed) return;
      dismissed = true;
      toast.classList.add('toast--closing');
      setTimeout(function () {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 250);
    }

    closeBtn.addEventListener('click', dismissToast);
    container.appendChild(toast);

    var timeoutMs = typeof duration === 'number' ? duration : 4000;
    setTimeout(dismissToast, timeoutMs);

    return toast;
  };

  // Global alias for quick calling
  window.toast = window.App.toast;

  /* ── Button Loading & Double-Submission Prevention ──────────── */
  window.App.setButtonLoading = function (btn, isLoading, loadingText) {
    if (!btn) return;

    if (isLoading) {
      if (btn.disabled && btn.classList.contains('is-loading')) return;
      btn.dataset.originalHtml = btn.innerHTML;
      var width = btn.offsetWidth;
      if (width > 0) {
        btn.style.minWidth = width + 'px';
      }
      btn.disabled = true;
      btn.classList.add('is-loading');
      var text = loadingText || btn.getAttribute('data-loading-text') || 'Saving...';
      btn.innerHTML = '<i class="fas fa-spinner fa-spin" style="margin-right: 6px;"></i> ' + text;
    } else {
      btn.disabled = false;
      btn.classList.remove('is-loading');
      btn.style.minWidth = '';
      if (btn.dataset.originalHtml) {
        btn.innerHTML = btn.dataset.originalHtml;
        delete btn.dataset.originalHtml;
      }
    }
  };

  /* ── Modal Dialog Manager (Global & Accessible) ─────────────── */
  var modalTriggers = {};

  window.openModal = function (modalId, triggerEl) {
    var modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
    if (!modal) return;

    var trigger = triggerEl || document.activeElement;
    if (trigger && modal.id) {
      modalTriggers[modal.id] = trigger;
    }

    modal.classList.add('is-active', 'is-open');
    document.body.style.overflow = 'hidden';

    // Auto-focus first visible input field after modal transitions
    setTimeout(function () {
      var firstField = modal.querySelector(
        'input:not([type="hidden"]):not([disabled]):not([readonly]), select:not([disabled]), textarea:not([disabled]), [autofocus]'
      );
      if (firstField && typeof firstField.focus === 'function') {
        firstField.focus();
      }
    }, 60);
  };

  window.closeModal = function (modalId) {
    var modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
    if (!modal) return;

    modal.classList.remove('is-active', 'is-open');
    document.body.style.overflow = '';

    // Smoothly return focus to the trigger button
    if (modal.id && modalTriggers[modal.id]) {
      var trigger = modalTriggers[modal.id];
      delete modalTriggers[modal.id];
      if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger)) {
        trigger.focus();
      }
    }
  };

  // Global click delegate for open/close modals
  document.addEventListener('click', function (e) {
    var targetBtn = e.target.closest('[data-modal-target]');
    if (targetBtn) {
      e.preventDefault();
      var modalId = targetBtn.getAttribute('data-modal-target');
      window.openModal(modalId, targetBtn);
      return;
    }

    var dismissBtn = e.target.closest('[data-modal-dismiss]');
    if (dismissBtn) {
      e.preventDefault();
      var targetModal = dismissBtn.closest('.modal');
      if (targetModal) {
        window.closeModal(targetModal.id || targetModal);
      } else {
        var dismissId = dismissBtn.getAttribute('data-modal-dismiss');
        if (dismissId) window.closeModal(dismissId);
      }
      return;
    }

    // Backdrop click
    if (e.target.classList && (e.target.classList.contains('modal') || e.target.classList.contains('modal-overlay'))) {
      window.closeModal(e.target.id || e.target);
    }
  });

  // Escape key closes active modal
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var activeModal = document.querySelector('.modal.is-active, .modal.is-open');
      if (activeModal) window.closeModal(activeModal.id || activeModal);
    }
  });

  /* ── Modern Glassmorphic Confirm Dialog ─────────────────────── */
  window.App.confirm = function (opts) {
    opts = opts || {};
    var title = opts.title || 'Please Confirm';
    var message = opts.message || 'Are you sure you want to proceed?';
    var confirmText = opts.confirmText || 'Confirm';
    var cancelText = opts.cancelText || 'Cancel';
    var type = opts.type || 'danger';
    var confirmClass = opts.confirmClass || (type === 'primary' ? 'btn-primary' : (type === 'warning' ? 'btn-warning' : 'btn-danger'));

    var iconClass = 'fas fa-triangle-exclamation';
    if (type === 'primary') iconClass = 'fas fa-circle-question';
    if (type === 'warning') iconClass = 'fas fa-triangle-exclamation';

    return new Promise(function (resolve) {
      var modal = document.getElementById('appConfirmModal');
      if (!modal) {
        modal = document.createElement('div');
        modal.id = 'appConfirmModal';
        modal.className = 'modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.innerHTML =
          '<div class="modal-dialog modal-dialog--sm confirm-dialog">' +
          '  <div class="confirm-dialog-header" style="display: flex; gap: 14px; align-items: flex-start; padding: 22px 24px 14px;">' +
          '    <div id="confirmDialogIcon" class="confirm-dialog-icon confirm-dialog-icon--danger">' +
          '      <i class="fas fa-triangle-exclamation"></i>' +
          '    </div>' +
          '    <div style="flex: 1;">' +
          '      <h4 id="confirmDialogTitle" class="confirm-dialog-title" style="margin: 0 0 6px; font-size: 1.05rem; font-weight: 700; color: var(--text-primary);"></h4>' +
          '      <p id="confirmDialogMsg" class="confirm-dialog-msg" style="margin: 0; font-size: 0.875rem; color: var(--text-muted); line-height: 1.45;"></p>' +
          '    </div>' +
          '  </div>' +
          '  <div class="modal-footer" style="padding: 14px 24px; display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--glass-border);">' +
          '    <button type="button" id="confirmDialogCancelBtn" class="btn btn-outline btn-sm">' + cancelText + '</button>' +
          '    <button type="button" id="confirmDialogOkBtn" class="btn btn-sm">' + confirmText + '</button>' +
          '  </div>' +
          '</div>';
        document.body.appendChild(modal);
      }

      var titleEl = modal.querySelector('#confirmDialogTitle');
      var msgEl = modal.querySelector('#confirmDialogMsg');
      var iconContainer = modal.querySelector('#confirmDialogIcon');
      var okBtn = modal.querySelector('#confirmDialogOkBtn');
      var cancelBtn = modal.querySelector('#confirmDialogCancelBtn');

      if (titleEl) titleEl.textContent = title;
      if (msgEl) msgEl.textContent = message;

      if (iconContainer) {
        iconContainer.className = 'confirm-dialog-icon confirm-dialog-icon--' + type;
        iconContainer.innerHTML = '<i class="' + iconClass + '"></i>';
      }

      if (okBtn) {
        okBtn.className = 'btn btn-sm ' + confirmClass;
        okBtn.textContent = confirmText;
      }
      if (cancelBtn) {
        cancelBtn.textContent = cancelText;
      }

      function cleanup(res) {
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        modal.removeEventListener('click', onBackdrop);
        document.removeEventListener('keydown', onKey);
        window.closeModal('appConfirmModal');
        resolve(res);
      }

      function onOk() { cleanup(true); }
      function onCancel() { cleanup(false); }
      function onBackdrop(e) {
        if (e.target === modal) cleanup(false);
      }
      function onKey(e) {
        if (e.key === 'Escape') cleanup(false);
      }

      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      modal.addEventListener('click', onBackdrop);
      document.addEventListener('keydown', onKey);

      window.openModal('appConfirmModal');
      setTimeout(function () {
        if (cancelBtn) cancelBtn.focus();
      }, 70);
    });
  };

  /* ── Universal Web Audio Engine (Chimes & Feedback) ─────────── */
  var audioCtx = null;
  window.App.playTone = function (freq, duration, type) {
    type = type || 'sine';
    duration = duration || 0.2;
    try {
      if (!audioCtx) {
        var AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) audioCtx = new AudioContextClass();
      }
      if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      if (!audioCtx) return;

      var osc = audioCtx.createOscillator();
      var gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (_) {}
  };

  window.App.playChime = function (outcome) {
    outcome = (outcome || '').toUpperCase();
    if (outcome === 'PRESENT' || outcome === 'SUCCESS') {
      window.App.playTone(880, 0.15, 'sine');
      setTimeout(function () { window.App.playTone(1320, 0.25, 'sine'); }, 110);
      if (navigator.vibrate) navigator.vibrate(80);
    } else if (outcome === 'LATE' || outcome === 'WARNING') {
      window.App.playTone(660, 0.18, 'triangle');
      setTimeout(function () { window.App.playTone(550, 0.22, 'triangle'); }, 130);
      if (navigator.vibrate) navigator.vibrate([60, 40, 60]);
    } else {
      window.App.playTone(220, 0.22, 'sawtooth');
      setTimeout(function () { window.App.playTone(180, 0.25, 'sawtooth'); }, 110);
      if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
    }
  };

  /* ── Instant Debounced Table Filter Engine ───────────────────── */
  function initInstantTableSearch() {
    var inputs = document.querySelectorAll('[data-table-search], .js-table-search');
    inputs.forEach(function (input) {
      if (input._searchBound) return;
      input._searchBound = true;

      var tableSelector = input.getAttribute('data-table-search') || input.dataset.table || 'table';
      var debounceTimer = null;

      input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          var filterVal = input.value.trim().toLowerCase();
          var table = document.querySelector(tableSelector);
          if (!table) return;

          var tbody = table.querySelector('tbody') || table;
          var rows = tbody.querySelectorAll('tr:not(.table-empty-row)');
          var visibleCount = 0;

          rows.forEach(function (row) {
            var text = row.textContent.toLowerCase();
            if (!filterVal || text.indexOf(filterVal) > -1) {
              row.style.display = '';
              visibleCount++;
            } else {
              row.style.display = 'none';
            }
          });

          var emptyRow = tbody.querySelector('.table-search-empty');
          if (visibleCount === 0 && filterVal) {
            if (!emptyRow) {
              emptyRow = document.createElement('tr');
              emptyRow.className = 'table-search-empty table-empty-row';
              var theadRow = table.querySelector('thead tr');
              var colCount = theadRow && theadRow.children.length ? theadRow.children.length : (rows[0] ? rows[0].children.length : 6);
              emptyRow.innerHTML =
                '<td colspan="' + colCount + '" style="text-align: center; padding: 32px 16px; color: var(--text-muted); font-size: 0.85rem;">' +
                '  <i class="fas fa-magnifying-glass" style="font-size: 1.5rem; opacity: 0.4; display: block; margin-bottom: 8px;"></i>' +
                '  No matching rows found for "' + filterVal + '"' +
                '</td>';
              tbody.appendChild(emptyRow);
            } else {
              emptyRow.style.display = '';
              var textSpan = emptyRow.querySelector('td');
              if (textSpan) {
                textSpan.innerHTML =
                  '<i class="fas fa-magnifying-glass" style="font-size: 1.5rem; opacity: 0.4; display: block; margin-bottom: 8px;"></i>' +
                  'No matching rows found for "' + filterVal + '"';
              }
            }
          } else if (emptyRow) {
            emptyRow.style.display = 'none';
          }
        }, 150);
      });

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && input.value) {
          input.value = '';
          input.dispatchEvent(new Event('input'));
        }
      });
    });
  }

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

      window.openModal('sessionInactivityModal');
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
        window.closeModal('sessionInactivityModal');
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

  /* ── DOM Ready Initializers ─────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss and enhance server-rendered Django toasts
    document.querySelectorAll('.toast').forEach(function (toast) {
      if (!toast.querySelector('.toast-dismiss')) {
        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'toast-dismiss';
        closeBtn.setAttribute('aria-label', 'Dismiss notification');
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', function () {
          toast.classList.add('toast--closing');
          setTimeout(function () { toast.remove(); }, 250);
        });
        toast.appendChild(closeBtn);
      }

      setTimeout(function () {
        toast.classList.add('toast--closing');
        setTimeout(function () { toast.remove(); }, 250);
      }, 5000);
    });

    // Mobile sidebar toggle & backdrop handling
    var menuBtn = document.getElementById('sidebar-toggle');
    var closeBtn = document.getElementById('sidebar-close');
    var sidebar = document.getElementById('sidebar');
    var backdrop = document.getElementById('sidebar-backdrop');

    function openSidebar() {
      if (sidebar) sidebar.classList.add('is-open');
      if (backdrop) backdrop.classList.add('is-active');
      document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove('is-open');
      if (backdrop) backdrop.classList.remove('is-active');
      document.body.style.overflow = '';
    }

    if (menuBtn) {
      menuBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (sidebar && sidebar.classList.contains('is-open')) {
          closeSidebar();
        } else {
          openSidebar();
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeSidebar();
      });
    }

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        closeSidebar();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) {
        closeSidebar();
      }
    });

    // Active nav link highlight
    var currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(function (link) {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
      }
    });

    // Initialize instant search and inactivity guard
    initInstantTableSearch();
    initSessionInactivityGuard();
  });

  /* ── Back-Forward Cache (bfcache) Invalidation ───────────────── */
  window.addEventListener('pageshow', function (event) {
    var navEntries = (window.performance && performance.getEntriesByType)
      ? performance.getEntriesByType('navigation')
      : [];
    var isBackForward = event.persisted ||
      (navEntries.length > 0 && navEntries[0].type === 'back_forward') ||
      (window.performance && window.performance.navigation && window.performance.navigation.type === 2);

    if (isBackForward) {
      window.location.reload();
    }
  });

})();

