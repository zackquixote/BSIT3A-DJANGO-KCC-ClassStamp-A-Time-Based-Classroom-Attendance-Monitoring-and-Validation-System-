/* KCC ClassStamp — Subjects: Inline Activate / Deactivate Toggle */
(function () {
  'use strict';

  function getCSRF() {
    var m = document.querySelector('meta[name="csrf-token"]');
    if (m) return m.getAttribute('content');
    var i = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return i ? i.value : '';
  }

  function toast(type, msg) {
    if (window.App && window.App.toast) { window.App.toast(type, msg); return; }
    var el = document.getElementById(type === 'error' ? 'subjectAlert' : 'subjectSuccess');
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(function () { el.style.display = 'none'; }, 4000);
  }

  document.addEventListener('click', async function (e) {
    var btn = e.target.closest('.js-toggle-subject');
    if (!btn) return;

    var pk       = btn.dataset.id;
    var isActive = btn.dataset.active === '1';
    var label    = isActive ? 'Deactivate' : 'Activate';

    if (!confirm(label + ' this subject?')) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + label + 'ing...';

    try {
      var res  = await fetch('/subjects/toggle/' + pk + '/', {
        method : 'POST',
        headers: { 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest' },
      });
      var data = await res.json();

      if (!data.ok) { toast('error', data.error || 'Toggle failed.'); return; }
      toast('success', data.message);

      /* Update the row status badge in-place */
      var row = btn.closest('tr');
      var badgeCell = row && row.querySelector('.js-status-badge');
      var newActive = data.is_active;

      if (badgeCell) {
        badgeCell.innerHTML = newActive
          ? '<span class="badge badge--green"><i class="fas fa-circle" style="font-size:.55rem;"></i> Active</span>'
          : '<span class="badge badge--muted">Inactive</span>';
      }

      /* Update toggle button */
      btn.dataset.active = newActive ? '1' : '0';
      btn.innerHTML = newActive
        ? '<i class="fas fa-toggle-off text-muted"></i><span>Deactivate</span>'
        : '<i class="fas fa-toggle-on text-green"></i><span>Activate</span>';

    } catch (err) {
      toast('error', 'Network error. Please try again.');
    } finally {
      btn.disabled = false;
    }
  });
})();
