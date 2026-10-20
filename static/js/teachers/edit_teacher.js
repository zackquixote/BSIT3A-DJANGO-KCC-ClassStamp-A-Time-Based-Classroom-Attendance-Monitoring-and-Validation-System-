/* KCC ClassStamp — Teachers: Edit Teacher Controller */
(function (window) {
  'use strict';

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }

  function initEditTeacher() {
    // Guard: only run if the teacher modal exists on this page
    if (!getEl('teacherModal')) return;

    // Event delegation on document to catch all Edit button clicks reliably
    document.addEventListener('click', async function (e) {
      var editBtn = e.target.closest('.js-edit-teacher');
      if (!editBtn) return;

      e.preventDefault();
      var teacherId = editBtn.dataset.id;
      if (!teacherId) return;

      // Provide visual loading indicator on the edit button
      var originalHtml = editBtn.innerHTML;
      editBtn.disabled = true;
      editBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

      try {
        var res = await fetch('/teachers/get/' + teacherId + '/');
        var data = await res.json();
        if (!data.ok) {
          alert(data.error || 'Failed to load teacher details.');
          return;
        }

        var t = data.teacher;
        var App = getApp();

        var titleEl = getEl('teacherModalTitle');       if (titleEl) titleEl.textContent = 'Edit Faculty Member';
        var saveLbl = getEl('teacherModalSaveLabel');    if (saveLbl) saveLbl.textContent = 'Update Teacher';
        var idEl    = getEl('teacherId');                if (idEl)    idEl.value = t.id;
        var fnEl    = getEl('teacherFirstName');         if (fnEl)    fnEl.value = t.first_name;
        var lnEl    = getEl('teacherLastName');          if (lnEl)    lnEl.value = t.last_name;
        var unEl    = getEl('teacherUsername');           if (unEl)    { unEl.value = t.username; unEl.disabled = true; }
        var emEl    = getEl('teacherEmail');             if (emEl)    emEl.value = t.email;
        var dpEl    = getEl('teacherDept');              if (dpEl)    dpEl.value = t.department_id;
        var pwEl    = getEl('teacherPassword');          if (pwEl)    pwEl.value = '';
        var acEl    = getEl('teacherIsActive');          if (acEl)    acEl.checked = t.is_active;
        var errEl   = getEl('teacherFormError');         if (errEl)   errEl.style.display = 'none';
        var gpwEl   = getEl('teacherGeneratedPw');       if (gpwEl)   gpwEl.style.display = 'none';

        if (App) App.showModal('teacherModal');
        else { var m = getEl('teacherModal'); if (m) { m.classList.add('is-active'); document.body.style.overflow = 'hidden'; } }
      } catch (err) {
        console.error('Error fetching teacher details:', err);
        alert('Network error while loading teacher details.');
      } finally {
        editBtn.disabled = false;
        editBtn.innerHTML = originalHtml;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEditTeacher);
  } else {
    initEditTeacher();
  }
})(window);
