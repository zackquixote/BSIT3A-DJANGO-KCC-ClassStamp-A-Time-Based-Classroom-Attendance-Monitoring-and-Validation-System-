/* KCC ClassStamp — Teachers: Toggle Active Status Controller */
(function (window) {
  'use strict';

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  function initToggleTeacher() {
    // Event delegation on document to catch Toggle button clicks
    document.addEventListener('click', async function (e) {
      var toggleBtn = e.target.closest('.js-toggle-teacher');
      if (!toggleBtn) return;

      e.preventDefault();
      var isActive = toggleBtn.dataset.active === '1';
      var label = isActive ? 'Deactivate' : 'Activate';

      var confirmed = window.App && window.App.confirm
        ? await window.App.confirm({
            title: label + ' Faculty Account',
            message: 'Are you sure you want to ' + label.toLowerCase() + ' this faculty account?',
            confirmText: label,
            confirmClass: isActive ? 'btn-danger' : 'btn-primary',
            type: isActive ? 'danger' : 'primary'
          })
        : confirm(label + ' this faculty account?');

      if (!confirmed) return;

      if (window.App && window.App.setButtonLoading) {
        window.App.setButtonLoading(toggleBtn, true, 'Updating...');
      } else {
        toggleBtn.disabled = true;
      }

      try {
        var res = await fetch('/teachers/toggle/' + toggleBtn.dataset.id + '/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() },
        });
        var data = await res.json();
        if (data.ok) {
          var successEl = getEl('teacherSuccess');
          if (window.App && window.App.toast) {
            window.App.toast('success', data.message);
          } else if (successEl) { successEl.style.display = 'block'; successEl.textContent = data.message; }
          setTimeout(function () { location.reload(); }, 600);
        } else {
          if (window.App && window.App.toast) {
            window.App.toast('error', data.error || 'Failed to update status.');
          } else {
            alert(data.error);
          }
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(toggleBtn, false);
          } else {
            toggleBtn.disabled = false;
          }
        }
      } catch (err) {
        if (window.App && window.App.toast) {
          window.App.toast('error', 'Network communication error.');
        } else {
          alert('Network error');
        }
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(toggleBtn, false);
        } else {
          toggleBtn.disabled = false;
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initToggleTeacher);
  } else {
    initToggleTeacher();
  }
})(window);
