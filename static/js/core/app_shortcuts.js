/* KCC ClassStamp — Core: Keyboard Shortcut Cheatsheet Modal (#13) */
(function (window) {
  'use strict';

  window.App = window.App || {};

  var SHORTCUT_HTML =
    '<div id="keyboardShortcutModal" class="modal" role="dialog" aria-modal="true" aria-label="Keyboard Shortcuts">' +
    '  <div class="modal-dialog modal-dialog--sm" style="max-width:560px;">' +
    '    <div class="modal-header">' +
    '      <h3 class="modal-title"><i class="fas fa-keyboard" style="color:var(--accent-gold);margin-right:8px;"></i>Keyboard Shortcuts</h3>' +
    '      <button type="button" class="modal-close" data-modal-dismiss aria-label="Close"><i class="fas fa-times"></i></button>' +
    '    </div>' +
    '    <div class="modal-body" style="padding:16px 24px 20px;">' +
    '      <div class="shortcut-modal-grid">' +
    '        <div>' +
    '          <div class="shortcut-row"><span class="text-muted">Show this help</span><span class="shortcut-key"><kbd>?</kbd></span></div>' +
    '          <div class="shortcut-row"><span class="text-muted">Close modal / drawer</span><span class="shortcut-key"><kbd>Esc</kbd></span></div>' +
    '          <div class="shortcut-row"><span class="text-muted">Focus table search</span><span class="shortcut-key"><kbd>/</kbd></span></div>' +
    '          <div class="shortcut-row"><span class="text-muted">Clear table search</span><span class="shortcut-key"><kbd>Esc</kbd> in search</span></div>' +
    '        </div>' +
    '        <div>' +
    '          <div class="shortcut-row"><span class="text-muted">Go to Dashboard</span><span class="shortcut-key"><kbd>G</kbd> <kbd>D</kbd></span></div>' +
    '          <div class="shortcut-row"><span class="text-muted">Go to Students</span><span class="shortcut-key"><kbd>G</kbd> <kbd>S</kbd></span></div>' +
    '          <div class="shortcut-row"><span class="text-muted">Go to Teachers</span><span class="shortcut-key"><kbd>G</kbd> <kbd>T</kbd></span></div>' +
    '          <div class="shortcut-row"><span class="text-muted">Go to Classes</span><span class="shortcut-key"><kbd>G</kbd> <kbd>C</kbd></span></div>' +
    '        </div>' +
    '      </div>' +
    '    </div>' +
    '  </div>' +
    '</div>';

  var gPending = null;

  function ensureModal() {
    var m = document.getElementById('keyboardShortcutModal');
    if (!m) {
      document.body.insertAdjacentHTML('beforeend', SHORTCUT_HTML);
      m = document.getElementById('keyboardShortcutModal');
    }
    return m;
  }

  function openShortcuts() {
    ensureModal();
    if (typeof window.openModal === 'function') window.openModal('keyboardShortcutModal');
  }

  document.addEventListener('keydown', function (e) {
    // Skip when user is typing in an input
    var tag = (e.target.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) return;

    // ? opens shortcut modal
    if (e.key === '?' || (e.shiftKey && e.key === '/')) {
      e.preventDefault();
      openShortcuts();
      return;
    }

    // / focuses nearest table search input
    if (e.key === '/') {
      e.preventDefault();
      var searchInput = document.querySelector('[data-table-search], .js-table-search');
      if (searchInput && typeof searchInput.focus === 'function') {
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // G + <key> navigation shortcuts
    if (e.key === 'g' || e.key === 'G') {
      gPending = setTimeout(function () { gPending = null; }, 1200);
      return;
    }
    if (gPending !== null) {
      clearTimeout(gPending);
      gPending = null;
      var dest = null;
      if (e.key === 'd' || e.key === 'D') dest = '/admin/dashboard/';
      else if (e.key === 's' || e.key === 'S') dest = '/students/';
      else if (e.key === 't' || e.key === 'T') dest = '/teachers/';
      else if (e.key === 'c' || e.key === 'C') dest = '/classes/';
      if (dest) { window.location.href = dest; }
    }
  });

  window.App.openKeyboardShortcuts = openShortcuts;
})(window);
