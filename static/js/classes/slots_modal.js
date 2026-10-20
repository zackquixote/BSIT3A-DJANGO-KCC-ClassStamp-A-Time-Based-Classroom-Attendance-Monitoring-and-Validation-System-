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
        html += '<div class="p-2" style="background: rgba(255,255,255,0.03); border: 1px solid var(--glass-border); border-radius: 4px; display: flex; align-items: center; justify-content: space-between;">' +
                '<span class="text-xs text-primary font-semibold">' + row.innerHTML + '</span>' +
                '<span class="text-xs text-muted">(Active)</span>' +
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
      slotsModal.classList.add('is-open');
      loadSlotsUI(slotsBtn);
    });

    // Add slot form submission
    if (addSlotForm) {
      addSlotForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!currentSlotClassId) return;
        var formData = new FormData(addSlotForm);
        fetch('/classes/' + currentSlotClassId + '/slot/save/', {
          method: 'POST',
          body: formData,
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.success) {
            window.location.reload();
          } else {
            alert(res.message || 'Error saving slot.');
          }
        })
        .catch(function (err) { alert('Request failed: ' + err); });
      });
    }

    // Close handler
    if (closeSlotsModal) {
      closeSlotsModal.addEventListener('click', function () {
        slotsModal.classList.remove('is-open');
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSlotsModal);
  } else {
    initSlotsModal();
  }
})(window);
