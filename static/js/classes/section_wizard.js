/* KCC ClassStamp — Section Builder Wizard v3 (Enhanced UX, Presets, Timetable Grid) */
(function () {
  'use strict';

  const boot = document.getElementById('wizard-boot');
  if (!boot) return;

  const $ = (id) => document.getElementById(id);
  const programs = JSON.parse($('wizard-programs').textContent || '[]');
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
    conflicts: []
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
      el.classList.toggle('is-active', s === n);
      el.classList.toggle('is-done', s < n);
      el.classList.toggle('is-clickable', s <= state.maxStep && s !== n);
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

  /* ── Step 1: Program/Year cascade ────────────────────────────── */
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
      state.slots = [];
      state.conflicts = [];
      populateSubjects();
      populateTeachers();
      populateExistingCodes(data);
      $('wiz-code').value = data.suggested_code || '';
      setStep(2);
    } catch (err) {
      showError('Network error while loading options.');
    } finally {
      setLoading(false);
    }
  }

  function populateSubjects() {
    const sel = $('wiz-subject');
    const emptyBox = $('wiz-empty-subjects');
    const emptyDesc = $('wiz-empty-subjects-desc');
    const link = $('wiz-curriculum-link');
    sel.innerHTML = '';

    const subjects = state.options.subjects || [];
    if (!subjects.length) {
      if (emptyBox) emptyBox.style.display = 'block';
      const p = programs.find((pr) => String(pr.id) === $('wiz-program').value);
      const pName = p ? p.code : 'this program';
      if (emptyDesc) {
        emptyDesc.textContent = `No active subjects found in curriculum matrix for ${pName}, Year ${$('wiz-year').value}, ${$('wiz-semester').selectedOptions[0].textContent}.`;
      }
      if (link && p) {
        link.href = `/programs/${p.id}/curriculum/`;
      }
      sel.appendChild(new Option('No curriculum subjects for this selection', ''));
      updateUnitsHint();
      return;
    }

    if (emptyBox) emptyBox.style.display = 'none';
    sel.appendChild(new Option('Select subject', ''));
    subjects.forEach((s) => {
      // Clean option formatting (no dashes)
      sel.appendChild(new Option(`${s.code} · ${s.name} (${s.units} units)`, String(s.id)));
    });
    updateUnitsHint();
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
    const existing = data.existing_codes || [];
    if (existing.length) {
      el.style.display = 'block';
      el.innerHTML = '<span class="text-muted">Existing sections in this term:</span> ' +
        existing.map((c) => `<span class="badge badge--dark badge--xs" style="margin-right:4px;">${c}</span>`).join(' ');
    } else {
      el.style.display = 'block';
      el.innerHTML = '<span class="text-muted">No sections created yet for this year level (starting with letter A).</span>';
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

  /* ── Step 5: Review ─────────────────────────────────────────── */
  function buildReview() {
    const summary = $('review-summary');
    summary.innerHTML = '';
    const subject = currentSubject();
    const teacher = (state.options.teachers || []).find((t) => String(t.profile_id) === $('wiz-teacher').value);
    const scheduleLines = state.slots.map((s) =>
      `${WEEKDAYS[s.weekday]} · ${fmtTime(s.starts_at)} – ${fmtTime(s.ends_at)}${s.room ? ` (${s.room})` : ' (TBA)'}`
    ).join('<br>');

    const rows = [
      { label: 'Academic Year', value: $('wiz-ay').selectedOptions[0].textContent },
      { label: 'Program', value: $('wiz-program').selectedOptions[0].textContent },
      { label: 'Year Level', value: 'Year ' + $('wiz-year').value },
      { label: 'Semester', value: $('wiz-semester').selectedOptions[0].textContent },
      { label: 'Subject', value: subject ? `${sClean(subject.code)} · ${sClean(subject.name)}` : '' },
      { label: 'Required Hours', value: `${fmtMinutes(requiredMinutes())} per week` },
      { label: 'Teacher', value: teacher ? teacher.name : '' },
      { label: 'Section Code', value: $('wiz-code').value.trim().toUpperCase(), badge: true },
      { label: 'Capacity', value: $('wiz-capacity').value || 'Unlimited' },
      { label: 'Grace Minutes', value: ($('wiz-grace').value || '10') + ' minutes' },
      { label: 'Weekly Schedule', value: scheduleLines, html: true, full: true },
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

    const warnings = $('review-warnings');
    warnings.innerHTML = '';
    state.conflicts.forEach((c) => {
      (c.room || []).forEach((text) => {
        const div = document.createElement('div');
        div.className = 'badge badge--gold';
        div.style.cssText = 'display:block;margin:8px 0 0;padding:8px 12px;';
        div.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Room warning (allowed): ${text}`;
        warnings.appendChild(div);
      });
    });
  }

  function sClean(str) {
    return String(str || '').replace(/—/g, '·').trim();
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
      body.set('subject_id', $('wiz-subject').value);
      body.set('teacher_profile_id', $('wiz-teacher').value);
      body.set('ay_id', $('wiz-ay').value);
      body.set('class_code', $('wiz-code').value.trim().toUpperCase());
      body.set('capacity', $('wiz-capacity').value);
      body.set('grace_minutes', $('wiz-grace').value || '10');
      body.set('slots', JSON.stringify(state.slots));
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
        `Section ${data.class_code} created with ${data.slots.length} schedule slot(s).`;

      /* Populate success summary */
      const sumDiv = $('success-summary');
      const subject = currentSubject();
      const teacher = (state.options.teachers || []).find((t) => String(t.profile_id) === $('wiz-teacher').value);
      sumDiv.innerHTML =
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px 20px;">' +
        renderSuccessItem('Section Code', `<span class="badge badge--purple" style="font-size:0.85rem;">${data.class_code}</span>`) +
        renderSuccessItem('Subject', subject ? subject.code : '') +
        renderSuccessItem('Teacher', teacher ? teacher.name : '') +
        renderSuccessItem('Slots', `${data.slots.length} weekly slot(s)`) +
        renderSuccessItem('Semester', $('wiz-semester').selectedOptions[0].textContent) +
        renderSuccessItem('Academic Year', $('wiz-ay').selectedOptions[0].textContent) +
        '</div>';

      const warnBox = $('success-warnings');
      warnBox.innerHTML = '';
      (data.warnings || []).forEach((text) => {
        const div = document.createElement('div');
        div.className = 'badge badge--gold';
        div.style.cssText = 'display:block;margin:4px 0;padding:8px 12px;';
        div.innerHTML = `<i class="fas fa-triangle-exclamation"></i> Room warning: ${text}`;
        warnBox.appendChild(div);
      });
    } catch (err) {
      showError('Network error while creating the section.');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-check"></i> Create Section';
    }
  }

  function renderSuccessItem(label, valueHtml) {
    return `<div><div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:3px;">${label}</div><div style="font-size:0.9rem;font-weight:600;color:var(--text-primary);">${valueHtml}</div></div>`;
  }

  /* ── Next / Back ─────────────────────────────────────────────── */
  async function onNext() {
    if (state.step === 1) return loadOptions();
    if (state.step === 2) {
      if (!$('wiz-subject').value) return showError('Select a subject.');
      if (!$('wiz-teacher').value) return showError('Select a teacher.');
      setStep(3);
      return;
    }
    if (state.step === 3) {
      if (!$('wiz-code').value.trim()) return showError('Section code is required.');
      setStep(4);
      return;
    }
    if (state.step === 4) {
      if (!isHoursOk()) {
        showError(
          `This subject needs ~${fmtMinutes(requiredMinutes())} per week; your slots total ${fmtMinutes(totalMinutes())}.`
        );
        return;
      }
      const ok = await checkConflicts();
      if (!ok) return;
      if (hasTeacherConflicts()) {
        showError('Resolve the teacher schedule clashes below before continuing.');
        return;
      }
      setStep(5);
    }
  }

  /* ── Keyboard: Enter to advance ──────────────────────────────── */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
      const next = $('wiz-next');
      const create = $('wiz-create');
      if (next && next.style.display !== 'none' && !next.disabled) next.click();
      else if (create && create.style.display !== 'none' && !create.disabled) create.click();
    }
  });

  /* ── Init ────────────────────────────────────────────────────── */
  function init() {
    $('wiz-program').addEventListener('change', onProgramChange);
    $('wiz-year').addEventListener('change', onStep1InputModified);
    $('wiz-semester').addEventListener('change', onStep1InputModified);
    $('wiz-ay').addEventListener('change', onStep1InputModified);

    $('wiz-subject').addEventListener('change', () => {
      updateUnitsHint();
      autoSuggestEndTime();
    });

    $('wiz-next').addEventListener('click', onNext);
    $('wiz-back').addEventListener('click', () => {
      if (state.step > 1) setStep(state.step - 1);
    });

    $('slot-add').addEventListener('click', addSlot);
    const clearBtn = $('slot-clear-all');
    if (clearBtn) clearBtn.addEventListener('click', clearAllSlots);

    $('wiz-create').addEventListener('click', createSection);

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
