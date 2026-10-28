/* KCC ClassStamp — Classes: Roster Enlistment Modal Controller */
(function (window) {
  'use strict';

  var currentRosterClassId = null;
  var lastRosterClassId = null;

  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = window.ClassesApp;
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function bindRemoveEnrollmentButtons() {
    document.querySelectorAll('.btn-remove-enrollment').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        var confirmed = window.App && window.App.confirm
          ? await window.App.confirm({
              title: 'Withdraw Student',
              message: 'Are you sure you want to withdraw this student from this class section?',
              confirmText: 'Withdraw',
              confirmClass: 'btn-danger',
              type: 'danger'
            })
          : confirm('Are you sure you want to withdraw this student from this class section?');

        if (!confirmed) return;
        var enrollmentId = btn.dataset.id;
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
    var programFilter           = getEl('rosterProgramFilter');
    var yearFilter              = getEl('rosterYearFilter');
    var batchLabel              = getEl('rosterBatchLabel');

    if (rosterStudentsList) {
      rosterStudentsList.innerHTML = '<p class="text-muted text-xs">Loading roster...</p>';
    }

    var params = new URLSearchParams();
    if (programFilter && programFilter.value) params.set('program_id', programFilter.value);
    if (yearFilter && yearFilter.value) params.set('year_level', yearFilter.value);
    var qs = params.toString() ? ('?' + params.toString()) : '';

    fetch('/classes/' + classId + '/roster/' + qs)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) return;
        if (rosterCountBadge) rosterCountBadge.textContent = data.enrolled_count;
        if (rosterCapacityText) {
          rosterCapacityText.textContent = data.capacity
            ? ('Seats: ' + data.enrolled_count + ' / ' + data.capacity)
            : (data.enrolled_count + ' enrolled \u00b7 no capacity limit');
        }

        // Auto-scope the candidate filters to the section's own program/year
        // the first time this section is opened, not on every reload.
        if (classId !== lastRosterClassId) {
          lastRosterClassId = classId;
          if (programFilter) programFilter.value = data.class_program_id ? String(data.class_program_id) : '';
          if (yearFilter) yearFilter.value = data.class_year_level ? String(data.class_year_level) : '';
        }
        if (batchLabel) {
          var scope = [];
          if (programFilter && programFilter.value) {
            var opt = programFilter.options[programFilter.selectedIndex];
            scope.push(opt ? opt.textContent : 'program');
          }
          if (yearFilter && yearFilter.value) scope.push('Year ' + yearFilter.value);
          batchLabel.textContent = scope.length
            ? ('Enlist All ' + scope.join(' ') + ' Students')
            : 'Enlist All Matching Students';
        }

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
    var btnBatchEnroll = getEl('btnRosterBatchEnroll');
    var programFilter = getEl('rosterProgramFilter');
    var yearFilter = getEl('rosterYearFilter');

    // Candidate scope filters reload the available-students dropdown
    [programFilter, yearFilter].forEach(function (sel) {
      if (sel) sel.addEventListener('change', function () {
        if (currentRosterClassId) loadRosterData(currentRosterClassId);
      });
    });

    // Batch enlist: every approved candidate in the current scope
    if (btnBatchEnroll) {
      btnBatchEnroll.addEventListener('click', async function () {
        if (!currentRosterClassId) return;
        var confirmed = window.App && window.App.confirm
          ? await window.App.confirm({
              title: 'Batch Enlistment',
              message: 'Enlist every approved student matching the current program/year scope into this section?',
              confirmText: 'Enlist All',
              confirmClass: 'btn-primary',
              type: 'info'
            })
          : confirm('Enlist every approved student matching the current program/year scope into this section?');

        if (!confirmed) return;

        if (window.App && window.App.setButtonLoading) {
          window.App.setButtonLoading(btnBatchEnroll, true, 'Enlisting...');
        }

        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', getCSRF());
        if (programFilter && programFilter.value) fd.append('program_id', programFilter.value);
        if (yearFilter && yearFilter.value) fd.append('year_level', yearFilter.value);

        fetch('/classes/' + currentRosterClassId + '/roster/enroll-batch/', {
          method: 'POST',
          body: fd,
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.success) {
            if (window.App && window.App.toast) {
              window.App.toast('success', res.message || 'Batch enlistment completed.');
            }
            loadRosterData(currentRosterClassId);
          } else {
            if (window.App && window.App.toast) {
              window.App.toast('error', res.message || 'Batch enlistment failed.');
            } else {
              alert(res.message || 'Batch enlistment failed.');
            }
          }
        })
        .catch(function (err) {
          if (window.App && window.App.toast) {
            window.App.toast('error', 'Batch enlist request failed: ' + err);
          } else {
            alert('Batch enlist request failed: ' + err);
          }
        })
        .finally(function () {
          if (window.App && window.App.setButtonLoading) {
            window.App.setButtonLoading(btnBatchEnroll, false);
          }
        });
      });
    }

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
