/* KCC ClassStamp — Programs: Add / Edit Modal & Save Controller */
(function (window) {
  'use strict';

  function getApp() { return window.ProgramsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initProgramModal() {
    var form       = getEl('editProgForm');
    var errorBox   = getEl('progFormError');
    var errorMsg   = getEl('progFormErrorMsg');
    var modalTitle = getEl('editProgModalTitle');
    var saveBtn    = getEl('saveProgBtn');

    if (!form) return;

    // Handle Create button clicks (event delegation)
    document.addEventListener('click', function (e) {
      var editBtn = e.target.closest('[data-modal-target="editProgModal"]');
      if (!editBtn) return;

      if (errorBox) errorBox.style.display = 'none';

      if (modalTitle) modalTitle.textContent = 'Add Program';
      form.reset();
      var idEl2 = getEl('prog_id');
      var yearsEl2 = getEl('prog_years');
      var actEl2 = getEl('prog_is_active');
      if (idEl2)    idEl2.value = '';
      if (yearsEl2) yearsEl2.value = '4';
      if (actEl2)   actEl2.checked = true;

      var App = getApp();
      if (typeof window.openModal === 'function') {
        window.openModal('editProgModal', editBtn);
      } else if (App && App.showModal) {
        App.showModal('editProgModal');
      } else {
        var modal = getEl('editProgModal');
        if (modal) modal.classList.add('is-active', 'is-open');
      }
    });

    // AJAX save with validation
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var formData = new FormData(form);
      if (window.App && window.App.setButtonLoading) {
        window.App.setButtonLoading(saveBtn, true, 'Saving...');
      } else if (saveBtn) {
        saveBtn.disabled = true;
      }

      var saveUrl = form.action || '/programs/save/';

      fetch(saveUrl, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCSRF()
        },
        body: formData
      })
      .then(function (r) {
        return r.json().then(function (data) {
          return { status: r.status, data: data };
        });
      })
      .then(function (res) {
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(saveBtn, false);
        } else if (saveBtn) {
          saveBtn.disabled = false;
        }

        if (res.status === 200 && res.data.status === 'success') {
          if (window.App && window.App.toast) {
            window.App.toast('success', res.data.message || 'Program saved successfully.');
          }
          var App = getApp();
          if (typeof window.closeModal === 'function') {
            window.closeModal('editProgModal');
          } else if (App && App.hideModal) {
            App.hideModal('editProgModal');
          }
          setTimeout(function () { window.location.reload(); }, 600);
        } else {
          var errMsg = res.data.error || 'Failed to save program.';
          if (window.App && window.App.toast) {
            window.App.toast('error', errMsg);
          }
          if (errorMsg) errorMsg.textContent = errMsg;
          if (errorBox) errorBox.style.display = 'flex';
        }
      })
      .catch(function () {
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(saveBtn, false);
        } else if (saveBtn) {
          saveBtn.disabled = false;
        }
        var netErr = 'Network or server error occurred.';
        if (window.App && window.App.toast) {
          window.App.toast('error', netErr);
        }
        if (errorMsg) errorMsg.textContent = netErr;
        if (errorBox) errorBox.style.display = 'flex';
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProgramModal);
  } else {
    initProgramModal();
  }
})(window);
