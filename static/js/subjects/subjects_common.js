/* KCC ClassStamp — Subjects: Common Utilities & Cascade Helpers */
(function (window) {
  'use strict';

  window.SubjectsApp = window.SubjectsApp || {};

  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) {
      return meta.getAttribute('content');
    }
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
      return input.value;
    }
    if (window.SUBJECTS_CONFIG && window.SUBJECTS_CONFIG.csrf) {
      return window.SUBJECTS_CONFIG.csrf;
    }
    return '';
  }

  function getProgramsList() {
    const el = document.getElementById('programsData');
    if (el && el.textContent) {
      try {
        return JSON.parse(el.textContent);
      } catch (err) {
        console.error('Failed to parse programsData JSON:', err);
      }
    }
    if (window.SUBJECTS_CONFIG && Array.isArray(window.SUBJECTS_CONFIG.programs)) {
      return window.SUBJECTS_CONFIG.programs;
    }
    return [];
  }

  let ALL_PROGRAMS = getProgramsList();

  function showAlert(el, msg, type = 'error') {
    if (!el) return;
    el.style.display = 'block';
    el.className = `toast toast--${type} mb-4`;
    el.textContent = msg;
    if (type === 'success') setTimeout(() => { el.style.display = 'none'; }, 4000);
  }

  function ordinalSuffix(n) {
    const num = parseInt(n, 10);
    return num === 1 ? '1st' : num === 2 ? '2nd' : num === 3 ? '3rd' : `${num}th`;
  }

  function showModal(id) {
    if (typeof window.openModal === 'function') {
      window.openModal(id);
    } else {
      const el = document.getElementById(id);
      if (el) {
        el.classList.add('is-active');
        document.body.style.overflow = 'hidden';
      }
    }
  }

  function hideModal(id) {
    if (typeof window.closeModal === 'function') {
      window.closeModal(id);
    } else {
      const el = document.getElementById(id);
      if (el) {
        el.classList.remove('is-active');
        document.body.style.overflow = '';
      }
    }
  }

  function populatePrograms(programSel, deptId, yearSel) {
    if (!programSel) return;
    if (!ALL_PROGRAMS || ALL_PROGRAMS.length === 0) {
      ALL_PROGRAMS = getProgramsList();
    }
    programSel.innerHTML = '<option value="">— program —</option>';
    const filtered = deptId
      ? ALL_PROGRAMS.filter(p => String(p.dept_id) === String(deptId))
      : ALL_PROGRAMS;
    filtered.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.code} — ${p.name}`;
      opt.dataset.years = p.years_total;
      programSel.appendChild(opt);
    });
    programSel.disabled = filtered.length === 0;
    if (yearSel) {
      yearSel.innerHTML = '<option value="">— year —</option>';
      yearSel.disabled = true;
    }
  }

  function populateYears(programSel, yearSel) {
    if (!programSel || !yearSel) return;
    const opt = programSel.selectedOptions[0];
    const maxYears = parseInt(opt?.dataset.years || '0', 10);
    yearSel.innerHTML = '<option value="">— year —</option>';
    yearSel.disabled = maxYears === 0;
    for (let i = 1; i <= maxYears; i++) {
      const o = document.createElement('option');
      o.value = i;
      o.textContent = `${ordinalSuffix(i)} Year`;
      yearSel.appendChild(o);
    }
  }

  function initCommon() {
    if (!ALL_PROGRAMS || ALL_PROGRAMS.length === 0) {
      ALL_PROGRAMS = getProgramsList();
    }

    // Filter bar cascade
    const filterDeptEl = document.getElementById('filterDept');
    const filterProgEl = document.getElementById('filterProgram');

    filterDeptEl?.addEventListener('change', function () {
      const deptId = this.value;
      if (!filterProgEl) return;
      filterProgEl.querySelectorAll('option').forEach(opt => {
        if (!opt.value) return;
        opt.hidden = deptId ? opt.dataset.dept !== deptId : false;
      });
      if (filterProgEl.selectedOptions[0]?.hidden) filterProgEl.value = '';
    });

    if (filterDeptEl?.value && filterProgEl) {
      const deptId = filterDeptEl.value;
      filterProgEl.querySelectorAll('option').forEach(opt => {
        if (!opt.value) return;
        opt.hidden = opt.dataset.dept !== deptId;
      });
    }

    // Modal dismiss bindings
    ['subjectModalClose', 'subjectModalCancel'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', () => hideModal('subjectModal'));
    });
    ['curriculumModalClose', 'curriculumModalClose2'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', () => hideModal('curriculumModal'));
    });
    ['subjectDeleteClose', 'subjectDeleteCancel'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', () => hideModal('subjectDeleteModal'));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCommon);
  } else {
    initCommon();
  }

  // Export to namespace
  Object.defineProperty(window.SubjectsApp, 'CSRF', {
    get: getCSRFToken,
    configurable: true,
    enumerable: true
  });
  Object.defineProperty(window.SubjectsApp, 'ALL_PROGRAMS', {
    get: function () {
      if (!ALL_PROGRAMS || ALL_PROGRAMS.length === 0) {
        ALL_PROGRAMS = getProgramsList();
      }
      return ALL_PROGRAMS;
    },
    configurable: true,
    enumerable: true
  });
  window.SubjectsApp.getCSRFToken = getCSRFToken;
  window.SubjectsApp.showAlert = showAlert;
  window.SubjectsApp.ordinalSuffix = ordinalSuffix;
  window.SubjectsApp.showModal = showModal;
  window.SubjectsApp.hideModal = hideModal;
  window.SubjectsApp.populatePrograms = populatePrograms;
  window.SubjectsApp.populateYears = populateYears;
})(window);
