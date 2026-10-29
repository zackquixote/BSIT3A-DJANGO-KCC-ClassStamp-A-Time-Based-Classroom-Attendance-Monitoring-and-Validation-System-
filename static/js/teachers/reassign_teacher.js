/* KCC ClassStamp — Teachers: Quick Department Reassignment (A-12) */
(function (window) {
  'use strict';

  var T = window.TeachersApp;
  if (!T) { return; }

  var reassignUrl = null;
  var confirmTarget = null;

  function currentDeptId() {
    return document.getElementById('reassignDept').dataset.currentDeptId || '';
  }

  function openReassign(btn) {
    if (!reassignUrl) {
      var holder = document.getElementById('teacher-reassign-boot');
      reassignUrl = holder ? holder.dataset.reassignUrl : '';
    }
    if (!reassignUrl) {
      T.showAlert(null, 'Reassignment endpoint is not configured.');
      return;
    }
    var teacherUrl = reassignUrl.replace('/0/reassign/', '/' + (btn.dataset.id || '0') + '/reassign/');

    document.getElementById('reassignTeacherName').textContent = btn.dataset.name || 'this faculty member';
    var select = document.getElementById('reassignDept');
    select.dataset.currentDeptId = btn.dataset.deptId || '';
    select.value = '';
    document.getElementById('reassignLoadText').textContent =
      'Current: ' + (btn.dataset.deptCode || 'None') + ' · Teaching load: ' +
      (btn.dataset.classCount || '0') + ' class(es) — kept intact on transfer.';
    var err = document.getElementById('reassignError');
    err.style.display = 'none';

    T.showModal('reassignTeacherModal');
    confirmTarget = teacherUrl;
  }

  function confirmReassign() {
    var select = document.getElementById('reassignDept');
    var deptId = select.value;
    var err = document.getElementById('reassignError');

    if (!deptId) {
      err.textContent = 'Please select the destination department.';
      err.style.display = 'block';
      return;
    }
    if (String(deptId) === String(currentDeptId())) {
      err.textContent = 'The teacher is already assigned to this department.';
      err.style.display = 'block';
      return;
    }

    fetch(confirmTarget, {
      method: 'POST',
      headers: {
        'X-CSRFToken': T.getCSRFToken(),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({ dept_id: deptId })
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (result.ok && result.data.ok) {
          T.hideModal('reassignTeacherModal');
          T.showAlert(null, result.data.message || 'Teacher reassigned.', 'success');
          setTimeout(function () { location.reload(); }, 900);
        } else {
          err.textContent = (result.data && result.data.error) || 'Reassignment failed.';
          err.style.display = 'block';
        }
      })
      .catch(function () {
        err.textContent = 'Network error while reassigning.';
        err.style.display = 'block';
      });
  }

  function init() {
    document.querySelectorAll('.js-reassign-teacher').forEach(function (btn) {
      btn.addEventListener('click', function () { openReassign(btn); });
    });

    var confirmBtn = document.getElementById('reassignConfirm');
    if (confirmBtn) { confirmBtn.addEventListener('click', confirmReassign); }

    document.querySelectorAll('[data-modal-dismiss="reassignTeacherModal"]').forEach(function (el) {
      el.addEventListener('click', function () { T.hideModal('reassignTeacherModal'); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
