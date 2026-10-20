/* KCC ClassStamp — Validation Queue: Approve & Reject Actions Controller */
(function (window) {
  'use strict';

  function initQueueActions() {
    // ── Approve confirmation ────────────────────────────────────
    document.querySelectorAll('.approve-form').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        var btn = form.querySelector('button[type="submit"]');
        var name = btn ? btn.getAttribute('data-name') : 'this student';
        if (!confirm('Approve registration for ' + name + '?')) {
          e.preventDefault();
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

        if (rejectModal) rejectModal.style.display = 'flex';
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

    function closeRejectModal() {
      if (rejectModal) rejectModal.style.display = 'none';
    }

    if (rejectCancel) {
      rejectCancel.addEventListener('click', closeRejectModal);
    }

    if (rejectModal) {
      rejectModal.addEventListener('click', function (e) {
        if (e.target === rejectModal) closeRejectModal();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeRejectModal();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initQueueActions);
  } else {
    initQueueActions();
  }
})(window);
