/* KCC ClassStamp — Student Directory: Cascading Filter Dropdown Script */
(function (window) {
  'use strict';

  function initStudentDirectory() {
    const deptSelect = document.getElementById('filter_dept');
    const progSelect = document.getElementById('filter_prog');
    const defaultProgOpt = document.getElementById('progDefaultOpt');
    if (!deptSelect || !progSelect) return;

    const allProgOptions = Array.from(progSelect.querySelectorAll('option:not(#progDefaultOpt)'));

    function filterPrograms() {
      const selectedDeptId = deptSelect.value;
      const currentSelectedProg = progSelect.value;

      progSelect.innerHTML = '';
      if (defaultProgOpt) {
        progSelect.appendChild(defaultProgOpt);
      }

      let found = false;
      allProgOptions.forEach(opt => {
        const optDept = opt.getAttribute('data-department');
        if (!selectedDeptId || optDept === selectedDeptId) {
          progSelect.appendChild(opt);
          if (opt.value === currentSelectedProg) {
            opt.selected = true;
            found = true;
          }
        }
      });

      if (!found && selectedDeptId && currentSelectedProg && defaultProgOpt) {
        defaultProgOpt.selected = true;
      }
    }

    deptSelect.addEventListener('change', filterPrograms);

    if (deptSelect.value) {
      filterPrograms();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStudentDirectory);
  } else {
    initStudentDirectory();
  }
})(window);
