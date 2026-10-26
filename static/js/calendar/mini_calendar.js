/**
 * ==============================================================================
 * KCC ClassStamp — Dashboard Mini Calendar Widget
 * Subsystem: Admin Command Center (Telemetry & Institutional Schedule)
 * Pure Vanilla JavaScript · Interactive Monthly View · PH Holiday Indicators
 * ==============================================================================
 */

document.addEventListener('DOMContentLoaded', function () {
  const container = document.getElementById('dashMiniCalendar');
  if (!container) return;

  // Retrieve embedded events JSON
  let events = [];
  const eventsScript = document.getElementById('mini-calendar-events-data');
  if (eventsScript) {
    try {
      events = JSON.parse(eventsScript.textContent) || [];
    } catch (e) {
      console.warn('[MiniCalendar] Could not parse embedded events data:', e);
    }
  }

  const monthTitle = document.getElementById('miniCalMonthTitle');
  const daysGrid = document.getElementById('miniCalDaysGrid');
  const prevBtn = document.getElementById('miniCalPrevBtn');
  const nextBtn = document.getElementById('miniCalNextBtn');
  const dayInspectEl = document.getElementById('miniCalDayInspect');
  const inspectDateText = document.getElementById('miniCalInspectDate');
  const inspectEventsList = document.getElementById('miniCalInspectEvents');

  const today = new Date();
  let currentYear = today.getFullYear();
  let currentMonth = today.getMonth(); // 0-indexed (0 = Jan, 9 = Oct)
  let selectedDateStr = toDateStr(today);

  function toDateStr(date) {
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  // Helper: Find events that span across or match a specific date string
  function getEventsForDate(dateStr) {
    return events.filter((e) => {
      const s = e.start_date.substring(0, 10);
      const end = (e.end_date || e.start_date).substring(0, 10);
      return dateStr >= s && dateStr <= end;
    });
  }

  // Render Days Grid
  function renderCalendar() {
    if (monthTitle) {
      monthTitle.textContent = `${monthNames[currentMonth]} ${currentYear}`;
    }

    if (!daysGrid) return;
    daysGrid.innerHTML = '';

    const firstDayIndex = new Date(currentYear, currentMonth, 1).getDay(); // 0 is Sunday
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

    const todayStr = toDateStr(today);

    // 1. Previous Month Spillover Days
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const dayNum = daysInPrevMonth - i;
      const prevDate = new Date(currentYear, currentMonth - 1, dayNum);
      const dateStr = toDateStr(prevDate);
      daysGrid.appendChild(createDayCell(dayNum, dateStr, true));
    }

    // 2. Current Month Days
    for (let day = 1; day <= daysInMonth; day++) {
      const currDate = new Date(currentYear, currentMonth, day);
      const dateStr = toDateStr(currDate);
      daysGrid.appendChild(createDayCell(day, dateStr, false, dateStr === todayStr));
    }

    // 3. Next Month Spillover Days (complete 35 or 42 grid cells)
    const totalCells = daysGrid.children.length;
    const remainingCells = (totalCells <= 35 ? 35 : 42) - totalCells;
    for (let nextDay = 1; nextDay <= remainingCells; nextDay++) {
      const nextDate = new Date(currentYear, currentMonth + 1, nextDay);
      const dateStr = toDateStr(nextDate);
      daysGrid.appendChild(createDayCell(nextDay, dateStr, true));
    }

    // Update Inspect Panel for selected or today
    inspectDate(selectedDateStr);
  }

  function createDayCell(dayNum, dateStr, isOtherMonth, isToday = false) {
    const dayEl = document.createElement('div');
    dayEl.className = 'mini-cal-day';
    if (isOtherMonth) dayEl.classList.add('is-other');
    if (isToday) dayEl.classList.add('is-today');
    if (dateStr === selectedDateStr) dayEl.classList.add('is-selected');

    const numSpan = document.createElement('span');
    numSpan.className = 'mini-cal-day-num';
    numSpan.textContent = dayNum;
    dayEl.appendChild(numSpan);

    // Check for events on this date
    const dayEvents = getEventsForDate(dateStr);
    if (dayEvents.length > 0) {
      dayEl.classList.add('has-events');
      const dotsContainer = document.createElement('div');
      dotsContainer.className = 'mini-cal-dots';

      // Up to 3 colored dots
      dayEvents.slice(0, 3).forEach((evt) => {
        const dot = document.createElement('span');
        dot.className = 'mini-cal-dot';
        dot.style.backgroundColor = evt.category_color || '#f59e0b';
        dotsContainer.appendChild(dot);
      });
      dayEl.appendChild(dotsContainer);

      // Tooltip with event titles
      const titles = dayEvents.map((e) => e.title).join(' • ');
      dayEl.title = `${dateStr}: ${titles}`;
    }

    dayEl.addEventListener('click', function () {
      document.querySelectorAll('.mini-cal-day.is-selected').forEach((el) => el.classList.remove('is-selected'));
      dayEl.classList.add('is-selected');
      selectedDateStr = dateStr;
      inspectDate(dateStr);
    });

    return dayEl;
  }

  function inspectDate(dateStr) {
    if (!dayInspectEl) return;
    const parts = dateStr.split('-');
    const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));

    const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' };
    if (inspectDateText) {
      inspectDateText.textContent = d.toLocaleDateString('en-US', options);
    }

    const dayEvents = getEventsForDate(dateStr);
    if (!inspectEventsList) return;
    inspectEventsList.innerHTML = '';

    if (dayEvents.length === 0) {
      inspectEventsList.innerHTML = '<span class="text-xs text-muted" style="font-style: italic;">No milestones scheduled on this day.</span>';
    } else {
      dayEvents.forEach((evt) => {
        const item = document.createElement('div');
        item.className = 'mini-cal-inspect-item';
        item.style.borderLeft = `3px solid ${evt.category_color || '#f59e0b'}`;

        const icon = document.createElement('i');
        icon.className = `fas ${evt.category_icon || 'fa-calendar'} mr-1.5`;
        icon.style.color = evt.category_color || '#f59e0b';
        icon.style.fontSize = '0.75rem';

        const titleSpan = document.createElement('span');
        titleSpan.className = 'mini-cal-inspect-title';
        titleSpan.textContent = evt.title;

        item.appendChild(icon);
        item.appendChild(titleSpan);
        inspectEventsList.appendChild(item);
      });
    }
  }

  // Navigation handlers
  if (prevBtn) {
    prevBtn.addEventListener('click', function (e) {
      e.preventDefault();
      currentMonth--;
      if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
      }
      if (currentYear === today.getFullYear() && currentMonth === today.getMonth()) {
        selectedDateStr = toDateStr(today);
      } else {
        selectedDateStr = toDateStr(new Date(currentYear, currentMonth, 1));
      }
      renderCalendar();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function (e) {
      e.preventDefault();
      currentMonth++;
      if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
      }
      if (currentYear === today.getFullYear() && currentMonth === today.getMonth()) {
        selectedDateStr = toDateStr(today);
      } else {
        selectedDateStr = toDateStr(new Date(currentYear, currentMonth, 1));
      }
      renderCalendar();
    });
  }

  // Tab switcher: Agenda vs Month Grid
  const tabAgenda = document.getElementById('calTabAgendaBtn');
  const tabMonth = document.getElementById('calTabMonthBtn');
  const agendaView = document.getElementById('miniCalAgendaView');
  const monthView = document.getElementById('miniCalMonthView');

  if (tabAgenda && tabMonth && agendaView && monthView) {
    tabAgenda.addEventListener('click', function (e) {
      e.preventDefault();
      tabAgenda.classList.add('is-active');
      tabAgenda.setAttribute('aria-selected', 'true');
      tabMonth.classList.remove('is-active');
      tabMonth.setAttribute('aria-selected', 'false');
      agendaView.style.display = 'block';
      monthView.style.display = 'none';
    });

    tabMonth.addEventListener('click', function (e) {
      e.preventDefault();
      tabMonth.classList.add('is-active');
      tabMonth.setAttribute('aria-selected', 'true');
      tabAgenda.classList.remove('is-active');
      tabAgenda.setAttribute('aria-selected', 'false');
      agendaView.style.display = 'none';
      monthView.style.display = 'flex';
      renderCalendar();
    });
  }

  // Initial render
  renderCalendar();
});
