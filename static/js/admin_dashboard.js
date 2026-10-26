/**
 * KCC ClassStamp — Admin Dashboard Controller
 * Handles:
 * 1. Live Philippine Standard Time (PST) Clock
 * 2. Dual Tab Switcher (Recently Approved vs Live Stamps Feed)
 * 3. Live Attendance Stamps Feed Real-Time Auto-Refresh Polling
 * 4. Active Sessions Inspection Modal Drawer
 * 5. Auto-Refresh Pending Validation Count Polling
 * 6. Interactive Attendance Analytics (Chart.js Bar Chart, Ranges, Historical Date Inspector & Loading Feedback)
 * 7. Notification Bell Dropdown Toggle
 */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  const boot = document.getElementById('admin-dashboard-boot');
  const chartBaseUrl = boot ? boot.dataset.chartUrl : '';
  const feedUrl = boot ? boot.dataset.feedUrl : '';

  // ── 1. Live Philippine Standard Time (PST) Clock ─────────────────────────────
  const clockEl = document.getElementById('clockTimeDisplay');
  function updatePstClock() {
    if (!clockEl) return;
    const now = new Date();
    const options = {
      timeZone: 'Asia/Manila',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    };
    clockEl.textContent = now.toLocaleTimeString('en-US', options) + ' PST';
  }
  updatePstClock();
  setInterval(updatePstClock, 1000);

  // ── 2. Dual Tab Switcher (Approved vs Live Stamps) ───────────────────────────
  const tabApprovedBtn = document.getElementById('tabApprovedBtn');
  const tabFeedBtn = document.getElementById('tabFeedBtn');
  const paneApproved = document.getElementById('paneApproved');
  const paneFeed = document.getElementById('paneFeed');
  const tabApprovedLink = document.getElementById('tabApprovedLink');
  const tabFeedLink = document.getElementById('tabFeedLink');

  if (tabApprovedBtn && tabFeedBtn && paneApproved && paneFeed) {
    tabApprovedBtn.addEventListener('click', function () {
      tabApprovedBtn.classList.add('is-active');
      tabFeedBtn.classList.remove('is-active');
      paneApproved.style.display = 'flex';
      paneFeed.style.display = 'none';
      if (tabApprovedLink) tabApprovedLink.style.display = 'inline-flex';
      if (tabFeedLink) tabFeedLink.style.display = 'none';
    });

    tabFeedBtn.addEventListener('click', function () {
      tabFeedBtn.classList.add('is-active');
      tabApprovedBtn.classList.remove('is-active');
      paneApproved.style.display = 'none';
      paneFeed.style.display = 'flex';
      if (tabApprovedLink) tabApprovedLink.style.display = 'none';
      if (tabFeedLink) tabFeedLink.style.display = 'inline-flex';
      // Fetch fresh live stamps when switching tab
      fetchLiveFeed();
    });
  }

  // ── 3. Real-Time Live Attendance Feed Auto-Refresh ──────────────────────────
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderFeed(feed) {
    if (!paneFeed) return;
    if (!feed || feed.length === 0) {
      paneFeed.innerHTML =
        '<div class="dash-empty">' +
        '  <i class="fas fa-satellite-dish"></i>' +
        '  <p>No live classroom stamp activity recorded yet today.</p>' +
        '</div>';
      return;
    }

    let html = '';
    feed.forEach(function (stamp) {
      const isPresent = (stamp.status === 'PRESENT');
      const iconClass = isPresent ? 'dash-feed-icon--present' : 'dash-feed-icon--late';
      const iconFa = isPresent ? 'fa-check' : 'fa-clock';
      const badgeClass = isPresent ? 'badge--success' : 'badge--warning';
      const method = stamp.method || 'QR';
      const timeHtml = stamp.stamped_time
        ? '<span><i class="fas fa-clock"></i> ' + escapeHtml(stamp.stamped_time) + '</span> · '
        : '';

      html +=
        '<div class="dash-feed-row">' +
        '  <div class="dash-feed-icon ' + iconClass + '">' +
        '    <i class="fas ' + iconFa + '"></i>' +
        '  </div>' +
        '  <div class="dash-feed-body">' +
        '    <div class="dash-feed-name">' + escapeHtml(stamp.student) + '</div>' +
        '    <div class="dash-feed-sub">' + escapeHtml(stamp.class_code) + ' • ' + escapeHtml(stamp.student_id) + '</div>' +
        '  </div>' +
        '  <div class="dash-feed-meta">' +
        '    <span class="badge ' + badgeClass + ' badge--xs">' + escapeHtml(stamp.status) + '</span>' +
        '    <div class="text-muted text-xs" style="font-size: 0.65rem; margin-top: 2px;">' +
        '      ' + timeHtml + '<i class="fas fa-qrcode"></i> ' + escapeHtml(method) +
        '    </div>' +
        '  </div>' +
        '</div>';
    });
    paneFeed.innerHTML = html;
  }

  function fetchLiveFeed() {
    if (!feedUrl) return;
    fetch(feedUrl)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && Array.isArray(data.feed)) {
          renderFeed(data.feed);
        }
      })
      .catch(function (err) { console.debug('Live feed poll failed:', err); });
  }

  if (feedUrl) {
    // Auto-poll live stamps every 30 seconds
    setInterval(fetchLiveFeed, 30000);
  }

  // ── 4. Active Sessions Modal Trigger ────────────────────────────────────────
  const activeSessionsCard = document.getElementById('activeSessionsCard');
  const radarDrawerTriggerBtn = document.getElementById('radarDrawerTriggerBtn');
  const activeSessionsModal = document.getElementById('activeSessionsModal');
  const closeSessionsModal = document.getElementById('closeSessionsModal');

  function openSessionsModal() {
    if (activeSessionsModal) activeSessionsModal.classList.add('is-open');
  }

  if (activeSessionsCard) activeSessionsCard.addEventListener('click', openSessionsModal);
  if (radarDrawerTriggerBtn) radarDrawerTriggerBtn.addEventListener('click', openSessionsModal);
  if (closeSessionsModal) {
    closeSessionsModal.addEventListener('click', function () {
      if (activeSessionsModal) activeSessionsModal.classList.remove('is-open');
    });
  }
  if (activeSessionsModal) {
    activeSessionsModal.addEventListener('click', function (e) {
      if (e.target === activeSessionsModal) {
        activeSessionsModal.classList.remove('is-open');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && activeSessionsModal.classList.contains('is-open')) {
        activeSessionsModal.classList.remove('is-open');
      }
    });
  }

  // ── 5. Auto-Refresh Pending Count Polling ───────────────────────────────────
  if (boot && boot.dataset.pendingCountUrl) {
    let currentPendingCount = Number(boot.dataset.pendingCount || 0);
    const pendingCountUrl = boot.dataset.pendingCountUrl;

    function checkPendingCount() {
      fetch(pendingCountUrl)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.pending_count !== undefined && data.pending_count !== currentPendingCount) {
            currentPendingCount = data.pending_count;
            const kpiVal = document.getElementById('pendingKpiValue');
            if (kpiVal) kpiVal.textContent = currentPendingCount;
          }
        })
        .catch(function (err) { console.debug('Pending count poll failed:', err); });
    }
    setInterval(checkPendingCount, 45000);
  }

  // ── 6. Interactive Attendance Analytics (Multi-Day & Historical Date Inspector) ──
  const chartScript = document.getElementById('dashChartData');
  const chartCanvas = document.getElementById('weeklyAttendanceChart');
  const chartWrapper = chartCanvas ? chartCanvas.closest('.dash-chart-canvas-wrapper') : null;
  const rangeButtons = document.querySelectorAll('#chartRangeButtons .dash-chart-range-btn');
  const datePicker = document.getElementById('chartDatePicker');
  const chartSubtitle = document.getElementById('dashChartSubtitle');
  const dayInspectBanner = document.getElementById('chartDayInspect');
  const inspectDateLabel = document.getElementById('inspectDateLabel');
  const inspectPresent = document.getElementById('inspectPresent');
  const inspectLate = document.getElementById('inspectLate');
  const inspectAbsent = document.getElementById('inspectAbsent');
  const inspectExcused = document.getElementById('inspectExcused');
  const inspectTotal = document.getElementById('inspectTotal');
  const closeInspectBtn = document.getElementById('closeInspectBtn');

  let attendanceChart = null;
  let currentChartData = null;

  if (chartScript && chartCanvas && typeof Chart !== 'undefined') {
    try {
      currentChartData = JSON.parse(chartScript.textContent || '{}');
      const ctx = chartCanvas.getContext('2d');

      function buildDatasets(data) {
        return [
          {
            label: 'Present',
            data: data.present || [],
            backgroundColor: '#22c55e',
            hoverBackgroundColor: '#16a34a',
            borderRadius: 4,
            borderSkipped: false,
            barPercentage: 0.55,
            categoryPercentage: 0.65,
          },
          {
            label: 'Late',
            data: data.late || [],
            backgroundColor: '#f59e0b',
            hoverBackgroundColor: '#d97706',
            borderRadius: 4,
            borderSkipped: false,
            barPercentage: 0.55,
            categoryPercentage: 0.65,
          },
          {
            label: 'Absent',
            data: data.absent || [],
            backgroundColor: '#ef4444',
            hoverBackgroundColor: '#dc2626',
            borderRadius: 4,
            borderSkipped: false,
            barPercentage: 0.55,
            categoryPercentage: 0.65,
          },
          {
            label: 'Excused',
            data: data.excused || [],
            backgroundColor: '#3b82f6',
            hoverBackgroundColor: '#2563eb',
            borderRadius: 4,
            borderSkipped: false,
            barPercentage: 0.55,
            categoryPercentage: 0.65,
          },
        ];
      }

      attendanceChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: currentChartData.labels || [],
          datasets: buildDatasets(currentChartData),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          animation: {
            duration: 700,
            easing: 'easeOutCubic',
          },
          onClick: function (evt, elements) {
            if (elements && elements.length > 0) {
              const idx = elements[0].index;
              showDayInspection(idx);
            }
          },
          plugins: {
            legend: {
              display: false,
            },
            tooltip: {
              backgroundColor: '#070d1e',
              titleColor: '#f8fafc',
              bodyColor: '#94a3b8',
              borderColor: 'rgba(245,158,11,0.3)',
              borderWidth: 1,
              padding: 10,
              boxPadding: 4,
              usePointStyle: true,
              footerColor: '#fbbf24',
              footerFont: {
                weight: 'bold',
                size: 11,
                family: "'Inter', system-ui, -apple-system, sans-serif",
              },
              footerMarginTop: 6,
              callbacks: {
                footer: function (items) {
                  let total = 0;
                  items.forEach(function (i) {
                    total += (Number(i.raw) || 0);
                  });
                  return 'Total Scan: ' + total;
                },
              },
            },
          },
          scales: {
            x: {
              stacked: true,
              grid: {
                display: false,
                drawBorder: false,
              },
              ticks: {
                color: '#94a3b8',
                font: {
                  size: 10,
                  weight: '500',
                  family: "'Inter', system-ui, -apple-system, sans-serif",
                },
              },
            },
            y: {
              stacked: true,
              beginAtZero: true,
              min: 0,
              suggestedMax: 2,
              grid: {
                color: 'rgba(255, 255, 255, 0.05)',
                drawBorder: false,
              },
              ticks: {
                color: '#64748b',
                maxTicksLimit: 3,
                font: {
                  size: 9,
                  family: "'Inter', system-ui, -apple-system, sans-serif",
                },
                precision: 0,
                stepSize: 1,
              },
            },
          },
        },
      });

      function showDayInspection(index) {
        if (!currentChartData || !dayInspectBanner) return;
        const dateLabel = (currentChartData.display_dates && currentChartData.display_dates[index])
          ? currentChartData.display_dates[index]
          : (currentChartData.labels ? currentChartData.labels[index] : 'Selected Date');

        const p = currentChartData.present ? (currentChartData.present[index] || 0) : 0;
        const l = currentChartData.late ? (currentChartData.late[index] || 0) : 0;
        const a = currentChartData.absent ? (currentChartData.absent[index] || 0) : 0;
        const e = currentChartData.excused ? (currentChartData.excused[index] || 0) : 0;
        const total = p + l + a + e;

        inspectDateLabel.textContent = dateLabel;
        inspectPresent.textContent = p;
        inspectLate.textContent = l;
        inspectAbsent.textContent = a;
        inspectExcused.textContent = e;
        inspectTotal.textContent = total + ' Total Scans';
        dayInspectBanner.style.display = 'flex';
      }

      if (closeInspectBtn && dayInspectBanner) {
        closeInspectBtn.addEventListener('click', function () {
          dayInspectBanner.style.display = 'none';
        });
      }

      function updateChartAjax(url) {
        if (chartWrapper) chartWrapper.classList.add('is-loading');
        fetch(url)
          .then(function (r) { return r.json(); })
          .then(function (newData) {
            currentChartData = newData;
            attendanceChart.data.labels = newData.labels || [];
            attendanceChart.data.datasets = buildDatasets(newData);
            attendanceChart.update();

            if (chartSubtitle && newData.range_label) {
              chartSubtitle.textContent = 'Daily breakdown of student classroom check-ins (' + newData.range_label + ')';
            }
          })
          .catch(function (err) { console.debug('Chart update failed:', err); })
          .finally(function () {
            if (chartWrapper) chartWrapper.classList.remove('is-loading');
          });
      }

      // Handle Range Presets (7D, 14D, 30D)
      rangeButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          rangeButtons.forEach(function (b) { b.classList.remove('is-active'); });
          this.classList.add('is-active');
          if (datePicker) datePicker.value = '';
          if (dayInspectBanner) dayInspectBanner.style.display = 'none';

          const days = this.dataset.days || 7;
          if (chartBaseUrl) {
            updateChartAjax(chartBaseUrl + '?days=' + days);
          }
        });
      });

      // Handle Historical Date Picker (e.g. Oct 07, 2026)
      if (datePicker) {
        datePicker.addEventListener('change', function () {
          const pickedDate = this.value;
          if (!pickedDate || !chartBaseUrl) return;

          rangeButtons.forEach(function (b) { b.classList.remove('is-active'); });
          if (chartWrapper) chartWrapper.classList.add('is-loading');
          fetch(chartBaseUrl + '?days=7&date=' + encodeURIComponent(pickedDate))
            .then(function (r) { return r.json(); })
            .then(function (newData) {
              currentChartData = newData;
              attendanceChart.data.labels = newData.labels || [];
              attendanceChart.data.datasets = buildDatasets(newData);
              attendanceChart.update();

              if (chartSubtitle && newData.range_label) {
                chartSubtitle.textContent = 'Historical View (' + newData.range_label + ')';
              }
              const lastIdx = (newData.labels || []).length - 1;
              if (lastIdx >= 0) {
                showDayInspection(lastIdx);
              }
            })
            .catch(function (err) { console.debug('Historical chart fetch failed:', err); })
            .finally(function () {
              if (chartWrapper) chartWrapper.classList.remove('is-loading');
            });
        });
      }

    } catch (e) {
      console.warn('Attendance chart init error:', e);
    }
  }

  // ── 7. Notification Bell — Full Enhancement Suite ────────────────────────────
  const notifBtn     = document.getElementById('notifBellBtn');
  const notifDropdown = document.getElementById('notifDropdown');
  const notifWrapper  = document.getElementById('notifBellWrapper');
  const notifUnreadDot   = document.getElementById('notifUnreadDot');
  const notifMarkReadBtn = document.getElementById('notifMarkReadBtn');
  const notifHeaderBadge = document.getElementById('notifHeaderBadge');
  const notifArriveToast = document.getElementById('notifArriveToast');
  const notifArriveClose = document.getElementById('notifArriveClose');
  const notifArriveTitle = document.getElementById('notifArriveTitle');
  const notifArriveSub   = document.getElementById('notifArriveSub');
  const notifArriveProgress = document.getElementById('notifArriveProgress');

  // ── 7a. Unread dot (sessionStorage-backed) ─────────────────────────────────
  const UNREAD_KEY = 'notif_unread';
  const unreadItems = document.querySelectorAll('.notif-item.is-unread');
  const hasServerUnread = unreadItems.length > 0;

  function getSeenIds() {
    try { return JSON.parse(sessionStorage.getItem(UNREAD_KEY) || '[]'); } catch (e) { return []; }
  }
  function saveSeenIds(ids) {
    try { sessionStorage.setItem(UNREAD_KEY, JSON.stringify(ids)); } catch (e) {}
  }

  // Compute which items are actually unseen this session
  const seenIds = getSeenIds();
  let realUnreadCount = 0;
  unreadItems.forEach(function (el) {
    const id = el.getAttribute('data-notif-id') || '';
    if (seenIds.indexOf(id) === -1) {
      realUnreadCount++;
    } else {
      el.classList.remove('is-unread');
    }
  });

  function refreshUnreadUi() {
    if (notifUnreadDot)   notifUnreadDot.style.display = realUnreadCount > 0 ? 'block' : 'none';
    if (notifMarkReadBtn) {
      if (realUnreadCount > 0) { notifMarkReadBtn.classList.add('is-visible'); }
      else                      { notifMarkReadBtn.classList.remove('is-visible'); }
    }
  }
  refreshUnreadUi();

  // ── 7b. Mark-all-read ──────────────────────────────────────────────────────
  if (notifMarkReadBtn) {
    notifMarkReadBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      const allIds = [];
      document.querySelectorAll('.notif-item[data-notif-id]').forEach(function (el) {
        el.classList.remove('is-unread');
        allIds.push(el.getAttribute('data-notif-id'));
      });
      saveSeenIds(allIds);
      realUnreadCount = 0;
      refreshUnreadUi();
      if (notifHeaderBadge) notifHeaderBadge.style.display = 'none';
    });
  }

  // ── 7c. Dropdown open/close ────────────────────────────────────────────────
  if (notifBtn && notifDropdown) {
    function openNotif() {
      notifDropdown.classList.add('is-open');
      notifBtn.setAttribute('aria-expanded', 'true');
      // Mark all items as seen when panel opens
      const nowSeen = getSeenIds();
      document.querySelectorAll('.notif-item[data-notif-id]').forEach(function (el) {
        const id = el.getAttribute('data-notif-id');
        if (nowSeen.indexOf(id) === -1) nowSeen.push(id);
        el.classList.remove('is-unread');
      });
      saveSeenIds(nowSeen);
      realUnreadCount = 0;
      refreshUnreadUi();
      if (notifHeaderBadge) notifHeaderBadge.style.display = 'none';
    }
    function closeNotif() {
      notifDropdown.classList.remove('is-open');
      notifBtn.setAttribute('aria-expanded', 'false');
    }
    function toggleNotif() {
      if (notifDropdown.classList.contains('is-open')) { closeNotif(); }
      else { openNotif(); }
    }

    notifBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleNotif();
    });
    document.addEventListener('click', function (e) {
      if (notifWrapper && !notifWrapper.contains(e.target) &&
          (!notifArriveToast || !notifArriveToast.contains(e.target))) {
        closeNotif();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { closeNotif(); notifBtn.focus(); }
    });
  }

  // ── 7d. Bell shake helper ──────────────────────────────────────────────────
  function shakeBell() {
    if (!notifBtn) return;
    notifBtn.classList.remove('btn-bell--shake');
    void notifBtn.offsetWidth; // reflow to restart animation
    notifBtn.classList.add('btn-bell--shake');
    notifBtn.addEventListener('animationend', function handler() {
      notifBtn.classList.remove('btn-bell--shake');
      notifBtn.removeEventListener('animationend', handler);
    });
  }

  // ── 7e. SSE Arrive Toast ───────────────────────────────────────────────────
  var _toastTimer = null;
  function showArriveToast(title, sub) {
    if (!notifArriveToast) return;
    if (notifArriveTitle) notifArriveTitle.textContent = title || 'New Notification';
    if (notifArriveSub)   notifArriveSub.textContent   = sub   || '';

    // Restart progress bar animation
    if (notifArriveProgress) {
      notifArriveProgress.style.animation = 'none';
      void notifArriveProgress.offsetWidth;
      notifArriveProgress.style.animation = '';
    }

    notifArriveToast.classList.add('is-visible');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(hideArriveToast, 5000);
  }
  function hideArriveToast() {
    if (notifArriveToast) notifArriveToast.classList.remove('is-visible');
    clearTimeout(_toastTimer);
  }
  if (notifArriveClose) {
    notifArriveClose.addEventListener('click', hideArriveToast);
  }

  // Expose for SSE handler below
  window._notifEnhancements = {
    shakeBell: shakeBell,
    showArriveToast: showArriveToast,
    addUnread: function (count) {
      realUnreadCount += count;
      refreshUnreadUi();
    }
  };


  // ── 8. Analytics View Switcher (Pulse Chart vs 35D Heatmap) ────────────────
  const btnViewBar = document.getElementById('btnViewBar');
  const btnViewHeatmap = document.getElementById('btnViewHeatmap');
  const dashChartCanvasWrap = document.getElementById('dashChartCanvasWrap');
  const dashHeatmapWrapper = document.getElementById('dashHeatmapWrapper');
  const chartRangeButtons = document.getElementById('chartRangeButtons');
  const chartDatePickerWrap = document.getElementById('chartDatePickerWrap');
  const dashChartLegend = document.getElementById('dashChartLegend');
  const dashChartTitle = document.getElementById('dashChartTitle');
  const dashChartSubtitle = document.getElementById('dashChartSubtitle');
  const dashAnalyticsIcon = document.getElementById('dashAnalyticsIcon');

  if (btnViewBar && btnViewHeatmap && dashChartCanvasWrap && dashHeatmapWrapper) {
    btnViewBar.addEventListener('click', function () {
      btnViewBar.classList.add('is-active');
      btnViewHeatmap.classList.remove('is-active');
      dashChartCanvasWrap.style.display = 'block';
      dashHeatmapWrapper.style.display = 'none';
      if (chartRangeButtons) chartRangeButtons.style.display = 'inline-flex';
      if (chartDatePickerWrap) chartDatePickerWrap.style.display = 'inline-flex';
      if (dashChartLegend) dashChartLegend.style.display = 'flex';
      if (dashChartTitle) dashChartTitle.textContent = 'Attendance Analytics Pulse';
      if (dashChartSubtitle) dashChartSubtitle.textContent = 'Daily breakdown of student classroom check-ins (Past 7 Days)';
      if (dashAnalyticsIcon) dashAnalyticsIcon.className = 'fas fa-chart-column';
    });

    btnViewHeatmap.addEventListener('click', function () {
      btnViewHeatmap.classList.add('is-active');
      btnViewBar.classList.remove('is-active');
      dashChartCanvasWrap.style.display = 'none';
      dashHeatmapWrapper.style.display = 'flex';
      if (chartRangeButtons) chartRangeButtons.style.display = 'none';
      if (chartDatePickerWrap) chartDatePickerWrap.style.display = 'none';
      if (dashChartLegend) dashChartLegend.style.display = 'none';
      if (dashChartTitle) dashChartTitle.textContent = 'Attendance Activity Heatmap';
      if (dashChartSubtitle) dashChartSubtitle.textContent = '35-day institutional attendance density matrix';
      if (dashAnalyticsIcon) dashAnalyticsIcon.className = 'fas fa-table-cells';
    });
  }

  // Heatmap Cell Click -> Inspection Ribbon
  const heatmapCells = document.querySelectorAll('.js-heatmap-cell');
  heatmapCells.forEach(function (cell) {
    cell.addEventListener('click', function () {
      const displayDate = cell.getAttribute('data-display-date') || 'Selected Date';
      const p = parseInt(cell.getAttribute('data-present') || '0', 10);
      const l = parseInt(cell.getAttribute('data-late') || '0', 10);
      const a = parseInt(cell.getAttribute('data-absent') || '0', 10);
      const e = parseInt(cell.getAttribute('data-excused') || '0', 10);
      const total = p + l + a + e;

      if (inspectDateLabel) inspectDateLabel.textContent = displayDate;
      if (inspectPresent) inspectPresent.textContent = p;
      if (inspectLate) inspectLate.textContent = l;
      if (inspectAbsent) inspectAbsent.textContent = a;
      if (inspectExcused) inspectExcused.textContent = e;
      if (inspectTotal) inspectTotal.textContent = total + ' Total Scans';
      if (dayInspectBanner) dayInspectBanner.style.display = 'flex';

      // Highlight active cell outline
      heatmapCells.forEach(function (c) { c.style.outline = ''; });
      cell.style.outline = '2px solid var(--accent-gold)';
    });
  });

  // ── 9. Real-Time SSE Push Stream with Graceful Fallback ────────────────────
  const liveStreamUrl = boot ? boot.dataset.liveStreamUrl : '';
  if (liveStreamUrl && typeof window.EventSource !== 'undefined') {
    try {
      const evtSource = new EventSource(liveStreamUrl);

      evtSource.addEventListener('stamp', function (e) {
        try {
          const payload = JSON.parse(e.data);
          if (payload && Array.isArray(payload.feed)) {
            renderFeed(payload.feed);
            const liveBadge = document.querySelector('.dash-chart-live-badge');
            if (liveBadge) {
              liveBadge.style.boxShadow = '0 0 12px rgba(34, 197, 94, 0.8)';
              setTimeout(function () { liveBadge.style.boxShadow = ''; }, 1500);
            }
          }
        } catch (err) {
          console.debug('SSE stamp parse error:', err);
        }
      });

      evtSource.addEventListener('pending', function (e) {
        try {
          const payload = JSON.parse(e.data);
          if (payload && typeof payload.pending_count === 'number') {
            const kpiVal = document.getElementById('pendingKpiValue');
            const oldCount = kpiVal ? parseInt(kpiVal.textContent || '0', 10) : 0;
            const newCount = payload.pending_count;

            if (kpiVal) kpiVal.textContent = newCount;

            // Badge on bell
            const bellBadge = document.getElementById('bellBadgeCount');
            if (bellBadge && newCount > 0) bellBadge.textContent = newCount;

            // If count increased — new student arrived
            if (newCount > oldCount) {
              const delta = newCount - oldCount;
              if (window._notifEnhancements) {
                window._notifEnhancements.shakeBell();
                window._notifEnhancements.addUnread(delta);
                window._notifEnhancements.showArriveToast(
                  delta === 1 ? 'New Pending Registration' : delta + ' New Pending Registrations',
                  delta === 1
                    ? 'A student is awaiting account review.'
                    : delta + ' students are awaiting account review.'
                );
              }
            }
          }
        } catch (err) {
          console.debug('SSE pending parse error:', err);
        }
      });

      evtSource.onerror = function () {
        // Automatically falls back to standard interval polling
        console.debug('SSE disconnected or unbuffered; polling fallback active');
      };
    } catch (e) {
      console.debug('SSE initialization skipped:', e);
    }
  }
});

