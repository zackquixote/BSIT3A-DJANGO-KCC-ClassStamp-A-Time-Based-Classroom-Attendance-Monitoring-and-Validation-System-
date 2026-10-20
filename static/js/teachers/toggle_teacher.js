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
      if (!confirm(label + ' this faculty account?')) return;

      toggleBtn.disabled = true;
      var App = getApp();

      try {
        var res = await fetch('/teachers/toggle/' + toggleBtn.dataset.id + '/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() },
        });
        var data = await res.json();
        if (data.ok) {
          var successEl = getEl('teacherSuccess');
          if (App) App.showAlert(successEl, data.message, 'success');
          else if (successEl) { successEl.style.display = 'block'; successEl.textContent = data.message; }
          setTimeout(function () { location.reload(); }, 800);
        } else {
          alert(data.error);
          toggleBtn.disabled = false;
        }
      } catch (err) {
        alert('Network error');
        toggleBtn.disabled = false;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initToggleTeacher);
  } else {
    initToggleTeacher();
  }
})(window);
