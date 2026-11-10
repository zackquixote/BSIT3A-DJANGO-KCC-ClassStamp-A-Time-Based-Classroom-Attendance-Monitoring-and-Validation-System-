/* KCC ClassStamp — Academic Years: Clone Class Structure (Req 12) */
(function (window) {
  'use strict';

  var App = window.AcademicYearsApp;

  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || '';
  }

  function resetModal() {
    var error = getEl('cloneError');
    if (error) {
      error.style.display = 'none';
      error.textContent = '';
    }
    var results = getEl('cloneResults');
    if (results) results.style.display = 'none';
    var summary = getEl('cloneSummary');
    if (summary) summary.innerHTML = '';
    var errors = getEl('cloneErrors');
    if (errors) errors.innerHTML = '';
    var btn = getEl('cloneExecuteBtn');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-copy"></i> Clone Classes';
    }
  }

  function confirmClone() {
    var msg = (
      'Clone every active class section and weekly slot into the target term?\n\n' +
      'Enrollments, sessions, attendance, and join codes are NOT copied. ' +
      'Existing classes in the target term are never overwritten.'
    );
    return window.confirm(msg);
  }

  function executeClone() {
    var source = getEl('cloneSource');
    var target = getEl('cloneTarget');
    var error = getEl('cloneError');
    var results = getEl('cloneResults');
    var summary = getEl('cloneSummary');
    var errorsBox = getEl('cloneErrors');
    var btn = getEl('cloneExecuteBtn');
    var modal = getEl('ayCloneModal');
    var url = modal ? modal.getAttribute('data-clone-url') : '/academic-years/clone-classes/';

    var sourceId = source ? source.value : '';
    var targetId = target ? target.value : '';
    if (!sourceId || !targetId) {
      if (error) {
        error.style.display = 'block';
        error.textContent = 'Choose both a source term and a target term.';
      }
      return;
    }
    if (sourceId === targetId) {
      if (error) {
        error.style.display = 'block';
        error.textContent = 'Source and target terms must be different.';
      }
      return;
    }
    if (!confirmClone()) return;

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cloning...';
    }
    if (error) error.style.display = 'none';
    if (results) results.style.display = 'none';

    var body = new URLSearchParams();
    body.set('source_year_id', sourceId);
    body.set('target_year_id', targetId);

    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCSRF(),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      },
      body: body.toString(),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (error) {
            error.style.display = 'block';
            error.textContent = res.data.error || 'Cloning failed.';
          }
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-copy"></i> Clone Classes';
          }
          return;
        }

        var copied = res.data.copied_class_count || 0;
        var slots = res.data.copied_slot_count || 0;
        var failed = (res.data.errors || []).length;
        if (summary) {
          summary.innerHTML =
            '<i class="fas fa-circle-check"></i> ' +
            (res.data.message || ('Copied ' + copied + ' class(es) and ' + slots + ' slot(s).'));
        }
        if (errorsBox) {
          if (failed) {
            var html = '<p class="text-gold mb-1"><i class="fas fa-triangle-exclamation"></i> ' +
              failed + ' class(es) skipped or failed:</p><ul style="margin:0;padding-left:18px;">';
            res.data.errors.forEach(function (item) {
              html += '<li><strong>' + (item.class_code || '?') + '</strong>: ' +
                (item.reason || 'unknown reason') + '</li>';
            });
            html += '</ul>';
            errorsBox.innerHTML = html;
          } else {
            errorsBox.innerHTML = '';
          }
        }
        if (results) results.style.display = 'block';
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-copy"></i> Clone Again';
        }
      })
      .catch(function () {
        if (error) {
          error.style.display = 'block';
          error.textContent = 'Network error while cloning the class structure.';
        }
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-copy"></i> Clone Classes';
        }
      });
  }

  function initClone() {
    var modal = getEl('ayCloneModal');
    if (!modal) return;
    var openBtn = getEl('cloneClassesBtn');
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        resetModal();
        if (App && App.showModal) App.showModal('ayCloneModal');
      });
    }
    var executeBtn = getEl('cloneExecuteBtn');
    if (executeBtn) {
      executeBtn.addEventListener('click', executeClone);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initClone);
  } else {
    initClone();
  }
})(window);
