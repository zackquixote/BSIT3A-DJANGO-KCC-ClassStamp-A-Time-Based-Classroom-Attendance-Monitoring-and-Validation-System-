/* KCC ClassStamp — Info: Delete Info Controller */
(function (window) {
  'use strict';

  var currentInfoId = null;

  function getCSRF() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function showAlert(msg) {
    var alertBox = document.getElementById('infoAlert');
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.style.display = 'flex';
    setTimeout(function () { alertBox.style.display = 'none'; }, 4000);
  }

  function initDeleteInfo() {
    var deleteBtn = document.getElementById('confirmDeleteInfoBtn');

    // Handle delete button click
    document.addEventListener('click', function (e) {
      var delBtn = e.target.closest('[data-modal-target="deleteInfoModal"]');
      if (!delBtn) return;

      currentInfoId = delBtn.getAttribute('data-id');
      var deleteName = document.getElementById('deleteInfoName');
      if (deleteName) deleteName.textContent = delBtn.getAttribute('data-name') || '';
    });

    // Confirm delete AJAX
    if (deleteBtn) {
      deleteBtn.addEventListener('click', function () {
        if (!currentInfoId) return;
        fetch('/info/ajax/delete/' + currentInfoId + '/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'deleted') {
            window.location.reload();
          } else {
            showAlert(data.error || 'Failed to delete record.');
            if (window.closeModal) window.closeModal('deleteInfoModal');
          }
        })
        .catch(function () {
          showAlert('Error deleting record.');
          if (window.closeModal) window.closeModal('deleteInfoModal');
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeleteInfo);
  } else {
    initDeleteInfo();
  }
})(window);
