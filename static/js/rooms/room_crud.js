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
})();
