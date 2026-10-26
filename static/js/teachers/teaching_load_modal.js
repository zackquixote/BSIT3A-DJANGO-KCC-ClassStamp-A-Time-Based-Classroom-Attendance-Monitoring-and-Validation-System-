/* KCC ClassStamp — Teachers: Teaching Load Modal Controller */
(function (window) {
  'use strict';

  var currentLoadTeacherId = null;

  function getApp() { return window.TeachersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  async function refreshTeacherLoadList(teacherId) {
    var container = getEl('loadClassesList');
    if (!container) return;
    container.innerHTML = '<div class="text-center text-muted py-3 text-xs"><i class="fas fa-spinner fa-spin mr-1"></i> Refreshing load...</div>';

    try {
      var res = await fetch('/teachers/get/' + teacherId + '/');
      var data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Failed to load details');
      var t = data.teacher;

      var nameEl = getEl('loadTeacherName');
      if (nameEl) nameEl.textContent = t.full_name;
      var deptEl = getEl('loadTeacherDept');
      if (deptEl) deptEl.textContent = t.department_code + ' \u2014 ' + t.department_name;
      var countEl = getEl('loadTeacherCount');
      if (countEl) countEl.textContent = t.classes.length + ' Section' + (t.classes.length === 1 ? '' : 's');

      if (!t.classes || t.classes.length === 0) {
        container.innerHTML =
          '<div style="background: rgba(255,255,255,0.02); border: 1px dashed var(--glass-border); border-radius: var(--radius-md); padding: 18px; text-align: center;" class="text-muted text-xs">'
          + '<i class="fas fa-folder-open" style="font-size: 1.4rem; opacity: 0.4; display: block; margin-bottom: 6px;"></i>'
          + 'No class sections assigned to this teacher yet. Use the form below to allocate subjects.'
          + '</div>';
        return;
      }

      var html = '<div style="display: flex; flex-direction: column; gap: 8px;">';
      t.classes.forEach(function (c) {
        html +=
          '<div style="background: rgba(255,255,255,0.03); border: 1px solid var(--glass-border); border-radius: var(--radius-md); padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px;">'
          + '<div>'
          + '<div class="flex items-center gap-2">'
          + '<span class="badge badge--primary font-mono text-xs font-bold">' + c.class_code + '</span>'
          + '<span class="font-semibold text-primary text-xs">' + c.subject_code + ' \u2014 ' + c.subject_name + '</span>'
          + '</div>'
          + '<div class="text-muted text-xs mt-0.5">'
          + '<i class="fas fa-calendar-day text-gold mr-1"></i> ' + c.academic_year + ' &nbsp;\u2022&nbsp; Grace: ' + c.grace_minutes + ' mins'
          + '</div>'
          + '</div>'
          + '<button type="button" class="btn btn-outline btn-sm js-unassign-class" data-teacher-id="' + teacherId + '" data-class-id="' + c.id + '" data-class-code="' + c.class_code + '" style="padding: 4px 8px; color: #f87171; border-color: rgba(239,68,68,0.3);" title="Remove from load">'
          + '<i class="fas fa-trash-can"></i>'
          + '</button>'
          + '</div>';
      });
      html += '</div>';
      container.innerHTML = html;

      // Attach unassign event handlers
      container.querySelectorAll('.js-unassign-class').forEach(function (btn) {
        btn.addEventListener('click', async function () {
          var classCode = btn.dataset.classCode;
          var confirmed = window.App && window.App.confirm
            ? await window.App.confirm({
                title: 'Remove from Teaching Load',
                message: 'Remove class section "' + classCode + '" from this teacher\'s load?',
                confirmText: 'Remove',
                confirmClass: 'btn-danger',
                type: 'danger'
              })
            : confirm('Remove class section "' + classCode + '" from this teacher\'s load?');

          if (!confirmed) return;
          btn.disabled = true;
          btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
          try {
            var r = await fetch('/teachers/' + btn.dataset.teacherId + '/unassign-class/' + btn.dataset.classId + '/', {
              method: 'POST',
              headers: { 'X-CSRFToken': getCSRF() },
            });
            var resData = await r.json();
            if (resData.ok) {
              refreshTeacherLoadList(teacherId);
              var successEl = getEl('teacherSuccess');
              if (window.App && window.App.toast) {
                window.App.toast('success', resData.message || 'Class removed from load.');
              } else if (successEl) { successEl.style.display = 'block'; successEl.textContent = resData.message; }
            } else {
              if (window.App && window.App.toast) {
                window.App.toast('error', resData.error || 'Failed to unassign class.');
              } else {
                alert(resData.error || 'Failed to unassign class.');
              }
              btn.disabled = false;
              btn.innerHTML = '<i class="fas fa-trash-can"></i>';
            }
          } catch (err) {
            if (window.App && window.App.toast) {
              window.App.toast('error', 'Network communication error.');
            } else {
              alert('Network communication error.');
            }
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-trash-can"></i>';
          }
        });
      });
    } catch (err) {
      container.innerHTML = '<div class="text-danger text-center text-xs py-3">' + err.message + '</div>';
    }
  }

  function initTeachingLoad() {
    // Guard: only run if the teaching load modal exists on this page
    if (!getEl('teachingLoadModal')) return;

    var App = getApp();

    // Event delegation for opening the teaching load modal
    document.addEventListener('click', function (e) {
      var loadBtn = e.target.closest('.js-assign-load');
      if (!loadBtn) return;

      e.preventDefault();
      currentLoadTeacherId = loadBtn.dataset.id;
      var assignIdEl = getEl('assignTeacherId');
      if (assignIdEl) assignIdEl.value = currentLoadTeacherId;
      var codeEl = getEl('assignClassCode');
      if (codeEl) codeEl.value = '';
      var errEl = getEl('assignLoadError');
      if (errEl) errEl.style.display = 'none';
      var succEl = getEl('assignLoadSuccess');
      if (succEl) succEl.style.display = 'none';

      refreshTeacherLoadList(currentLoadTeacherId);

      if (typeof window.openModal === 'function') {
        window.openModal('teachingLoadModal', loadBtn);
      } else if (App && App.showModal) {
        App.showModal('teachingLoadModal');
      } else {
        var m = getEl('teachingLoadModal');
        if (m) { m.classList.add('is-active', 'is-open'); document.body.style.overflow = 'hidden'; }
      }
    });

    // Auto-suggest class code when Subject is selected
    var assignSubject = getEl('assignSubject');
    if (assignSubject) {
      assignSubject.addEventListener('change', function () {
        var opt = this.options[this.selectedIndex];
        if (!opt || !opt.value) return;
        var subCode = opt.textContent.split('\u2014')[0].trim();
        var codeInput = getEl('assignClassCode');
        if (codeInput && (!codeInput.value || codeInput.value.startsWith('BSIT-'))) {
          var match = subCode.match(/\d/);
          var yr = match ? match[0] : '1';
          codeInput.value = 'BSIT-' + yr + 'A-' + subCode;
        }
      });
    }

    // Assign to load form submit
    var assignForm = getEl('assignLoadForm');
    if (assignForm) {
      assignForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        var submitBtn = getEl('assignLoadSubmit');
        var errBox = getEl('assignLoadError');
        var succBox = getEl('assignLoadSuccess');
        if (errBox) errBox.style.display = 'none';
        if (succBox) succBox.style.display = 'none';

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Assigning...';
        }

        try {
          var fd = new FormData(assignForm);
          var res = await fetch('/teachers/' + currentLoadTeacherId + '/assign-class/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRF() },
            body: fd,
          });
          var data = await res.json();
          if (data.ok) {
            if (window.App && window.App.toast) {
              window.App.toast('success', data.message || 'Class assigned to teacher load.');
            }
            if (succBox) { succBox.textContent = data.message; succBox.style.display = 'block'; }
            var codeInput = getEl('assignClassCode');
            if (codeInput) codeInput.value = '';
            refreshTeacherLoadList(currentLoadTeacherId);
            setTimeout(function () { if (succBox) succBox.style.display = 'none'; }, 4000);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast('error', data.error || 'Failed to assign class.');
            }
            if (errBox) { errBox.textContent = data.error || 'Failed to assign class.'; errBox.style.display = 'block'; }
          }
        } catch (err) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Network communication error.');
          }
          if (errBox) { errBox.textContent = 'Network communication error.'; errBox.style.display = 'block'; }
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plus"></i> Assign to Teacher Load';
          }
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTeachingLoad);
  } else {
    initTeachingLoad();
  }
})(window);
