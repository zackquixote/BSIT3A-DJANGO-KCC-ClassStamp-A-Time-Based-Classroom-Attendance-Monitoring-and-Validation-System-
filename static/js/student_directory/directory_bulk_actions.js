/* KCC ClassStamp — Student Directory Bulk Actions (A-06, A-13) */
(function (window) {
  'use strict';

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function toast(message, type) {
    if (window.App && window.App.toast) {
      window.App.toast(message, type);
    } else if (window.toast) {
      window.toast(message, type);
    } else {
      alert(message);
    }
  }

  function postForm(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams(data).toString()
    }).then(function (r) { return r.json(); });
  }

  function initPromoteAll() {
    var btn = document.getElementById('promoteAllBtn');
    if (!btn) return;

    btn.addEventListener('click', function () {
      var ok = window.confirm(
        'Promote ALL approved students to the next year level?\n\n' +
        'Students at their program\'s final year will not be moved. ' +
        'This action is permanent and fully audited.'
      );
      if (!ok) return;

      btn.disabled = true;
      postForm(btn.getAttribute('data-url'), {})
        .then(function (data) {
          if (data.status === 'success') {
            toast(data.message || 'Promotion complete.', 'success');
          } else {
            toast(data.error || 'Promotion failed.', 'error');
          }
        })
        .catch(function () {
          toast('Network error while promoting students.', 'error');
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  function initQrReset() {
    var url = window.ProfileEditorConfig ? window.ProfileEditorConfig.qrResetUrl : null;
    if (!url) return;

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.js-qr-reset');
      if (!btn) return;

      var studentNumber = btn.getAttribute('data-student-number') || 'this student';
      var ok = window.confirm(
        'Rotate the TOTP QR secret for ' + studentNumber + '?\n\n' +
        'The student\'s current QR badge and any unused offline badges ' +
        'will immediately stop working.'
      );
      if (!ok) return;

      btn.disabled = true;
      postForm(url, { student_id: btn.getAttribute('data-student-id') })
        .then(function (data) {
          if (data.status === 'success') {
            toast(data.message || 'QR secret rotated.', 'success');
          } else {
            toast(data.error || 'QR reset failed.', 'error');
          }
        })
        .catch(function () {
          toast('Network error during QR reset.', 'error');
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initPromoteAll();
      initQrReset();
    });
  } else {
    initPromoteAll();
    initQrReset();
  }
})(window);
