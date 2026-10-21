/* KCC ClassStamp — Pending Registrations: Filtering & Search Controller */
(function (window) {
  'use strict';

  function initPendingFilters() {
    var deptSelect     = document.getElementById('filterDeptSelect');
    var progSelect     = document.getElementById('filterProgSelect');
    var searchInput    = document.getElementById('filterSearchInput');
    var clearBtn       = document.getElementById('clearFiltersBtn');
    var resetInlineBtn = document.getElementById('resetFiltersInlineBtn');
    var rows           = Array.from(document.querySelectorAll('.pending-row'));
    var noMatchesRow   = document.getElementById('noFilterMatchesRow');
    var visibleCounter = document.getElementById('visiblePendingCount');
    var deptTabs       = Array.from(document.querySelectorAll('.dept-tab-pill'));

    if (!deptSelect || !progSelect) return;

    // Cache program options for cascading
    var progOptions = Array.from(progSelect.querySelectorAll('option:not(#progDefaultOption)'));

    function filterProgramOptions(deptId) {
      var currentSelectedProg = progSelect.value;
      progSelect.innerHTML = '';
      var defaultOpt = document.createElement('option');
      defaultOpt.value = '';
      defaultOpt.textContent = deptId ? 'All Programs in this Department' : 'All Programs';
      defaultOpt.id = 'progDefaultOption';
      progSelect.appendChild(defaultOpt);

      var foundSelected = false;
      progOptions.forEach(function (opt) {
        var optDept = opt.getAttribute('data-department');
        if (!deptId || optDept === deptId) {
          progSelect.appendChild(opt);
          if (opt.value === currentSelectedProg) {
            opt.selected = true;
            foundSelected = true;
          }
        }
      });

      if (!foundSelected) {
        defaultOpt.selected = true;
      }
    }

    function applyFilters() {
      var selectedDept = deptSelect.value.trim();
      var selectedProg = progSelect.value.trim();
      var query = searchInput ? searchInput.value.trim().toLowerCase() : '';

      // Update active state on tab pills
      deptTabs.forEach(function (tab) {
        var tabDeptId = tab.getAttribute('data-dept-id');
        if (tabDeptId === selectedDept) {
          tab.classList.add('is-active');
        } else {
          tab.classList.remove('is-active');
        }
      });

      var visibleCount = 0;

      rows.forEach(function (row) {
        var rowDept = row.getAttribute('data-department-id');
        var rowProg = row.getAttribute('data-program-id');
        var rowName = (row.getAttribute('data-name') || '').toLowerCase();
        var rowStudentNo = (row.getAttribute('data-student-no') || '').toLowerCase();
        var rowEmail = (row.getAttribute('data-email') || '').toLowerCase();
        var rowUsername = (row.getAttribute('data-username') || '').toLowerCase();

        var matchesDept = !selectedDept || rowDept === selectedDept;
        var matchesProg = !selectedProg || rowProg === selectedProg;
        var matchesQuery = !query ||
          rowName.indexOf(query) !== -1 ||
          rowStudentNo.indexOf(query) !== -1 ||
          rowEmail.indexOf(query) !== -1 ||
          rowUsername.indexOf(query) !== -1;

        if (matchesDept && matchesProg && matchesQuery) {
          row.style.display = '';
          visibleCount++;
        } else {
          row.style.display = 'none';
        }
      });

      if (visibleCounter) {
        visibleCounter.textContent = visibleCount;
      }

      if (noMatchesRow) {
        if (visibleCount === 0 && rows.length > 0) {
          noMatchesRow.style.display = '';
        } else {
          noMatchesRow.style.display = 'none';
        }
      }

      // Show/hide clear button
      var hasFilter = selectedDept !== '' || selectedProg !== '' || query !== '';
      if (clearBtn) {
        if (hasFilter) {
          clearBtn.classList.remove('is-hidden');
          clearBtn.style.display = 'inline-flex';
        } else {
          clearBtn.classList.add('is-hidden');
          clearBtn.style.display = 'none';
        }
      }

      // Synchronize URL query parameters without reloading
      var url = new URL(window.location.href);
      if (selectedDept) url.searchParams.set('department', selectedDept);
      else url.searchParams.delete('department');

      if (selectedProg) url.searchParams.set('program', selectedProg);
      else url.searchParams.delete('program');

      if (query) url.searchParams.set('q', query);
      else url.searchParams.delete('q');

      window.history.replaceState({}, '', url);
    }

    // Tab Pill Click Handler
    deptTabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var deptId = this.getAttribute('data-dept-id');
        deptSelect.value = deptId;
        filterProgramOptions(deptId);
        applyFilters();
      });
    });

    // Dropdown change handlers
    deptSelect.addEventListener('change', function () {
      filterProgramOptions(this.value);
      applyFilters();
    });

    progSelect.addEventListener('change', applyFilters);

    // Search input handler with debounce
    var searchTimeout = null;
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(applyFilters, 150);
      });
    }

    // Inline reset button
    if (resetInlineBtn) {
      resetInlineBtn.addEventListener('click', function () {
        deptSelect.value = '';
        filterProgramOptions('');
        if (searchInput) searchInput.value = '';
        applyFilters();
      });
    }

    // Initialize cascading options on load
    if (deptSelect.value) {
      filterProgramOptions(deptSelect.value);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPendingFilters);
  } else {
    initPendingFilters();
  }
})(window);
