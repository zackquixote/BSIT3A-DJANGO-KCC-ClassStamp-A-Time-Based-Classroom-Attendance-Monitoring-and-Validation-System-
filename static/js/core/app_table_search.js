/* KCC ClassStamp — Core: Instant Debounced Table Filter Engine */
(function (window) {
  'use strict';

  window.App = window.App || {};

  /* ── Instant Debounced Table Filter Engine ───────────────────── */
  function initInstantTableSearch() {
    var inputs = document.querySelectorAll('[data-table-search], .js-table-search');
    inputs.forEach(function (input) {
      if (input._searchBound) return;
      input._searchBound = true;

      var tableSelector = input.getAttribute('data-table-search') || input.dataset.table || 'table';
      var debounceTimer = null;

      input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          var filterVal = input.value.trim().toLowerCase();
          var table = document.querySelector(tableSelector);
          if (!table) return;

          var tbody = table.querySelector('tbody') || table;
          var rows = tbody.querySelectorAll('tr:not(.table-empty-row)');
          var visibleCount = 0;

          rows.forEach(function (row) {
            var text = row.textContent.toLowerCase();
            if (!filterVal || text.indexOf(filterVal) > -1) {
              row.style.display = '';
              visibleCount++;
            } else {
              row.style.display = 'none';
            }
          });

          var emptyRow = tbody.querySelector('.table-search-empty');
          if (visibleCount === 0 && filterVal) {
            if (!emptyRow) {
              emptyRow = document.createElement('tr');
              emptyRow.className = 'table-search-empty table-empty-row';
              var theadRow = table.querySelector('thead tr');
              var colCount = theadRow && theadRow.children.length ? theadRow.children.length : (rows[0] ? rows[0].children.length : 6);
              emptyRow.innerHTML =
                '<td colspan="' + colCount + '" style="text-align: center; padding: 32px 16px; color: var(--text-muted); font-size: 0.85rem;">' +
                '  <i class="fas fa-magnifying-glass" style="font-size: 1.5rem; opacity: 0.4; display: block; margin-bottom: 8px;"></i>' +
                '  No matching rows found for "' + filterVal + '"' +
                '</td>';
              tbody.appendChild(emptyRow);
            } else {
              emptyRow.style.display = '';
              var textSpan = emptyRow.querySelector('td');
              if (textSpan) {
                textSpan.innerHTML =
                  '<i class="fas fa-magnifying-glass" style="font-size: 1.5rem; opacity: 0.4; display: block; margin-bottom: 8px;"></i>' +
                  'No matching rows found for "' + filterVal + '"';
              }
            }
          } else if (emptyRow) {
            emptyRow.style.display = 'none';
          }
        }, 150);
      });

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && input.value) {
          input.value = '';
          input.dispatchEvent(new Event('input'));
        }
      });
    });
  }

  window.App.initInstantTableSearch = initInstantTableSearch;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initInstantTableSearch);
  } else {
    initInstantTableSearch();
  }
})(window);
