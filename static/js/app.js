/* KCC ClassStamp — App JS (Vanilla, no framework) */

document.addEventListener('DOMContentLoaded', function () {

  /* ── Auto-dismiss toasts after 5s ──────────────────────────── */
  document.querySelectorAll('.toast').forEach(function (toast) {
    setTimeout(function () {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(function () { toast.remove(); }, 300);
    }, 5000);
  });

  /* ── Mobile sidebar toggle ──────────────────────────────────── */
  const menuBtn = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', function () {
      sidebar.classList.toggle('is-open');
    });
    // Close on outside click
    document.addEventListener('click', function (e) {
      if (!sidebar.contains(e.target) && e.target !== menuBtn) {
        sidebar.classList.remove('is-open');
      }
    });
  }

  /* ── Active nav link highlight (by URL match) ───────────────── */
  const currentPath = window.location.pathname;
  document.querySelectorAll('.sidebar-link').forEach(function (link) {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
  /* ── Modal Dialog Manager (Vanilla JS) ─────────────────────── */
  window.openModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.add('is-active');
    document.body.style.overflow = 'hidden';
  };

  window.closeModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.remove('is-active');
    document.body.style.overflow = '';
  };

  // Open modal triggers
  document.addEventListener('click', function (e) {
    const targetBtn = e.target.closest('[data-modal-target]');
    if (targetBtn) {
      e.preventDefault();
      const modalId = targetBtn.getAttribute('data-modal-target');
      window.openModal(modalId);
    }
    
    // Close modal triggers
    const dismissBtn = e.target.closest('[data-modal-dismiss]');
    if (dismissBtn) {
      e.preventDefault();
      const modal = dismissBtn.closest('.modal');
      if (modal) window.closeModal(modal.id);
    }

    // Backdrop click
    if (e.target.classList.contains('modal')) {
      window.closeModal(e.target.id);
    }
  });

  // Escape key closes modal
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const activeModal = document.querySelector('.modal.is-active');
      if (activeModal) window.closeModal(activeModal.id);
    }
  });

});
