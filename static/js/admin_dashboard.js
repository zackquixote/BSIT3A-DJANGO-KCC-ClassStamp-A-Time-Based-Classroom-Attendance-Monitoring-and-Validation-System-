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
  const activeSessionsModal = document.getElementById('activeSessionsModal');
  const closeSessionsModal = document.getElementById('closeSessionsModal');

  if (activeSessionsCard && activeSessionsModal) {
    activeSessionsCard.addEventListener('click', function () {
      activeSessionsModal.classList.add('is-open');
    });
    if (closeSessionsModal) {
      closeSessionsModal.addEventListener('click', function () {
        activeSessionsModal.classList.remove('is-open');
      });
    }
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

  // ── 7. Notification Bell Dropdown Toggle ──────────────────────────────────────
  const notifBtn = document.getElementById('notifBellBtn');
  const notifDropdown = document.getElementById('notifDropdown');
  const notifWrapper = document.getElementById('notifBellWrapper');

  if (notifBtn && notifDropdown) {
    function openNotif() {
      notifDropdown.classList.add('is-open');
      notifBtn.setAttribute('aria-expanded', 'true');
    }
    function closeNotif() {
      notifDropdown.classList.remove('is-open');
      notifBtn.setAttribute('aria-expanded', 'false');
    }
    function toggleNotif() {
      if (notifDropdown.classList.contains('is-open')) {
        closeNotif();
      } else {
        openNotif();
      }
    }

    notifBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleNotif();
    });

    document.addEventListener('click', function (e) {
      if (notifWrapper && !notifWrapper.contains(e.target)) {
        closeNotif();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeNotif();
        notifBtn.focus();
      }
    });
  }
});
