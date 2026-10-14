/* KCC ClassStamp — App JS (Vanilla, no framework) */

(function () {
  'use strict';

  /* ── Modal Dialog Manager (Global) ─────────────────────────── */
  window.openModal = function (modalId) {
    var modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.add('is-active');
    document.body.style.overflow = 'hidden';
  };

  window.closeModal = function (modalId) {
    var modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.remove('is-active');
    document.body.style.overflow = '';
  };

  // Global click delegate for open/close modals
  document.addEventListener('click', function (e) {
    var targetBtn = e.target.closest('[data-modal-target]');
    if (targetBtn) {
      e.preventDefault();
      var modalId = targetBtn.getAttribute('data-modal-target');
      window.openModal(modalId);
      return;
    }

    var dismissBtn = e.target.closest('[data-modal-dismiss]');
    if (dismissBtn) {
      e.preventDefault();
      var targetModal = dismissBtn.closest('.modal');
      if (targetModal) {
        window.closeModal(targetModal.id);
      } else {
        var dismissId = dismissBtn.getAttribute('data-modal-dismiss');
        if (dismissId) window.closeModal(dismissId);
      }
      return;
    }

    // Backdrop click
    if (e.target.classList && e.target.classList.contains('modal')) {
      window.closeModal(e.target.id);
    }
  });

  // Escape key closes active modal
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var activeModal = document.querySelector('.modal.is-active');
      if (activeModal) window.closeModal(activeModal.id);
    }
  });

  /* ── DOM Ready Initializers ─────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss toasts after 5s
    document.querySelectorAll('.toast').forEach(function (toast) {
      setTimeout(function () {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(function () { toast.remove(); }, 300);
      }, 5000);
    });

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
  });

  /* ── Back-Forward Cache (bfcache) Invalidation ───────────────── */
  // If user navigated back/forward into a cached protected page after logout,
  // force a reload so the server can evaluate session authentication and redirect.
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

})();
