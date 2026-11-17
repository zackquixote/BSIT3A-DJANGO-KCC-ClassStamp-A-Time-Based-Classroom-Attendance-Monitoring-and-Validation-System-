/**
 * KCC ClassStamp — Campus Room CRUD Management Controller
 * Handles create/update modal, validation, AJAX submission, and protected deactivation.
 */
(function () {
  'use strict';

  function getEl(id) {
    return document.getElementById(id);
  }

  function openModal(modalId) {
    var modal = getEl(modalId);
    if (!modal) return;
    if (typeof window.openModal === 'function') {
      window.openModal(modalId);
    } else {
      modal.classList.add('is-active', 'is-open');
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal(modalId) {
    var modal = getEl(modalId);
    if (!modal) return;
    if (typeof window.closeModal === 'function') {
      window.closeModal(modalId);
    } else {
      modal.classList.remove('is-active', 'is-open');
      modal.style.display = 'none';
      document.body.style.overflow = '';
    }
  }

  // Dismiss listeners are handled globally by static/js/core/app_modals.js.

  // Add Room Button Click
  var addBtn = getEl('addRoomBtn');
  if (addBtn) {
    addBtn.addEventListener('click', function () {
      var form = getEl('editRoomForm');
      if (form) form.reset();
      getEl('room_id').value = '';
      getEl('editRoomModalTitle').textContent = 'Add Campus Room';
      getEl('room_capacity').value = '40';
      getEl('room_is_active').checked = true;
      var errBox = getEl('roomFormError');
      if (errBox) errBox.style.display = 'none';
      openModal('editRoomModal');
    });
  }

  // Edit Room Delegated Click
  document.addEventListener('click', function (e) {
    var editBtn = e.target.closest('.js-edit-room');
    if (!editBtn) return;

    var d = editBtn.dataset;
    getEl('room_id').value = d.id || '';
    getEl('room_code').value = d.code || '';
    getEl('room_name').value = d.name || '';
    if (d.type) getEl('room_type').value = d.type;
    getEl('room_capacity').value = d.capacity || '40';
    getEl('room_notes').value = d.notes || '';
    getEl('room_is_active').checked = d.active === 'true';

    getEl('editRoomModalTitle').textContent = 'Edit Room ' + (d.code || '');
    var errBox = getEl('roomFormError');
    if (errBox) errBox.style.display = 'none';
    openModal('editRoomModal');
  });

  // Save Room Form Submission
  var roomForm = getEl('editRoomForm');
  if (roomForm) {
    roomForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var saveBtn = getEl('saveRoomBtn');
      var errBox = getEl('roomFormError');
      var errMsg = getEl('roomFormErrorMsg');

      if (errBox) errBox.style.display = 'none';
      var originalBtnHtml = saveBtn.innerHTML;
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

      var formData = new FormData(roomForm);
      if (!getEl('room_is_active').checked) {
        formData.set('is_active', '0');
      } else {
        formData.set('is_active', '1');
      }

      try {
        var res = await fetch(roomForm.action, {
          method: 'POST',
          body: formData,
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
        });

        var data = await res.json();
        if (!res.ok || data.error) {
          throw new Error(data.error || 'Failed to save room.');
        }

        if (window.App && window.App.toast) {
          window.App.toast('success', data.message || 'Room saved successfully.');
        }
        closeModal('editRoomModal');
        window.location.reload();
      } catch (err) {
        if (errBox && errMsg) {
          errMsg.textContent = err.message;
          errBox.style.display = 'flex';
        } else {
          alert(err.message);
        }
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalBtnHtml;
      }
    });
  }

  // Delete / Deactivate Room Delegated Click
  document.addEventListener('click', function (e) {
    var delBtn = e.target.closest('.js-delete-room');
    if (!delBtn) return;

    var d = delBtn.dataset;
    var slots = parseInt(d.slots || '0', 10);

    getEl('delete_room_code').textContent = d.code || '';
    getEl('deleteRoomForm').action = '/rooms/delete/' + d.id + '/';

    var warn = getEl('delete_room_warning');
    var slotCountEl = getEl('delete_room_slot_count');
    var errBox = getEl('deleteRoomError');
    if (errBox) errBox.style.display = 'none';

    var applyCount = function (count) {
      if (slotCountEl) slotCountEl.textContent = count;
      if (warn) warn.style.display = count > 0 ? 'flex' : 'none';
    };

    // Prefer the server-side attached-slot count (same rule the delete
    // service uses: room_ref FK OR legacy code-string match, any status).
    // Fall back to the row's data-slots attribute if the fetch fails.
    if (d.id) {
      fetch('/rooms/' + d.id + '/json/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && typeof data.attached_slot_count === 'number') {
            applyCount(data.attached_slot_count);
          } else {
            applyCount(slots);
          }
        })
        .catch(function () { applyCount(slots); });
    } else {
      applyCount(slots);
    }

    openModal('deleteRoomModal');
  });

  // Delete Room Form Submission
  var delForm = getEl('deleteRoomForm');
  if (delForm) {
    delForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = getEl('confirmDeleteRoomBtn');
      var originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

      try {
        var formData = new FormData(delForm);
        var res = await fetch(delForm.action, {
          method: 'POST',
          body: formData,
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
        });
        var data = await res.json();
        if (!res.ok || data.error) {
          throw new Error(data.error || 'Operation failed.');
        }
        closeModal('deleteRoomModal');
        window.location.reload();
      } catch (err) {
        var errBox = getEl('deleteRoomError');
        var errMsg = getEl('deleteRoomErrorMsg');
        if (errBox && errMsg) {
          errMsg.textContent = err.message;
          errBox.style.display = 'flex';
        } else {
          alert(err.message);
        }
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      }
    });
  }
  /* ── Facility type manager (inside Add / Edit Room) ────────── */
  (function () {
    var panel = getEl('typeManager');
    if (!panel) return;

    var toggle = getEl('toggleTypeManager');
    var list = getEl('typeManagerList');
    var nameInput = getEl('newTypeName');
    var addBtn = getEl('addTypeBtn');

    nameInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        addBtn.click();
      }
    });
    var errorEl = getEl('typeManagerError');
    var select = getEl('room_type');
    var saveUrl = panel.dataset.saveUrl;
    var deleteTemplate = panel.dataset.deleteUrlTemplate;
    var csrfEl = document.querySelector('#editRoomForm [name="csrfmiddlewaretoken"]');
    var csrf = csrfEl ? csrfEl.value : '';

    function showError(msg) {
      if (!errorEl) return;
      errorEl.textContent = msg || '';
      errorEl.style.display = msg ? 'block' : 'none';
    }

    function optionFor(code) {
      for (var i = 0; i < select.options.length; i++) {
        if (select.options[i].value === code) return select.options[i];
      }
      return null;
    }

    function submitType(fields, onOk) {
      var body = new FormData();
      Object.keys(fields).forEach(function (key) { body.append(key, fields[key]); });
      fetch(saveUrl, {
        method: 'POST',
        body: body,
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data.status !== 'success') throw new Error(data.error || 'Save failed.');
          showError('');
          onOk(data.type);
        })
        .catch(function (err) { showError(err.message); });
    }

    function makeButton(cls, title, icon) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'type-icon-btn ' + cls;
      btn.title = title;
      var i = document.createElement('i');
      i.className = 'fas ' + icon;
      btn.appendChild(i);
      return btn;
    }

    function makeRow(t) {
      var row = document.createElement('div');
      row.className = 'type-row';
      row.dataset.id = t.id;
      row.dataset.code = t.code;
      row.dataset.name = t.name;
      row.dataset.used = t.room_count || 0;
      row.dataset.protected = t.protected ? 'true' : 'false';

      var name = document.createElement('span');
      name.className = 'type-name';
      name.textContent = t.name;
      row.appendChild(name);

      if (t.protected) {
        var flag = document.createElement('span');
        flag.className = 'type-flag';
        flag.textContent = 'built-in';
        row.appendChild(flag);
      }

      row.appendChild(makeButton('js-type-rename', 'Rename facility type', 'fa-pen'));
      row.appendChild(makeButton('js-type-delete', 'Delete facility type', 'fa-trash'));
      return row;
    }

    toggle.addEventListener('click', function () {
      var willOpen = panel.hidden;
      panel.hidden = !willOpen;
      toggle.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
      if (willOpen) showError('');
    });

    addBtn.addEventListener('click', function () {
      var name = (nameInput.value || '').trim();
      if (!name) {
        showError('Enter a name for the new facility type.');
        nameInput.focus();
        return;
      }
      var code = name.toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 20);
      if (!code) {
        showError('Use letters or numbers in the type name.');
        return;
      }
      submitType({ code: code, name: name }, function (t) {
        if (!optionFor(t.code)) select.add(new Option(t.name, t.code));
        list.appendChild(makeRow(t));
        select.value = t.code;
        nameInput.value = '';
      });
    });

    list.addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      var row = btn.closest('.type-row');
      if (!row) return;
      var d = row.dataset;

      if (btn.classList.contains('js-type-rename')) {
        var next = window.prompt('Rename facility type', d.name);
        if (!next || !next.trim() || next.trim() === d.name) return;
        submitType({ id: d.id, code: d.code, name: next.trim() }, function (t) {
          row.dataset.name = t.name;
          row.querySelector('.type-name').textContent = t.name;
          var option = optionFor(t.code);
          if (option) option.textContent = t.name;
        });
        return;
      }

      if (btn.classList.contains('js-type-delete')) {
        if (d.protected === 'true') {
          showError('Built-in types can be renamed but not deleted.');
          return;
        }
        if (parseInt(d.used || '0', 10) > 0) {
          showError(d.name + ' is used by ' + d.used + ' room(s). Reassign them first.');
          return;
        }
        if (!window.confirm('Delete "' + d.name + '"?')) return;
        fetch(deleteTemplate.replace('/0/', '/' + d.id + '/'), {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then(function (res) { return res.json(); })
          .then(function (data) {
            if (data.status !== 'success') throw new Error(data.error || 'Delete failed.');
            var option = optionFor(d.code);
            if (option) option.remove();
            row.remove();
            showError('');
          })
          .catch(function (err) { showError(err.message); });
      }
    });
  })();

})();
