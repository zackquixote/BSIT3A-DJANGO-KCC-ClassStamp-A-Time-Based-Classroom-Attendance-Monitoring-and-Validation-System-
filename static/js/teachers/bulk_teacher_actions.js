// ==============================================================================
// KCC CLASSSTAMP - TEACHERS: BULK SELECTION & BULK ACTIONS CONTROLLER
// ==============================================================================
// Wires the bulk action bar + confirmation modal on the faculty roster:
//   - Row checkboxes with select-all / indeterminate state
//   - Explicit activate / deactivate / reset-password (never a blind toggle)
//   - Displays generated temporary credentials after a bulk reset
// ==============================================================================
(function (window) {
  'use strict';

  function getEl(id) { return document.getElementById(id); }

  function getCSRF() {
    if (window.TeachersApp && typeof window.TeachersApp.CSRF === 'string') {
      return window.TeachersApp.CSRF;
    }
    var meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || '';
  }

  function toast(type, message) {
    if (window.App && typeof window.App.toast === 'function') {
      window.App.toast(type, message);
    } else if (type === 'error') {
      alert(message);
    }
  }

  function showModal(id) {
    if (typeof window.openModal === 'function') window.openModal(id);
    else { var el = getEl(id); if (el) el.classList.add('is-active'); }
  }

  function hideModal(id) {
    if (typeof window.closeModal === 'function') window.closeModal(id);
    else { var el = getEl(id); if (el) el.classList.remove('is-active'); }
  }

  function init() {
    var bar = getEl('bulkActionsBar');
    var table = getEl('teacherTable');
    if (!bar || !table) return;

    var selectAll = getEl('selectAllTeachers');
    var actionSel = getEl('bulkAction');
    var countEl = getEl('bulkCount');
    var btnExecute = getEl('btnExecuteBulk');
    var btnCancel = getEl('btnCancelBulk');
    var btnConfirm = getEl('btnConfirmBulk');
    var actionDesc = getEl('bulkActionDesc');
    var countDesc = getEl('bulkCountDesc');
    var bulkUrl = bar.getAttribute('data-bulk-url') || '/teachers/bulk-operation/';

    var pendingAction = null;
    var pendingIds = [];

    function boxes() {
      return Array.prototype.slice.call(table.querySelectorAll('.teacher-checkbox'));
    }

    function selectedIds() {
      return boxes().filter(function (b) { return b.checked; }).map(function (b) { return b.value; });
    }

    function refresh() {
      var ids = selectedIds();
      var all = boxes();
      if (ids.length > 0) {
        bar.style.display = 'block';
        if (countEl) countEl.textContent = ids.length + ' of ' + all.length + ' selected';
      } else {
        bar.style.display = 'none';
      }
      if (selectAll) {
        selectAll.checked = ids.length > 0 && ids.length === all.length;
        selectAll.indeterminate = ids.length > 0 && ids.length < all.length;
      }
    }

    function clearSelection() {
      boxes().forEach(function (b) { b.checked = false; });
      if (actionSel) actionSel.value = '';
      refresh();
    }

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        boxes().forEach(function (b) { b.checked = selectAll.checked; });
        refresh();
      });
    }

    table.addEventListener('change', function (e) {
      if (e.target && e.target.classList.contains('teacher-checkbox')) refresh();
    });

    if (btnCancel) {
      btnCancel.addEventListener('click', clearSelection);
    }

    var ACTION_LABELS = {
      activate: 'activate',
      deactivate: 'deactivate',
      'reset-pw': 'reset the password of'
    };

    if (btnExecute) {
      btnExecute.addEventListener('click', function () {
        var ids = selectedIds();
        var action = actionSel ? actionSel.value : '';
        if (ids.length === 0) { toast('error', 'Select at least one faculty member.'); return; }
        if (!ACTION_LABELS[action]) { toast('error', 'Choose a bulk action first.'); return; }

        pendingAction = action;
        pendingIds = ids;
        if (actionDesc) actionDesc.textContent = ACTION_LABELS[action];
        if (countDesc) countDesc.textContent = ids.length + ' teacher' + (ids.length > 1 ? 's' : '');
        showModal('bulkConfirmation');
      });
    }

    if (btnConfirm) {
      btnConfirm.addEventListener('click', function () {
        if (!pendingAction || pendingIds.length === 0) return;

        var action = pendingAction;
        var ids = pendingIds.slice();
        hideModal('bulkConfirmation');

        if (window.App && typeof window.App.setButtonLoading === 'function') {
          window.App.setButtonLoading(btnConfirm, true, 'Processing...');
        } else {
          btnConfirm.disabled = true;
        }

        var body = new URLSearchParams();
        body.append('action', action);
        ids.forEach(function (id) { body.append('teacher_ids[]', id); });

        fetch(bulkUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCSRF(),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
          },
          body: body.toString()
        })
          .then(function (res) {
            return res.json().catch(function () { return {}; }).then(function (data) {
              return { ok: res.ok, data: data };
            });
          })
          .then(function (result) {
            if (!result.ok || !result.data.ok) {
              throw new Error((result.data && result.data.error) || 'Bulk action failed.');
            }
            var data = result.data;
            toast('success', data.message);

            if (data.credentials && data.credentials.length > 0) {
              showCredentials(data.credentials);
              clearSelection();
            } else {
              clearSelection();
              setTimeout(function () { window.location.reload(); }, 700);
            }
          })
          .catch(function (err) {
            toast('error', err.message || 'Bulk action failed.');
          })
          .then(function () {
            if (window.App && typeof window.App.setButtonLoading === 'function') {
              window.App.setButtonLoading(btnConfirm, false);
            } else {
              btnConfirm.disabled = false;
            }
          });
      });
    }

    function showCredentials(creds) {
      var existing = getEl('bulkPwResultModal');
      if (existing) existing.parentNode.removeChild(existing);

      var modal = document.createElement('div');
      modal.id = 'bulkPwResultModal';
      modal.className = 'modal';

      var dialog = document.createElement('div');
      dialog.className = 'modal-dialog';
      dialog.style.maxWidth = '560px';

      var header = document.createElement('div');
      header.className = 'modal-header';
      var title = document.createElement('h3');
      title.className = 'modal-title';
      title.textContent = 'Temporary Passwords';
      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'modal-close';
      closeBtn.innerHTML = '<i class="fas fa-xmark"></i>';
      closeBtn.addEventListener('click', function () {
        hideModal('bulkPwResultModal');
        window.location.reload();
      });
      header.appendChild(title);
      header.appendChild(closeBtn);

      var bodyEl = document.createElement('div');
      bodyEl.className = 'modal-body';

      var hint = document.createElement('p');
      hint.className = 'text-secondary text-sm';
      hint.textContent = 'Share each credential securely. These passwords are shown only once.';
      bodyEl.appendChild(hint);

      creds.forEach(function (c) {
        var row = document.createElement('div');
        row.style.cssText = 'display:flex;justify-content:space-between;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--glass-border);';

        var label = document.createElement('div');
        var name = document.createElement('div');
        name.className = 'text-primary text-sm font-semibold';
        name.textContent = c.display_name;
        var uname = document.createElement('div');
        uname.className = 'text-muted text-xs font-mono';
        uname.textContent = c.username;
        label.appendChild(name);
        label.appendChild(uname);

        var pw = document.createElement('code');
        pw.className = 'font-mono text-gold';
        pw.style.cssText = 'background:rgba(0,0,0,0.35);padding:4px 10px;border-radius:4px;user-select:all;';
        pw.textContent = c.temporary_password;

        var copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'btn btn-outline btn-sm';
        copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
        copyBtn.addEventListener('click', function () {
          if (navigator.clipboard) {
            navigator.clipboard.writeText(c.temporary_password).then(function () {
              toast('info', 'Password copied for ' + c.username);
            });
          }
        });

        var right = document.createElement('div');
        right.style.cssText = 'display:flex;align-items:center;gap:8px;';
        right.appendChild(pw);
        right.appendChild(copyBtn);

        row.appendChild(label);
        row.appendChild(right);
        bodyEl.appendChild(row);
      });

      var footer = document.createElement('div');
      footer.className = 'modal-footer';
      var done = document.createElement('button');
      done.type = 'button';
      done.className = 'btn btn-primary';
      done.textContent = 'Done';
      done.addEventListener('click', function () {
        hideModal('bulkPwResultModal');
        window.location.reload();
      });
      footer.appendChild(done);

      dialog.appendChild(header);
      dialog.appendChild(bodyEl);
      dialog.appendChild(footer);
      modal.appendChild(dialog);
      document.body.appendChild(modal);

      showModal('bulkPwResultModal');
    }

    refresh();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
