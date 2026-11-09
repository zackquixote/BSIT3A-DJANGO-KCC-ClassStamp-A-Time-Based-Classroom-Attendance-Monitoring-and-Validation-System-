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
    programCode: '',
    matrixUrl: '',
    yearsTotal: 0,
    semesters: [],
    entries: [],
    subjects: [],
    version: null,
    draftVersion: null,
    approvedVersion: null,
    canEdit: false,
    isLegacy: false,
    terms: []
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

    var title = document.createElement('span');
    title.className = 'curriculum-chip-title';
    title.textContent = entry.subject_name || '';
    chip.appendChild(title);

    var units = document.createElement('span');
    units.className = 'curriculum-chip-units';
    units.textContent = entry.subject_units ? entry.subject_units + ' units' : '';
    if (units.textContent) chip.appendChild(units);
    var typeBadge = document.createElement(state.canEdit ? 'button' : 'span');
    typeBadge.className = 'badge badge--' + (entry.is_major ? 'purple' : 'muted') +
      ' badge--xs' + (state.canEdit ? ' curriculum-chip-major-toggle' : '');
    if (state.canEdit) {
      typeBadge.type = 'button';
      typeBadge.setAttribute('data-entry-id', entry.id);
      typeBadge.title = 'Click to mark as ' + (entry.is_major ? 'non-major' : 'major');
      typeBadge.setAttribute(
        'aria-label',
        'Mark ' + (entry.subject_code || 'subject') + ' as ' +
          (entry.is_major ? 'non-major' : 'major')
      );
    }
    typeBadge.textContent = entry.is_major ? 'Major' : 'Non-major';
    chip.appendChild(typeBadge);

    if (state.canEdit) {
      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'curriculum-chip-remove';
      removeBtn.title = 'Remove ' + (entry.subject_code || '') + ' from this year/semester';
      removeBtn.setAttribute('data-entry-id', entry.id);
      var icon = document.createElement('i');
      icon.className = 'fas fa-xmark';
      removeBtn.appendChild(icon);
      chip.appendChild(removeBtn);
    }

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
          cell.textContent = '—';
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

  function setFormEnabled(enabled) {
    var addForm = getEl('curriculumAddForm');
    if (!addForm) return;
    addForm.querySelectorAll('select, input, button').forEach(function (el) {
      el.disabled = !enabled;
    });
    var note = getEl('curriculumReadOnlyNote');
    if (note) note.style.display = enabled ? 'none' : 'flex';
    var lockedNotice = getEl('curriculumFormLockedNotice');
    if (lockedNotice) lockedNotice.style.display = enabled ? 'none' : 'block';
  }

  function versionBadge(label, tone) {
    var badge = document.createElement('span');
    badge.className = 'badge badge--' + tone;
    badge.textContent = label;
    return badge;
  }

  function renderVersionBar() {
    var bar = getEl('curriculumVersionBar');
    var summary = getEl('curriculumVersionSummary');
    var createBtn = getEl('curriculumCreateDraftBtn');
    var approveWrap = getEl('curriculumApproveWrap');
    if (!bar || !summary) return;

    bar.style.display = 'flex';
    summary.innerHTML = '';

    if (state.draftVersion) {
      summary.appendChild(versionBadge('Draft v' + state.draftVersion.version_number, 'warning'));
      var text = document.createElement('span');
      text.className = 'text-sm';
      text.textContent = state.approvedVersion
        ? 'Editing the draft. Approved v' + state.approvedVersion.version_number +
          ' stays in force until you approve this draft.'
        : 'Editing the first draft. It becomes official when approved.';
      summary.appendChild(text);
    } else if (state.approvedVersion) {
      summary.appendChild(versionBadge('Approved v' + state.approvedVersion.version_number, 'success'));
      var approvedText = document.createElement('span');
      approvedText.className = 'text-sm';
      approvedText.textContent = 'This approved curriculum is read-only.';
      summary.appendChild(approvedText);
    } else {
      summary.appendChild(versionBadge('No version yet', 'muted'));
      var legacyText = document.createElement('span');
      legacyText.className = 'text-sm';
      legacyText.textContent = state.isLegacy
        ? 'Legacy mappings are shown. Create a draft to start version control.'
        : 'Create the first draft to start building this curriculum.';
      summary.appendChild(legacyText);
    }

    if (createBtn) {
      createBtn.style.display = state.draftVersion ? 'none' : 'inline-flex';
    }
    if (approveWrap) {
      var select = getEl('curriculumEffectiveTerm');
      if (state.draftVersion) {
        approveWrap.style.display = 'flex';
        if (select && select.options.length === 0) {
          var allOption = document.createElement('option');
          allOption.value = '';
          allOption.textContent = 'No effective term (applies to all)';
          select.appendChild(allOption);
          state.terms.forEach(function (term) {
            var opt = document.createElement('option');
            opt.value = term.id;
            opt.textContent = term.name + (term.is_active ? ' (active)' : '');
            select.appendChild(opt);
          });
        }
      } else {
        approveWrap.style.display = 'none';
      }
    }
    setFormEnabled(state.canEdit);
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
        var sOpt = document.createElement('option');
        sOpt.value = sem.value;
        sOpt.textContent = sem.label;
        semSelect.appendChild(sOpt);
      });
    }

    if (subjSelect) {
      subjSelect.innerHTML = '<option value="">Select Subject</option>';
      state.subjects.forEach(function (s) {
        var subOpt = document.createElement('option');
        subOpt.value = s.id;
        subOpt.textContent = s.code + ' — ' + s.name;
        subjSelect.appendChild(subOpt);
      });
    }
  }

  function fetchMatrix() {
    var grid = getEl('curriculumGrid');
    if (grid) grid.innerHTML = '<p class="text-muted text-sm"><i class="fas fa-spinner fa-spin"></i> Loading curriculum…</p>';
    hideError();

    return fetch(state.matrixUrl, {
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
      state.version = result.data.version || null;
      state.draftVersion = result.data.draft_version || null;
      state.approvedVersion = result.data.approved_version || null;
      state.canEdit = !!result.data.can_edit;
      state.isLegacy = !!result.data.is_legacy;
      state.terms = result.data.terms || [];

      var filter = getEl('curriculumEffectiveTerm');
      if (filter) filter.innerHTML = '';

      populateSelects();
      renderGrid();
      renderVersionBar();
    })
    .catch(function (err) {
      if (grid) grid.innerHTML = '';
      showError(err && err.message ? err.message : 'Unable to load curriculum matrix.');
    });
  }

  function loadMatrix(button) {
    state.matrixUrl = button.getAttribute('data-curriculum-url');
    state.programId = button.getAttribute('data-program-id');
    state.programCode = button.getAttribute('data-program-code') || '';

    var title = getEl('curriculumMatrixTitle');
    if (title) title.textContent = 'Curriculum Matrix — ' + state.programCode;

    showModal('curriculumMatrixModal');
    return fetchMatrix();
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

  function templateUrl(modal, attribute, fallback) {
    var template = modal.getAttribute(attribute) || fallback;
    return template.replace('999999', state.programId);
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
        return;
      }

      var majorBtn = e.target.closest('.curriculum-chip-major-toggle');
      if (majorBtn) {
        e.preventDefault();
        var majorEntryId = majorBtn.getAttribute('data-entry-id');
        var majorEntry = state.entries.find(function (entry) {
          return String(entry.id) === String(majorEntryId);
        });
        if (!majorEntryId || !majorEntry) return;
        majorBtn.disabled = true;
        var majorPrefix = modal.getAttribute('data-major-url-prefix') ||
          '/programs/curriculum/major/';
        postJSON(majorPrefix + majorEntryId + '/', toFormBody({
          is_major: majorEntry.is_major ? 'false' : 'true'
        }))
        .then(function (result) {
          if (!result.data.ok) {
            throw new Error(result.data.error || 'Unable to update subject classification.');
          }
          state.entries = state.entries.map(function (entry) {
            return String(entry.id) === String(majorEntryId) ? result.data.entry : entry;
          });
          renderGrid();
          toast('success', result.data.message || 'Subject classification updated.');
        })
        .catch(function (err) {
          majorBtn.disabled = false;
          var message = err && err.message ? err.message : 'Unable to update subject classification.';
          showError(message);
          if (err && err.message) toast('error', message);
        });
        return;
      }

      var draftBtn = e.target.closest('#curriculumCreateDraftBtn, .js-create-draft-btn');
      if (draftBtn) {
        e.preventDefault();
        draftBtn.disabled = true;
        var draftUrl = templateUrl(
          modal,
          'data-draft-url-template',
          '/programs/999999/curriculum/draft/'
        );
        postJSON(draftUrl, '')
        .then(function (result) {
          draftBtn.disabled = false;
          if (!result.data.ok) {
            throw new Error(result.data.error || 'Unable to create a draft.');
          }
          toast('success', result.data.message || 'Draft created.');
          return fetchMatrix();
        })
        .catch(function (err) {
          draftBtn.disabled = false;
          var message = err && err.message ? err.message : 'Unable to create a draft.';
          showError(message);
          if (err && err.message) toast('error', message);
        });
        return;
      }

      var approveBtn = e.target.closest('#curriculumApproveBtn');
      if (approveBtn) {
        e.preventDefault();
        if (!state.draftVersion) return;
        approveBtn.disabled = true;
        var approveUrl = templateUrl(
          modal,
          'data-approve-url-template',
          '/programs/999999/curriculum/approve/'
        );
        var termSelect = getEl('curriculumEffectiveTerm');
        postJSON(approveUrl, toFormBody({
          version_id: state.draftVersion.id,
          effective_from: termSelect ? termSelect.value : ''
        }))
        .then(function (result) {
          approveBtn.disabled = false;
          if (!result.data.ok) {
            throw new Error(result.data.error || 'Unable to approve the draft.');
          }
          toast('success', result.data.message || 'Curriculum approved.');
          return fetchMatrix();
        })
        .catch(function (err) {
          approveBtn.disabled = false;
          var message = err && err.message ? err.message : 'Unable to approve the draft.';
          showError(message);
          if (err && err.message) toast('error', message);
        });
      }
    });

    var addForm = getEl('curriculumAddForm');
    if (addForm) {
      addForm.addEventListener('submit', function (e) {
        e.preventDefault();
        hideError();

        if (!state.canEdit) {
          showError('This curriculum version is read-only. Create a draft to make changes.');
          return;
        }

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
          semester: semester,
          is_major: getEl('curriculumMajorCheckbox').checked ? 'true' : 'false'
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
          addForm.reset();
          if (!state.draftVersion) {
            return fetchMatrix().then(function () {
              toast('success', result.data.message || 'Subject assigned to curriculum.');
            });
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

    var openProgramId = modal.getAttribute('data-open-program-id');
    if (openProgramId) {
      var openButton = Array.prototype.find.call(
        document.querySelectorAll('.js-curriculum-matrix-btn'),
        function (button) {
          return button.getAttribute('data-program-id') === openProgramId;
        }
      );
      if (openButton) loadMatrix(openButton);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCurriculumMatrix);
  } else {
    initCurriculumMatrix();
  }
})(window);
