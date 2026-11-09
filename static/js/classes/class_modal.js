/* KCC ClassStamp — Classes: Edit Class Modal Controller */
(function (window) {
  'use strict';

  function getEl(id) { return document.getElementById(id); }

  function initClassModal() {
    // Guard: only run if the class modal exists on this page
    var classModal = getEl('classModal');
    if (!classModal) return;

    var classForm         = getEl('classForm');
    var formClassId       = getEl('formClassId');
    var formClassCode     = getEl('formClassCode');
    var formSubjectId     = getEl('formSubjectId');
    var formTeacherId     = getEl('formTeacherId');
    var formProgramId     = getEl('formProgramId');
    var formYearLevel     = getEl('formYearLevel');
    var formAyId          = getEl('formAyId');
    var formCapacity      = getEl('formCapacity');
    var formGraceMinutes  = getEl('formGraceMinutes');

    var closeClassModal   = getEl('closeClassModal');
    var cancelClassModal  = getEl('cancelClassModal');

    // Event delegation for Edit button clicks
    document.addEventListener('click', function (e) {
      var editBtn = e.target.closest('.btn-edit-class');
      if (!editBtn) return;

      e.preventDefault();
      if (formClassId)      formClassId.value      = editBtn.dataset.id || '';
      if (formClassCode)    formClassCode.value    = editBtn.dataset.code || '';
      if (formSubjectId)    formSubjectId.value    = editBtn.dataset.subjectId || '';
      if (formTeacherId)    formTeacherId.value    = editBtn.dataset.teacherId || '';
      if (formProgramId)    formProgramId.value    = editBtn.dataset.programId || '';
      if (formYearLevel)    formYearLevel.value    = editBtn.dataset.yearLevel || '';
      if (formAyId)         formAyId.value         = editBtn.dataset.ayId || '';
      if (formCapacity)     formCapacity.value     = editBtn.dataset.capacity || '';
      if (formGraceMinutes) formGraceMinutes.value = editBtn.dataset.grace || '10';
      syncTeacherScoping();
      classModal.classList.add('is-open');
    });

    function syncTeacherScoping() {
      if (!formTeacherId || !formProgramId) return;
      var selProgOpt = formProgramId.options[formProgramId.selectedIndex];
      var deptId = selProgOpt ? selProgOpt.getAttribute('data-dept-id') : null;
      var optgroups = formTeacherId.querySelectorAll('optgroup');
      optgroups.forEach(function (og) {
        var ogDeptId = og.getAttribute('data-dept-id');
        if (!deptId || !ogDeptId || ogDeptId === deptId) {
          og.style.opacity = '1';
        } else {
          og.style.opacity = '0.65';
        }
      });
    }

    if (formProgramId) {
      formProgramId.addEventListener('change', syncTeacherScoping);
    }

    // Close handlers
    function closeClassModalFn() { classModal.classList.remove('is-open'); }
    if (closeClassModal)  closeClassModal.addEventListener('click', closeClassModalFn);
    if (cancelClassModal) cancelClassModal.addEventListener('click', closeClassModalFn);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initClassModal);
  } else {
    initClassModal();
  }
})(window);
