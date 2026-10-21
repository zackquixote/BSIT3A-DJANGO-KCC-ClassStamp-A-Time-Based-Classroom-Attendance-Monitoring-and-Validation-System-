/* KCC ClassStamp — Teachers: Add Teacher Controller */
(function (window) {
  'use strict';

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }

  function initAddTeacher() {
    // Guard: only run if the add button exists on this page
    var addBtn = getEl('addTeacherBtn');
    if (!addBtn) return;

    addBtn.addEventListener('click', function () {
      var titleEl = getEl('teacherModalTitle');       if (titleEl) titleEl.textContent = 'Add Faculty Member';
      var saveLbl = getEl('teacherModalSaveLabel');    if (saveLbl) saveLbl.textContent = 'Create Teacher';
      var idEl    = getEl('teacherId');                if (idEl)    idEl.value = '';
      var fnEl    = getEl('teacherFirstName');         if (fnEl)    fnEl.value = '';
      var lnEl    = getEl('teacherLastName');          if (lnEl)    lnEl.value = '';
      var unEl    = getEl('teacherUsername');           if (unEl)    { unEl.value = ''; unEl.disabled = false; }
      var emEl    = getEl('teacherEmail');             if (emEl)    emEl.value = '';
      var dpEl    = getEl('teacherDept');              if (dpEl)    dpEl.value = '';
      var pwEl    = getEl('teacherPassword');          if (pwEl)    pwEl.value = '';
      var acEl    = getEl('teacherIsActive');          if (acEl)    acEl.checked = true;
      var errEl   = getEl('teacherFormError');         if (errEl)   errEl.style.display = 'none';
      var gpwEl   = getEl('teacherGeneratedPw');       if (gpwEl)   gpwEl.style.display = 'none';

      var App = getApp();
      if (App) App.showModal('teacherModal');
      else { var m = getEl('teacherModal'); if (m) { m.classList.add('is-active'); document.body.style.overflow = 'hidden'; } }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAddTeacher);
  } else {
    initAddTeacher();
  }
})(window);
