/* KCC ClassStamp — Programs: Curriculum Matrix Builder (A-07) */
(function (window) {
  'use strict';

  function getApp() { return window.ProgramsApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  var state = {
    programId: null,
    yearsTotal: 0,
    semesters: [],
    entries: [],
    subjects: []
  };

  function toast(type, message) {
    if (typeof window.toast === 'function') { window.toast(type, message); return; }
    if (window.App && typeof window.App.toast === 'function') { window.App.toast(type, message); }
  }

  function showModal(id) {
    var App = getApp();
    if (App && App.showModal) { App.showModal(id); return; }
    if (typeof window.openModal === 'function') { window.openModal(id); return; }
    var modal = getEl(id);
    if (modal) modal.classList.add('is-active');
  }

  function hideModal(id) {
    var App = getApp();
    if (App && App.hideModal) { App.hideModal(id); return; }
    if (typeof window.closeModal === 'function') { window.closeModal(id); return; }
    var modal = getEl(id);
    if (modal) modal.classList.remove('is-active');
  }

  function showError(message) {
    var box = getEl('curriculumMatrixError');
    var msg = getEl('curriculumMatrixErrorMsg');
    if (box) box.style.display = 'flex';
    if (msg) msg.textContent = message;
  }

  function hideError() {
    var box = getEl('curriculumMatrixError');
    if (box) box.style.display = 'none';
  }

  function makeChip(entry) {
    var chip = document.createElement('span');
    chip.className = 'curriculum-chip';

    var code = document.createElement('strong');
    code.textContent = entry.subject_code;
    chip.appendChild(code);

    chip.appendChild(document.createTextNode(' ' + (entry.subject_name || '')));

    var removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'curriculum-chip-remove';
    removeBtn.title = 'Remove ' + (entry.subject_code || '') + ' from this year/semester';
    removeBtn.setAttribute('data-entry-id', entry.id);
    var icon = document.createElement('i');
    icon.className = 'fas fa-xmark';
    removeBtn.appendChild(icon);
    chip.appendChild(removeBtn);

    return chip;
  }

  function renderGrid() {
    var grid = getEl('curriculumGrid');
    if (!grid) return;
    grid.innerHTML = '';

    var table = document.createElement('table');
    table.className = 'curriculum-table';

    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    var corner = document.createElement('th');
    corner.textContent = 'Year \\ Semester';
    headRow.appendChild(corner);
    state.semesters.forEach(function (sem) {
      var th = document.createElement('th');
      th.textContent = sem.label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    for (var year = 1; year <= state.yearsTotal; year++) {
      var row = document.createElement('tr');
      var yearCell = document.createElement('th');
      yearCell.textContent = 'Year ' + year;
      row.appendChild(yearCell);

      state.semesters.forEach(function (sem) {
        var cell = document.createElement('td');
        cell.setAttribute('data-year', year);
        cell.setAttribute('data-semester', sem.value);

        var cellEntries = state.entries.filter(function (e) {
          return e.year_level === year && e.semester === sem.value;
        });

        if (cellEntries.length === 0) {
          cell.classList.add('curriculum-cell-empty');
          cell.textContent = '\u2014';
        } else {
          var list = document.createElement('div');
          list.className = 'curriculum-chip-list';
          cellEntries.forEach(function (entry) {
            list.appendChild(makeChip(entry));
          });
          cell.appendChild(list);
        }
        row.appendChild(cell);
      });

      tbody.appendChild(row);
    }
    table.appendChild(tbody);
    grid.appendChild(table);
  }

  function populateSelects() {
    var yearSelect = getEl('curriculumYearSelect');
    var semSelect = getEl('curriculumSemesterSelect');
    var subjSelect = getEl('curriculumSubjectSelect');

    if (yearSelect) {
      yearSelect.innerHTML = '<option value="">Select Year Level</option>';
      for (var y = 1; y <= state.yearsTotal; y++) {
        var opt = document.createElement('option');
        opt.value = y;
        opt.textContent = 'Year ' + y;
        yearSelect.appendChild(opt);
      }
    }

    if (semSelect) {
      semSelect.innerHTML = '<option value="">Select Semester</option>';
      state.semesters.forEach(function (sem) {
        var opt = document.createElement('option');
        opt.value = sem.value;
        opt.textContent = sem.label;
        semSelect.appendChild(opt);
      });
    }

    if (subjSelect) {
      subjSelect.innerHTML = '<option value="">Select Subject</option>';
      state.subjects.forEach(function (s) {
        var opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.code + ' — ' + s.name;
        subjSelect.appendChild(opt);
      });
    }
  }

  function loadMatrix(button) {
    var url = button.getAttribute('data-curriculum-url');
    state.programId = button.getAttribute('data-program-id');
    var code = button.getAttribute('data-program-code') || '';

    var title = getEl('curriculumMatrixTitle');
    if (title) title.textContent = 'Curriculum Matrix — ' + code;

    var grid = getEl('curriculumGrid');
    if (grid) grid.innerHTML = '<p class="text-muted text-sm"><i class="fas fa-spinner fa-spin"></i> Loading curriculum…</p>';
    hideError();
    showModal('curriculumMatrixModal');

    fetch(url, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCSRF()
      }
    })
    .then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    })
    .then(function (result) {
      if (!result.data.ok) {
        throw new Error(result.data.error || 'Unable to load curriculum matrix.');
      }
      state.yearsTotal = result.data.years_total || 0;
      state.semesters = result.data.semesters || [];
      state.entries = result.data.entries || [];
      state.subjects = result.data.subjects || [];
      populateSelects();
      renderGrid();
    })
    .catch(function (err) {
      if (grid) grid.innerHTML = '';
      showError(err && err.message ? err.message : 'Unable to load curriculum matrix.');
    });
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCSRF(),
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: body
    }).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function toFormBody(params) {
    return Object.keys(params).map(function (key) {
      return encodeURIComponent(key) + '=' + encodeURIComponent(params[key]);
    }).join('&');
  }

  function initCurriculumMatrix() {
    var modal = getEl('curriculumMatrixModal');
    if (!modal) return;

    document.addEventListener('click', function (e) {
      var openBtn = e.target.closest('.js-curriculum-matrix-btn');
      if (openBtn) {
        e.preventDefault();
        loadMatrix(openBtn);
        return;
      }

      var removeBtn = e.target.closest('.curriculum-chip-remove');
      if (removeBtn) {
        e.preventDefault();
        var entryId = removeBtn.getAttribute('data-entry-id');
        if (!entryId) return;
        removeBtn.disabled = true;
        var prefix = modal.getAttribute('data-remove-url-prefix') || '/programs/curriculum/remove/';
        postJSON(prefix + entryId + '/', '')
        .then(function (result) {
          if (!result.data.ok) {
            throw new Error(result.data.error || 'Unable to remove curriculum entry.');
          }
          state.entries = state.entries.filter(function (en) {
            return String(en.id) !== String(entryId);
          });
          renderGrid();
          toast('success', result.data.message || 'Curriculum entry removed.');
        })
        .catch(function (err) {
          removeBtn.disabled = false;
          showError(err && err.message ? err.message : 'Unable to remove curriculum entry.');
          if (err && err.message) toast('error', err.message);
        });
      }
    });

    var addForm = getEl('curriculumAddForm');
    if (addForm) {
      addForm.addEventListener('submit', function (e) {
        e.preventDefault();
        hideError();

        var subjectId = getEl('curriculumSubjectSelect').value;
        var yearLevel = getEl('curriculumYearSelect').value;
        var semester = getEl('curriculumSemesterSelect').value;
        if (!subjectId || !yearLevel || !semester) {
          showError('Please select a subject, year level, and semester.');
          return;
        }

        var addBtn = getEl('curriculumAddBtn');
        if (addBtn) addBtn.disabled = true;

        var assignUrl = modal.getAttribute('data-assign-url') || '/programs/curriculum/assign/';
        postJSON(assignUrl, toFormBody({
          program_id: state.programId,
          subject_id: subjectId,
          year_level: yearLevel,
          semester: semester
        }))
        .then(function (result) {
          if (addBtn) addBtn.disabled = false;
          if (!result.data.ok) {
            throw new Error(result.data.error || 'Unable to assign subject.');
          }
          if (result.data.entry) {
            state.entries.push(result.data.entry);
            renderGrid();
          }
          toast('success', result.data.message || 'Subject assigned to curriculum.');
        })
        .catch(function (err) {
          if (addBtn) addBtn.disabled = false;
          var message = err && err.message ? err.message : 'Unable to assign subject.';
          showError(message);
          if (err && err.message) toast('error', message);
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCurriculumMatrix);
  } else {
    initCurriculumMatrix();
  }
})(window);
