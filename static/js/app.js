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

    // Mobile sidebar toggle
    var menuBtn = document.getElementById('sidebar-toggle');
    var sidebar = document.getElementById('sidebar');
    if (menuBtn && sidebar) {
      menuBtn.addEventListener('click', function () {
        sidebar.classList.toggle('is-open');
      });
      document.addEventListener('click', function (e) {
        if (!sidebar.contains(e.target) && e.target !== menuBtn) {
          sidebar.classList.remove('is-open');
        }
      });
    }

    // Active nav link highlight
    var currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(function (link) {
      if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
      }
    });
  });

})();
