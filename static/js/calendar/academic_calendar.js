/**
 * ==============================================================================
 * KCC ClassStamp — Academic Calendar & Institutional Schedule Controller
 * Subsystem: Academic Administration (RBAC: Admin Only)
 * Powered by FullCalendar 6 Standard Bundle
 * ==============================================================================
 */

document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('academicCalendar');
  if (!calendarEl) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

  // DOM Elements
  const eventModal = document.getElementById('eventModal');
  const eventDetailModal = document.getElementById('eventDetailModal');
  const eventForm = document.getElementById('eventForm');
  const addEventBtn = document.getElementById('addEventBtn');
  const syncHolidaysBtn = document.getElementById('syncHolidaysBtn');
  const printCalendarBtn = document.getElementById('printCalendarBtn');
  const searchInput = document.getElementById('eventSearchInput');
  const categoryFilter = document.getElementById('categoryFilter');
  const academicYearFilter = document.getElementById('academicYearFilter');
  const semesterFilter = document.getElementById('semesterFilter');
  const statusFilter = document.getElementById('statusFilter');
  const resetFiltersBtn = document.getElementById('resetFiltersBtn');
  const jumpToDateInput = document.getElementById('jumpToDateInput');
  const isAllDayCheckbox = document.getElementById('isAllDayCheckbox');
  const startDatetimeInput = document.getElementById('startDatetimeInput');
  const endDatetimeInput = document.getElementById('endDatetimeInput');
  const overlapWarningBox = document.getElementById('overlapWarningBox');
  const overlapWarningText = document.getElementById('overlapWarningText');
  const editEventBtn = document.getElementById('editEventBtn');
  const cancelEventBtn = document.getElementById('cancelEventBtn');
  const deleteEventBtn = document.getElementById('deleteEventBtn');

  let calendar = null;
  let currentDetailEvent = null;

  // ── Robust Modal Management ───────────────────────────────────────────────────
  function openCalendarModal(modal) {
    if (!modal) return;
    modal.style.display = 'flex';
    modal.classList.add('is-active', 'is-open');
    document.body.style.overflow = 'hidden';
    if (typeof window.openModal === 'function') {
      window.openModal(modal.id || modal);
    }
  }

  function closeCalendarModal(modal) {
    if (!modal) return;
    modal.style.display = 'none';
    modal.classList.remove('is-active', 'is-open');
    document.body.style.overflow = '';
    if (typeof window.closeModal === 'function') {
      window.closeModal(modal.id || modal);
    }
  }

  // Bind close buttons for both modals
  document.querySelectorAll('[data-modal-close], [data-modal-dismiss], .modal-close').forEach((btn) => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const modal = this.closest('.modal');
      if (modal) {
        closeCalendarModal(modal);
      } else {
        const targetId = this.getAttribute('data-modal-close') || this.getAttribute('data-modal-dismiss');
        if (targetId) closeCalendarModal(document.getElementById(targetId));
      }
    });
  });

  // Backdrop click closing
  [eventModal, eventDetailModal].forEach((m) => {
    if (m) {
      m.addEventListener('click', function (e) {
        if (e.target === m) closeCalendarModal(m);
      });
    }
  });

  // Escape key closes modals
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (eventModal && (eventModal.classList.contains('is-open') || eventModal.style.display === 'flex')) {
        closeCalendarModal(eventModal);
      }
      if (eventDetailModal && (eventDetailModal.classList.contains('is-open') || eventDetailModal.style.display === 'flex')) {
        closeCalendarModal(eventDetailModal);
      }
    }
  });

  // ── Unified Confirmation Dialog ───────────────────────────────────────────────
  function confirmAction(options, onConfirmed) {
    if (window.App && typeof window.App.confirm === 'function') {
      window.App.confirm(options).then(function (confirmed) {
        if (confirmed) onConfirmed();
      });
    } else if (typeof window.appConfirm === 'function') {
      window.appConfirm(options).then(function (confirmed) {
        if (confirmed) onConfirmed();
      });
    } else if (window.confirm(options.message || 'Are you sure you want to proceed?')) {
      onConfirmed();
    }
  }

  // ── Date Formatting Helpers ──────────────────────────────────────────────────
  function ensureDate(val) {
    if (!val) return new Date();
    if (val instanceof Date) return val;
    return new Date(val);
  }

  function toLocalISOString(date) {
    const d = ensureDate(date);
    if (isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    const y = d.getFullYear();
    const m = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const h = pad(d.getHours());
    const min = pad(d.getMinutes());
    return `${y}-${m}-${day}T${h}:${min}`;
  }

  function toDateOnlyString(date) {
    const d = ensureDate(date);
    if (isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function calculateDuration(start, end, allDay) {
    if (!start) return '—';
    const s = ensureDate(start);
    const e = end ? ensureDate(end) : s;
    if (isNaN(s.getTime())) return '—';

    if (allDay) {
      const diffMs = e.getTime() - s.getTime();
      const diffDays = Math.max(1, Math.round(diffMs / (1000 * 60 * 60 * 24)));
      return diffDays === 1 ? '1 Day (All-day)' : `${diffDays} Days (All-day)`;
    }

    const diffMs = Math.max(0, e.getTime() - s.getTime());
    const totalMinutes = Math.round(diffMs / (1000 * 60));
    if (totalMinutes === 0) return 'Instant milestone';

    const days = Math.floor(totalMinutes / (60 * 24));
    const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
    const mins = totalMinutes % 60;

    const parts = [];
    if (days > 0) parts.push(`${days} day${days > 1 ? 's' : ''}`);
    if (hours > 0) parts.push(`${hours} hr${hours > 1 ? 's' : ''}`);
    if (mins > 0) parts.push(`${mins} min${mins > 1 ? 's' : ''}`);

    return parts.join(' ') || '< 1 min';
  }

  // Toggle All-Day Date Inputs
  function updateAllDayFields(isAllDay) {
    if (!startDatetimeInput || !endDatetimeInput) return;
    if (isAllDay) {
      startDatetimeInput.type = 'date';
      endDatetimeInput.type = 'date';
      if (startDatetimeInput.value.includes('T')) {
        startDatetimeInput.value = startDatetimeInput.value.split('T')[0];
      }
      if (endDatetimeInput.value.includes('T')) {
        endDatetimeInput.value = endDatetimeInput.value.split('T')[0];
      }
    } else {
      startDatetimeInput.type = 'datetime-local';
      endDatetimeInput.type = 'datetime-local';
      if (startDatetimeInput.value && !startDatetimeInput.value.includes('T')) {
        startDatetimeInput.value = `${startDatetimeInput.value}T08:00`;
      }
      if (endDatetimeInput.value && !endDatetimeInput.value.includes('T')) {
        endDatetimeInput.value = `${endDatetimeInput.value}T17:00`;
      }
    }
  }

  if (isAllDayCheckbox) {
    isAllDayCheckbox.addEventListener('change', function () {
      updateAllDayFields(this.checked);
    });
  }

  // ── Initialize FullCalendar 6 ────────────────────────────────────────────────
  calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: window.innerWidth < 768 ? 'listMonth' : 'dayGridMonth',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,timeGridDay,listMonth',
    },
    buttonText: {
      today: 'Today',
      dayGridMonth: 'Month',
      timeGridWeek: 'Week',
      timeGridDay: 'Day',
      listMonth: 'List',
    },
    navLinks: true,
    editable: true,
    selectable: true,
    selectMirror: true,
    dayMaxEvents: 3,
    nowIndicator: true,
    height: 'auto',

    // Synchronize jump-to-date input whenever user navigates view
    datesSet: function (dateInfo) {
      if (jumpToDateInput && calendar) {
        const currentDate = calendar.getDate();
        if (currentDate) {
          jumpToDateInput.value = toDateOnlyString(currentDate);
        }
      }
    },

    // Responsive view fallback
    windowResize: function (view) {
      if (window.innerWidth < 768 && calendar.view.type === 'dayGridMonth') {
        calendar.changeView('listMonth');
      }
    },

    // Dynamic JSON Feed with Filter Parameters
    events: function (fetchInfo, successCallback, failureCallback) {
      const params = new URLSearchParams({
        start: fetchInfo.startStr,
        end: fetchInfo.endStr,
        category: categoryFilter?.value || '',
        academic_year: academicYearFilter?.value || '',
        semester: semesterFilter?.value || '',
        status: statusFilter?.value || '',
        q: searchInput?.value || '',
      });

      fetch(`/admin/calendar/events/?${params.toString()}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then((res) => {
          if (!res.ok) throw new Error('Failed to load calendar events');
          return res.json();
        })
        .then((data) => successCallback(data))
        .catch((err) => {
          console.error('[Calendar Feed Error]', err);
          if (window.showToast) window.showToast('Could not load calendar events.', 'error');
          failureCallback(err);
        });
    },

    // Date Click / Date Range Select -> Open Add Modal
    select: function (selectionInfo) {
      openAddEventModal(selectionInfo.start, selectionInfo.end, selectionInfo.allDay);
      calendar.unselect();
    },

    // Event Click -> Open Detail View Modal
    eventClick: function (info) {
      info.jsEvent.preventDefault();
      openEventDetailModal(info.event);
    },

    // Drag-and-Drop Reschedule
    eventDrop: function (changeInfo) {
      handleReschedule(changeInfo.event, changeInfo.revert);
    },

    // Event Resize
    eventResize: function (changeInfo) {
      handleReschedule(changeInfo.event, changeInfo.revert);
    },

    // Custom Event Content Rendering (Icons & Strike-through for Canceled)
    eventDidMount: function (arg) {
      const iconClass = arg.event.extendedProps.category_icon || 'fa-calendar';
      const isCanceled = arg.event.extendedProps.status === 'CANCELED';
      const icon = document.createElement('i');
      icon.className = `fas ${iconClass}`;
      icon.style.marginRight = '4px';
      icon.style.fontSize = '0.75rem';

      const titleEl = arg.el.querySelector('.fc-event-title');
      if (titleEl) {
        titleEl.prepend(icon);
        if (isCanceled) {
          titleEl.style.textDecoration = 'line-through';
          titleEl.title = '[CANCELED] ' + arg.event.title;
        }
      }
    },
  });

  calendar.render();

  // ── Open Add Event Modal ─────────────────────────────────────────────────────
  function openAddEventModal(startDate, endDate, isAllDay = false) {
    if (eventForm) eventForm.reset();
    document.getElementById('modalEventId').value = '';
    document.getElementById('eventModalTitle').innerHTML = '<i class="fas fa-calendar-plus text-gold"></i> Create Academic Event';
    document.getElementById('eventSubmitBtnText').textContent = 'Save Event';
    if (overlapWarningBox) overlapWarningBox.style.display = 'none';

    const now = new Date();
    const start = startDate ? ensureDate(startDate) : now;
    let end = endDate ? ensureDate(endDate) : null;

    if (!end) {
      end = new Date(start.getTime() + 60 * 60 * 1000); // 1 hour duration
    }

    if (isAllDay) {
      if (isAllDayCheckbox) isAllDayCheckbox.checked = true;
      updateAllDayFields(true);
      if (startDatetimeInput) startDatetimeInput.value = toDateOnlyString(start);
      // For all-day selections in month view, FullCalendar sets end to next day midnight
      const endAdjusted = new Date(end.getTime() - (endDate ? 1000 : 0));
      if (endDatetimeInput) endDatetimeInput.value = toDateOnlyString(endAdjusted >= start ? endAdjusted : start);
    } else {
      if (isAllDayCheckbox) isAllDayCheckbox.checked = false;
      updateAllDayFields(false);
      if (startDatetimeInput) startDatetimeInput.value = toLocalISOString(start);
      if (endDatetimeInput) endDatetimeInput.value = toLocalISOString(end);
    }

    // Auto-select filter values if active
    if (academicYearFilter && academicYearFilter.value) {
      const aySelect = document.getElementById('eventAcademicYear');
      if (aySelect) aySelect.value = academicYearFilter.value;
    }
    if (categoryFilter && categoryFilter.value) {
      const catSelect = document.getElementById('eventCategory');
      if (catSelect) catSelect.value = categoryFilter.value;
    }

    openCalendarModal(eventModal);
  }

  // Add Event Button Trigger
  if (addEventBtn) {
    addEventBtn.addEventListener('click', function (e) {
      e.preventDefault();
      openAddEventModal();
    });
  }

  // ── Sync Philippine Holidays Button ──────────────────────────────────────────
  if (syncHolidaysBtn) {
    syncHolidaysBtn.addEventListener('click', function (e) {
      e.preventDefault();
      const originalHtml = this.innerHTML;
      this.disabled = true;
      this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';

      fetch('/admin/calendar/sync-holidays/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
        .then((res) => res.json())
        .then((data) => {
          syncHolidaysBtn.disabled = false;
          syncHolidaysBtn.innerHTML = originalHtml;
          if (data.status === 'success') {
            if (window.showToast) window.showToast(data.message, 'success');
            calendar.refetchEvents();
          } else {
            if (window.showToast) window.showToast(data.error || 'Sync failed', 'error');
          }
        })
        .catch((err) => {
          syncHolidaysBtn.disabled = false;
          syncHolidaysBtn.innerHTML = originalHtml;
          console.error('[Sync Holidays Error]', err);
          if (window.showToast) window.showToast('Network error while syncing Philippine holidays.', 'error');
        });
    });
  }

  // ── Open Event Detail Modal ──────────────────────────────────────────────────
  function openEventDetailModal(event) {
    currentDetailEvent = event;
    const props = event.extendedProps || {};

    const detailTitle = document.getElementById('detailTitle');
    if (detailTitle) detailTitle.textContent = event.title;

    const detailCategoryBadge = document.getElementById('detailCategoryBadge');
    if (detailCategoryBadge) {
      detailCategoryBadge.textContent = props.category_label || props.category || 'General';
      detailCategoryBadge.style.backgroundColor = props.category_bg || 'rgba(59, 130, 246, 0.15)';
      detailCategoryBadge.style.color = props.category_color || '#3b82f6';
      detailCategoryBadge.style.borderColor = props.category_color || '#3b82f6';
    }

    const iconEl = document.getElementById('detailCategoryIcon');
    if (iconEl) {
      iconEl.className = `fas ${props.category_icon || 'fa-calendar'} event-detail-icon`;
      iconEl.style.backgroundColor = props.category_bg || 'rgba(59, 130, 246, 0.15)';
      iconEl.style.color = props.category_color || '#3b82f6';
    }

    const statusBadge = document.getElementById('detailStatusBadge');
    const cancelText = document.getElementById('cancelEventBtnText');
    const cancelIcon = document.getElementById('cancelEventBtnIcon');

    if (props.status === 'CANCELED') {
      if (statusBadge) {
        statusBadge.textContent = 'Canceled';
        statusBadge.className = 'badge badge--danger';
      }
      if (cancelText) cancelText.textContent = 'Restore Event';
      if (cancelIcon) cancelIcon.className = 'fas fa-rotate-left';
    } else {
      if (statusBadge) {
        statusBadge.textContent = 'Scheduled';
        statusBadge.className = 'badge badge--success';
      }
      if (cancelText) cancelText.textContent = 'Cancel Event';
      if (cancelIcon) cancelIcon.className = 'fas fa-ban';
    }

    const detailDates = document.getElementById('detailDates');
    if (detailDates) {
      detailDates.textContent = props.start_formatted ? `${props.start_formatted} — ${props.end_formatted}` : `${toDateOnlyString(event.start)}`;
    }

    const detailDuration = document.getElementById('detailDuration');
    if (detailDuration) {
      detailDuration.textContent = calculateDuration(event.start, event.end, event.allDay);
    }

    const detailLocation = document.getElementById('detailLocation');
    if (detailLocation) detailLocation.textContent = props.location || 'Not specified';

    const detailAcademicYear = document.getElementById('detailAcademicYear');
    if (detailAcademicYear) detailAcademicYear.textContent = props.academic_year_name || 'General';

    const detailSemester = document.getElementById('detailSemester');
    if (detailSemester) detailSemester.textContent = props.semester_display || 'Entire Year';

    const detailVisibility = document.getElementById('detailVisibility');
    if (detailVisibility) detailVisibility.textContent = props.visibility_display || 'Public';

    const detailCreatedBy = document.getElementById('detailCreatedBy');
    if (detailCreatedBy) detailCreatedBy.textContent = props.created_by || 'System';

    const detailDescription = document.getElementById('detailDescription');
    if (detailDescription) detailDescription.textContent = props.description || 'No detailed briefing provided.';

    // Potential Schedule Conflict Advisory
    const conflictBox = document.getElementById('detailConflictBox');
    const conflictText = document.getElementById('detailConflictText');
    if (conflictBox && conflictText) {
      if (props.conflicts_count && props.conflicts_count > 0 && (props.category === 'HOLIDAY' || props.category === 'ACADEMIC_TERM')) {
        conflictBox.style.display = 'block';
        conflictText.textContent = `This date span coincides with ${props.conflicts_count} active class timetable section(s). Teachers and students will see institutional advisories on their dashboards.`;
      } else {
        conflictBox.style.display = 'none';
      }
    }

    openCalendarModal(eventDetailModal);
  }

  // ── Edit Event Handler ───────────────────────────────────────────────────────
  if (editEventBtn) {
    editEventBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (!currentDetailEvent) return;

      closeCalendarModal(eventDetailModal);

      const event = currentDetailEvent;
      const props = event.extendedProps || {};

      document.getElementById('modalEventId').value = event.id;
      document.getElementById('eventModalTitle').innerHTML = '<i class="fas fa-pen-to-square text-gold"></i> Edit Academic Event';
      document.getElementById('eventSubmitBtnText').textContent = 'Update Event';
      document.getElementById('eventTitleInput').value = event.title;
      document.getElementById('eventDescriptionInput').value = props.description || '';
      document.getElementById('eventCategory').value = props.category || 'OTHER';
      document.getElementById('eventStatus').value = props.status || 'SCHEDULED';
      document.getElementById('eventVisibility').value = props.visibility || 'ALL';
      document.getElementById('eventLocationInput').value = props.location || '';
      document.getElementById('eventAcademicYear').value = props.academic_year_id || '';
      document.getElementById('eventSemester').value = props.semester || 'ALL';

      const isAllDay = event.allDay === true;
      if (isAllDayCheckbox) isAllDayCheckbox.checked = isAllDay;
      updateAllDayFields(isAllDay);

      const start = ensureDate(event.start);
      const end = event.end ? ensureDate(event.end) : start;

      if (isAllDay) {
        if (startDatetimeInput) startDatetimeInput.value = toDateOnlyString(start);
        const endDt = event.end ? new Date(end.getTime() - 1000) : start;
        if (endDatetimeInput) endDatetimeInput.value = toDateOnlyString(endDt >= start ? endDt : start);
      } else {
        if (startDatetimeInput) startDatetimeInput.value = toLocalISOString(start);
        if (endDatetimeInput) endDatetimeInput.value = event.end ? toLocalISOString(end) : toLocalISOString(start);
      }

      if (overlapWarningBox) overlapWarningBox.style.display = 'none';
      openCalendarModal(eventModal);
    });
  }

  // ── Cancel / Restore Event Handler ──────────────────────────────────────────
  if (cancelEventBtn) {
    cancelEventBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (!currentDetailEvent) return;
      const props = currentDetailEvent.extendedProps || {};
      const isCanceled = props.status === 'CANCELED';
      const actionVerb = isCanceled ? 'Restore Event' : 'Cancel Event';
      const actionPrompt = isCanceled ? 'restore this canceled event to Scheduled status' : 'cancel this event';

      confirmAction({
        title: actionVerb,
        message: `Are you sure you want to ${actionPrompt}? The record will be preserved for administrative history.`,
        confirmText: actionVerb,
        type: isCanceled ? 'primary' : 'warning',
      }, function () {
        fetch(`/admin/calendar/events/${currentDetailEvent.id}/cancel/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.status === 'success') {
              if (window.showToast) window.showToast(data.message, 'success');
              closeCalendarModal(eventDetailModal);
              calendar.refetchEvents();
            } else {
              if (window.showToast) window.showToast(data.error || 'Operation failed', 'error');
            }
          })
          .catch((err) => {
            console.error('[Cancel Event Error]', err);
            if (window.showToast) window.showToast('Network error while updating event.', 'error');
          });
      });
    });
  }

  // ── Delete Event Handler ────────────────────────────────────────────────────
  if (deleteEventBtn) {
    deleteEventBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (!currentDetailEvent) return;

      confirmAction({
        title: 'Delete Academic Event',
        message: `Are you sure you want to permanently delete "${currentDetailEvent.title}"? This action is logged to the system audit trail.`,
        confirmText: 'Delete Permanently',
        type: 'danger',
      }, function () {
        fetch(`/admin/calendar/events/${currentDetailEvent.id}/delete/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.status === 'success') {
              if (window.showToast) window.showToast(data.message, 'success');
              closeCalendarModal(eventDetailModal);
              calendar.refetchEvents();
            } else {
              if (window.showToast) window.showToast(data.error || 'Failed to delete event', 'error');
            }
          })
          .catch((err) => {
            console.error('[Delete Event Error]', err);
            if (window.showToast) window.showToast('Network error while deleting event.', 'error');
          });
      });
    });
  }

  // ── Reschedule (Drag & Drop / Resize) ────────────────────────────────────────
  function handleReschedule(event, revertFunc) {
    const startStr = event.allDay ? toDateOnlyString(event.start) : event.start.toISOString();
    let endStr = '';
    if (event.end) {
      endStr = event.allDay ? toDateOnlyString(new Date(event.end.getTime() - 1000)) : event.end.toISOString();
    } else {
      endStr = startStr;
    }

    const formData = new FormData();
    formData.append('start', startStr);
    formData.append('end', endStr);
    formData.append('all_day', event.allDay ? 'true' : 'false');

    fetch(`/admin/calendar/events/${event.id}/reschedule/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: formData,
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === 'success') {
          if (window.showToast) window.showToast(data.message, 'success');
          calendar.refetchEvents();
        } else {
          if (window.showToast) window.showToast(data.error || 'Failed to reschedule', 'error');
          if (revertFunc) revertFunc();
        }
      })
      .catch((err) => {
        console.error('[Reschedule Error]', err);
        if (window.showToast) window.showToast('Network error while rescheduling.', 'error');
        if (revertFunc) revertFunc();
      });
  }

  // ── Form Submit: Save Event (Create or Edit) ────────────────────────────────
  if (eventForm) {
    eventForm.addEventListener('submit', function (e) {
      e.preventDefault();

      const title = document.getElementById('eventTitleInput')?.value?.trim();
      const startVal = startDatetimeInput?.value?.trim();
      const endVal = endDatetimeInput?.value?.trim();

      if (!title) {
        if (window.showToast) window.showToast('Please provide an event title.', 'warning');
        return;
      }
      if (!startVal) {
        if (window.showToast) window.showToast('Please select a start date and time.', 'warning');
        return;
      }

      if (endVal && endVal < startVal) {
        if (window.showToast) window.showToast('End date cannot precede the start date.', 'error');
        return;
      }

      const submitBtn = document.getElementById('eventSubmitBtn');
      const originalText = submitBtn ? submitBtn.innerHTML : 'Save';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
      }

      const formData = new FormData(eventForm);

      fetch('/admin/calendar/events/save/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      })
        .then((res) => res.json())
        .then((data) => {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
          }

          if (data.status === 'success') {
            if (window.showToast) {
              window.showToast(data.message, 'success');
              if (data.warning) {
                setTimeout(() => window.showToast(data.warning, 'info'), 700);
              }
            }
            closeCalendarModal(eventModal);
            calendar.refetchEvents();
          } else {
            if (window.showToast) window.showToast(data.error || 'Error saving event.', 'error');
          }
        })
        .catch((err) => {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
          }
          console.error('[Save Event Error]', err);
          if (window.showToast) window.showToast('Network error while saving event.', 'error');
        });
    });
  }

  // ── Filter Triggers ─────────────────────────────────────────────────────────
  const refetch = () => calendar.refetchEvents();

  if (categoryFilter) categoryFilter.addEventListener('change', refetch);
  if (academicYearFilter) academicYearFilter.addEventListener('change', refetch);
  if (semesterFilter) semesterFilter.addEventListener('change', refetch);
  if (statusFilter) statusFilter.addEventListener('change', refetch);

  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(refetch, 300);
    });
  }

  // Jump to Date Picker Handler
  if (jumpToDateInput) {
    jumpToDateInput.addEventListener('change', function () {
      if (this.value) {
        calendar.gotoDate(this.value);
      }
    });
  }

  // Print Calendar Button Handler
  if (printCalendarBtn) {
    printCalendarBtn.addEventListener('click', function (e) {
      e.preventDefault();
      window.print();
    });
  }

  // Sync Philippine Holidays Button Handler
  if (syncHolidaysBtn) {
    syncHolidaysBtn.addEventListener('click', function (e) {
      e.preventDefault();
      confirmAction({
        title: 'Synchronize Philippine Holidays',
        message: 'Automatically ingest official Philippine regular and special non-working holidays into the academic calendar? Existing holidays will not be duplicated.',
        confirmText: 'Sync Holidays Now',
        type: 'primary',
      }, function () {
        const originalHtml = syncHolidaysBtn.innerHTML;
        syncHolidaysBtn.disabled = true;
        syncHolidaysBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';

        fetch('/admin/calendar/sync-holidays/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then((res) => res.json())
          .then((data) => {
            syncHolidaysBtn.disabled = false;
            syncHolidaysBtn.innerHTML = originalHtml;
            if (data.status === 'success') {
              if (window.showToast) window.showToast(data.message, 'success');
              calendar.refetchEvents();
            } else {
              if (window.showToast) window.showToast(data.error || 'Failed to sync holidays.', 'error');
            }
          })
          .catch((err) => {
            syncHolidaysBtn.disabled = false;
            syncHolidaysBtn.innerHTML = originalHtml;
            console.error('[Sync Holidays Error]', err);
            if (window.showToast) window.showToast('Network error while syncing holidays.', 'error');
          });
      });
    });
  }

  // Reset Filters Button Trigger
  if (resetFiltersBtn) {
    resetFiltersBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (searchInput) searchInput.value = '';
      if (categoryFilter) categoryFilter.value = '';
      if (academicYearFilter) academicYearFilter.value = '';
      if (semesterFilter) semesterFilter.value = '';
      if (statusFilter) statusFilter.value = '';
      if (jumpToDateInput) jumpToDateInput.value = toDateOnlyString(new Date());
      document.querySelectorAll('.category-legend-pill').forEach((p) => p.classList.remove('active'));
      calendar.today();
      refetch();
    });
  }

  // Legend Category Click-to-Filter
  document.querySelectorAll('.category-legend-pill').forEach((pill) => {
    pill.addEventListener('click', function (e) {
      e.preventDefault();
      const cat = this.getAttribute('data-category');
      const isActive = this.classList.contains('active');

      document.querySelectorAll('.category-legend-pill').forEach((p) => p.classList.remove('active'));

      if (isActive) {
        if (categoryFilter) categoryFilter.value = '';
      } else {
        this.classList.add('active');
        if (categoryFilter) categoryFilter.value = cat;
      }
      refetch();
    });
  });

  // Upcoming Event Item Click -> View in Calendar
  document.querySelectorAll('.upcoming-event-item').forEach((item) => {
    item.addEventListener('click', function (e) {
      e.preventDefault();
      const eventId = this.getAttribute('data-event-id');
      const startDateStr = this.getAttribute('data-start');
      if (startDateStr) {
        calendar.gotoDate(startDateStr);
      }
      fetch(`/admin/calendar/events/${eventId}/get/`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.status === 'success') {
            const tempEvent = {
              id: data.event.id,
              title: data.event.title,
              start: new Date(data.event.start),
              end: new Date(data.event.end),
              allDay: data.event.allDay,
              extendedProps: data.event.extendedProps,
            };
            openEventDetailModal(tempEvent);
          }
        })
        .catch((err) => console.error('[Upcoming Event Click]', err));
    });
  });
});
