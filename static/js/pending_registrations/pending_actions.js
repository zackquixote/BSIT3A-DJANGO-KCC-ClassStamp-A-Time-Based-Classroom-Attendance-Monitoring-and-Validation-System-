/* KCC ClassStamp — Pending Registrations: Approve & Reject Actions Controller */
(function (window) {
  'use strict';

  function initPendingActions() {
    // ── Approve confirmation ────────────────────────────────────
    document.querySelectorAll('.approve-form').forEach(function (form) {
      form.addEventListener('submit', async function (e) {
        if (form._confirmed) {
          form._confirmed = false;
          return;
        }
        e.preventDefault();
        var btn = form.querySelector('button[type="submit"]');
        var name = btn ? btn.getAttribute('data-name') : 'this student';

        var ok = window.App && window.App.confirm
          ? await window.App.confirm({
              title: 'Approve Registration',
              message: 'Approve student registration for ' + name + '?',
              confirmText: 'Approve',
              confirmClass: 'btn-primary',
              type: 'primary'
            })
          : confirm('Approve registration for ' + name + '?');

        if (ok) {
          if (window.App && window.App.setButtonLoading && btn) {
            window.App.setButtonLoading(btn, true, 'Approving...');
          }
          form._confirmed = true;
          form.submit();
        }
      });
    });

    // ── Reject Modal ────────────────────────────────────────────
    var rejectModal  = document.getElementById('rejectModal');
    var rejectForm   = document.getElementById('rejectModalForm');
    var rejectReason = document.getElementById('rejectModalReason');
    var rejectName   = document.getElementById('rejectModalStudentName');
    var rejectCancel = document.getElementById('rejectModalCancel');
    var modalChips   = document.querySelectorAll('.modal-chip');

    document.querySelectorAll('.open-reject-modal').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (rejectForm) rejectForm.action = this.getAttribute('data-reject-url');
        if (rejectName) rejectName.textContent = this.getAttribute('data-name');
        if (rejectReason) rejectReason.value = '';
        modalChips.forEach(function (c) { c.classList.remove('is-selected'); });

        if (window.openModal) {
          window.openModal('rejectModal');
        } else if (rejectModal) {
          rejectModal.classList.add('is-active');
        }

        setTimeout(function () {
          if (rejectReason) rejectReason.focus();
        }, 80);
      });
    });

    modalChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        if (rejectReason) rejectReason.value = this.getAttribute('data-reason');
        modalChips.forEach(function (c) { c.classList.remove('is-selected'); });
        this.classList.add('is-selected');
      });
    });

    if (rejectCancel) {
      rejectCancel.addEventListener('click', function () {
        if (window.closeModal) {
          window.closeModal('rejectModal');
        } else if (rejectModal) {
          rejectModal.classList.remove('is-active');
        }
      });
    }

    // ── Batch Actions (#3) ──────────────────────────────────────
    initBatchActions();
  }

  function getCSRF() {
    var token = '';
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === 'csrftoken=') {
          token = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    if (!token) {
      var meta = document.querySelector('meta[name="csrf-token"]');
      if (meta && meta.getAttribute('content')) token = meta.getAttribute('content');
    }
    if (!token) {
      var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
      if (input && input.value) token = input.value;
    }
    return token;
  }

  function initBatchActions() {
    var selectAll = document.getElementById('batchSelectAll');
    var bar = document.getElementById('batchActionBar');
    if (!bar) return;

    var batchUrl = bar.getAttribute('data-batch-url');
    var approveBtn = document.getElementById('batchApproveBtn');
    var rejectBtn = document.getElementById('batchRejectBtn');
    var clearBtn = document.getElementById('batchClearBtn');
    var countEl = document.getElementById('batchSelectedCount');
    var numEls = document.querySelectorAll('.batch-selected-num');
    var batchRejectModal = document.getElementById('batchRejectModal');
    var confirmRejectBtn = document.getElementById('confirmBatchRejectBtn');
    var batchReasonInput = document.getElementById('batchRejectReason');

    function getSelectedCheckboxes() {
      return Array.from(document.querySelectorAll('.row-select-checkbox:checked'));
    }

    function getVisibleCheckboxes() {
      return Array.from(document.querySelectorAll('.pending-row')).filter(function (row) {
        return row.style.display !== 'none';
      }).map(function (row) {
        return row.querySelector('.row-select-checkbox');
      }).filter(Boolean);
    }

    function updateBatchUI() {
      var selected = getSelectedCheckboxes();
      var count = selected.length;
      if (countEl) countEl.textContent = count;
      numEls.forEach(function (el) { el.textContent = count; });

      if (count > 0) {
        bar.classList.add('is-visible');
      } else {
        bar.classList.remove('is-visible');
      }

      var visible = getVisibleCheckboxes();
      if (selectAll) {
        selectAll.checked = visible.length > 0 && selected.length >= visible.length;
      }
    }

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        var shouldCheck = this.checked;
        getVisibleCheckboxes().forEach(function (cb) {
          cb.checked = shouldCheck;
        });
        updateBatchUI();
      });
    }

    document.addEventListener('change', function (e) {
      if (e.target && e.target.classList.contains('row-select-checkbox')) {
        updateBatchUI();
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        document.querySelectorAll('.row-select-checkbox').forEach(function (cb) {
          cb.checked = false;
        });
        if (selectAll) selectAll.checked = false;
        updateBatchUI();
      });
    }

    if (approveBtn) {
      approveBtn.addEventListener('click', async function () {
        var selected = getSelectedCheckboxes();
        if (!selected.length) return;

        var ids = selected.map(function (cb) { return cb.getAttribute('data-id'); });
        var count = ids.length;

        var ok = window.App && window.App.confirm
          ? await window.App.confirm({
              title: 'Batch Approve Registrations',
              message: 'Approve ' + count + ' selected student registration' + (count > 1 ? 's' : '') + '?',
              confirmText: 'Approve All (' + count + ')',
              confirmClass: 'btn-success',
              type: 'success'
            })
          : confirm('Approve ' + count + ' student registrations?');

        if (!ok) return;

        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(approveBtn, true, 'Approving...');
        }

        var csrf = getCSRF();
        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', csrf);
        fd.append('action', 'approve');
        ids.forEach(function (id) { fd.append('ids[]', id); });

        try {
          var res = await fetch(batchUrl, {
            method: 'POST',
            headers: {
              'X-CSRFToken': csrf,
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: fd
          });
          var data = null;
          try {
            data = await res.json();
          } catch (_) {}

          if (res.ok && data) {
            if (window.App && typeof window.App.toast === 'function') {
              window.App.toast('success', 'Successfully approved ' + (data.approved || ids.length) + ' student(s).');
            }
            setTimeout(function () { window.location.reload(); }, 600);
          } else {
            var errDetail = (data && data.error) ? data.error : ('Server returned ' + res.status + ' (' + res.statusText + ')');
            if (window.App && typeof window.App.toast === 'function') {
              window.App.toast('error', 'Batch approval failed: ' + errDetail);
            } else {
              alert('Batch approval failed: ' + errDetail);
            }
            if (window.App && window.App.setButtonLoading) {
              window.App.setButtonLoading(approveBtn, false);
            }
          }
        } catch (err) {
          console.error('Batch approval error:', err);
          var errMsg = 'Network error during batch approval: ' + (err.message || 'Check connection.');
          if (window.App && typeof window.App.toast === 'function') {
            window.App.toast('error', errMsg);
          } else {
            alert(errMsg);
          }
          if (window.App && window.App.setButtonLoading) window.App.setButtonLoading(approveBtn, false);
        }
      });
    }

    if (rejectBtn) {
      rejectBtn.addEventListener('click', function () {
        var selected = getSelectedCheckboxes();
        if (!selected.length) return;

        var rCountEl = document.getElementById('batchRejectCount');
        if (rCountEl) rCountEl.textContent = selected.length;
        if (batchReasonInput) batchReasonInput.value = '';
        document.querySelectorAll('#batchModalChips .modal-chip').forEach(function (c) {
          c.classList.remove('is-selected');
        });

        if (window.openModal) {
          window.openModal('batchRejectModal');
        } else if (batchRejectModal) {
          batchRejectModal.classList.add('is-active');
        }
      });
    }

    document.querySelectorAll('#batchModalChips .modal-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        if (batchReasonInput) batchReasonInput.value = this.getAttribute('data-reason');
        document.querySelectorAll('#batchModalChips .modal-chip').forEach(function (c) {
          c.classList.remove('is-selected');
        });
        this.classList.add('is-selected');
      });
    });

    if (confirmRejectBtn) {
      confirmRejectBtn.addEventListener('click', async function () {
        var selected = getSelectedCheckboxes();
        if (!selected.length) return;

        var reason = (batchReasonInput ? batchReasonInput.value : '').trim();
        if (!reason) {
          if (window.App && typeof window.App.toast === 'function') {
            window.App.toast('warning', 'Please enter a rejection reason.');
          } else {
            alert('Please enter a rejection reason.');
          }
          if (batchReasonInput) batchReasonInput.focus();
          return;
        }

        var ids = selected.map(function (cb) { return cb.getAttribute('data-id'); });
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(confirmRejectBtn, true, 'Rejecting...');
        }

        var csrf = getCSRF();
        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', csrf);
        fd.append('action', 'reject');
        fd.append('reason', reason);
        ids.forEach(function (id) { fd.append('ids[]', id); });

        try {
          var res = await fetch(batchUrl, {
            method: 'POST',
            headers: {
              'X-CSRFToken': csrf,
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: fd
          });
          var data = null;
          try {
            data = await res.json();
          } catch (_) {}

          if (res.ok && data) {
            if (window.closeModal) window.closeModal('batchRejectModal');
            if (window.App && typeof window.App.toast === 'function') {
              window.App.toast('warning', 'Rejected ' + (data.rejected || ids.length) + ' student registration(s).');
            }
            setTimeout(function () { window.location.reload(); }, 600);
          } else {
            var errDetail = (data && data.error) ? data.error : ('Server returned ' + res.status + ' (' + res.statusText + ')');
            if (window.App && typeof window.App.toast === 'function') {
              window.App.toast('error', 'Batch rejection failed: ' + errDetail);
            } else {
              alert('Batch rejection failed: ' + errDetail);
            }
            if (window.App && window.App.setButtonLoading) {
              window.App.setButtonLoading(confirmRejectBtn, false);
            }
          }
        } catch (err) {
          console.error('Batch rejection error:', err);
          var errMsg = 'Network error during batch rejection: ' + (err.message || 'Check connection.');
          if (window.App && typeof window.App.toast === 'function') {
            window.App.toast('error', errMsg);
          } else {
            alert(errMsg);
          }
          if (window.App && window.App.setButtonLoading) window.App.setButtonLoading(confirmRejectBtn, false);
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPendingActions);
  } else {
    initPendingActions();
  }
})(window);
