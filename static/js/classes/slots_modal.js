/* KCC ClassStamp — Classes: Timetable Slots Modal Controller */
(function (window) {
  'use strict';

  var currentSlotClassId = null;

  function getEl(id) { return document.getElementById(id); }

  function loadSlotsUI(btnElement) {
    var existingSlotsContainer = getEl('existingSlotsContainer');
    if (!existingSlotsContainer) return;

    var tr = btnElement.closest('tr');
    var slotRows = tr.querySelectorAll('td:nth-child(4) .flex-col > div');
    var html = '';
    if (slotRows.length === 0) {
      html = '<p class="text-muted text-xs">No schedule slots currently registered.</p>';
    } else {
      slotRows.forEach(function (row) {
        var slotId = row.dataset.slotId;
        html += '<div class="p-2" style="background: rgba(255,255,255,0.03); border: 1px solid var(--glass-border); border-radius: 4px; display: flex; align-items: center; justify-content: space-between;">' +
                '<span class="text-xs text-primary font-semibold">' + row.innerHTML + '</span>' +
                (slotId ? '<button type="button" class="btn btn-ghost btn-xs text-danger btn-delete-slot" data-slot-id="' + slotId + '" style="color: #f87171; padding: 2px 6px;" title="Remove timetable slot"><i class="fas fa-trash"></i></button>' : '<span class="text-xs text-muted">(Active)</span>') +
                '</div>';
      });
    }
    existingSlotsContainer.innerHTML = html;
  }

  function initSlotsModal() {
    // Guard: only run if the slots modal exists on this page
    var slotsModal = getEl('slotsModal');
    if (!slotsModal) return;

    var closeSlotsModal    = getEl('closeSlotsModal');
    var slotsModalClassCode = getEl('slotsModalClassCode');
    var addSlotForm         = getEl('addSlotForm');

    // Event delegation for Manage Slots button clicks
    document.addEventListener('click', function (e) {
      var slotsBtn = e.target.closest('.btn-manage-slots');
      if (!slotsBtn) return;

      e.preventDefault();
      currentSlotClassId = slotsBtn.dataset.classId;
      if (slotsModalClassCode) slotsModalClassCode.textContent = slotsBtn.dataset.classCode;
      if (typeof window.openModal === 'function') {
        window.openModal('slotsModal', slotsBtn);
      } else {
        slotsModal.classList.add('is-open', 'is-active');
      }
      loadSlotsUI(slotsBtn);
    });

    // Delete slot action
    document.addEventListener('click', function (e) {
      var delBtn = e.target.closest('.btn-delete-slot');
      if (!delBtn) return;
      var slotId = delBtn.dataset.slotId;
      if (!slotId) return;

      var doDelete = confirm('Are you sure you want to remove this timetable slot?');
      if (!doDelete) return;

      delBtn.disabled = true;
      var csrf = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
      fetch('/classes/slot/delete/' + slotId + '/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res.success) {
          if (window.App && window.App.toast) {
            window.App.toast('success', res.message || 'Timetable slot removed.');
          }
          setTimeout(function () { window.location.reload(); }, 600);
        } else {
          alert(res.message || 'Error removing slot.');
          delBtn.disabled = false;
        }
      })
      .catch(function (err) {
        alert('Network error: ' + err);
        delBtn.disabled = false;
      });
    });

    // Add slot form submission
    if (addSlotForm) {
      addSlotForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!currentSlotClassId) return;

        var submitBtn = addSlotForm.querySelector('button[type="submit"]');
        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(submitBtn, true, 'Saving Slot...');
        }

        var formData = new FormData(addSlotForm);
        fetch('/classes/' + currentSlotClassId + '/slot/save/', {
          method: 'POST',
          body: formData,
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.success) {
            if (window.App && window.App.toast) {
              window.App.toast('success', 'Timetable slot added successfully.');
            }
            setTimeout(function () { window.location.reload(); }, 600);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast('error', res.message || 'Error saving slot.');
            } else {
              alert(res.message || 'Error saving slot.');
            }
            if (window.App && window.App.setButtonLoading) {
              window.App.setButtonLoading(submitBtn, false);
            }
          }
        })
        .catch(function (err) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Request failed: ' + err);
          } else {
            alert('Request failed: ' + err);
          }
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(submitBtn, false);
          }
        });
      });
    }

    // Close handler
    if (closeSlotsModal) {
      closeSlotsModal.addEventListener('click', function () {
        if (typeof window.closeModal === 'function') {
          window.closeModal('slotsModal');
        } else {
          slotsModal.classList.remove('is-open', 'is-active');
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSlotsModal);
  } else {
    initSlotsModal();
  }
})(window);
