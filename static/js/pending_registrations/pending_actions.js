/* KCC ClassStamp — Pending Registrations: Approve & Reject Actions Controller */
(function (window) {
  'use strict';

  function initPendingActions() {
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPendingActions);
  } else {
    initPendingActions();
  }
})(window);
