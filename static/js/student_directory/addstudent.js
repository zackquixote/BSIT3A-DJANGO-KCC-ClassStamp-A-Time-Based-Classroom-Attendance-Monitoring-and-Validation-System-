/* KCC ClassStamp — Student Directory: Add Student Modal Controller */
(function (window) {
  'use strict';

  function initAddStudent() {
    const addStudentBtn = document.getElementById('addStudentBtn');
    if (!addStudentBtn) return;

    // Department & Program cascade in Add Student modal (if present)
    const modalDeptSel = document.getElementById('addStudentDept');
    const modalProgSel = document.getElementById('addStudentProgram');

    modalDeptSel?.addEventListener('change', function () {
      const deptId = this.value;
      if (!modalProgSel) return;
      modalProgSel.querySelectorAll('option').forEach(opt => {
        if (!opt.value) return;
        opt.hidden = deptId ? opt.dataset.dept !== deptId : false;
      });
      if (modalProgSel.selectedOptions[0]?.hidden) modalProgSel.value = '';
    });

    // Open Add Student Modal
    addStudentBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (window.openModal) {
        window.openModal('addStudentModal');
      } else {
        const modal = document.getElementById('addStudentModal');
        if (modal) modal.classList.add('is-active');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAddStudent);
  } else {
    initAddStudent();
  }
})(window);
