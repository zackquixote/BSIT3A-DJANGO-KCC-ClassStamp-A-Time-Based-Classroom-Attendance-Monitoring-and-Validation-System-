/* KCC ClassStamp — Section Builder Wizard v3 (Enhanced UX, Presets, Timetable Grid) */
(function () {
  'use strict';

  const boot = document.getElementById('wizard-boot');
  if (!boot) return;

  const $ = (id) => document.getElementById(id);
  const programs = JSON.parse($('wizard-programs').textContent || '[]');
  const departments = JSON.parse(($('wizard-departments') || { textContent: '[]' }).textContent || '[]');
  const existingRooms = JSON.parse(($('wizard-rooms') || { textContent: '[]' }).textContent || '[]');
  const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const WEEKDAYS_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrf = csrfMeta ? csrfMeta.content : (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
  const GRACE_MINUTES = 5; // ±5 min tolerance for hours matching

  const state = {
    step: 1,
    maxStep: 1,
    step1Key: '',
    options: null,
    slots: [],
    conflicts: [],
    offerings: [],
    sectionCode: '',
    finalOffering: null,
    codeStatus: { available: true, message: '' }
  };

  /* ── Utilities ───────────────────────────────────────────────── */
  function showError(msg) {
    const el = $('wiz-error');
    if (!el) return;
    el.textContent = msg || '';
    el.style.display = msg ? 'block' : 'none';
  }

  function toMins(hhmm) {
    const parts = String(hhmm).split(':').map(Number);
    return parts[0] * 60 + (parts[1] || 0);
  }

  function fromMins(mins) {
    const h = Math.floor(mins / 60) % 24;
    const m = mins % 60;
    return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
  }

  function fmtMinutes(mins) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? h + 'h ' + m + 'm' : h + 'h';
  }

  function fmtTime(hhmm) {
    const [h, m] = String(hhmm).split(':').map(Number);
    const suffix = h >= 12 ? 'PM' : 'AM';
    const hour12 = h % 12 || 12;
    return hour12 + ':' + String(m).padStart(2, '0') + ' ' + suffix;
  }

  function totalMinutes() {
    return state.slots.reduce((acc, s) => acc + (toMins(s.ends_at) - toMins(s.starts_at)), 0);
  }

  function currentSubject() {
    const subjects = state.options ? state.options.subjects : [];
    return subjects.find((s) => String(s.id) === $('wiz-subject').value) || null;
  }

  function requiredMinutes() {
    const subject = currentSubject();
    return subject ? subject.units * 60 : 0;
  }

  function hasTeacherConflicts() {
    return state.conflicts.some((c) => c.teacher && c.teacher.length);
  }

  function isHoursOk() {
    const diff = Math.abs(totalMinutes() - requiredMinutes());
    return diff <= GRACE_MINUTES;
  }

  function getStep1Key() {
    return `${$('wiz-program').value}|${$('wiz-year').value}|${$('wiz-semester').value}|${$('wiz-ay').value}`;
  }

  /* ── Loading indicator on Continue button ───────────────────── */
  function setLoading(on) {
    const btn = $('wiz-next');
    const icon = $('wiz-next-icon');
    const spinner = $('wiz-next-spinner');
    btn.disabled = on;
    if (icon) icon.style.display = on ? 'none' : '';
    if (spinner) spinner.style.display = on ? '' : 'none';
  }

  /* ── Step navigation ─────────────────────────────────────────── */
  function setStep(n) {
    state.step = n;
    state.maxStep = Math.max(state.maxStep || 1, n);

    for (let i = 1; i <= 5; i++) {
      const section = $('wizard-step-' + i);
      if (section) section.style.display = i === n ? '' : 'none';
    }

    document.querySelectorAll('[data-step-indicator]').forEach((el) => {
      const s = parseInt(el.dataset.stepIndicator, 10);
      const clickable = s <= state.maxStep && s !== n;
      el.classList.toggle('is-active', s === n);
      el.classList.toggle('is-done', s < n);
      el.classList.toggle('is-clickable', clickable);
      // Keyboard reachability mirrors the pointer affordance: a step you can
      // click is a step you can tab to.
      el.tabIndex = clickable ? 0 : -1;
      if (s === n) {
        el.setAttribute('aria-current', 'step');
      } else {
        el.removeAttribute('aria-current');
      }
    });

    $('wiz-back').style.visibility = n === 1 ? 'hidden' : 'visible';
    $('wiz-next').style.display = n < 5 ? '' : 'none';
    $('wiz-create').style.display = n === 5 ? '' : 'none';
    showError('');

    if (n === 4) {
      renderSlots();
      updateTally();
      renderTimetableGrid();
      checkConflicts();
    }
    if (n === 5) buildReview();
  }

  /* ── Step indicator click ───────────────────────────────────── */
  document.querySelectorAll('[data-step-indicator]').forEach((el) => {
    el.addEventListener('click', function () {
      const target = parseInt(this.dataset.stepIndicator, 10);
      if (target <= state.maxStep && target !== state.step) {
        setStep(target);
      }
    });
    el.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
        // Stop the document-level "Enter advances the wizard" handler from
        // also firing on the same keystroke.
        event.preventDefault();
        event.stopPropagation();
        this.click();
      }
    });
  });

  /* ── Room datalist autocomplete ─────────────────────────────── */
  function populateRoomSuggestions() {
    const dl = $('room-suggestions');
    if (!dl || !existingRooms.length) return;
    dl.innerHTML = '';
    existingRooms.forEach((room) => {
      const opt = document.createElement('option');
      opt.value = room;
      dl.appendChild(opt);
    });
  }

  /* ── Step 1: Department / Program / Year cascade ────────────── */
  function onDepartmentChange() {
    const deptSel = $('wiz-department');
    const deptId = deptSel ? deptSel.value : '';
    const progSel = $('wiz-program');
    if (!progSel) return;
    const prevProgId = progSel.value;
    progSel.innerHTML = '<option value="">Select Program</option>';

    const filtered = deptId
      ? programs.filter((p) => String(p.department_id) === String(deptId))
      : programs;

    filtered.forEach((p) => {
      progSel.appendChild(new Option(`${p.code} · ${p.name}`, String(p.id)));
    });

    if (filtered.some((p) => String(p.id) === prevProgId)) {
      progSel.value = prevProgId;
    } else {
      progSel.value = '';
      onProgramChange();
    }
  }

  function onProgramChange() {
    const yearSel = $('wiz-year');
    const program = programs.find((p) => String(p.id) === $('wiz-program').value);
    yearSel.innerHTML = '';
    if (!program) {
      yearSel.disabled = true;
      yearSel.appendChild(new Option('Select program first', ''));
      return;
    }
    yearSel.disabled = false;
    for (let y = 1; y <= program.years_total; y++) {
      yearSel.appendChild(new Option('Year ' + y, String(y)));
    }
    onStep1InputModified();
  }

  function onStep1InputModified() {
    const currentKey = getStep1Key();
    if (state.step1Key && state.step1Key !== currentKey) {
      state.maxStep = 1;
      document.querySelectorAll('[data-step-indicator]').forEach((el) => {
        const s = parseInt(el.dataset.stepIndicator, 10);
        el.classList.toggle('is-clickable', s === 1);
        if (s > 1) el.classList.remove('is-done', 'is-active');
      });
    }
  }

  async function loadOptions() {
    if (!$('wiz-program').value || !$('wiz-year').value) {
      showError('Select a program and year level first.');
      return;
    }

    const currentKey = getStep1Key();
    // Non-destructive step navigation: if already loaded and unchanged, keep existing data!
    if (state.options && state.step1Key === currentKey) {
      setStep(2);
      return;
    }

    showError('');
    setLoading(true);
    try {
      const params = new URLSearchParams({
        program_id: $('wiz-program').value,
        year_level: $('wiz-year').value,
        semester: $('wiz-semester').value,
        ay_id: $('wiz-ay').value,
      });
      const res = await fetch(boot.dataset.optionsUrl + '?' + params.toString());
      const data = await res.json();
      if (!res.ok || !data.success) {
        showError(data.message || 'Failed to load wizard options.');
        return;
      }
      state.options = data;
      state.step1Key = currentKey;
      state.offerings = [];
      state.sectionCode = '';
      state.finalOffering = null;
      state.slots = [];
      state.conflicts = [];
      populateSubjects();
      populateTeachers();
      populateExistingCodes(data);
      renderCoverageIndicator(data);
      $('wiz-code').value = data.suggested_code || '';
      setStep(2);
    } catch (err) {
      console.error('Unable to load class setup options:', err);
      showError('Unable to prepare setup options. Please retry or reload the page.');
    } finally {
      setLoading(false);
    }
  }

  function renderCoverageIndicator(data) {
    const banner = $('wiz-coverage-banner');
    if (!banner) return;
    if (!data || typeof data.subjects_total !== 'number' || data.subjects_total === 0) {
      banner.style.display = 'none';
      banner.innerHTML = '';
      return;
    }
    const total = data.subjects_total;
    const covered = data.subjects_covered || 0;
    const pct = Math.min(100, Math.round((covered / total) * 100));
    const isFull = covered >= total;
    banner.style.display = 'block';
    banner.innerHTML = `
      <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--glass-border); border-radius: var(--radius-md); padding: 12px 16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
          <span style="font-size:0.75rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; color:var(--text-muted);">
            <i class="fas fa-chart-pie text-primary"></i> Curriculum Sectioning Progress (This Term)
          </span>
          <span class="badge ${isFull ? 'badge--success' : 'badge--gold'} badge--xs">
            ${covered} of ${total} subjects scheduled (${pct}%)
          </span>
        </div>
        <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
          <div style="width:${pct}%; height:100%; background:${isFull ? '#22c55e' : '#6366f1'}; transition:width 0.3s ease;"></div>
        </div>
      </div>
    `;
  }

  function renderAddedOfferings() {
    const container = $('wiz-added-offerings');
    const list = $('wiz-added-offerings-list');
    if (!container || !list) return;
    list.innerHTML = '';
    if (!state.offerings.length) {
      container.style.display = 'none';
      return;
    }

    container.style.display = '';
    const message = container.querySelector('span');
    if (message) {
      message.textContent =
        `${state.offerings.length} subject offering${state.offerings.length === 1 ? '' : 's'} saved for ${state.sectionCode}. You can remove one before creating the section.`;
    }

    state.offerings.forEach((offering, index) => {
      const subject = (state.options.subjects || []).find(
        (item) => String(item.id) === String(offering.subject_id)
      );
      const teacher = (state.options.teachers || []).find(
        (item) => String(item.profile_id) === String(offering.teacher_profile_id)
      );
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:6px 0;border-top:1px solid rgba(255,255,255,.08);';

      const details = document.createElement('span');
      details.textContent = `${subject ? subject.code : 'Subject'} · ${teacher ? teacher.name : 'Teacher'} · ${(offering.slots || []).length} schedule slot(s)`;
      row.appendChild(details);

      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'btn btn-outline btn-xs';
      removeButton.style.marginLeft = 'auto';
      removeButton.textContent = 'Remove';
      removeButton.setAttribute(
        'aria-label',
        `Remove ${subject ? subject.code : 'subject'} offering`
      );
      removeButton.addEventListener('click', () => {
        state.offerings.splice(index, 1);
        populateSubjects();
      });
      row.appendChild(removeButton);
      list.appendChild(row);
    });
  }

  function populateSubjects() {
    const sel = $('wiz-subject');
    const emptyBox = $('wiz-empty-subjects');
    const emptyDesc = $('wiz-empty-subjects-desc');
    const link = $('wiz-curriculum-link');
    const selectedSubjectId = sel.value;
    sel.innerHTML = '';

    const addedSubjectIds = new Set(state.offerings.map((offering) => String(offering.subject_id)));
    const subjects = (state.options.subjects || [])
      .filter((subject) => !addedSubjectIds.has(String(subject.id)));
    if (!subjects.length) {
      if (emptyBox) emptyBox.style.display = 'block';
      const p = programs.find((pr) => String(pr.id) === $('wiz-program').value);
      const pName = p ? p.code : 'this program';
      if (emptyDesc) {
        emptyDesc.textContent = state.offerings.length
          ? 'All curriculum subjects have been added to this section.'
          : `No active subjects found in curriculum matrix for ${pName}, Year ${$('wiz-year').value}, ${$('wiz-semester').selectedOptions[0].textContent}.`;
      }
      if (link && p) {
        const curriculumUrl = new URL(boot.dataset.programsUrl, window.location.origin);
        curriculumUrl.searchParams.set('open_curriculum', p.id);
        link.href = curriculumUrl.toString();
      }
      sel.appendChild(new Option('No curriculum subjects for this selection', ''));
      updateUnitsHint();
      renderAddedOfferings();
      return;
    }

    if (emptyBox) emptyBox.style.display = 'none';
    sel.appendChild(new Option('Select subject', ''));
    subjects.forEach((s) => {
      const majorLabel = s.is_major ? ' · MAJOR' : '';
      const option = new Option(`${s.code} · ${s.name}${majorLabel} (${s.units} units)`, String(s.id));
      option.dataset.code = s.code;
      sel.appendChild(option);
    });
    if (subjects.some((subject) => String(subject.id) === selectedSubjectId)) {
      sel.value = selectedSubjectId;
    }
    updateUnitsHint();
    renderAddedOfferings();
  }

  function populateTeachers() {
    const sel = $('wiz-teacher');
    sel.innerHTML = '';
    const teachers = state.options.teachers || [];
    if (!teachers.length) {
      sel.appendChild(new Option('No active teachers in this department', ''));
      return;
    }

    sel.appendChild(new Option('Select teacher', ''));
    teachers.forEach((t) => {
      const load = `${t.active_classes} class(es), ${t.active_slots} slot(s)/week`;
      // Clean option formatting
      sel.appendChild(new Option(`${t.name} (${load})`, String(t.profile_id)));
    });
  }

  function populateExistingCodes(data) {
    const el = $('wiz-existing-sections');
    if (!el) return;

    const sections = data.existing_sections || [];
    el.style.display = 'block';

    if (!sections.length) {
      const legacy = data.existing_codes || [];
      el.innerHTML = legacy.length
        ? '<span class="text-muted">Existing sections in this term:</span> ' +
          legacy.map((c) => `<span class="badge badge--dark badge--xs" style="margin-right:4px;">${c}</span>`).join(' ')
        : '<span class="text-muted">No sections created yet for this year level (starting with letter A).</span>';
      return;
    }

    // One badge per SECTION, with the subject count — repeating the full
    // class_code once per subject is what made the old list unreadable.
    el.innerHTML = '<span class="text-muted">Existing sections in this term:</span> ' +
      sections.map((s) => {
        const subjects = (s.subjects || []).join(' · ');
        const label = `${s.section_code} · ${s.subject_count} subject${s.subject_count === 1 ? '' : 's'}`;
        return `<span class="badge badge--dark badge--xs" style="margin-right:4px;" title="${escapeHtml(subjects)}">${escapeHtml(label)}</span>`;
      }).join(' ');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ── Section-code availability (step 3) ─────────────────────── */
  async function checkCodeAvailability() {
    const codeInput = $('wiz-code');
    if (!codeInput) return true;
    const code = codeInput.value.trim().toUpperCase();
    codeInput.value = code;

    if (!code) {
      state.codeStatus = { available: false, message: 'Section code is required.' };
      renderCodeStatus();
      return false;
    }

    const subjectSelect = $('wiz-subject');
    const subjectCode = subjectSelect && subjectSelect.selectedOptions.length
      ? (subjectSelect.selectedOptions[0].dataset.code || '')
      : '';

    const params = new URLSearchParams({
      code: code,
      ay: $('wiz-ay') ? $('wiz-ay').value : '',
      subject: subjectCode,
      batch: '1',
    });

    try {
      const res = await fetch(boot.dataset.codeCheckUrl + '?' + params.toString(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      state.codeStatus = await res.json();
    } catch (err) {
      // A failed check must not block the wizard; the server still enforces the
      // unique constraint at save time.
      state.codeStatus = { available: true, message: '' };
    }

    renderCodeStatus();
    return !!state.codeStatus.available;
  }

  function renderCodeStatus() {
    const el = $('wiz-code-status');
    if (!el) return;

    const status = state.codeStatus || {};
    if (status.available) {
      el.style.display = 'none';
      el.innerHTML = '';
      return;
    }

    el.style.display = 'block';
    let html = `<span class="text-danger text-xs"><i class="fas fa-circle-exclamation"></i> ${escapeHtml(status.message || 'That code is already taken.')}</span>`;
    if (status.suggestion) {
      html += ` <button type="button" class="btn btn-outline btn-xs" id="wiz-code-suggest" style="margin-left:6px;">Use ${escapeHtml(status.suggestion)}</button>`;
    }
    el.innerHTML = html;

    const btn = $('wiz-code-suggest');
    if (btn) {
      btn.addEventListener('click', function () {
        $('wiz-code').value = status.suggestion;
        checkCodeAvailability();
      });
    }
  }

  function updateUnitsHint() {
    const subject = currentSubject();
    $('wiz-subject-units').textContent = subject
      ? `Requires ${fmtMinutes(requiredMinutes())} of schedule per week (${subject.units} credit unit${subject.units !== 1 ? 's' : ''}).`
      : '';
  }

  /* ── Step 4: auto-suggest end time based on subject units ────── */
  function autoSuggestEndTime() {
    const startInput = $('slot-start');
    const endInput = $('slot-end');
    const endHint = $('slot-end-hint');
    const subject = currentSubject();
    if (!subject || !startInput.value) return;

    const needed = requiredMinutes() - totalMinutes();
    if (needed <= 0) return;

    const startMins = toMins(startInput.value);
    const endMins = startMins + Math.min(needed, 180); // max 3 hours per slot
    const endStr = fromMins(endMins);

    endInput.value = endStr;
    if (endHint) {
      endHint.textContent = `(auto: +${fmtMinutes(endMins - startMins)})`;
      setTimeout(() => { if (endHint) endHint.textContent = ''; }, 3000);
    }
  }

  /* ── Step 4: 1-Click Quick Schedule Presets ─────────────────── */
  function applyPreset(pattern, slotDurationMinutes) {
    const subject = currentSubject();
    if (!subject) {
      showError('Please pick a subject first.');
      return;
    }

    const startInput = $('slot-start');
    const roomInput = $('slot-room');
    const startsAt = startInput.value || '08:00';
    const room = roomInput.value.trim();

    const startMins = toMins(startsAt);
    const endMins = startMins + slotDurationMinutes;
    const endsAt = fromMins(endMins);

    let targetDays = [];
    if (pattern === 'MWF') targetDays = [0, 2, 4]; // Monday, Wednesday, Friday
    else if (pattern === 'TTH') targetDays = [1, 3]; // Tuesday, Thursday
    else if (pattern === 'MW') targetDays = [0, 2]; // Monday, Wednesday
    else if (pattern === 'SAT') targetDays = [5]; // Saturday

    // Check overlaps
    for (const d of targetDays) {
      const overlaps = state.slots.some((s) =>
        s.weekday === d && toMins(s.starts_at) < toMins(endsAt) && toMins(startsAt) < toMins(s.ends_at)
      );
      if (overlaps) {
        showError(`Slot overlaps existing schedule on ${WEEKDAYS[d]}.`);
        return;
      }
    }

    // Add all preset days
    targetDays.forEach((weekday) => {
      state.slots.push({ weekday, starts_at: startsAt, ends_at: endsAt, room });
    });

    state.slots.sort((a, b) => a.weekday - b.weekday || toMins(a.starts_at) - toMins(b.starts_at));
    showError('');
    $('wiz-schedule-subject').textContent = subject ? `${subject.code} — ${subject.name}` : 'this subject';
    $('wiz-offering-count').textContent = state.offerings.length
      ? `${state.offerings.length} subject offering${state.offerings.length === 1 ? '' : 's'} ready for this section.`
      : 'No subject offerings added yet.';
    renderSlots();
    updateTally();
    renderTimetableGrid();
    checkConflicts();
  }

  /* ── Step 4: Add / Remove custom slot ───────────────────────── */
  function addSlot() {
    const weekday = parseInt($('slot-weekday').value, 10);
    const startsAt = $('slot-start').value;
    const endsAt = $('slot-end').value;
    const room = $('slot-room').value.trim();

    if (!startsAt || !endsAt) {
      showError('Start and end times are required.');
      return;
    }
    if (toMins(startsAt) >= toMins(endsAt)) {
      showError('End time must be after the start time.');
      return;
    }
    const overlaps = state.slots.some((s) =>
      s.weekday === weekday && toMins(s.starts_at) < toMins(endsAt) && toMins(startsAt) < toMins(s.ends_at)
    );
    if (overlaps) {
      showError('That window overlaps another slot in this list.');
      return;
    }
    state.slots.push({ weekday, starts_at: startsAt, ends_at: endsAt, room });
    state.slots.sort((a, b) => a.weekday - b.weekday || toMins(a.starts_at) - toMins(b.starts_at));
    showError('');
    $('slot-room').value = '';
    renderSlots();
    updateTally();
    renderTimetableGrid();
    checkConflicts();
  }

  function removeSlot(index) {
    state.slots.splice(index, 1);
    renderSlots();
    updateTally();
    renderTimetableGrid();
    checkConflicts();
  }

  function clearAllSlots() {
    if (!state.slots.length) return;
    state.slots = [];
    state.conflicts = [];
    renderSlots();
    updateTally();
    renderTimetableGrid();
  }

  function updateTally() {
    const total = totalMinutes();
    const required = requiredMinutes();
    const diff = total - required;
    const el = $('hours-tally');
    let label = `Scheduled: ${fmtMinutes(total)} / Required: ${fmtMinutes(required)}`;
    if (total > 0 && diff !== 0) {
      label += diff > 0 ? ` (+${fmtMinutes(diff)} over)` : ` (${fmtMinutes(-diff)} remaining)`;
    }
    el.textContent = label;
    const ok = isHoursOk();
    el.classList.toggle('badge--success', ok && total > 0);
    el.classList.toggle('badge--gold', !ok || total === 0);
  }

  /* ── Visual Weekly Timetable Grid Preview ────────────────────── */
  function renderTimetableGrid() {
    const container = $('wizard-timetable-grid');
    if (!container) return;
    container.innerHTML = '';

    for (let dayIndex = 0; dayIndex < 7; dayIndex++) {
      const daySlots = state.slots.filter((s) => s.weekday === dayIndex);
      const col = document.createElement('div');
      col.className = 'wizard-day-col' + (daySlots.length ? ' has-slots' : '');

      const head = document.createElement('div');
      head.className = 'wizard-day-head';
      head.textContent = WEEKDAYS_SHORT[dayIndex];
      col.appendChild(head);

      if (daySlots.length) {
        daySlots.forEach((slot) => {
          const pill = document.createElement('div');
          pill.className = 'wizard-slot-pill';
          pill.innerHTML = `
            <div class="wizard-slot-pill-time">${fmtTime(slot.starts_at)} &ndash; ${fmtTime(slot.ends_at)}</div>
            ${slot.room ? `<div class="wizard-slot-pill-room"><i class="fas fa-door-open"></i> ${slot.room}</div>` : ''}
          `;
          col.appendChild(pill);
        });
      } else {
        const empty = document.createElement('div');
        empty.className = 'wizard-day-empty';
        empty.textContent = '&mdash;';
        col.appendChild(empty);
      }

      container.appendChild(col);
    }
  }

  function renderSlots() {
    const list = $('slot-list');
    list.innerHTML = '';
    if (!state.slots.length) {
      const empty = document.createElement('p');
      empty.className = 'text-muted text-sm';
      empty.textContent = 'No slots added yet. Use the 1-Click presets above or add custom meeting times.';
      list.appendChild(empty);
      return;
    }
    state.slots.forEach((slot, index) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;border-radius:8px;background:rgba(255,255,255,0.03);border:1px solid var(--glass-border);margin-bottom:6px;';

      const icon = document.createElement('i');
      icon.className = 'fas fa-clock text-muted';
      icon.style.fontSize = '0.85rem';
      row.appendChild(icon);

      const label = document.createElement('span');
      label.className = 'font-semibold text-primary text-sm';
      label.textContent = `${WEEKDAYS[slot.weekday]} · ${fmtTime(slot.starts_at)} – ${fmtTime(slot.ends_at)}`;
      row.appendChild(label);

      if (slot.room) {
        const roomBadge = document.createElement('span');
        roomBadge.className = 'badge badge--dark badge--xs';
        roomBadge.innerHTML = `<i class="fas fa-door-open"></i> ${slot.room}`;
        row.appendChild(roomBadge);
      }

      const dur = document.createElement('span');
      dur.className = 'text-muted text-xs';
      dur.textContent = fmtMinutes(toMins(slot.ends_at) - toMins(slot.starts_at));
      row.appendChild(dur);

      const conflicts = state.conflicts[index] || { teacher: [], room: [] };
      (conflicts.teacher || []).forEach((text) => {
        const badge = document.createElement('span');
        badge.className = 'badge badge--danger badge--xs';
        badge.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Teacher clash: ${text}`;
        row.appendChild(badge);
      });
      (conflicts.room || []).forEach((text) => {
        const badge = document.createElement('span');
        badge.className = 'badge badge--gold badge--xs';
        badge.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Room used: ${text}`;
        row.appendChild(badge);
      });

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-outline btn-xs';
      removeBtn.style.marginLeft = 'auto';
      removeBtn.innerHTML = '<i class="fas fa-trash"></i>';
      removeBtn.title = 'Remove this slot';
      removeBtn.addEventListener('click', () => removeSlot(index));
      row.appendChild(removeBtn);

      list.appendChild(row);
    });
  }

  async function checkConflicts() {
    if (!state.slots.length || !$('wiz-teacher').value) {
      state.conflicts = [];
      renderSlots();
      return true;
    }
    try {
      const body = new URLSearchParams();
      body.set('teacher_profile_id', $('wiz-teacher').value);
      body.set('ay_id', $('wiz-ay').value);
      body.set('slots', JSON.stringify(state.slots));
      const res = await fetch(boot.dataset.checkUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body: body,
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        showError(data.message || 'Conflict check failed.');
        return false;
      }
      state.conflicts = data.slots;
      renderSlots();
      return true;
    } catch (err) {
      showError('Network error during conflict check.');
      return false;
    }
  }

  function currentOfferingData() {
    return {
      subject_id: $('wiz-subject').value,
      teacher_profile_id: $('wiz-teacher').value,
      slots: state.slots.map((slot) => ({ ...slot }))
    };
  }

  async function validateCurrentOffering() {
    if (!$('wiz-subject').value) {
      showError('Select a subject.');
      return null;
    }
    if (!$('wiz-teacher').value) {
      showError('Select a teacher.');
      return null;
    }
    if (!isHoursOk()) {
      showError(
        `This subject needs ~${fmtMinutes(requiredMinutes())} per week; your slots total ${fmtMinutes(totalMinutes())}.`
      );
      return null;
    }
    if (!await checkConflicts()) return null;
    if (hasTeacherConflicts()) {
      showError('Resolve the teacher schedule clashes below before continuing.');
      return null;
    }
    return currentOfferingData();
  }

  async function addOffering() {
    const offering = await validateCurrentOffering();
    if (!offering) return;
    const sectionCode = $('wiz-code').value.trim().toUpperCase();
    if (!sectionCode) {
      showError('Enter the section code before adding subject offerings.');
      return;
    }
    state.sectionCode = sectionCode;
    state.offerings.push(offering);
    state.slots = [];
    state.conflicts = [];
    state.finalOffering = null;
    populateSubjects();
    updateUnitsHint();
    $('wiz-teacher').value = '';
    setStep(2);
  }

  /* ── Step 5: Review ─────────────────────────────────────────── */
  function buildReview() {
    const summary = $('review-summary');
    summary.innerHTML = '';
    const offerings = state.offerings.concat(state.finalOffering ? [state.finalOffering] : []);

    const rows = [
      { label: 'Academic Year', value: $('wiz-ay').selectedOptions[0].textContent },
      { label: 'Program', value: $('wiz-program').selectedOptions[0].textContent },
      { label: 'Year Level', value: 'Year ' + $('wiz-year').value },
      { label: 'Semester', value: $('wiz-semester').selectedOptions[0].textContent },
      { label: 'Section Code', value: state.sectionCode || $('wiz-code').value.trim().toUpperCase(), badge: true },
      { label: 'Subject Offerings', value: String(offerings.length) },
      { label: 'Capacity', value: $('wiz-capacity').value || 'Unlimited' },
      { label: 'Grace Minutes', value: ($('wiz-grace').value || '10') + ' minutes' },
    ];

    const grid = document.createElement('div');
    grid.className = 'review-grid';

    rows.forEach(({ label, value, badge, html, full }) => {
      const item = document.createElement('div');
      item.className = 'review-item' + (full ? ' review-item--full' : '');

      const lbl = document.createElement('div');
      lbl.className = 'review-item-label';
      lbl.textContent = label;
      item.appendChild(lbl);

      const val = document.createElement('div');
      val.className = 'review-item-value';
      if (badge) {
        val.innerHTML = `<span class="badge badge--purple" style="font-size:0.85rem;padding:4px 10px;">${value}</span>`;
      } else if (html) {
        val.innerHTML = value || '<span class="text-muted">—</span>';
      } else {
        val.textContent = value || '—';
      }
      item.appendChild(val);
      grid.appendChild(item);
    });

    summary.appendChild(grid);

    offerings.forEach((offering, index) => {
      const subject = (state.options.subjects || []).find(
        (item) => String(item.id) === String(offering.subject_id)
      );
      const teacher = (state.options.teachers || []).find(
        (item) => String(item.profile_id) === String(offering.teacher_profile_id)
      );
      const card = document.createElement('div');
      card.className = 'review-item review-item--full';
      const title = document.createElement('div');
      title.className = 'review-item-label';
      title.textContent = `${index + 1}. ${subject ? `${subject.code} — ${subject.name}` : 'Subject'}`;
      card.appendChild(title);
      const details = document.createElement('div');
      details.className = 'review-item-value';
      details.textContent = `Class ${state.sectionCode || $('wiz-code').value.trim().toUpperCase()}-${subject ? subject.code : ''} · ${subject && subject.is_major ? 'Major' : 'Non-major'} · Teacher: ${teacher ? teacher.name : '—'} · ${subject ? fmtMinutes(subject.units * 60) : '—'} per week`;
      card.appendChild(details);
      const schedule = document.createElement('div');
      schedule.className = 'text-muted text-xs mt-1';
      schedule.textContent = (offering.slots || []).map((slot) =>
        `${WEEKDAYS[slot.weekday]} · ${fmtTime(slot.starts_at)}–${fmtTime(slot.ends_at)} · ${slot.room || 'TBA'}`
      ).join(' | ');
      card.appendChild(schedule);
      summary.appendChild(card);
    });

    const warnings = $('review-warnings');
    warnings.innerHTML = '';
    let hasRoomConflicts = false;
    state.conflicts.forEach((c) => {
      (c.room || []).forEach((text) => {
        hasRoomConflicts = true;
        const div = document.createElement('div');
        div.className = 'badge badge--gold';
        div.style.cssText = 'display:block;margin:8px 0 0;padding:8px 12px;';
        div.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Room conflict (blocks saving): ${text}`;
        warnings.appendChild(div);
      });
    });
    const overrideBox = $('review-override');
    if (overrideBox) {
      overrideBox.style.display = hasRoomConflicts ? '' : 'none';
      const overrideCheck = $('wiz-override-room');
      if (overrideCheck && !hasRoomConflicts) overrideCheck.checked = false;
    }
  }

  /* ── Create Section ─────────────────────────────────────────── */
  async function createSection() {
    const btn = $('wiz-create');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
    showError('');
    try {
      const body = new URLSearchParams();
      body.set('program_id', $('wiz-program').value);
      body.set('year_level', $('wiz-year').value);
      body.set('semester', $('wiz-semester').value);
      body.set('ay_id', $('wiz-ay').value);
      body.set('class_code', state.sectionCode || $('wiz-code').value.trim().toUpperCase());
      body.set('capacity', $('wiz-capacity').value);
      body.set('grace_minutes', $('wiz-grace').value || '10');
      const overrideRoom = $('wiz-override-room');
      body.set('override_conflicts', overrideRoom && overrideRoom.checked ? '1' : '0');
      body.set('offerings', JSON.stringify(
        state.offerings.concat(state.finalOffering ? [state.finalOffering] : [])
      ));
      const res = await fetch(boot.dataset.saveUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body: body,
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        showError(data.message || 'Failed to create the section.');
        return;
      }

      /* Show success panel */
      $('wizard-card').style.display = 'none';
      $('wizard-progress').style.display = 'none';
      $('wizard-success').style.display = '';
      $('success-code').textContent =
        `Section ${data.section_code} created with ${data.classes.length} subject offering(s).`;

      /* Populate success summary with quick-action links */
      const sumDiv = $('success-summary');
      sumDiv.innerHTML = '';
      const list = document.createElement('div');
      list.style.cssText = 'display:flex;flex-direction:column;gap:8px;';

      const classesUrl = boot.dataset.classesUrl || '/classes/';
      const classesList = data.classes || (data.class_id ? [{
        class_id: data.class_id,
        class_code: data.class_code,
        subject: '',
        teacher: '',
        slots: data.slots || [],
      }] : []);

      classesList.forEach((item) => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:8px;flex-wrap:wrap;gap:8px;';

        const info = document.createElement('div');
        info.innerHTML = `<strong>${escapeHtml(item.class_code)}</strong> &middot; ${escapeHtml(item.subject || '')} &middot; <span class="text-muted">${escapeHtml(item.teacher || '')}</span> &middot; <span class="badge badge--dark badge--xs">${(item.slots || []).length} slot(s)</span>`;
        row.appendChild(info);

        const actions = document.createElement('div');
        actions.style.cssText = 'display:flex;align-items:center;gap:6px;';

        if (item.class_id) {
          const rosterLink = document.createElement('a');
          rosterLink.className = 'btn btn-outline btn-xs';
          rosterLink.href = `${classesUrl}?setup_class=${item.class_id}&setup_action=roster`;
          rosterLink.innerHTML = '<i class="fas fa-users"></i> Enlist Students';
          actions.appendChild(rosterLink);

          const joinCodeLink = document.createElement('a');
          joinCodeLink.className = 'btn btn-outline btn-xs';
          joinCodeLink.href = `${classesUrl}?setup_class=${item.class_id}&setup_action=joincode`;
          joinCodeLink.innerHTML = '<i class="fas fa-key"></i> Join Code';
          actions.appendChild(joinCodeLink);
        }

        row.appendChild(actions);
        list.appendChild(row);
      });
      sumDiv.appendChild(list);

      const gotoBtn = $('success-goto');
      if (gotoBtn && data.section_code) {
        gotoBtn.href = `${classesUrl}?search=${encodeURIComponent(data.section_code)}`;
      }

      const warnBox = $('success-warnings');
      warnBox.innerHTML = '';
      (data.warnings || []).forEach((text) => {
        const div = document.createElement('div');
        div.className = 'badge badge--gold';
        div.style.cssText = 'display:block;margin:4px 0;padding:8px 12px;';
        div.textContent = `Room warning: ${text}`;
        warnBox.appendChild(div);
      });
    } catch (err) {
      showError('Network error while creating the section.');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-check"></i> Create Section & Offerings';
    }
  }

  /* ── Next / Back ─────────────────────────────────────────────── */
  async function onNext() {
    if (state.step === 1) return loadOptions();
    if (state.step === 2) {
      if (!$('wiz-subject').value && state.offerings.length) {
        state.finalOffering = null;
        setStep(5);
        return;
      }
      if (!$('wiz-subject').value) return showError('Select a subject.');
      if (!$('wiz-teacher').value) return showError('Select a teacher.');
      if (state.sectionCode) {
        const free = await checkCodeAvailability();
        if (!free) {
          showError((state.codeStatus && state.codeStatus.message) || 'This subject is already added to that section.');
          return;
        }
        setStep(4);
        return;
      }
      setStep(3);
      return;
    }
    if (state.step === 3) {
      if (!$('wiz-code').value.trim()) return showError('Section code is required.');
      const free = await checkCodeAvailability();
      if (!free) {
        showError((state.codeStatus && state.codeStatus.message) || 'That section code is already taken.');
        return;
      }
      state.sectionCode = $('wiz-code').value.trim().toUpperCase();
      setStep(4);
      return;
    }
    if (state.step === 4) {
      state.finalOffering = await validateCurrentOffering();
      if (!state.finalOffering) return;
      setStep(5);
    }
  }

  /* ── Keyboard: Enter to advance or add slot ─────────────────── */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      if (e.target.tagName === 'TEXTAREA') return;

      // In Step 4 slot input form: Enter adds the slot instead of advancing wizard!
      if (e.target.closest('#wizard-step-4') && (e.target.id === 'slot-start' || e.target.id === 'slot-end' || e.target.id === 'slot-room' || e.target.id === 'slot-weekday')) {
        e.preventDefault();
        e.stopPropagation();
        const addBtn = $('slot-add');
        if (addBtn) addBtn.click();
        return;
      }

      const next = $('wiz-next');
      const create = $('wiz-create');
      if (next && next.style.display !== 'none' && !next.disabled) next.click();
      else if (create && create.style.display !== 'none' && !create.disabled) create.click();
    }
  });

  /* ── Init ────────────────────────────────────────────────────── */
  function init() {
    const deptSel = $('wiz-department');
    if (deptSel) deptSel.addEventListener('change', onDepartmentChange);
    $('wiz-program').addEventListener('change', onProgramChange);
    $('wiz-year').addEventListener('change', onStep1InputModified);
    $('wiz-semester').addEventListener('change', onStep1InputModified);
    $('wiz-ay').addEventListener('change', onStep1InputModified);

    $('wiz-subject').addEventListener('change', () => {
      updateUnitsHint();
      autoSuggestEndTime();
    });

    const codeInput = $('wiz-code');
    if (codeInput) {
      codeInput.addEventListener('blur', checkCodeAvailability);
      codeInput.addEventListener('input', () => {
        // Typing invalidates the previous verdict; the check re-runs on blur.
        state.codeStatus = { available: true, message: '' };
        renderCodeStatus();
      });
    }

    $('wiz-next').addEventListener('click', onNext);
    $('wiz-back').addEventListener('click', () => {
      if (state.step > 1) setStep(state.step - 1);
    });

    $('slot-add').addEventListener('click', addSlot);
    const clearBtn = $('slot-clear-all');
    if (clearBtn) clearBtn.addEventListener('click', clearAllSlots);

    $('wiz-create').addEventListener('click', createSection);
    $('wiz-add-offering').addEventListener('click', addOffering);

    // 1-Click preset buttons
    document.querySelectorAll('.js-preset-slot').forEach((btn) => {
      btn.addEventListener('click', function () {
        const pattern = this.dataset.pattern;
        const duration = parseInt(this.dataset.duration, 10);
        applyPreset(pattern, duration);
      });
    });

    // Auto-suggest end time when start time changes
    $('slot-start').addEventListener('change', autoSuggestEndTime);
    $('slot-end').addEventListener('change', () => {
      const endHint = $('slot-end-hint');
      if (endHint) endHint.textContent = '';
    });

    populateRoomSuggestions();
    setStep(1);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
