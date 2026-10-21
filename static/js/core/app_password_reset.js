/* KCC ClassStamp — Core: Admin User Password Reset Controller (#4) */
(function (window) {
  'use strict';

  window.App = window.App || {};

  var MODAL_HTML =
    '<div id="adminResetPwModal" class="modal" role="dialog" aria-modal="true" aria-label="Reset User Password">' +
    '  <div class="modal-dialog modal-dialog--sm" style="max-width:480px;">' +
    '    <div class="modal-header">' +
    '      <h3 class="modal-title"><i class="fas fa-key" style="color:var(--accent-gold);margin-right:8px;"></i>Force Reset Password</h3>' +
    '      <button type="button" class="modal-close" data-modal-dismiss="adminResetPwModal" aria-label="Close"><i class="fas fa-times"></i></button>' +
    '    </div>' +
    '    <div class="modal-body" style="padding:16px 22px;">' +
    '      <div style="background:rgba(255,255,255,0.03);border:1px solid var(--glass-border);border-radius:var(--radius-md);padding:12px 14px;margin-bottom:16px;">' +
    '        <div class="text-xs text-muted uppercase font-semibold" style="letter-spacing:0.5px;">Target Account</div>' +
    '        <div class="font-semibold text-primary mt-1" id="adminResetTargetName" style="font-size:1rem;">—</div>' +
    '      </div>' +
    '      <p class="text-secondary text-sm" style="margin-bottom:16px;">' +
    '        Clicking reset will generate a secure, temporary 10-character password and log an administrative audit event. The user must use this temporary credential on their next sign in.' +
    '      </p>' +
    '      <div id="adminResetPwAlert" class="toast toast--error mb-3" style="display:none;"></div>' +
    '      <div id="adminResetResultBox" style="display:none;background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.3);border-radius:var(--radius-md);padding:14px;margin-bottom:16px;">' +
    '        <div class="flex items-center gap-2 text-success text-xs font-semibold mb-2">' +
    '          <i class="fas fa-circle-check"></i> Password Reset Successfully!' +
    '        </div>' +
    '        <div class="text-xs text-muted">New Temporary Password:</div>' +
    '        <div class="flex items-center justify-between gap-2 mt-1.5">' +
    '          <code class="font-mono text-primary font-bold text-base" id="adminResetTempPw" style="letter-spacing:1.5px;background:rgba(0,0,0,0.35);padding:6px 12px;border-radius:4px;display:inline-block;user-select:all;"></code>' +
    '          <button type="button" class="btn btn-outline btn-sm" id="adminResetCopyBtn" style="padding:6px 12px;" title="Copy to clipboard">' +
    '            <i class="fas fa-copy"></i> <span id="adminResetCopyText">Copy</span>' +
    '          </button>' +
    '        </div>' +
    '        <div class="text-xs text-muted mt-2">Please share this credential securely with the user.</div>' +
    '      </div>' +
    '    </div>' +
    '    <div class="modal-footer" style="padding:12px 22px;">' +
    '      <button type="button" class="btn btn-outline btn-sm" data-modal-dismiss="adminResetPwModal">Close</button>' +
    '      <button type="button" class="btn btn-primary btn-sm" id="adminResetConfirmBtn">' +
    '        <i class="fas fa-rotate-right"></i> Generate &amp; Reset Password' +
    '      </button>' +
    '    </div>' +
    '  </div>' +
    '</div>';

  var currentUserId = null;

  function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function ensureModal() {
    var m = document.getElementById('adminResetPwModal');
    if (!m) {
      document.body.insertAdjacentHTML('beforeend', MODAL_HTML);
      m = document.getElementById('adminResetPwModal');
      bindModalEvents(m);
    }
    return m;
  }

  function bindModalEvents(m) {
    var confirmBtn = m.querySelector('#adminResetConfirmBtn');
    var copyBtn = m.querySelector('#adminResetCopyBtn');
    var copyText = m.querySelector('#adminResetCopyText');
    var tempPw = m.querySelector('#adminResetTempPw');
    var alertBox = m.querySelector('#adminResetPwAlert');
    var resultBox = m.querySelector('#adminResetResultBox');

    if (confirmBtn) {
      confirmBtn.addEventListener('click', async function () {
        if (!currentUserId) return;
        if (alertBox) alertBox.style.display = 'none';

        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(confirmBtn, true, 'Resetting...');
        }

        try {
          var res = await fetch('/admin/users/' + currentUserId + '/reset-password/', {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCSRF(),
              'Accept': 'application/json'
            }
          });
          var data = await res.json();
          if (res.ok && data.temp_password) {
            if (tempPw) tempPw.textContent = data.temp_password;
            if (resultBox) resultBox.style.display = 'block';
            confirmBtn.style.display = 'none';
            if (window.App && window.App.toast) {
              window.App.toast.success('Password reset for ' + (data.full_name || data.username));
            }
          } else {
            if (alertBox) {
              alertBox.textContent = data.error || 'Failed to reset password.';
              alertBox.style.display = 'block';
            }
          }
        } catch (err) {
          if (alertBox) {
            alertBox.textContent = 'Network error while resetting password.';
            alertBox.style.display = 'block';
          }
        } finally {
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(confirmBtn, false);
          }
        }
      });
    }

    if (copyBtn && tempPw) {
      copyBtn.addEventListener('click', function () {
        var text = tempPw.textContent || '';
        if (!text) return;
        navigator.clipboard.writeText(text).then(function () {
          if (copyText) copyText.textContent = 'Copied!';
          if (window.App && window.App.toast) {
            window.App.toast.info('Temporary password copied to clipboard');
          }
          setTimeout(function () {
            if (copyText) copyText.textContent = 'Copy';
          }, 2000);
        });
      });
    }

    // Dismiss button delegation for the injected modal
    m.querySelectorAll('[data-modal-dismiss]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (typeof window.closeModal === 'function') window.closeModal('adminResetPwModal');
        else m.classList.remove('is-active');
      });
    });
  }

  function openResetPasswordModal(userId, name) {
    var m = ensureModal();
    currentUserId = userId;
    var nameEl = m.querySelector('#adminResetTargetName');
    if (nameEl) nameEl.textContent = name || ('User #' + userId);

    var alertBox = m.querySelector('#adminResetPwAlert');
    var resultBox = m.querySelector('#adminResetResultBox');
    var confirmBtn = m.querySelector('#adminResetConfirmBtn');

    if (alertBox) alertBox.style.display = 'none';
    if (resultBox) resultBox.style.display = 'none';
    if (confirmBtn) confirmBtn.style.display = 'inline-flex';

    if (typeof window.openModal === 'function') {
      window.openModal('adminResetPwModal');
    } else {
      m.classList.add('is-active');
    }
  }

  // Global click delegation for [data-admin-reset-pw] and .js-admin-reset-pw
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-admin-reset-pw], .js-admin-reset-pw');
    if (!btn) return;
    e.preventDefault();
    var uid = btn.getAttribute('data-user-id') || btn.getAttribute('data-id');
    var name = btn.getAttribute('data-name') || btn.getAttribute('data-username');
    if (uid) openResetPasswordModal(uid, name);
  });

  window.App.openResetPasswordModal = openResetPasswordModal;
})(window);
