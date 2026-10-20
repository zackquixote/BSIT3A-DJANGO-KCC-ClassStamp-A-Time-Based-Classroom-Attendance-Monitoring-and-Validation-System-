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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdjudicateModal);
  } else {
    initAdjudicateModal();
  }
})(window);
