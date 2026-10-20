/* KCC ClassStamp — Classes: Roster Enlistment Modal Controller */
(function (window) {
  'use strict';

  var currentRosterClassId = null;

  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = window.ClassesApp;
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function bindRemoveEnrollmentButtons() {
    document.querySelectorAll('.btn-remove-enrollment').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!confirm('Are you sure you want to withdraw this student from this class section?')) return;
        var enrollmentId = this.dataset.id;
        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', getCSRF());

        fetch('/classes/roster/remove/' + enrollmentId + '/', {
          method: 'POST',
          body: fd,
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.success) {
            if (window.App && window.App.toast) {
              window.App.toast('success', 'Student removed from section.');
            }
            loadRosterData(currentRosterClassId);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast('error', res.message || 'Failed to remove student.');
            } else {
              alert(res.message || 'Failed to remove student.');
            }
          }
        })
        .catch(function (err) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Request failed: ' + err);
          } else {
            alert('Request failed: ' + err);
          }
        });
      });
    });
  }

  function loadRosterData(classId) {
    var rosterStudentsList      = getEl('rosterStudentsList');
    var rosterCountBadge        = getEl('rosterCountBadge');
    var rosterCapacityText      = getEl('rosterCapacityText');
    var availableStudentsSelect = getEl('availableStudentsSelect');

    if (rosterStudentsList) {
      rosterStudentsList.innerHTML = '<p class="text-muted text-xs">Loading roster...</p>';
    }

    fetch('/classes/' + classId + '/roster/')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) return;
        if (rosterCountBadge) rosterCountBadge.textContent = data.enrolled_count;
        if (rosterCapacityText) rosterCapacityText.textContent = data.capacity ? ('Capacity: ' + data.capacity + ' max') : 'No capacity limit';

        // Render available dropdown
        var optHtml = '<option value="">Choose an approved student to enlist...</option>';
        data.available.forEach(function (s) {
          optHtml += '<option value="' + s.profile_id + '">' + s.student_name + ' (' + s.student_id + ' \u00b7 ' + s.program + ')</option>';
        });
        if (availableStudentsSelect) availableStudentsSelect.innerHTML = optHtml;

        // Render enrolled list
        if (data.enrolled.length === 0) {
          if (rosterStudentsList) rosterStudentsList.innerHTML = '<p class="text-muted text-xs p-3 text-center">No students currently enrolled in this section.</p>';
        } else {
          var listHtml = '';
          data.enrolled.forEach(function (en) {
            listHtml +=
              '<div class="p-2 flex items-center justify-between" style="background: rgba(255,255,255,0.03); border: 1px solid var(--glass-border); border-radius: 4px;">' +
              '  <div>' +
              '    <div class="font-semibold text-xs text-primary">' + en.student_name + '</div>' +
              '    <div class="text-xs text-muted" style="font-size: 0.68rem;">' + en.student_id + ' \u00b7 ' + en.program + ' \u00b7 Enrolled ' + en.enrolled_at + '</div>' +
              '  </div>' +
              '  <button type="button" class="btn btn-ghost btn-xs text-error btn-remove-enrollment" data-id="' + en.enrollment_id + '" title="Withdraw student from section">' +
              '    <i class="fas fa-user-minus"></i> Remove' +
              '  </button>' +
              '</div>';
          });
          if (rosterStudentsList) rosterStudentsList.innerHTML = listHtml;
          bindRemoveEnrollmentButtons();
        }
      })
      .catch(function (err) {
        if (rosterStudentsList) rosterStudentsList.innerHTML = '<p class="text-error text-xs">Failed to load roster: ' + err + '</p>';
      });
  }

  function initRosterModal() {
    // Guard: only run if the roster modal exists on this page
    var rosterModal = getEl('rosterModal');
    if (!rosterModal) return;

    var closeRosterModal = getEl('closeRosterModal');
    var btnEnrollStudent = getEl('btnEnrollStudent');

    // Event delegation for Manage Roster button clicks
    document.addEventListener('click', function (e) {
      var rosterBtn = e.target.closest('.btn-manage-roster');
      if (!rosterBtn) return;

      e.preventDefault();
      currentRosterClassId = rosterBtn.dataset.classId;
      var rosterModalClassCode = getEl('rosterModalClassCode');
      if (rosterModalClassCode) rosterModalClassCode.textContent = rosterBtn.dataset.classCode;
      if (typeof window.openModal === 'function') {
        window.openModal('rosterModal', rosterBtn);
      } else {
        rosterModal.classList.add('is-open', 'is-active');
      }
      loadRosterData(currentRosterClassId);
    });

    // Enroll student button click
    if (btnEnrollStudent) {
      btnEnrollStudent.addEventListener('click', function () {
        var availableStudentsSelect = getEl('availableStudentsSelect');
        var profileId = availableStudentsSelect && availableStudentsSelect.value;
        if (!profileId || !currentRosterClassId) {
          if (window.App && window.App.toast) {
            window.App.toast('warning', 'Please choose an approved student to enlist.');
          } else {
            alert('Please choose a student to enlist.');
          }
          return;
        }

        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(btnEnrollStudent, true, 'Enlisting...');
        }

        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', getCSRF());
        fd.append('profile_id', profileId);

        fetch('/classes/' + currentRosterClassId + '/roster/enroll/', {
          method: 'POST',
          body: fd,
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.success) {
            if (window.App && window.App.toast) {
              window.App.toast('success', 'Student enlisted successfully.');
            }
            loadRosterData(currentRosterClassId);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast('error', res.message || 'Failed to enlist student.');
            } else {
              alert(res.message || 'Failed to enlist student.');
            }
          }
        })
        .catch(function (err) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Enroll request failed: ' + err);
          } else {
            alert('Enroll request failed: ' + err);
          }
        })
        .finally(function () {
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(btnEnrollStudent, false);
          }
        });
      });
    }

    // Close handler
    if (closeRosterModal) {
      closeRosterModal.addEventListener('click', function () {
        if (typeof window.closeModal === 'function') {
          window.closeModal('rosterModal');
        } else {
          rosterModal.classList.remove('is-open', 'is-active');
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRosterModal);
  } else {
    initRosterModal();
  }
})(window);
