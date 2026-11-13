/* KCC ClassStamp — Responsive tables (phones)
   -----------------------------------------------------------------------------
   The admin console is built around wide data tables (8–20 columns). They read
   well on a laptop and are unusable on a 390px phone: the row scrolls sideways
   and the status / action buttons end up off-screen.

   Instead of hand-writing a card layout per page, this module copies each
   column's <th> into the matching <td data-label="…"> once, and the stylesheet
   turns `.table.is-stacked` into cards. Anything without a header (colspan
   empty states, layout tables) is left alone.

   The User Accounts table opts out — it already ships its own card layout with
   a curated set of columns. */

(function (window, document) {
  'use strict';

  var MOBILE_MAX = 820;
  var SELECTOR = 'table.table:not(.users-table):not([data-no-stack])';

  function labelize(table) {
    var heads = [];
    var headRow = table.tHead && table.tHead.rows[0];
    if (!headRow) return false;

    Array.prototype.forEach.call(headRow.cells, function (th) {
      heads.push((th.textContent || '').replace(/\s+/g, ' ').trim());
    });

    if (!heads.length) return false;

    var rows = table.tBodies.length ? table.tBodies[0].rows : [];
    var labelled = 0;

    Array.prototype.forEach.call(rows, function (tr) {
      Array.prototype.forEach.call(tr.cells, function (td, index) {
        if (td.hasAttribute('colspan')) return;
        if (!td.hasAttribute('data-label') && heads[index]) {
          td.setAttribute('data-label', heads[index]);
          labelled += 1;
        }
      });
    });

    return labelled > 0 || table.classList.contains('is-stacked');
  }

  function apply() {
    var isPhone = window.innerWidth <= MOBILE_MAX;
    var tables = document.querySelectorAll(SELECTOR);

    Array.prototype.forEach.call(tables, function (table) {
      if (isPhone) {
        var ok = labelize(table);
        if (ok) table.classList.add('is-stacked');
      } else if (table.classList.contains('is-stacked')) {
        table.classList.remove('is-stacked');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }

  var resizeTimer = null;
  window.addEventListener('resize', function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(apply, 150);
  });
})(window, document);
