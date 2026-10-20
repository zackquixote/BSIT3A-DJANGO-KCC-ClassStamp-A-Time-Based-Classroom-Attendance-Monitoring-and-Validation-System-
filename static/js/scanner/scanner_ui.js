/* KCC ClassStamp — Teacher Scanner: UI Controller */
(function (window) {
  'use strict';

  window.ScannerApp = window.ScannerApp || {};

  function getEl(id) {
    return document.getElementById(id);
  }

  function showAlert(msg) {
    var alertBox = getEl('scannerAlert');
    var alertText = getEl('scannerAlertText');
    if (!alertBox || !alertText) return;
    alertText.textContent = msg;
    alertBox.style.display = 'flex';
    setTimeout(function () { alertBox.style.display = 'none'; }, 5000);
  }

  function initGraceTimer(cutoffTime) {
    var graceCountdownEl = getEl('graceCountdown');
    if (!graceCountdownEl || !cutoffTime) return;

    function updateGraceTimer() {
      var now = Date.now();
      var diff = cutoffTime - now;
      if (diff > 0) {
        var mins = Math.floor(diff / 60000);
        var secs = Math.floor((diff % 60000) / 1000);
        graceCountdownEl.textContent = mins + 'm ' + (secs < 10 ? '0' : '') + secs + 's (Present)';
        graceCountdownEl.className = 'font-mono text-sm font-bold text-success';
      } else {
        var lateMins = Math.floor(Math.abs(diff) / 60000);
        graceCountdownEl.textContent = 'Grace Ended (+' + lateMins + 'm Late)';
        graceCountdownEl.className = 'font-mono text-sm font-bold text-warning';
      }
    }
    updateGraceTimer();
    setInterval(updateGraceTimer, 1000);
  }

  function updateHeroCard(data) {
    var heroPlaceholder  = getEl('heroPlaceholder');
    var heroContent      = getEl('heroContent');
    var heroTimestamp    = getEl('heroTimestamp');
    var heroInitials     = getEl('heroInitials');
    var heroName         = getEl('heroName');
    var heroStudentNumber = getEl('heroStudentNumber');
    var heroProgram      = getEl('heroProgram');
    var heroStatusBadge  = getEl('heroStatusBadge');
    var heroLateNote     = getEl('heroLateNote');

    if (heroPlaceholder) heroPlaceholder.style.display = 'none';
    if (heroContent) heroContent.style.display = 'block';

    if (heroTimestamp) heroTimestamp.textContent = data.stamped_at;
    if (heroInitials) heroInitials.textContent = data.initials || '??';
    if (heroName) heroName.textContent = data.student_name;
    if (heroStudentNumber) heroStudentNumber.textContent = data.student_number;
    if (heroProgram) heroProgram.textContent = data.program_code + ' · Year ' + data.year_level;

    if (data.record_status === 'PRESENT') {
      if (heroStatusBadge) {
        heroStatusBadge.className = 'badge badge--success text-sm';
        heroStatusBadge.innerHTML = '<i class="fas fa-circle-check"></i> PRESENT';
      }
      if (heroLateNote) {
        heroLateNote.textContent = 'Stamped on-time within grace window';
        heroLateNote.className = 'text-success';
      }
    } else {
      if (heroStatusBadge) {
        heroStatusBadge.className = 'badge badge--warning text-sm';
        heroStatusBadge.innerHTML = '<i class="fas fa-clock"></i> LATE (+' + data.late_minutes + 'm)';
      }
      if (heroLateNote) {
        heroLateNote.textContent = 'Tardy arrival: +' + data.late_minutes + ' minutes past grace period cutoff';
        heroLateNote.className = 'text-warning';
      }
    }
  }

  function updateRosterRow(data) {
    var row = document.getElementById('roster-row-' + data.student_id);
    var statusWrap = document.getElementById('roster-status-wrap-' + data.student_id);
    if (row && statusWrap) {
      row.setAttribute('data-status', data.record_status);

      if (data.record_status === 'PRESENT') {
        statusWrap.innerHTML =
          '<span class="badge badge--success text-xs"><i class="fas fa-circle-check"></i> Present</span>' +
          '<span class="text-muted text-xs font-mono ml-1" style="font-size: 0.62rem;">' + data.stamped_at + '</span>';
      } else {
        statusWrap.innerHTML =
          '<span class="badge badge--warning text-xs"><i class="fas fa-clock"></i> Late (+' + data.late_minutes + 'm)</span>' +
          '<span class="text-muted text-xs font-mono ml-1" style="font-size: 0.62rem;">' + data.stamped_at + '</span>';
      }

      row.style.background = 'rgba(34, 197, 94, 0.15)';
      setTimeout(function () { row.style.background = ''; }, 1800);
    }
  }

  function updateCounters(counts) {
    if (!counts) return;
    var p = getEl('counterPresent');
    var l = getEl('counterLate');
    var a = getEl('counterAbsent');
    var pen = getEl('counterPending');
    var modalPen = getEl('modalPendingCount');

    if (p) p.textContent = counts.present;
    if (l) l.textContent = counts.late;
    if (a) a.textContent = counts.absent;
    if (pen) pen.textContent = counts.pending;
    if (modalPen) modalPen.textContent = counts.pending;
  }

  function initRosterFilters() {
    var rosterSearch = getEl('rosterSearch');
    var statusFilter = getEl('statusFilter');

    function filterRoster() {
      var q = (rosterSearch && rosterSearch.value ? rosterSearch.value : '').toLowerCase().trim();
      var st = (statusFilter && statusFilter.value ? statusFilter.value : 'ALL').toUpperCase();

      document.querySelectorAll('#rosterTbody tr').forEach(function (row) {
        var name = (row.getAttribute('data-name') || '').toLowerCase();
        var ident = (row.getAttribute('data-ident') || '').toLowerCase();
        var status = (row.getAttribute('data-status') || '').toUpperCase();

        var matchesQuery = !q || name.indexOf(q) !== -1 || ident.indexOf(q) !== -1;
        var matchesStatus = st === 'ALL' || status === st;

        row.style.display = (matchesQuery && matchesStatus) ? '' : 'none';
      });
    }

    if (rosterSearch) rosterSearch.addEventListener('input', filterRoster);
    if (statusFilter) statusFilter.addEventListener('change', filterRoster);
  }

  function initManualDrawer() {
    var manualDrawer    = getEl('manualInputDrawer');
    var manualToggleBtn = getEl('manualInputToggleBtn');
    var manualInput     = getEl('manualPayloadInput');
    var manualSubmitBtn = getEl('manualSubmitBtn');

    if (manualToggleBtn && manualDrawer) {
      manualToggleBtn.addEventListener('click', function () {
        var isHidden = manualDrawer.style.display === 'none';
        manualDrawer.style.display = isHidden ? 'block' : 'none';
        if (isHidden && manualInput) manualInput.focus();
      });
    }

    if (manualSubmitBtn && manualInput) {
      manualSubmitBtn.addEventListener('click', function () {
        var val = manualInput.value.trim();
        if (!val) return;
        if (window.ScannerApp && window.ScannerApp.onQrCodeScanned) {
          window.ScannerApp.onQrCodeScanned(val);
        }
        manualInput.value = '';
      });

      manualInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          manualSubmitBtn.click();
        }
      });
    }
  }

  function initOverrideModal(sessionId, csrfToken) {
    window.openOverrideModal = function (studentId, fullName, ident, currentStatus) {
      var sIdEl = getEl('override_student_id');
      var nameEl = getEl('override_student_name');
      var identEl = getEl('override_student_ident');
      var statusEl = getEl('override_status');
      var reasonEl = getEl('override_reason');
      var alertEl = getEl('overrideAlert');

      if (sIdEl) sIdEl.value = studentId;
      if (nameEl) nameEl.textContent = fullName;
      if (identEl) identEl.textContent = 'ID: ' + ident;
      if (statusEl) statusEl.value = currentStatus === 'PENDING' ? 'PRESENT' : currentStatus;
      if (reasonEl) reasonEl.value = '';
      if (alertEl) alertEl.style.display = 'none';

      if (window.openModal) window.openModal('overrideModal');
      else {
        var m = getEl('overrideModal');
        if (m) m.classList.add('is-active');
      }
    };

    var overrideForm = getEl('overrideForm');
    var overrideAlert = getEl('overrideAlert');
    if (overrideForm) {
      overrideForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var sId = getEl('override_student_id').value;
        var statusVal = getEl('override_status').value;
        var reasonVal = getEl('override_reason').value;

        var postData = new FormData();
        postData.append('student_id', sId);
        postData.append('status', statusVal);
        postData.append('reason', reasonVal);

        fetch('/teacher/session/' + sessionId + '/override/', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: postData
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'success') {
            var row = document.getElementById('roster-row-' + sId);
            var statusWrap = document.getElementById('roster-status-wrap-' + sId);
            if (row && statusWrap) {
              row.setAttribute('data-status', data.new_status);
              if (data.new_status === 'PRESENT') {
                statusWrap.innerHTML = '<span class="badge badge--success text-xs"><i class="fas fa-circle-check"></i> Present</span> <span class="text-muted text-xs font-mono ml-1" style="font-size: 0.62rem;">' + data.stamped_at + '</span>';
              } else if (data.new_status === 'LATE') {
                statusWrap.innerHTML = '<span class="badge badge--warning text-xs"><i class="fas fa-clock"></i> Late</span> <span class="text-muted text-xs font-mono ml-1" style="font-size: 0.62rem;">' + data.stamped_at + '</span>';
              } else if (data.new_status === 'EXCUSED') {
                statusWrap.innerHTML = '<span class="badge badge--purple text-xs"><i class="fas fa-file-medical"></i> Excused</span>';
              } else {
                statusWrap.innerHTML = '<span class="badge badge--danger text-xs"><i class="fas fa-circle-xmark"></i> Absent</span>';
              }
            }
            updateCounters(data.counts);
            if (window.closeModal) window.closeModal('overrideModal');
            else {
              var m = getEl('overrideModal');
              if (m) m.classList.remove('is-active');
            }
            if (window.ScannerApp && window.ScannerApp.playChime) {
              window.ScannerApp.playChime(data.new_status === 'PRESENT' ? 'PRESENT' : 'LATE');
            }
          } else {
            if (overrideAlert) {
              overrideAlert.textContent = data.error || 'Failed to update record.';
              overrideAlert.style.display = 'flex';
            }
          }
        })
        .catch(function () {
          if (overrideAlert) {
            overrideAlert.textContent = 'Network communication error.';
            overrideAlert.style.display = 'flex';
          }
        });
      });
    }
  }

  function initUI() {
    var config = window.ScannerConfig || {};
    initGraceTimer(config.graceCutoffTime);
    initRosterFilters();
    initManualDrawer();
    initOverrideModal(config.sessionId, config.csrfToken);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUI);
  } else {
    initUI();
  }

  window.ScannerApp.showAlert = showAlert;
  window.ScannerApp.updateHeroCard = updateHeroCard;
  window.ScannerApp.updateRosterRow = updateRosterRow;
  window.ScannerApp.updateCounters = updateCounters;
})(window);
