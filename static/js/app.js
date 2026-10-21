/* KCC ClassStamp — App Namespace Root
 * ─────────────────────────────────────────────────────────────────
 * This file is kept as a namespace initializer and legacy shim.
 * All feature modules now live in static/js/core/:
 *
 *   app_toasts.js        — window.App.toast / window.toast
 *   app_buttons.js       — window.App.setButtonLoading
 *   app_modals.js        — window.openModal / window.closeModal
 *   app_confirm.js       — window.App.confirm
 *   app_audio.js         — window.App.playTone / window.App.playChime
 *   app_table_search.js  — data-table-search debounced row filter
 *   app_session_guard.js — idle inactivity watchdog + keepalive
 *   app_navigation.js    — sidebar toggle, active link, bfcache
 *
 * base.html loads each module in dependency order before
 * {% block extra_js %}. This file is no longer required but kept
 * as a safety net to ensure window.App always exists.
 * ─────────────────────────────────────────────────────────────────
 */
(function () {
  'use strict';
  window.App = window.App || {};
})();
