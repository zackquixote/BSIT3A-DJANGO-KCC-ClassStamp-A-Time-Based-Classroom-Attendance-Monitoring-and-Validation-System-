/* KCC ClassStamp — Users: Delete User Controller */
(function (window) {
  'use strict';

  var currentDeleteId = null;

  function getApp() { return window.UsersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initDeleteUser() {
    var confirmDeleteBtn = getEl('confirmDeleteBtn');

    // Delete Button Click (event delegation)
    document.addEventListener('click', function (e) {
      var delBtn = e.target.closest('[data-modal-target="deleteUserModal"]');
      if (!delBtn) return;

      currentDeleteId = delBtn.getAttribute('data-id');
      var userBox  = getEl('delete_username');
      var identBox = getEl('delete_ident');

      if (userBox)  userBox.textContent  = delBtn.getAttribute('data-name') || '';
      if (identBox) identBox.textContent = delBtn.getAttribute('data-ident') || '';

      var App = getApp();
      if (App) App.showModal('deleteUserModal');
      else if (typeof window.openModal === 'function') window.openModal('deleteUserModal');
      else {
        var m = getEl('deleteUserModal');
        if (m) m.classList.add('is-active');
      }
    });

    // Confirm Delete
    if (confirmDeleteBtn) {
      confirmDeleteBtn.addEventListener('click', function () {
        if (!currentDeleteId) return;
        var App = getApp();

        fetch('/users/ajax/delete/' + currentDeleteId + '/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'deleted') {
            window.location.reload();
          } else {
            if (App) {
              App.showAlert(data.error || 'Failed to delete user.', true);
              App.hideModal('deleteUserModal');
            } else if (window.closeModal) {
              window.closeModal('deleteUserModal');
            }
          }
        })
        .catch(function () {
          if (App) {
            App.showAlert('Error deleting user.', true);
            App.hideModal('deleteUserModal');
          } else if (window.closeModal) {
            window.closeModal('deleteUserModal');
          }
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteUser);
  } else {
    initDeleteUser();
  }
})(window);
