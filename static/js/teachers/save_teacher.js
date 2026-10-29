/* KCC ClassStamp - Teachers: Save (Create / Update) Controller v4 */
(function (window) {
  'use strict';

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    return '';
  }

  /* Core save handler */
  async function handleSave(e) {
    if (e) e.preventDefault();
    console.log('[ClassStamp] Save Teacher triggered.');

    var formEl = getEl('teacherForm');
    if (!formEl) { console.error('[ClassStamp] teacherForm not found!'); return; }

    if (typeof formEl.checkValidity === 'function' && !formEl.checkValidity()) {
      console.warn('[ClassStamp] Form validation failed.');
      formEl.reportValidity();
      return;
    }

    var profileId = (getEl('teacherId') && getEl('teacherId').value) || '';
    var isEdit    = !!profileId;
    var btn       = getEl('teacherModalSave');
    var errEl     = getEl('teacherFormError');
    var App       = getApp();

    if (errEl) errEl.style.display = 'none';

    var fd = new FormData(formEl);
    var activeEl = getEl('teacherIsActive');
    fd.set('is_active', (activeEl && activeEl.checked) ? '1' : '0');

    var debugSnap = {};
    fd.forEach(function (v, k) { debugSnap[k] = v; });
    console.log('[ClassStamp] FormData being sent:', debugSnap);

    var url  = isEdit ? '/teachers/update/' + profileId + '/' : '/teachers/create/';
    var csrf = getCSRF();
    console.log('[ClassStamp] POST to:', url, '| CSRF present:', !!csrf);

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + (isEdit ? 'Updating...' : 'Creating...');
    }

    try {
      var res = await fetch(url, {
        method : 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf },
        body   : fd,
      });
      console.log('[ClassStamp] HTTP status:', res.status);

      var data;
      try {
        data = await res.json();
      } catch (jsonErr) {
        console.error('[ClassStamp] Non-JSON response. Session may have expired. Status:', res.status);
        if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Server error (' + res.status + '). Please reload and try again.'; }
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = isEdit ? '<i class="fas fa-floppy-disk"></i> Update Teacher'
            : '<i class="fas fa-user-plus"></i> <span id="teacherModalSaveLabel">Create Teacher</span>';
        }
        return;
      }

      console.log('[ClassStamp] Server response:', data);

      if (data.ok) {
        if (data.generated_password) {
          var gpwEl = getEl('teacherGeneratedPw');
          var pwMsg = 'Account created! Temporary password: ' + data.generated_password;
          if (App && App.showAlert) { App.showAlert(gpwEl, pwMsg, 'success'); }
          else if (gpwEl) { gpwEl.style.display = 'block'; gpwEl.textContent = pwMsg; }
          if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-check"></i> Created'; }
          setTimeout(function () { location.reload(); }, 3500);
        } else {
          if (App && App.hideModal) { App.hideModal('teacherModal'); }
          else if (typeof window.closeModal === 'function') { window.closeModal('teacherModal'); }
          else {
            var m = getEl('teacherModal');
            if (m) { m.classList.remove('is-active', 'is-open'); document.body.style.overflow = ''; }
          }
          var successEl = getEl('teacherSuccess');
          if (App && App.showAlert) { App.showAlert(successEl, data.message || 'Teacher saved.', 'success'); }
          setTimeout(function () { location.reload(); }, 800);
        }
      } else {
        var errorMsg = data.error || 'Failed to save faculty account.';
        console.error('[ClassStamp] Server error:', errorMsg);
        if (App && App.showAlert) { App.showAlert(errEl, errorMsg); }
        else if (errEl) { errEl.style.display = 'block'; errEl.textContent = errorMsg; }
        if (errEl && errEl.scrollIntoView) { errEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = isEdit ? '<i class="fas fa-floppy-disk"></i> Update Teacher'
            : '<i class="fas fa-user-plus"></i> <span id="teacherModalSaveLabel">Create Teacher</span>';
        }
      }
    } catch (err) {
      console.error('[ClassStamp] Fetch error:', err);
      if (errEl) { errEl.style.display = 'block'; errEl.textContent = 'Network error. Please try again.'; }
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = isEdit ? '<i class="fas fa-floppy-disk"></i> Update Teacher'
          : '<i class="fas fa-user-plus"></i> <span id="teacherModalSaveLabel">Create Teacher</span>';
      }
    }
  }

  /* Init: direct bind + delegation fallback */
  function initSaveTeacher() {
    console.log('[ClassStamp] Save Teacher module v4 loaded.');
    var saveBtn = getEl('teacherModalSave');
    var form    = getEl('teacherForm');

    if (saveBtn) {
      saveBtn.addEventListener('click', handleSave);
      saveBtn._saveHandlerBound = true;
      console.log('[ClassStamp] Direct click listener attached to teacherModalSave.');
    } else {
      console.warn('[ClassStamp] teacherModalSave not found at DOMContentLoaded.');
    }
    if (form) {
      form.addEventListener('submit', handleSave);
      console.log('[ClassStamp] Submit listener attached to teacherForm.');
    }

    /* Delegation fallback */
    document.addEventListener('click', function (e) {
      var target = e.target.closest('#teacherModalSave');
      if (!target || target._saveHandlerBound) return;
      handleSave(e);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSaveTeacher);
  } else {
    initSaveTeacher();
  }

})(window);