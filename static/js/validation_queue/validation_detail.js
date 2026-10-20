/* KCC ClassStamp — Validation Queue: Validation Detail Rejection Chip Controller */
(function (window) {
  'use strict';

  function initValidationDetail() {
    var reasonInput = document.getElementById('rejectionReasonInput');
    var chips = document.querySelectorAll('.reject-chip');

    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var text = this.getAttribute('data-reason');
        if (reasonInput) {
          reasonInput.value = text;
          reasonInput.focus();
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initValidationDetail);
  } else {
    initValidationDetail();
  }
})(window);
