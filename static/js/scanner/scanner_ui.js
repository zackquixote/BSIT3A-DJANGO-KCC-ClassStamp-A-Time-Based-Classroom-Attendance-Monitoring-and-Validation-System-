/* KCC ClassStamp — Teacher Scanner: UI Controller */
(function (window) {
  'use strict';

  window.ScannerApp = window.ScannerApp || {};

  function getEl(id) {
    return document.getElementById(id);
  }

  function showAlert(msg) {
    if (window.App && window.App.toast) { window.App.toast('error', msg); return; }
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

    if (kiosk.active) updateKioskResult(data);
  }

  // ---------------------------------------------------------------------------
  // KIOSK MODE (T-07): fullscreen projector overlay with masked identity data
  // ---------------------------------------------------------------------------
  var kiosk = { active: false, hideTimer: null };

  function maskStudentNumber(number) {
    if (!number) return '—';
    var str = String(number);
    if (str.length <= 4) return '•••' + str.slice(-2);
    return '••••••' + str.slice(-4);
  }

  function resetKioskHideTimer() {
    if (!kiosk.active) return;
    if (kiosk.hideTimer) clearTimeout(kiosk.hideTimer);
    kiosk.hideTimer = setTimeout(showKioskIdle, 2500);
  }

  function showKioskIdle() {
    var idle = getEl('kioskIdle');
    var result = getEl('kioskResult');
    if (idle) idle.style.display = 'block';
    if (result) result.style.display = 'none';
  }

  function updateKioskResult(data) {
    var idle = getEl('kioskIdle');
    var result = getEl('kioskResult');
    if (idle) idle.style.display = 'none';
    if (result) result.style.display = 'block';

    var initials = getEl('kioskInitials');
    var name = getEl('kioskName');
    var number = getEl('kioskStudentNumber');
    var program = getEl('kioskProgram');
    var status = getEl('kioskStatus');
    var note = getEl('kioskLateNote');

    if (initials) initials.textContent = data.initials || '??';
    if (name) name.textContent = data.student_name;
    if (number) number.textContent = maskStudentNumber(data.student_number);
    if (program) program.textContent = (data.program_code || '') + ' · Year ' + data.year_level;

    if (data.record_status === 'PRESENT') {
      if (status) {
        status.className = 'badge badge--success';
        status.innerHTML = '<i class="fas fa-circle-check"></i> PRESENT';
      }
      if (note) { note.textContent = 'Attendance recorded — on time'; note.className = 'text-success'; }
    } else {
      if (status) {
        status.className = 'badge badge--warning';
        status.innerHTML = '<i class="fas fa-clock"></i> LATE (+' + data.late_minutes + 'm)';
      }
      if (note) { note.textContent = 'Attendance recorded — ' + data.late_minutes + ' min(s) late'; note.className = 'text-warning'; }
    }
    resetKioskHideTimer();
  }

  function enterKiosk() {
    var overlay = getEl('kioskOverlay');
    if (!overlay) return;
    kiosk.active = true;
    if (kiosk.hideTimer) clearTimeout(kiosk.hideTimer);
    overlay.style.display = 'flex';
    showKioskIdle();

    var docEl = document.documentElement;
    if (docEl.requestFullscreen) {
      docEl.requestFullscreen().catch(function () { /* user gesture denied — overlay mode only */ });
    } else if (docEl.webkitRequestFullscreen) {
      docEl.webkitRequestFullscreen();
    }
  }

  function exitKiosk() {
    kiosk.active = false;
    if (kiosk.hideTimer) clearTimeout(kiosk.hideTimer);
    var overlay = getEl('kioskOverlay');
    if (overlay) overlay.style.display = 'none';
    if (document.fullscreenElement) {
      if (document.exitFullscreen) document.exitFullscreen().catch(function () {});
      else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    }
  }

  function initKioskMode() {
    var kioskBtn = getEl('kioskModeBtn');
    var exitBtn = getEl('kioskExitBtn');
    if (kioskBtn) kioskBtn.addEventListener('click', enterKiosk);
    if (exitBtn) exitBtn.addEventListener('click', exitKiosk);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && kiosk.active) exitKiosk();
    });
    document.addEventListener('fullscreenchange', function () {
      if (kiosk.active && !document.fullscreenElement) exitKiosk();
    });
  }

  var GRID_COLORS = {
    PRESENT: { bg: 'rgba(34, 197, 94, 0.12)', border: 'rgba(34, 197, 94, 0.45)' },
    LATE:    { bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.45)' },
    ABSENT:  { bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.45)' },
    EXCUSED: { bg: 'rgba(139, 92, 246, 0.12)', border: 'rgba(139, 92, 246, 0.45)' },
    PENDING: { bg: 'rgba(148, 163, 184, 0.10)', border: 'rgba(148, 163, 184, 0.30)' }
  };

  function statusBadgeHtml(status, stampedAt, lateMinutes) {
    var stamp = stampedAt
      ? '<span class="text-muted text-xs font-mono ml-1" style="font-size: 0.62rem;">' + stampedAt + '</span>'
      : '';
    if (status === 'PRESENT') {
      return '<span class="badge badge--success text-xs"><i class="fas fa-circle-check"></i> Present</span>' + stamp;
    }
    if (status === 'LATE') {
      return '<span class="badge badge--warning text-xs"><i class="fas fa-clock"></i> Late (+' + (lateMinutes || 0) + 'm)</span>' + stamp;
    }
    if (status === 'ABSENT') {
      return '<span class="badge badge--danger text-xs"><i class="fas fa-circle-xmark"></i> Absent</span>';
    }
    if (status === 'EXCUSED') {
      return '<span class="badge badge--purple text-xs"><i class="fas fa-file-medical"></i> Excused</span>';
    }
    return '<span class="badge badge--muted text-xs"><i class="fas fa-hourglass-start"></i> Pending</span>';
  }

  function updateGridCard(studentId, status, stampedAt, lateMinutes) {
    var card = document.getElementById('roster-grid-' + studentId);
    if (!card) return;
    card.setAttribute('data-status', status);
    var colors = GRID_COLORS[status] || GRID_COLORS.PENDING;
    card.style.background = colors.bg;
    card.style.borderColor = colors.border;
    var statusEl = document.getElementById('roster-grid-status-' + studentId);
    if (statusEl) statusEl.innerHTML = statusBadgeHtml(status, stampedAt, lateMinutes);
  }

  function updateRosterRow(data) {
    var row = document.getElementById('roster-row-' + data.student_id);
    var statusWrap = document.getElementById('roster-status-wrap-' + data.student_id);
    if (row && statusWrap) {
      row.setAttribute('data-status', data.record_status);
      statusWrap.innerHTML = statusBadgeHtml(data.record_status, data.stamped_at, data.late_minutes);

      row.style.background = 'rgba(34, 197, 94, 0.15)';
      setTimeout(function () { row.style.background = ''; }, 1800);
    }
    updateGridCard(data.student_id, data.record_status, data.stamped_at, data.late_minutes);
  }

  function updateCounters(counts) {
    if (!counts) return;
    var p = getEl('counterPresent');
    var l = getEl('counterLate');
    var a = getEl('counterAbsent');
    var e = getEl('counterExcused');
    var pen = getEl('counterPending');
    var modalPen = getEl('modalPendingCount');
    var rate = getEl('counterRate');
    var line = getEl('liveCounterLine');

    if (p) p.textContent = counts.present;
    if (l) l.textContent = counts.late;
    if (a) a.textContent = counts.absent;
    if (e && counts.excused != null) e.textContent = counts.excused;
    if (pen) pen.textContent = counts.pending;
    if (modalPen) modalPen.textContent = counts.pending;
    if (rate && counts.attendance_rate != null) rate.textContent = counts.attendance_rate + '%';
    if (line && counts.total != null) {
      line.textContent =
        'Present: ' + counts.present + ' | Late: ' + counts.late +
        ' | Absent: ' + counts.absent + ' | Excused: ' + (counts.excused || 0) +
        ' | Total: ' + counts.total + ' (' + counts.attendance_rate + '%)';
    }
  }

  function initRosterFilters() {
    var rosterSearch = getEl('rosterSearch');
    var statusFilter = getEl('statusFilter');

    function filterRoster() {
      var q = (rosterSearch && rosterSearch.value ? rosterSearch.value : '').toLowerCase().trim();
      var st = (statusFilter && statusFilter.value ? statusFilter.value : 'ALL').toUpperCase();

      function matches(row) {
        var name = (row.getAttribute('data-name') || '').toLowerCase();
        var ident = (row.getAttribute('data-ident') || '').toLowerCase();
        var status = (row.getAttribute('data-status') || '').toUpperCase();

        var matchesQuery = !q || name.indexOf(q) !== -1 || ident.indexOf(q) !== -1;
        var matchesStatus = st === 'ALL' || status === st;
        return matchesQuery && matchesStatus;
      }

      document.querySelectorAll('#rosterTbody tr').forEach(function (row) {
        row.style.display = matches(row) ? '' : 'none';
      });
      document.querySelectorAll('#rosterGridView .roster-grid-card').forEach(function (card) {
        card.style.display = matches(card) ? '' : 'none';
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
              statusWrap.innerHTML = statusBadgeHtml(data.new_status, data.stamped_at, data.late_minutes);
            }
            updateGridCard(sId, data.new_status, data.stamped_at, data.late_minutes);
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

  var localOps = 0;
  function beginLocalOp() { localOps += 1; }
  function endLocalOp() { localOps = Math.max(0, localOps - 1); }

  function initViewToggle() {
    var listBtn = getEl('viewListBtn');
    var gridBtn = getEl('viewGridBtn');
    var tableView = getEl('rosterTableView');
    var gridView = getEl('rosterGridView');
    if (!listBtn || !gridBtn || !tableView || !gridView) return;

    function setView(isGrid) {
      tableView.style.display = isGrid ? 'none' : '';
      gridView.style.display = isGrid ? 'grid' : 'none';
      listBtn.style.background = isGrid ? '' : 'rgba(245, 158, 11, 0.15)';
      gridBtn.style.background = isGrid ? 'rgba(245, 158, 11, 0.15)' : '';
    }

    listBtn.addEventListener('click', function () { setView(false); });
    gridBtn.addEventListener('click', function () { setView(true); });
  }

  function initLiveMatrixPolling(rosterUrl, isOpen) {
    if (!rosterUrl || !isOpen) return;

    var timer = setInterval(function () {
      if (localOps > 0) return; // a local scan/override is in flight; skip stale reconciliation
      fetch(rosterUrl, { headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data || data.is_open === false) {
            clearInterval(timer);
            return;
          }
          updateCounters(data.counts);
          (data.students || []).forEach(function (st) {
            var row = document.getElementById('roster-row-' + st.student_id);
            if (row && row.getAttribute('data-status') !== st.status) {
              row.setAttribute('data-status', st.status);
              var statusWrap = document.getElementById('roster-status-wrap-' + st.student_id);
              if (statusWrap) statusWrap.innerHTML = statusBadgeHtml(st.status, st.stamped_at, st.late_minutes);
            }
            var card = document.getElementById('roster-grid-' + st.student_id);
            if (card && card.getAttribute('data-status') !== st.status) {
              updateGridCard(st.student_id, st.status, st.stamped_at, st.late_minutes);
            }
          });
        })
        .catch(function () { /* transient network failure — retry on next tick */ });
    }, 10000);
  }

  function initUI() {
    var config = window.ScannerConfig || {};
    initGraceTimer(config.graceCutoffTime);
    initRosterFilters();
    initManualDrawer();
    initOverrideModal(config.sessionId, config.csrfToken);
    initViewToggle();
    initKioskMode();
    initLiveMatrixPolling(config.rosterUrl, config.isOpen);
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
  window.ScannerApp.beginLocalOp = beginLocalOp;
  window.ScannerApp.endLocalOp = endLocalOp;
  window.ScannerApp.enterKiosk = enterKiosk;
  window.ScannerApp.exitKiosk = exitKiosk;
})(window);
