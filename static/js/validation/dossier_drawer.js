/**
 * // ==============================================================================
 * // KCC CLASSSTAMP - SLIDE-OVER DOSSIER PREVIEW DRAWER (A-02)
 * // ==============================================================================
 * // Off-canvas drawer on the validation hub for reviewing a pending registration
 * // without leaving the queue. Keyboard-first workflow:
 * //   J        -> next pending student
 * //   K        -> previous pending student
 * //   A        -> approve current student
 * //   R        -> open reject modal for current student
 * //   Esc      -> close drawer
 * // ==============================================================================
 */
(function () {
  'use strict';

  var state = {
    currentId: null,
    prevUrl: null,
    nextUrl: null,
    approveUrl: '',
    rejectUrl: '',
    studentName: '',
    open: false,
  };

  function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function el(id) { return document.getElementById(id); }

  function show() {
    var backdrop = el('dossierBackdrop');
    if (backdrop) backdrop.style.display = 'block';
    state.open = true;
  }

  function hide() {
    var backdrop = el('dossierBackdrop');
    if (backdrop) backdrop.style.display = 'none';
    state.open = false;
  }

  function setLoading(isLoading) {
    var loading = el('dossierLoading');
    var body = el('dossierBody');
    if (loading) loading.style.display = isLoading ? 'flex' : 'none';
    if (body) body.style.display = isLoading ? 'none' : 'block';
  }

  function fillField(id, value, fallback) {
    var node = el(id);
    if (!node) return;
    node.textContent = (value === null || value === undefined || value === '') ? (fallback || '—') : value;
  }

  function renderProof(url) {
    var imgWrap = el('dossierProofImgWrap');
    var pdfWrap = el('dossierProofPdfWrap');
    var noneWrap = el('dossierProofNone');
    if (!url) {
      if (imgWrap) imgWrap.style.display = 'none';
      if (pdfWrap) pdfWrap.style.display = 'none';
      if (noneWrap) noneWrap.style.display = 'block';
      return;
    }
    if (String(url).toLowerCase().indexOf('.pdf') !== -1) {
      if (imgWrap) imgWrap.style.display = 'none';
      if (noneWrap) noneWrap.style.display = 'none';
      if (pdfWrap) {
        pdfWrap.style.display = 'block';
        var link = el('dossierProofLink');
        if (link) link.href = url;
      }
      return;
    }
    if (pdfWrap) pdfWrap.style.display = 'none';
    if (noneWrap) noneWrap.style.display = 'none';
    if (imgWrap) {
      imgWrap.style.display = 'block';
      var img = el('dossierProofImg');
      if (img) img.src = url;
      var open = el('dossierProofOpen');
      if (open) open.href = url;
    }
  }

  function renderDossier(d) {
    state.currentId = d.id;
    state.prevUrl = d.prev_url;
    state.nextUrl = d.next_url;
    state.approveUrl = d.approve_url || '';
    state.rejectUrl = d.reject_url || '';
    state.studentName = d.full_name || 'this student';

    fillField('dossierName', d.full_name);
    fillField('dossierEmail', d.email);
    fillField('dossierUsername', d.username);
    fillField('dossierStudentNo', d.student_number);
    fillField('dossierDept', d.department_code ? (d.department_code + ' — ' + (d.department_name || '')) : null);
    fillField('dossierProgram', d.program_code ? (d.program_code + ' — ' + (d.program_name || '')) : null);
    fillField('dossierYear', d.year_level ? (d.year_level + ' Year') : null);
    fillField('dossierGender', d.gender);
    fillField('dossierType', d.student_type);
    fillField('dossierPhone', d.phone_number);
    fillField('dossierRegistered', d.created_at ? new Date(d.created_at).toLocaleString() : null);
    fillField('dossierCounter', d.current_index ? (d.current_index + ' of ' + d.total_pending) : null);

    var initials = el('dossierInitials');
    if (initials) {
      var parts = (d.full_name || '?').trim().split(/\s+/);
      initials.textContent = ((parts[0] || '?').charAt(0) + (parts.length > 1 ? parts[parts.length - 1].charAt(0) : '')).toUpperCase();
    }

    var approveForm = el('dossierApproveForm');
    if (approveForm) approveForm.action = state.approveUrl;
    var detailLink = el('dossierDetailLink');
    if (detailLink) detailLink.href = d.detail_url || '#';

    var prevBtn = el('dossierPrevBtn');
    var nextBtn = el('dossierNextBtn');
    if (prevBtn) prevBtn.disabled = !state.prevUrl;
    if (nextBtn) nextBtn.disabled = !state.nextUrl;

    renderProof(d.registration_proof_url);
    setLoading(false);
    show();
  }

  function openDossier(url) {
    if (!url) return;
    setLoading(true);
    show();
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        if (!data.ok || !data.dossier) throw new Error('Bad payload');
        renderDossier(data.dossier);
      })
      .catch(function () {
        setLoading(false);
        hide();
        if (window.toast) window.toast('error', 'Could not load dossier preview.');
      });
  }

  function openRejectModal() {
    var modal = el('rejectModalBackdrop');
    var form = el('rejectForm');
    var nameEl = el('rejectStudentName');
    var reasonEl = el('rejectionReasonInput');
    if (!modal) return;
    if (form) form.action = state.rejectUrl;
    if (nameEl) nameEl.textContent = state.studentName;
    if (reasonEl) reasonEl.value = '';
    document.querySelectorAll('#hubRejectChips .modal-chip').forEach(function (c) {
      c.classList.remove('is-selected');
    });
    modal.style.display = 'flex';
  }

  function approveCurrent() {
    var form = el('dossierApproveForm');
    if (form && state.approveUrl) form.submit();
  }

  function bindEvents() {
    var backdrop = el('dossierBackdrop');
    var closeBtn = el('dossierCloseBtn');
    var rejectBtn = el('dossierRejectBtn');
    var prevBtn = el('dossierPrevBtn');
    var nextBtn = el('dossierNextBtn');

    if (backdrop) {
      backdrop.addEventListener('click', function (e) {
        if (e.target === backdrop) hide();
      });
    }
    if (closeBtn) closeBtn.addEventListener('click', hide);
    if (rejectBtn) rejectBtn.addEventListener('click', openRejectModal);
    if (prevBtn) prevBtn.addEventListener('click', function () { if (state.prevUrl) openDossier(state.prevUrl); });
    if (nextBtn) nextBtn.addEventListener('click', function () { if (state.nextUrl) openDossier(state.nextUrl); });

    document.querySelectorAll('.open-dossier-drawer').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openDossier(this.dataset.dossierUrl);
      });
    });

    document.addEventListener('keydown', function (e) {
      if (!state.open) return;
      var tag = (e.target && e.target.tagName) || '';
      if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return;
      var key = e.key.toLowerCase();
      if (key === 'escape') {
        hide();
      } else if (key === 'j' && state.nextUrl) {
        openDossier(state.nextUrl);
      } else if (key === 'k' && state.prevUrl) {
        openDossier(state.prevUrl);
      } else if (key === 'a') {
        e.preventDefault();
        approveCurrent();
      } else if (key === 'r') {
        openRejectModal();
      }
    });
  }

  document.addEventListener('DOMContentLoaded', bindEvents);
})();
