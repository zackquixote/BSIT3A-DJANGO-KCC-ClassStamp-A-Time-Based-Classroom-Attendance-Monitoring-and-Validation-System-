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
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
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

        var fd = new FormData();
        fd.append('action', 'approve');
        ids.forEach(function (id) { fd.append('ids[]', id); });

        try {
          var res = await fetch(batchUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
            body: fd
          });
          var data = await res.json();
          if (res.ok) {
            if (window.App && window.App.toast) {
              window.App.toast.success('Successfully approved ' + data.approved + ' students.');
            }
            setTimeout(function () { window.location.reload(); }, 600);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast.error(data.error || 'Batch approval failed.');
            }
            if (window.App && window.App.setButtonLoading) {
              window.App.setButtonLoading(approveBtn, false);
            }
          }
        } catch (err) {
          if (window.App && window.App.toast) window.App.toast.error('Network error during batch approval.');
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

        if (window.openModal) {
          window.openModal('batchRejectModal');
        } else if (batchRejectModal) {
          batchRejectModal.classList.add('is-active');
        }
      });
    }

    if (confirmRejectBtn) {
      confirmRejectBtn.addEventListener('click', async function () {
        var selected = getSelectedCheckboxes();
        if (!selected.length) return;

        var reason = (batchReasonInput ? batchReasonInput.value : '').trim();
        if (!reason) {
          if (window.App && window.App.toast) {
            window.App.toast.warning('Please enter a rejection reason.');
          }
          if (batchReasonInput) batchReasonInput.focus();
          return;
        }

        var ids = selected.map(function (cb) { return cb.getAttribute('data-id'); });
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(confirmRejectBtn, true, 'Rejecting...');
        }

        var fd = new FormData();
        fd.append('action', 'reject');
        fd.append('reason', reason);
        ids.forEach(function (id) { fd.append('ids[]', id); });

        try {
          var res = await fetch(batchUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
            body: fd
          });
          var data = await res.json();
          if (res.ok) {
            if (window.closeModal) window.closeModal('batchRejectModal');
            if (window.App && window.App.toast) {
              window.App.toast.warning('Rejected ' + data.rejected + ' student registrations.');
            }
            setTimeout(function () { window.location.reload(); }, 600);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast.error(data.error || 'Batch rejection failed.');
            }
            if (window.App && window.App.setButtonLoading) {
              window.App.setButtonLoading(confirmRejectBtn, false);
            }
          }
        } catch (err) {
          if (window.App && window.App.toast) window.App.toast.error('Network error during batch rejection.');
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
