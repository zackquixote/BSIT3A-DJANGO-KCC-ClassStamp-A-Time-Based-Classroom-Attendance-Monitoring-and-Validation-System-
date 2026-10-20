/* KCC ClassStamp — Programs: Delete Program Controller */
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

  function initDeleteProgram() {
    var deleteForm    = getEl('deleteProgForm');
    var deleteCode    = getEl('delete_prog_code');
    var deleteWarning = getEl('delete_prog_warning');
    var confirmBtn    = getEl('confirmDeleteProgBtn');

    if (!deleteForm) return;

    // Handle Delete button click (event delegation)
    document.addEventListener('click', function (e) {
      var delBtn = e.target.closest('[data-modal-target="deleteProgModal"]');
      if (!delBtn) return;

      var progId = delBtn.getAttribute('data-id');
      var progCode = delBtn.getAttribute('data-code');
      var studentCount = parseInt(delBtn.getAttribute('data-students') || '0', 10);

      if (deleteCode) deleteCode.textContent = progCode;
      deleteForm.action = '/programs/delete/' + progId + '/';

      if (deleteWarning) {
        if (studentCount > 0) {
          deleteWarning.style.display = 'flex';
        } else {
          deleteWarning.style.display = 'none';
        }
      }

      var App = getApp();
      if (App) {
        App.showModal('deleteProgModal');
      } else if (typeof window.openModal === 'function') {
        window.openModal('deleteProgModal');
      } else {
        var modal = getEl('deleteProgModal');
        if (modal) modal.classList.add('is-active');
      }
    });

    // AJAX delete with form submit fallback
    deleteForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (confirmBtn) confirmBtn.disabled = true;

      fetch(deleteForm.action, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCSRF()
        }
      })
      .then(function (r) {
        return r.json().then(function (data) {
          return { status: r.status, data: data };
        });
      })
      .then(function () {
        if (confirmBtn) confirmBtn.disabled = false;
        var App = getApp();
        if (App) App.hideModal('deleteProgModal');
        else if (typeof window.closeModal === 'function') window.closeModal('deleteProgModal');
        window.location.reload();
      })
      .catch(function () {
        if (confirmBtn) confirmBtn.disabled = false;
        deleteForm.submit(); // fallback to standard POST
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteProgram);
  } else {
    initDeleteProgram();
  }
})(window);
