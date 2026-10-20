/* KCC ClassStamp — Classes: Create / Edit Class Modal Controller */
(function (window) {
  'use strict';

  function getEl(id) { return document.getElementById(id); }

  function initClassModal() {
    // Guard: only run if the class modal exists on this page
    var classModal = getEl('classModal');
    if (!classModal) return;

    var classModalHeading = getEl('classModalHeading');
    var classForm         = getEl('classForm');
    var formClassId       = getEl('formClassId');
    var formClassCode     = getEl('formClassCode');
    var formSubjectId     = getEl('formSubjectId');
    var formTeacherId     = getEl('formTeacherId');
    var formAyId          = getEl('formAyId');
    var formCapacity      = getEl('formCapacity');
    var formGraceMinutes  = getEl('formGraceMinutes');

    var closeClassModal   = getEl('closeClassModal');
    var cancelClassModal  = getEl('cancelClassModal');

    // Open Create Modal
    var openCreateBtn = getEl('openCreateClassBtn');
    if (openCreateBtn) {
      openCreateBtn.addEventListener('click', function () {
        if (classModalHeading) classModalHeading.textContent = 'Create Class Section';
        if (formClassId) formClassId.value = '';
        if (classForm) classForm.reset();
        classModal.classList.add('is-open');
      });
    }

    // Event delegation for Edit button clicks
    document.addEventListener('click', function (e) {
      var editBtn = e.target.closest('.btn-edit-class');
      if (!editBtn) return;

      e.preventDefault();
      if (classModalHeading) classModalHeading.textContent = 'Edit Class Section';
      if (formClassId)      formClassId.value      = editBtn.dataset.id || '';
      if (formClassCode)    formClassCode.value    = editBtn.dataset.code || '';
      if (formSubjectId)    formSubjectId.value    = editBtn.dataset.subjectId || '';
      if (formTeacherId)    formTeacherId.value    = editBtn.dataset.teacherId || '';
      if (formAyId)         formAyId.value         = editBtn.dataset.ayId || '';
      if (formCapacity)     formCapacity.value     = editBtn.dataset.capacity || '';
      if (formGraceMinutes) formGraceMinutes.value = editBtn.dataset.grace || '10';
      classModal.classList.add('is-open');
    });

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
