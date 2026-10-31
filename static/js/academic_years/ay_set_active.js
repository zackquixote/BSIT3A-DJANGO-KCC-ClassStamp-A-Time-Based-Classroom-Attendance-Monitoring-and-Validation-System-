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

      var confirmed = window.App && window.App.confirm
        ? await window.App.confirm({
            title: 'Set Active Academic Year',
            message: 'Set this as the active institutional academic term for all classes and timetables?',
            confirmText: 'Set Active',
            confirmClass: 'btn-primary',
            type: 'primary'
          })
        : confirm('Set this as the active institutional academic term?');

      if (!confirmed) return;

      if (window.App && window.App.setButtonLoading) {
        window.App.setButtonLoading(btn, true, 'Activating...');
      } else {
        btn.disabled = true;
      }

      try {
        var url = '/academic-years/set-active/' + id + '/';

        function restoreButton() {
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(btn, false);
          } else {
            btn.disabled = false;
          }
        }

        function toast(kind, message) {
          if (window.App && window.App.toast) {
            window.App.toast(kind, message);
          } else {
            alert(message);
          }
        }

        var res = await fetch(url, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() }
        });
        var data = await res.json();

        // 409 = the outgoing term still holds live data. Offer a deliberate
        // override that carries a written reason into the audit trail.
        if (!data.ok && res.status === 409 && data.requires_force) {
          var proceed = window.App && window.App.confirm
            ? await window.App.confirm({
                title: 'Switch term with live data?',
                message: data.error + ' Switching anyway leaves those records in the outgoing term.',
                confirmText: 'Switch anyway',
                confirmClass: 'btn-danger',
                type: 'danger'
              })
            : confirm(data.error + '\n\nSwitch anyway?');

          if (!proceed) { restoreButton(); return; }

          var reason = window.prompt('Reason for forcing the switch (recorded in the audit log):', '');
          if (!reason || !reason.trim()) {
            toast('error', 'A written reason is required to force the switch.');
            restoreButton();
            return;
          }

          var forced = await fetch(url, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCSRF(),
              'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: 'force=1&reason=' + encodeURIComponent(reason)
          });
          data = await forced.json();
        }

        if (data.ok) {
          toast('success', data.message);
          setTimeout(function () { location.reload(); }, 600);
        } else {
          toast('error', data.error || 'Failed to set active term.');
          restoreButton();
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
