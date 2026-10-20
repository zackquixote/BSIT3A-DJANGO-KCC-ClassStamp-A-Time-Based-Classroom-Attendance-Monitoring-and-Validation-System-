/* KCC ClassStamp — Anomalies: Adjudicate Modal Controller */
(function (window) {
  'use strict';

  function initAdjudicateModal() {
    var modal = document.getElementById('adjudicateModal');
    if (!modal) return;

    var closeBtn = document.getElementById('closeAdjudicateBtn');
    var cancelBtn = document.getElementById('cancelAdjudicateBtn');
    var form = document.getElementById('adjudicateForm');
    var modalStudentName = document.getElementById('modalStudentName');
    var modalRuleCode = document.getElementById('modalRuleCode');

    function closeModal() {
      modal.classList.remove('is-open');
    }

    // Open modal on adjudicate button click
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.adjudicate-btn');
      if (!btn) return;

      var flagId = btn.dataset.flagId;
      if (modalStudentName) modalStudentName.textContent = btn.dataset.student || '';
      if (modalRuleCode) modalRuleCode.textContent = btn.dataset.rule || '';
      if (form) form.action = '/admin/anomalies/' + flagId + '/adjudicate/';
      modal.classList.add('is-open');
    });

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('is-open')) {
        closeModal();
      }
    });
    // ── Bulk Anomaly Actions (#11) ──────────────────────────────
    initBatchAnomalies();
  }

  function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function initBatchAnomalies() {
    var bar = document.getElementById('anomalyBatchBar');
    if (!bar) return;

    var selectAll = document.getElementById('anomalySelectAll');
    var batchUrl = bar.getAttribute('data-batch-url');
    var countEl = document.getElementById('anomalySelectedCount');
    var numEls = document.querySelectorAll('.anomaly-selected-num');
    var dismissBtn = document.getElementById('bulkDismissBtn');
    var confirmBtn = document.getElementById('bulkConfirmBtn');
    var clearBtn = document.getElementById('anomalyClearBtn');

    function getSelectedCheckboxes() {
      return Array.from(document.querySelectorAll('.anomaly-select-checkbox:checked'));
    }

    function getAllCheckboxes() {
      return Array.from(document.querySelectorAll('.anomaly-select-checkbox'));
    }

    function updateBatchUI() {
      var selected = getSelectedCheckboxes();
      var count = selected.length;
      if (countEl) countEl.textContent = count;
      numEls.forEach(function (el) { el.textContent = count; });

      if (count > 0) bar.classList.add('is-visible');
      else bar.classList.remove('is-visible');

      var all = getAllCheckboxes();
      if (selectAll) selectAll.checked = all.length > 0 && selected.length >= all.length;
    }

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        var shouldCheck = this.checked;
        getAllCheckboxes().forEach(function (cb) { cb.checked = shouldCheck; });
        updateBatchUI();
      });
    }

    document.addEventListener('change', function (e) {
      if (e.target && e.target.classList.contains('anomaly-select-checkbox')) {
        updateBatchUI();
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        getAllCheckboxes().forEach(function (cb) { cb.checked = false; });
        if (selectAll) selectAll.checked = false;
        updateBatchUI();
      });
    }

    async function submitBulk(decision, confirmMsg, successMsg, btn) {
      var selected = getSelectedCheckboxes();
      if (!selected.length) return;

      var ok = window.App && window.App.confirm
        ? await window.App.confirm({
            title: 'Bulk Anomaly Action',
            message: confirmMsg,
            confirmText: 'Confirm (' + selected.length + ')',
            confirmClass: decision === 'DISMISS' ? 'btn-success' : 'btn-danger',
            type: decision === 'DISMISS' ? 'success' : 'danger'
          })
        : confirm(confirmMsg);

      if (!ok) return;

      if (window.App && window.App.setButtonLoading && btn) {
        window.App.setButtonLoading(btn, true, 'Processing...');
      }

      var fd = new FormData();
      fd.append('decision', decision);
      selected.forEach(function (cb) {
        fd.append('ids[]', cb.getAttribute('data-id'));
      });

      try {
        var res = await fetch(batchUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() },
          body: fd
        });
        var data = await res.json();
        if (res.ok) {
          if (window.App && window.App.toast) {
            window.App.toast.success(successMsg.replace('{n}', data.updated));
          }
          setTimeout(function () { window.location.reload(); }, 600);
        } else {
          if (window.App && window.App.toast) {
            window.App.toast.error(data.error || 'Bulk adjudication failed.');
          }
          if (window.App && window.App.setButtonLoading && btn) {
            window.App.setButtonLoading(btn, false);
          }
        }
      } catch (err) {
        if (window.App && window.App.toast) window.App.toast.error('Network error during bulk adjudication.');
        if (window.App && window.App.setButtonLoading && btn) {
          window.App.setButtonLoading(btn, false);
        }
      }
    }

    if (dismissBtn) {
      dismissBtn.addEventListener('click', function () {
        var count = getSelectedCheckboxes().length;
        submitBulk('DISMISS', 'Dismiss ' + count + ' flagged anomal' + (count > 1 ? 'ies' : 'y') + ' as false positive?', 'Successfully dismissed {n} flags.', dismissBtn);
      });
    }

    if (confirmBtn) {
      confirmBtn.addEventListener('click', function () {
        var count = getSelectedCheckboxes().length;
        submitBulk('CONFIRM_PROXY', 'Confirm proxy attendance fraud for ' + count + ' flagged record' + (count > 1 ? 's' : '') + '?', 'Confirmed {n} proxy attendance violations.', confirmBtn);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdjudicateModal);
  } else {
    initAdjudicateModal();
  }
})(window);
