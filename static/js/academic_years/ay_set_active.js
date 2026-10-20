/* KCC ClassStamp — Academic Years: Set Active Controller */
(function (window) {
  'use strict';

  function getApp() { return window.AcademicYearsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function initAySetActive() {
    document.addEventListener('click', async function (e) {
      var btn = e.target.closest('.js-set-active');
      if (!btn) return;

      var id = btn.dataset.id;
      if (!id) return;

      if (!confirm('Set this as the active institutional academic term?')) return;

      if (window.App && window.App.setButtonLoading) {
        window.App.setButtonLoading(btn, true, 'Activating...');
      } else {
        btn.disabled = true;
      }
      var App = getApp();
      var successEl = getEl('aySuccess');

      try {
        var res = await fetch('/academic-years/set-active/' + id + '/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() }
        });
        var data = await res.json();
        if (data.ok) {
          if (window.App && window.App.toast) {
            window.App.toast('success', data.message);
          }
          if (App && App.showAlert) App.showAlert(successEl, data.message, 'success');
          setTimeout(function () { location.reload(); }, 600);
        } else {
          if (window.App && window.App.toast) {
            window.App.toast('error', data.error || 'Failed to set active term.');
          } else {
            alert(data.error || 'Failed to set active term.');
          }
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(btn, false);
          } else {
            btn.disabled = false;
          }
        }
      } catch (_) {
        if (window.App && window.App.toast) {
          window.App.toast('error', 'Network communication error.');
        } else {
          alert('Network error');
        }
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(btn, false);
        } else {
          btn.disabled = false;
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAySetActive);
  } else {
    initAySetActive();
  }
})(window);
