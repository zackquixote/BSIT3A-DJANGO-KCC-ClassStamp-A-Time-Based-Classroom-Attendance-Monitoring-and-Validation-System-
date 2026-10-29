/* KCC ClassStamp — Info: Add / Edit Info Modal & Save Controller */
(function (window) {
  'use strict';

  function getCSRF() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initInfoModal() {
    var form     = document.getElementById('infoForm');
    var errorBox = document.getElementById('infoFormError');
    var title    = document.getElementById('infoModalTitle');
    var submitBtn = document.getElementById('infoSubmitBtn');

    if (!form) return;

    // Handle Edit / Create click (event delegation)
    document.addEventListener('click', function (e) {
      var infoBtn = e.target.closest('[data-modal-target="infoModal"]');
      if (!infoBtn) return;

      if (errorBox) errorBox.style.display = 'none';
      var mode = infoBtn.getAttribute('data-mode');

      if (mode === 'edit') {
        if (title) title.textContent = 'Edit Info';
        if (submitBtn) submitBtn.textContent = 'Update Info';
        var idVal = infoBtn.getAttribute('data-id') || '';
        var nameVal = infoBtn.getAttribute('data-name') || '';
        var ageVal = infoBtn.getAttribute('data-age') || '';
        var addressVal = infoBtn.getAttribute('data-address') || '';
        var emailVal = infoBtn.getAttribute('data-email') || '';

        var idEl = document.getElementById('info_id');
        var nameEl = document.getElementById('info_name');
        var ageEl = document.getElementById('info_age');
        var addressEl = document.getElementById('info_address');
        var emailEl = document.getElementById('info_email');

        if (idEl) idEl.value = idVal;
        if (nameEl) nameEl.value = nameVal;
        if (ageEl) ageEl.value = ageVal;
        if (addressEl) addressEl.value = addressVal;
        if (emailEl) emailEl.value = emailVal;
      } else {
        if (title) title.textContent = 'Add Info';
        if (submitBtn) submitBtn.textContent = 'Save Info';
        form.reset();
        var idEl2 = document.getElementById('info_id');
        if (idEl2) idEl2.value = '';
      }
    });

    // Save info AJAX
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var formData = new FormData(form);

      fetch('/info/ajax/save/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRF() },
        body: formData
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          if (errorBox) {
            errorBox.textContent = data.error;
            errorBox.style.display = 'flex';
          }
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        if (errorBox) {
          errorBox.textContent = 'Communication error.';
          errorBox.style.display = 'flex';
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initInfoModal);
  } else {
    initInfoModal();
  }
})(window);
