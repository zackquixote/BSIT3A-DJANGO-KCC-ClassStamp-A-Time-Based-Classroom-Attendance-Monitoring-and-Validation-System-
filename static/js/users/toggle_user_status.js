/* KCC ClassStamp — Users: Toggle User Status Controller */
(function (window) {
  'use strict';

  function getApp() { return window.UsersApp || null; }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initToggleStatus() {
    document.querySelectorAll('.user-status-toggle').forEach(function (chk) {
      chk.addEventListener('change', function () {
        var userId = this.getAttribute('data-id');
        var badge = document.getElementById('status-badge-' + userId);
        var isChecked = this.checked;
        var that = this;
        var App = getApp();

        fetch('/users/ajax/toggle-status/' + userId + '/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCSRF()
          }
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'success') {
            if (badge) {
              if (data.is_active) {
                badge.className = 'badge badge--success text-xs';
                badge.innerHTML = '<i class="fas fa-circle-check"></i> Active';
              } else {
                badge.className = 'badge badge--danger text-xs';
                badge.innerHTML = '<i class="fas fa-circle-xmark"></i> Inactive';
              }
            }
            if (App) App.showAlert(data.message || 'Status updated.');
          } else {
            that.checked = !isChecked; // Revert switch
            if (App) App.showAlert(data.error || 'Failed to update status.', true);
          }
        })
        .catch(function () {
          that.checked = !isChecked; // Revert switch
          if (App) App.showAlert('Network error while toggling status.', true);
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initToggleStatus);
  } else {
    initToggleStatus();
  }
})(window);
