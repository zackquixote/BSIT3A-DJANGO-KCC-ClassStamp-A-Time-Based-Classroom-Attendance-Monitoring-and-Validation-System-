/* KCC ClassStamp — Core: Navigation, Sidebar & bfcache */
(function (window) {
  'use strict';

  window.App = window.App || {};

  function initNavigation() {
    // Mobile sidebar toggle & backdrop handling
    var menuBtn = document.getElementById('sidebar-toggle');
    var closeBtn = document.getElementById('sidebar-close');
    var sidebar = document.getElementById('sidebar');
    var backdrop = document.getElementById('sidebar-backdrop');

    function openSidebar() {
      if (sidebar) sidebar.classList.add('is-open');
      if (backdrop) backdrop.classList.add('is-active');
      document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove('is-open');
      if (backdrop) backdrop.classList.remove('is-active');
      document.body.style.overflow = '';
    }

    if (menuBtn) {
      menuBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (sidebar && sidebar.classList.contains('is-open')) {
          closeSidebar();
        } else {
          openSidebar();
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeSidebar();
      });
    }

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        closeSidebar();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) {
        closeSidebar();
      }
    });

    // Active nav link highlight
    var currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(function (link) {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
      }
    });
  }

  /* ── Back-Forward Cache (bfcache) Invalidation ───────────────── */
  window.addEventListener('pageshow', function (event) {
    var navEntries = (window.performance && performance.getEntriesByType)
      ? performance.getEntriesByType('navigation')
      : [];
    var isBackForward = event.persisted ||
      (navEntries.length > 0 && navEntries[0].type === 'back_forward') ||
      (window.performance && window.performance.navigation && window.performance.navigation.type === 2);

    if (isBackForward) {
      window.location.reload();
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNavigation);
  } else {
    initNavigation();
  }
})(window);
