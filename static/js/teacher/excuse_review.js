/* KCC ClassStamp — Teacher: Excuse Slip Adjudication (S-08) */
(function (window) {
  'use strict';

  var activeSlipId = null;

  function getEl(id) { return document.getElementById(id); }

  function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || '';
  }

  function showModal(id) {
    if (typeof window.openModal === 'function') { window.openModal(id); return; }
    var m = getEl(id);
    if (m) m.classList.add('is-active');
  }

  function hideModal(id) {
    if (typeof window.closeModal === 'function') { window.closeModal(id); return; }
    var m = getEl(id);
    if (m) m.classList.remove('is-active');
  }

  function showAlert(msg) {
    var box = getEl('excuseReviewAlert');
    if (box) {
      box.textContent = msg;
      box.style.display = 'block';
      setTimeout(function () { box.style.display = 'none'; }, 5000);
    }
  }

  function review(slipId, action, note) {
    var prefix = '/teacher/excuse-slips/';
    var container = document.querySelector('[data-review-url-prefix]');
    if (container) {
      var raw = container.getAttribute('data-review-url-prefix');
      if (raw) prefix = raw.replace(/0\/review\/?$/, '');
    }
    return fetch(prefix + slipId + '/review/', {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCSRF(),
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: 'action=' + encodeURIComponent(action) + '&note=' + encodeURIComponent(note || '')
    })
    .then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function removePendingRow(slipId) {
    var row = document.querySelector('tr[data-slip-id="' + slipId + '"]');
    if (row && row.parentElement) row.parentElement.removeChild(row);
  }

  function init() {
    var approveBtns = document.querySelectorAll('.js-approve-slip');
    var rejectBtns = document.querySelectorAll('.js-reject-slip');
    var rejectModal = getEl('rejectSlipModal');
    if (!rejectModal) return;

    approveBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var slipId = btn.getAttribute('data-slip-id');
        btn.disabled = true;
        review(slipId, 'approve', '')
        .then(function (result) {
          if (result.data.ok) {
            removePendingRow(slipId);
            if (typeof window.toast === 'function') window.toast('success', result.data.message);
            setTimeout(function () { window.location.reload(); }, 600);
          } else {
            btn.disabled = false;
            showAlert(result.data.error || 'Unable to approve slip.');
          }
        })
        .catch(function () {
          btn.disabled = false;
          showAlert('Network error while reviewing slip.');
        });
      });
    });

    rejectBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        activeSlipId = btn.getAttribute('data-slip-id');
        getEl('rejectStudentName').textContent = btn.getAttribute('data-student') || '—';
        getEl('rejectNote').value = '';
        getEl('rejectSlipError').style.display = 'none';
        showModal('rejectSlipModal');
      });
    });

    getEl('confirmRejectBtn').addEventListener('click', function () {
      var note = getEl('rejectNote').value.trim();
      var errEl = getEl('rejectSlipError');
      if (!note) {
        errEl.textContent = 'A review note is required.';
        errEl.style.display = 'block';
        return;
      }
      var confirmBtn = getEl('confirmRejectBtn');
      confirmBtn.disabled = true;
      review(activeSlipId, 'reject', note)
      .then(function (result) {
        confirmBtn.disabled = false;
        if (result.data.ok) {
          removePendingRow(activeSlipId);
          hideModal('rejectSlipModal');
          if (typeof window.toast === 'function') window.toast('success', result.data.message);
          setTimeout(function () { window.location.reload(); }, 600);
        } else {
          errEl.textContent = result.data.error || 'Unable to reject slip.';
          errEl.style.display = 'block';
        }
      })
      .catch(function () {
        confirmBtn.disabled = false;
        errEl.textContent = 'Network error while reviewing slip.';
        errEl.style.display = 'block';
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
