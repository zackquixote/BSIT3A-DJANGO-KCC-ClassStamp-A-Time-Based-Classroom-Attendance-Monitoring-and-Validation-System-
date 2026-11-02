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
      document.body.classList.add('sidebar-open');
      document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove('is-open');
      if (backdrop) backdrop.classList.remove('is-active');
      document.body.classList.remove('sidebar-open');
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

    /* Desktop collapsible rail (drawer stays untouched at 900px and below) */
    var collapseBtn = document.getElementById('sidebar-collapse');
    var navTip = null;
    var COLLAPSE_KEY = 'kcc_sidebar_collapsed';

    function isRailCollapsed() {
      return document.documentElement.classList.contains('sidebar-collapsed');
    }

    function hideNavTip() {
      if (navTip) navTip.classList.remove('is-visible');
    }

    function showNavTip(link) {
      if (!isRailCollapsed() || window.innerWidth <= 900) return;
      var label = link.querySelector('span:not(.sidebar-badge)');
      var text = label ? (label.textContent || '').trim() : '';
      if (!text) return;
      if (!navTip) {
        navTip = document.createElement('div');
        navTip.className = 'kcc-nav-tip';
        navTip.setAttribute('role', 'tooltip');
        document.body.appendChild(navTip);
      }
      var rect = link.getBoundingClientRect();
      navTip.textContent = text;
      navTip.style.top = (rect.top + rect.height / 2) + 'px';
      navTip.style.left = (rect.right + 10) + 'px';
      navTip.classList.add('is-visible');
    }

    function muteNativeTitles() {
      document.querySelectorAll('.sidebar-link[title]').forEach(function (link) {
        link.setAttribute('data-kcc-title', link.getAttribute('title'));
        link.removeAttribute('title');
      });
    }

    function restoreNativeTitles() {
      document.querySelectorAll('.sidebar-link[data-kcc-title]').forEach(function (link) {
        link.setAttribute('title', link.getAttribute('data-kcc-title'));
        link.removeAttribute('data-kcc-title');
      });
    }

    function syncCollapseButton() {
      if (!collapseBtn) return;
      var collapsed = isRailCollapsed();
      collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      collapseBtn.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      collapseBtn.setAttribute('title', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    }

    function applyRailState(collapsed, persist) {
      document.documentElement.classList.toggle('sidebar-collapsed', collapsed);
      if (collapsed) {
        muteNativeTitles();
      } else {
        restoreNativeTitles();
      }
      syncCollapseButton();
      hideNavTip();
      if (persist) {
        try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0'); } catch (err) {}
      }
    }

    if (collapseBtn) {
      collapseBtn.addEventListener('click', function () {
        applyRailState(!isRailCollapsed(), true);
      });
    }
    applyRailState(isRailCollapsed(), false);

    document.querySelectorAll('.sidebar-link').forEach(function (link) {
      link.addEventListener('mouseenter', function () { showNavTip(link); });
      link.addEventListener('mouseleave', hideNavTip);
      link.addEventListener('focus', function () { showNavTip(link); });
      link.addEventListener('blur', hideNavTip);
    });

    var sidebarNav = document.querySelector('.sidebar-nav');
    if (sidebarNav) sidebarNav.addEventListener('scroll', hideNavTip, { passive: true });
    window.addEventListener('resize', hideNavTip);

    // Active nav link highlight
    var currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(function (link) {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
      }
    });

    // In-page section navigation (teacher "Scan Attendance" / "My Classes")
    function focusSection(hash, smooth, flash) {
      var id = (hash || '').replace(/^#/, '');
      var target = id ? document.getElementById(id) : null;
      if (!target) return false;

      target.scrollIntoView({
        behavior: smooth ? 'smooth' : 'auto',
        block: 'start'
      });

      if (flash) {
        target.classList.remove('anchor-target-flash');
        void target.offsetWidth;
        target.classList.add('anchor-target-flash');
        window.setTimeout(function () {
          target.classList.remove('anchor-target-flash');
        }, 1200);
      }
      return true;
    }

    document.querySelectorAll('.sidebar-link[href*="#"], .mobile-bottom-nav-item[href*="#"]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        var href = link.getAttribute('href') || '';
        var linkUrl;
        try {
          linkUrl = new URL(href, window.location.href);
        } catch (err) {
          return;
        }
        if (linkUrl.pathname !== window.location.pathname) return;
        if (!linkUrl.hash || !document.getElementById(linkUrl.hash.slice(1))) return;

        e.preventDefault();
        focusSection(linkUrl.hash, true, true);
        if (window.history && history.replaceState) {
          history.replaceState(null, '', linkUrl.hash);
        }
        closeSidebar();
      });
    });

    if (window.location.hash) {
      window.setTimeout(function () {
        focusSection(window.location.hash, false, false);
      }, 60);
    }
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
