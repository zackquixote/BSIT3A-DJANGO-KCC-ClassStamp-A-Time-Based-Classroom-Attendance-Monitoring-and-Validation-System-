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
    matrixBaseUrl: '',
    yearsTotal: 0,
    semesters: [],
    entries: [],
    subjects: [],
    version: null,
    draftVersion: null,
    approvedVersion: null,
    versions: [],
    selectedVersionId: null,
    canEdit: false,
    isLegacy: false,
    terms: [],
    includeSummer: false,
    viewMode: 'prospectus'
  };

  function yearNumberToWord(year) {
    var words = ['First Year', 'Second Year', 'Third Year', 'Fourth Year', 'Fifth Year', 'Sixth Year', 'Seventh Year', 'Eighth Year'];
    return words[year - 1] || ('Year ' + year);
  }

  function semesterNumberToWord(sem) {
    if (sem === 1) return 'First Semester';
    if (sem === 2) return 'Second Semester';
    if (sem === 3) return 'Summer Term';
    return 'Semester ' + sem;
  }

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
    var card = document.createElement('div');
    card.className = 'curriculum-subject-card' + (entry.is_major ? ' is-major' : '');

    var top = document.createElement('div');
    top.className = 'curriculum-card-top';

    var codeBadge = document.createElement('span');
    codeBadge.className = 'badge badge--' + (entry.is_major ? 'purple' : 'blue') + ' font-mono font-semibold';
    codeBadge.style.fontSize = '0.72rem';
    codeBadge.textContent = entry.subject_code;
    top.appendChild(codeBadge);

    var units = entry.subject_units || 3;
    var unitsBadge = document.createElement('span');
    unitsBadge.className = 'badge badge--teal';
    unitsBadge.style.fontSize = '0.7rem';
    unitsBadge.textContent = units + 'u';
    unitsBadge.title = units + ' Credit Units';
    top.appendChild(unitsBadge);


    var typeBadge = document.createElement(state.canEdit ? 'button' : 'span');
    typeBadge.className = 'badge badge--' + (entry.is_major ? 'gold' : 'muted') +
      ' badge--xs' + (state.canEdit ? ' curriculum-chip-major-toggle' : '');
    if (state.canEdit) {
      typeBadge.type = 'button';
      typeBadge.setAttribute('data-entry-id', entry.id);
      typeBadge.title = 'Click to toggle major / non-major';
      typeBadge.setAttribute(
        'aria-label',
        'Mark ' + (entry.subject_code || 'subject') + ' as ' +
          (entry.is_major ? 'non-major' : 'major')
      );
    }
    typeBadge.textContent = entry.is_major ? 'Major' : 'Core / GenEd';
    top.appendChild(typeBadge);

    if (state.canEdit) {
      var removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'curriculum-chip-remove';
      removeBtn.title = 'Remove ' + (entry.subject_code || '') + ' from this year/semester';
      removeBtn.setAttribute('data-entry-id', entry.id);
      var icon = document.createElement('i');
      icon.className = 'fas fa-xmark';
      removeBtn.appendChild(icon);
      top.appendChild(removeBtn);
    }

    card.appendChild(top);

    var title = document.createElement('div');
    title.className = 'curriculum-card-title';
    title.textContent = entry.subject_name || '';
    card.appendChild(title);

    if (entry.teachers && entry.teachers.length > 0) {
      var instructorRow = document.createElement('div');
      instructorRow.className = 'curriculum-card-instructor';
      instructorRow.innerHTML = '<i class="fas fa-chalkboard-user text-teal" style="font-size:0.68rem;"></i> ' +
        entry.teachers.map(function (t) { return '<span>' + t + '</span>'; }).join(', ');
      card.appendChild(instructorRow);
    }

    return card;
  }

  function updateSummerButton() {
    var btn = getEl('curriculumSummerToggleBtn');
    var text = getEl('curriculumSummerToggleText');
    if (!btn) return;

    if (state.includeSummer) {
      btn.classList.add('is-active');
      btn.style.borderColor = 'rgba(245, 158, 11, 0.6)';
      btn.style.background = 'rgba(245, 158, 11, 0.16)';
      btn.style.color = '#fbbf24';
      if (text) text.innerHTML = '<i class="fas fa-sun text-gold"></i> Summer Term: <strong>Included</strong>';
      btn.title = 'Summer term is currently displayed. Click to hide summer.';
    } else {
      btn.classList.remove('is-active');
      btn.style.borderColor = 'var(--glass-border)';
      btn.style.background = 'transparent';
      btn.style.color = 'var(--text-muted)';
      if (text) text.innerHTML = '<i class="fas fa-sun text-muted" style="opacity: 0.5;"></i> Summer Term: <strong>Excluded</strong>';
      btn.title = 'Summer term is currently hidden. Click to include summer.';
    }
  }

  function updateViewModeButtons() {
    var prosBtn = getEl('curriculumViewProspectusBtn');
    var matBtn = getEl('curriculumViewMatrixBtn');
    if (!prosBtn || !matBtn) return;

    if (state.viewMode === 'prospectus') {
      prosBtn.style.background = 'rgba(59, 130, 246, 0.35)';
      prosBtn.style.color = '#93c5fd';
      prosBtn.style.fontWeight = '600';
      matBtn.style.background = 'transparent';
      matBtn.style.color = 'var(--text-muted)';
      matBtn.style.fontWeight = '400';
    } else {
      matBtn.style.background = 'rgba(59, 130, 246, 0.35)';
      matBtn.style.color = '#93c5fd';
      matBtn.style.fontWeight = '600';
      prosBtn.style.background = 'transparent';
      prosBtn.style.color = 'var(--text-muted)';
      prosBtn.style.fontWeight = '400';
    }
  }

  function renderProspectusView() {
    var grid = getEl('curriculumGrid');
    if (!grid) return;
    grid.innerHTML = '';

    var wrapper = document.createElement('div');
    wrapper.className = 'curriculum-prospectus';

    var semsToShow = state.includeSummer ? [1, 2, 3] : [1, 2];

    for (var year = 1; year <= state.yearsTotal; year++) {
      var yearSection = document.createElement('div');
      yearSection.className = 'curriculum-year-section';

      // Year stats
      var yearEntries = state.entries.filter(function (e) {
        if (!state.includeSummer && e.semester === 3) return false;
        return e.year_level === year;
      });
      var yearUnits = yearEntries.reduce(function (sum, e) {
        return sum + (Number(e.subject_units) || 3);
      }, 0);

      // Header for Year (e.g. FIRST YEAR)
      var yearHeader = document.createElement('div');
      yearHeader.className = 'curriculum-year-header';
      yearHeader.innerHTML =
        '<div class="curriculum-year-title">' +
          '<span class="curriculum-year-badge"><i class="fas fa-graduation-cap"></i> ' + yearNumberToWord(year).toUpperCase() + '</span>' +
          '<span class="curriculum-year-name">' + state.programCode + ' — ' + yearNumberToWord(year) + '</span>' +
        '</div>' +
        '<div class="curriculum-year-stats">' +
          '<span class="badge badge--gold" style="font-size: 0.74rem;"><i class="fas fa-layer-group"></i> ' + yearEntries.length + ' Subject' + (yearEntries.length === 1 ? '' : 's') + '</span>' +
          '<span class="badge badge--teal" style="font-size: 0.74rem;"><i class="fas fa-award"></i> ' + yearUnits + '.0 Units Total</span>' +
        '</div>';
      yearSection.appendChild(yearHeader);

      // Semesters list
      var semsContainer = document.createElement('div');
      semsContainer.className = 'curriculum-prospectus-sems-wrap';

      semsToShow.forEach(function (sem) {
        var semBlock = document.createElement('div');
        semBlock.className = 'curriculum-prospectus-sem' + (sem === 3 ? ' is-summer' : '');

        var semEntries = state.entries.filter(function (e) {
          return e.year_level === year && e.semester === sem;
        });
        var semUnits = semEntries.reduce(function (sum, e) {
          return sum + (Number(e.subject_units) || 3);
        }, 0);

        var semHeader = document.createElement('div');
        semHeader.className = 'curriculum-prospectus-sem-header';
        var semIcon = sem === 3 ? 'fa-sun text-gold' : 'fa-calendar-week text-primary';
        var semTitleColor = sem === 3 ? 'text-gold' : 'text-primary';
        semHeader.innerHTML =
          '<div class="flex items-center gap-2">' +
            '<i class="fas ' + semIcon + '"></i>' +
            '<strong class="' + semTitleColor + '" style="font-size: 0.88rem; letter-spacing: 0.04em; text-transform: uppercase;">' +
              semesterNumberToWord(sem) +
            '</strong>' +
          '</div>' +
          '<div class="text-xs text-muted font-medium">' +
            semEntries.length + ' Subject' + (semEntries.length === 1 ? '' : 's') + ' • ' + semUnits + '.0 Units' +
          '</div>';
        semBlock.appendChild(semHeader);

        if (semEntries.length === 0) {
          var emptyDiv = document.createElement('div');
          emptyDiv.className = 'curriculum-prospectus-empty';
          emptyDiv.innerHTML =
            '<i class="fas fa-folder-open text-muted" style="opacity: 0.5; font-size: 1.1rem;"></i>' +
            '<span>No subjects allocated for ' + semesterNumberToWord(sem) + ' yet.</span>';
          semBlock.appendChild(emptyDiv);
        } else {
          var tableWrap = document.createElement('div');
          tableWrap.className = 'curriculum-prospectus-table-wrap';

          var table = document.createElement('table');
          table.className = 'curriculum-prospectus-table';

          var thead = document.createElement('thead');
          var thRow = document.createElement('tr');
          thRow.innerHTML =
            '<th style="width: 125px;">Subj Code</th>' +
            '<th>Descriptive Title</th>' +
            '<th style="width: 75px; text-align: center;">Units</th>' +
            '<th style="width: 140px; text-align: center;">Classification</th>' +
            '<th style="width: 220px;">Faculty / Handled By</th>' +
            (state.canEdit ? '<th style="width: 65px; text-align: right;">Action</th>' : '');
          thead.appendChild(thRow);
          table.appendChild(thead);

          var tbody = document.createElement('tbody');
          semEntries.forEach(function (entry) {
            var tr = document.createElement('tr');

            // Code
            var tdCode = document.createElement('td');
            tdCode.innerHTML = '<span class="badge badge--' + (entry.is_major ? 'purple' : 'blue') + ' font-mono font-bold" style="font-size: 0.76rem;">' + (entry.subject_code || '') + '</span>';
            tr.appendChild(tdCode);

            // Descriptive Title
            var tdTitle = document.createElement('td');
            tdTitle.innerHTML = '<span class="text-white font-medium" style="font-size: 0.84rem;">' + (entry.subject_name || '') + '</span>';
            tr.appendChild(tdTitle);

            // Units
            var tdUnits = document.createElement('td');
            tdUnits.style.textAlign = 'center';
            tdUnits.innerHTML = '<span class="badge badge--teal font-bold" style="font-size: 0.74rem;">' + (entry.subject_units || 3) + 'u</span>';
            tr.appendChild(tdUnits);

            // Classification
            var tdClass = document.createElement('td');
            tdClass.style.textAlign = 'center';
            if (state.canEdit) {
              var majorBtn = document.createElement('button');
              majorBtn.type = 'button';
              majorBtn.className = 'badge badge--' + (entry.is_major ? 'gold' : 'muted') + ' curriculum-chip-major-toggle';
              majorBtn.style.border = 'none';
              majorBtn.style.cursor = 'pointer';
              majorBtn.setAttribute('data-entry-id', entry.id);
              majorBtn.title = 'Click to toggle Major / Core';
              majorBtn.textContent = entry.is_major ? 'Major' : 'Core / GenEd';
              tdClass.appendChild(majorBtn);
            } else {
              tdClass.innerHTML = '<span class="badge badge--' + (entry.is_major ? 'gold' : 'muted') + '">' + (entry.is_major ? 'Major' : 'Core / GenEd') + '</span>';
            }
            tr.appendChild(tdClass);

            // Faculty
            var tdFaculty = document.createElement('td');
            if (entry.teachers && entry.teachers.length > 0) {
              var teacherBadges = entry.teachers.map(function (t) {
                return '<span class="badge badge--teal" style="font-size: 0.7rem; display: inline-flex; align-items: center; gap: 4px;">' +
                  '<i class="fas fa-chalkboard-user"></i> ' + t +
                '</span>';
              }).join(' ');
              tdFaculty.innerHTML = '<div style="display: flex; flex-wrap: wrap; gap: 4px;">' + teacherBadges + '</div>';
            } else {
              tdFaculty.innerHTML = '<span class="text-muted text-xs" style="opacity: 0.6;">— unassigned</span>';
            }
            tr.appendChild(tdFaculty);

            // Action
            if (state.canEdit) {
              var tdAct = document.createElement('td');
              tdAct.style.textAlign = 'right';
              var rmBtn = document.createElement('button');
              rmBtn.type = 'button';
              rmBtn.className = 'btn btn-outline btn-icon-xs text-danger curriculum-chip-remove';
              rmBtn.setAttribute('data-entry-id', entry.id);
              rmBtn.title = 'Remove ' + (entry.subject_code || '') + ' from curriculum';
              rmBtn.innerHTML = '<i class="fas fa-trash-can"></i>';
              tdAct.appendChild(rmBtn);
              tr.appendChild(tdAct);
            }

            tbody.appendChild(tr);
          });
          table.appendChild(tbody);

          // Subtotal footer
          var tfoot = document.createElement('tfoot');
          var tfRow = document.createElement('tr');
          tfRow.innerHTML =
            '<td colspan="2" class="text-right text-muted font-semibold text-xs" style="text-transform: uppercase; letter-spacing: 0.05em;">' +
              semesterNumberToWord(sem) + ' Subtotal:' +
            '</td>' +
            '<td style="text-align: center;"><span class="font-bold text-teal" style="font-size: 0.82rem;">' + semUnits + '.0u</span></td>' +
            '<td colspan="' + (state.canEdit ? 3 : 2) + '" class="text-xs text-muted font-medium">' +
              semEntries.length + ' Subject' + (semEntries.length === 1 ? '' : 's') +
            '</td>';
          tfoot.appendChild(tfRow);
          table.appendChild(tfoot);

          tableWrap.appendChild(table);
          semBlock.appendChild(tableWrap);
        }

        semsContainer.appendChild(semBlock);
      });

      yearSection.appendChild(semsContainer);
      wrapper.appendChild(yearSection);
    }

    grid.appendChild(wrapper);
  }

  function renderMatrixTableView() {
    var grid = getEl('curriculumGrid');
    if (!grid) return;
    grid.innerHTML = '';

    var visibleSemesters = state.semesters.filter(function (sem) {
      if (sem.value === 3) {
        return !!state.includeSummer;
      }
      return true;
    });

    var table = document.createElement('table');
    table.className = 'curriculum-table';

    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    var corner = document.createElement('th');
    corner.textContent = 'Year Level';
    headRow.appendChild(corner);
    visibleSemesters.forEach(function (sem) {
      var th = document.createElement('th');
      var icon = sem.value === 3 ? 'fa-sun text-gold' : 'fa-calendar-week';
      th.innerHTML = '<i class="fas ' + icon + '" style="margin-right:4px;"></i> ' + sem.label;
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

      visibleSemesters.forEach(function (sem) {
        var cell = document.createElement('td');
        cell.setAttribute('data-year', year);
        cell.setAttribute('data-semester', sem.value);

        var cellEntries = state.entries.filter(function (e) {
          return e.year_level === year && e.semester === sem.value;
        });

        if (cellEntries.length === 0) {
          cell.classList.add('curriculum-cell-empty');
          var emptySlot = document.createElement('div');
          emptySlot.className = 'curriculum-empty-slot';
          emptySlot.innerHTML = '<i class="fas fa-minus-circle"></i><span>No subjects allocated</span>';
          cell.appendChild(emptySlot);
        } else {
          var totalUnits = cellEntries.reduce(function (sum, e) {
            return sum + (Number(e.subject_units) || 3);
          }, 0);

          var statsBar = document.createElement('div');
          statsBar.className = 'curriculum-cell-stats';
          statsBar.innerHTML =
            '<span class="badge badge--gold" style="font-size:0.7rem;"><i class="fas fa-layer-group"></i> ' + cellEntries.length + ' Subject' + (cellEntries.length > 1 ? 's' : '') + '</span>' +
            '<span class="badge badge--teal" style="font-size:0.7rem;"><i class="fas fa-award"></i> ' + totalUnits + ' Units</span>';
          cell.appendChild(statsBar);

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

  function renderGrid() {
    updateSummerButton();
    updateViewModeButtons();
    if (state.viewMode === 'prospectus') {
      renderProspectusView();
    } else {
      renderMatrixTableView();
    }
  }

  function setFormEnabled(enabled) {
    var lockedNotice = getEl('curriculumFormLockedNotice');
    var editableWrap = getEl('curriculumFormEditableWrap');
    var addForm = getEl('curriculumAddForm');
    var note = getEl('curriculumReadOnlyNote');

    if (lockedNotice) lockedNotice.style.display = enabled ? 'none' : 'flex';
    if (editableWrap) editableWrap.style.display = enabled ? 'block' : 'none';
    if (note) note.style.display = enabled ? 'none' : 'flex';
    if (addForm) {
      addForm.querySelectorAll('select, input, button').forEach(function (el) {
        el.disabled = !enabled;
      });
    }
  }

  function versionBadge(label, tone) {
    var badge = document.createElement('span');
    badge.className = 'badge badge--' + tone;
    badge.textContent = label;
    return badge;
  }

  function batchYearOf(version) {
    return version && version.batch_year ? version.batch_year : '';
  }

  function renderBatchSelector() {
    var wrap = getEl('curriculumBatchWrap');
    var select = getEl('curriculumBatchSelect');
    if (!wrap || !select) return;

    // Only offer a choice when a program actually has multiple batches/versions.
    if (!state.versions || state.versions.length <= 1) {
      wrap.style.display = 'none';
      return;
    }

    wrap.style.display = 'flex';
    select.innerHTML = '';
    state.versions.forEach(function (v) {
      var opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = v.batch_label || (v.label + ' (' + v.status_label + ')');
      select.appendChild(opt);
    });
    if (state.selectedVersionId) {
      select.value = String(state.selectedVersionId);
    }
  }

  function resetToDefaultVersion() {
    state.selectedVersionId = null;
    state.matrixUrl = state.matrixBaseUrl;
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
      summary.appendChild(versionBadge(batchYearOf(state.draftVersion) || 'Draft', 'warning'));
      var text = document.createElement('span');
      text.className = 'text-sm';
      text.textContent = state.approvedVersion
        ? 'Editing the draft. The approved ' + (batchYearOf(state.approvedVersion) || 'curriculum') +
          ' stays in force until you approve this draft.'
        : 'Editing the first draft. It becomes official when approved.';
      summary.appendChild(text);
    } else if (state.approvedVersion) {
      summary.appendChild(versionBadge(batchYearOf(state.approvedVersion) || 'Approved', 'success'));
      var approvedText = document.createElement('span');
      approvedText.className = 'text-sm';
      approvedText.textContent = 'Approved · this curriculum is read-only.';
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

  function updateMajorCheckboxForSubject(subjId) {
    var majorCb = getEl('curriculumMajorCheckbox');
    var hint = getEl('curriculumMajorHint');
    if (!majorCb) return;

    if (!subjId) {
      majorCb.disabled = false;
      if (hint) { hint.textContent = 'Unchecked = Core / GenEd'; hint.style.color = ''; }
      return;
    }

    var subj = state.subjects.find(function (s) { return String(s.id) === String(subjId); });
    if (!subj) {
      majorCb.disabled = false;
      if (hint) { hint.textContent = 'Unchecked = Core / GenEd'; hint.style.color = ''; }
      return;
    }

    var canBeMajor = (subj.can_be_major !== false); // default true if field absent
    if (!canBeMajor) {
      majorCb.checked = false;
      majorCb.disabled = true;
      if (hint) {
        hint.textContent = subj.major_restriction_reason || 'Cannot be marked as Major for this program.';
        hint.style.color = '#f87171';
      }
    } else {
      majorCb.disabled = false;
      if (hint) {
        var note = subj.category === 'ge' ? 'General Education subject' : '';
        hint.textContent = note || 'Unchecked = Core / GenEd';
        hint.style.color = '';
      }
    }
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

      // Check if subjects carry category info (enriched API)
      var hasCategories = state.subjects.some(function (s) { return s.category; });

      if (hasCategories) {
        // Build optgroups: Program Major → General Education → Other
        var groups = {};
        var groupOrder = [];
        state.subjects.forEach(function (s) {
          var label = s.category_label || 'Other';
          if (!groups[label]) { groups[label] = []; groupOrder.push(label); }
          groups[label].push(s);
        });

        groupOrder.forEach(function (label) {
          var grp = document.createElement('optgroup');
          grp.label = label;
          groups[label].forEach(function (s) {
            var subOpt = document.createElement('option');
            subOpt.value = s.id;
            var suffix = (s.can_be_major === false) ? ' (Non-Major Only)' : '';
            subOpt.textContent = s.code + ' \u2014 ' + s.name + suffix;
            grp.appendChild(subOpt);
          });
          subjSelect.appendChild(grp);
        });
      } else {
        // Fallback: flat list
        state.subjects.forEach(function (s) {
          var subOpt = document.createElement('option');
          subOpt.value = s.id;
          subOpt.textContent = s.code + ' \u2014 ' + s.name;
          subjSelect.appendChild(subOpt);
        });
      }

      // Wire up subject-change listener for major checkbox enforcement
      subjSelect.removeEventListener('change', subjSelect._majorHandler || function(){});
      subjSelect._majorHandler = function () {
        updateMajorCheckboxForSubject(this.value);
      };
      subjSelect.addEventListener('change', subjSelect._majorHandler);

      // Apply immediately for whatever value is currently selected
      updateMajorCheckboxForSubject(subjSelect.value);
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
      state.versions = result.data.versions || [];
      state.selectedVersionId = result.data.selected_version_id || null;
      state.canEdit = !!result.data.can_edit;
      state.isLegacy = !!result.data.is_legacy;
      state.terms = result.data.terms || [];

      var savedSummer = null;
      try {
        savedSummer = localStorage.getItem('kcc_curriculum_summer_' + state.programId);
      } catch (e) {}

      var hasSummer = (result.data.entries || []).some(function (e) {
        return e.semester === 3;
      });

      if (savedSummer !== null) {
        state.includeSummer = savedSummer === '1';
      } else {
        state.includeSummer = hasSummer || (state.programCode === 'BSIT');
      }

      var filter = getEl('curriculumEffectiveTerm');
      if (filter) filter.innerHTML = '';

      populateSelects();
      renderGrid();
      renderVersionBar();
      renderBatchSelector();
    })
    .catch(function (err) {
      if (grid) grid.innerHTML = '';
      showError(err && err.message ? err.message : 'Unable to load curriculum matrix.');
    });
  }

  function loadMatrix(button) {
    state.matrixUrl = button.getAttribute('data-curriculum-url');
    state.matrixBaseUrl = state.matrixUrl;
    state.selectedVersionId = null;
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

  function toggleFullscreen() {
    var dialog = getEl('curriculumModalDialog');
    var btn = getEl('curriculumFullscreenBtn');
    var label = getEl('curriculumFsLabel');
    if (!dialog) return;

    var isFs = dialog.classList.toggle('is-fullscreen');
    if (btn) {
      var icon = btn.querySelector('i');
      if (icon) {
        icon.className = isFs ? 'fas fa-compress' : 'fas fa-expand';
      }
    }
    if (label) {
      label.textContent = isFs ? 'Exit Fullscreen' : 'Fullscreen';
    }
  }

  function initCurriculumMatrix() {
    var modal = getEl('curriculumMatrixModal');
    if (!modal) return;

    document.addEventListener('click', function (e) {
      var fsBtn = e.target.closest('#curriculumFullscreenBtn');
      if (fsBtn) {
        e.preventDefault();
        toggleFullscreen();
        return;
      }

      var prosBtn = e.target.closest('#curriculumViewProspectusBtn');
      if (prosBtn) {
        e.preventDefault();
        state.viewMode = 'prospectus';
        renderGrid();
        return;
      }

      var matBtn = e.target.closest('#curriculumViewMatrixBtn');
      if (matBtn) {
        e.preventDefault();
        state.viewMode = 'matrix';
        renderGrid();
        return;
      }

      var summerBtn = e.target.closest('#curriculumSummerToggleBtn');
      if (summerBtn) {
        e.preventDefault();
        state.includeSummer = !state.includeSummer;
        try {
          localStorage.setItem('kcc_curriculum_summer_' + state.programId, state.includeSummer ? '1' : '0');
        } catch (err) {}
        renderGrid();
        toast(
          state.includeSummer ? 'info' : 'secondary',
          state.includeSummer
            ? 'Summer term included for ' + (state.programCode || 'this program') + '.'
            : 'Summer term hidden for ' + (state.programCode || 'this program') + '.'
        );
        return;
      }

      var draftShortcut = e.target.closest('.js-create-draft-shortcut');
      if (draftShortcut) {
        e.preventDefault();
        var topDraftBtn = getEl('curriculumCreateDraftBtn');
        if (topDraftBtn) {
          topDraftBtn.click();
        }
        return;
      }

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
          resetToDefaultVersion();
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
          resetToDefaultVersion();
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

    var batchSelect = getEl('curriculumBatchSelect');
    if (batchSelect) {
      batchSelect.addEventListener('change', function () {
        var id = this.value;
        state.selectedVersionId = id || null;
        state.matrixUrl = state.matrixBaseUrl +
          (id ? '?version_id=' + encodeURIComponent(id) : '');
        fetchMatrix();
      });
    }

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
            if (Number(semester) === 3) {
              state.includeSummer = true;
            }
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
