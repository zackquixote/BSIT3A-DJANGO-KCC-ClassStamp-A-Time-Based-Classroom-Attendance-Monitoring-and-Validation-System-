/* KCC ClassStamp — Add Section (one-page form) */
(function () {
  'use strict';

  const boot = document.getElementById('wizard-boot');
  if (!boot) return;

  const $ = (id) => document.getElementById(id);
  const programs = JSON.parse($('wizard-programs').textContent || '[]');
  const departments = JSON.parse(($('wizard-departments') || { textContent: '[]' }).textContent || '[]');
  const rooms = JSON.parse(($('wizard-rooms') || { textContent: '[]' }).textContent || '[]');

  const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const WEEKDAYS_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrf = csrfMeta ? csrfMeta.content : (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';

  const state = {
    options: null,
    step1Key: '',
    slots: [],
    conflicts: [],
    codeStatus: { available: true, message: '' },
    checkTimer: null,
    lastSavedSection: '',
    pinnedSection: '',
  };

  /* ── Small helpers ──────────────────────────────────────────── */
  function showError(msg) {
    const el = $('wiz-error');
    if (!el) return;
    el.textContent = msg || '';
    el.style.display = msg ? 'block' : 'none';
  }

  function showSuccess(msg) {
    const el = $('wiz-success');
    if (!el) return;
    $('wiz-success-text').textContent = msg || '';
    el.style.display = msg ? 'block' : 'none';
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function toMins(hhmm) {
    const parts = String(hhmm).split(':').map(Number);
    return (parts[0] || 0) * 60 + (parts[1] || 0);
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

  function step1Key() {
    return [$('wiz-program').value, $('wiz-year').value, $('wiz-semester').value, $('wiz-ay').value].join('|');
  }

  function setBusy(on) {
    const btn = $('wiz-create');
    btn.disabled = on;
    $('wiz-create-icon').style.display = on ? 'none' : '';
    $('wiz-create-spinner').style.display = on ? '' : 'none';
    $('wiz-create-label').textContent = on ? 'Saving…' : 'Create this subject';
  }

  /* ── Cascades ───────────────────────────────────────────────── */
  function fillDepartments() {
    const sel = $('wiz-department');
    departments.forEach((d) => {
      sel.appendChild(new Option(d.code ? d.code + ' · ' + d.name : d.name, String(d.id)));
    });
  }

  function fillPrograms() {
    const deptId = $('wiz-department').value;
    const prev = $('wiz-program').value;
    const sel = $('wiz-program');
    sel.innerHTML = '<option value="">Select Program</option>';
    const list = deptId
      ? programs.filter((p) => String(p.department_id) === String(deptId))
      : programs;
    list.forEach((p) => {
      sel.appendChild(new Option(p.code + ' · ' + p.name, String(p.id)));
    });
    if (list.some((p) => String(p.id) === prev)) sel.value = prev;
    else onProgramChange();
  }

  function onProgramChange() {
    const program = programs.find((p) => String(p.id) === $('wiz-program').value);
    const yearSel = $('wiz-year');
    yearSel.innerHTML = '';
    if (!program) {
      yearSel.disabled = true;
      yearSel.appendChild(new Option('Select program first', ''));
    } else {
      yearSel.disabled = false;
      yearSel.appendChild(new Option('Select year', ''));
      for (let y = 1; y <= program.years_total; y++) {
        yearSel.appendChild(new Option('Year ' + y, String(y)));
      }
    }
    resetOptions();
  }

  function resetOptions() {
    state.options = null;
    state.slots = [];
    state.conflicts = [];
    state.codeStatus = { available: true, message: '' };
    const subject = $('wiz-subject');
    subject.innerHTML = '<option value="">Select program / year first</option>';
    $('wiz-teacher').innerHTML = '<option value="">Select subject first</option>';
    $('wiz-code').value = '';
    $('wiz-subject-units').textContent = '';
    $('wiz-existing').innerHTML = '';
    renderCodeStatus();
    renderSlots();
    updateTally();
    renderPresets();
    renderWeekGrid();
  }

  /* ── Options feed ───────────────────────────────────────────── */
  async function loadOptions() {
    const programId = $('wiz-program').value;
    const year = $('wiz-year').value;
    if (!programId || !year) {
      resetOptions();
      return;
    }
    const key = step1Key();
    if (state.options && state.step1Key === key) return;

    showError('');
    showSuccess('');
    try {
      const params = new URLSearchParams({
        program_id: programId,
        year_level: year,
        semester: $('wiz-semester').value,
        ay_id: $('wiz-ay').value,
      });
      const res = await fetch(boot.dataset.optionsUrl + '?' + params.toString());
      const data = await res.json();
      if (!res.ok || !data.success) {
        showError(data.message || 'Failed to load subjects and teachers.');
        return;
      }
      state.options = data;
      state.step1Key = key;
      state.slots = [];
      state.conflicts = [];
      if (state.pinnedSection) {
        $('wiz-code').value = state.pinnedSection;
      } else if (!$('wiz-code').value.trim()) {
        $('wiz-code').value = data.suggested_code || '';
      }
      populateSubjects();
      populateTeachers();
      populateExisting(data);
      renderCodeStatus();
      renderSlots();
      updateTally();
      renderPresets();
      renderWeekGrid();
      // A new program/year should get a fresh availability verdict.
      checkCodeAvailability();
    } catch (err) {
      console.error('Unable to load section options:', err);
      showError('Unable to load subjects. Please retry or reload the page.');
    }
  }

  function populateSubjects() {
    const sel = $('wiz-subject');
    const empty = $('wiz-empty-subjects');
    sel.innerHTML = '';
    const subjects = (state.options && state.options.subjects) || [];
    if (!subjects.length) {
      sel.appendChild(new Option('No curriculum subjects', ''));
      const p = programs.find((pr) => String(pr.id) === $('wiz-program').value);
      $('wiz-empty-subjects-desc').textContent =
        'No active subjects in the curriculum for ' + (p ? p.code : 'this program') +
        ', Year ' + $('wiz-year').value + '. Map them in the Curriculum Matrix first.';
      empty.style.display = 'block';
      const link = $('wiz-curriculum-link');
      if (link && p) {
        const url = new URL(boot.dataset.programsUrl, window.location.origin);
        url.searchParams.set('open_curriculum', p.id);
        link.href = url.toString();
      }
      updateTally();
      renderPresets();
      return;
    }
    empty.style.display = 'none';
    sel.appendChild(new Option('Select subject', ''));
    subjects.forEach((s) => {
      const major = s.is_major ? ' · MAJOR' : '';
      sel.appendChild(new Option(s.code + ' · ' + s.name + major + ' (' + s.units + 'u)', String(s.id)));
    });
    updateTally();
    renderPresets();
  }

  function populateTeachers() {
    const sel = $('wiz-teacher');
    sel.innerHTML = '';
    const teachers = (state.options && state.options.teachers) || [];
    if (!teachers.length) {
      sel.appendChild(new Option('No active teachers in this department', ''));
      return;
    }
    sel.appendChild(new Option('Select teacher', ''));
    teachers.forEach((t) => {
      const load = t.active_classes + ' class(es), ' + t.active_slots + ' slot(s)/week';
      sel.appendChild(new Option(t.name + ' (' + load + ')', String(t.profile_id)));
    });
  }

  function populateExisting(data) {
    const box = $('wiz-existing');
    box.innerHTML = '';
    const sections = (data && data.existing_sections) || [];
    if (!sections.length) {
      box.innerHTML = '<span>No sections yet for this year level — starting at A.</span>';
      return;
    }
    const label = document.createElement('span');
    label.textContent = 'Already this term:';
    box.appendChild(label);
    sections.forEach((s) => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.title = (s.subjects || []).join(', ');
      chip.textContent = s.section_code + ' · ' + s.subject_count + (s.subject_count === 1 ? ' subject' : ' subjects');
      box.appendChild(chip);
    });
  }

  /* ── Section code ───────────────────────────────────────────── */
  async function checkCodeAvailability() {
    const codeInput = $('wiz-code');
    const code = codeInput.value.trim().toUpperCase();
    codeInput.value = code;
    if (!code) {
      state.codeStatus = { available: true, message: '' };
      renderCodeStatus();
      return true;
    }
    const subject = currentSubject();
    const params = new URLSearchParams({
      code: code,
      ay: $('wiz-ay').value,
      subject: subject ? subject.code : '',
      batch: '1',
    });
    try {
      const res = await fetch(boot.dataset.codeCheckUrl + '?' + params.toString(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      state.codeStatus = await res.json();
    } catch (err) {
      // Do not block the form on a failed check; the server still enforces uniqueness.
      state.codeStatus = { available: true, message: '' };
    }
    renderCodeStatus();
    return !!state.codeStatus.available;
  }

  function renderCodeStatus() {
    const el = $('wiz-code-status');
    const status = state.codeStatus || {};
    if (status.available) {
      el.style.display = 'none';
      el.innerHTML = '';
      return;
    }
    el.style.display = 'block';
    el.innerHTML =
      '<span style="color:#fca5a5;"><i class="fas fa-circle-exclamation"></i> ' +
      escapeHtml(status.message || 'That section code is already taken.') +
      '</span>';
  }

  /* ── Rooms ──────────────────────────────────────────────────── */
  function fillRooms() {
    const sel = $('slot-room-select');
    sel.innerHTML = '<option value="TBA">TBA (Unassigned)</option>';
    const labs = rooms.filter((r) => r.is_lab || r.room_type === 'LABORATORY');
    const lecs = rooms.filter((r) => !labs.includes(r));
    appendRoomGroup(sel, 'Computer Laboratories', labs);
    appendRoomGroup(sel, 'Lecture / Other Rooms', lecs);
  }

  function appendRoomGroup(sel, label, list) {
    if (!list.length) return;
    const group = document.createElement('optgroup');
    group.label = label;
    list.forEach((r) => {
      const opt = new Option(
        r.code + ' — ' + r.name + ' (' + r.capacity + ' cap)',
        r.code,
      );
      opt.dataset.id = r.id;
      opt.dataset.type = r.room_type;
      opt.dataset.cap = r.capacity;
      group.appendChild(opt);
    });
    sel.appendChild(group);
  }

  function onRoomChange() {
    const sel = $('slot-room-select');
    const opt = sel.selectedOptions[0];
    $('slot-room').value = sel.value || 'TBA';
    $('slot-room-id').value = (opt && opt.dataset.id) || '';
  }

  /* ── Units / presets / hours ────────────────────────────────── */
  function updateTally() {
    const el = $('hours-tally');
    const subject = currentSubject();
    if (!subject) {
      el.textContent = 'Pick a subject to see required hours';
      el.classList.remove('is-ok');
      return;
    }
    const total = totalMinutes();
    const required = requiredMinutes();
    if (total === required) {
      el.textContent = fmtMinutes(total) + ' of ' + fmtMinutes(required) + ' — ready';
      el.classList.add('is-ok');
    } else {
      const diff = required - total;
      el.textContent =
        fmtMinutes(total) + ' of ' + fmtMinutes(required) +
        (diff > 0 ? ' — add ' + fmtMinutes(diff) : ' — ' + fmtMinutes(-diff) + ' too much');
      el.classList.remove('is-ok');
    }
  }

  function renderPresets() {
    const bar = $('preset-bar');
    bar.innerHTML = '';
    const subject = currentSubject();
    if (!subject) return;
    const needed = subject.units * 60;

    const presets = [];
    if (needed >= 60 && needed <= 300) {
      presets.push({ label: 'One ' + fmtMinutes(needed) + ' block', pattern: 'SAT', duration: needed });
    }
    if (needed % 3 === 0) {
      presets.push({ label: 'MWF ' + fmtMinutes(needed / 3), pattern: 'MWF', duration: needed / 3 });
    }
    if (needed % 2 === 0) {
      presets.push({ label: 'TTh ' + fmtMinutes(needed / 2), pattern: 'TTH', duration: needed / 2 });
      presets.push({ label: 'MW ' + fmtMinutes(needed / 2), pattern: 'MW', duration: needed / 2 });
    }

    presets.forEach((p) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'preset-btn';
      btn.textContent = p.label;
      btn.title = 'Fill ' + p.label + ' at the Start time below';
      btn.addEventListener('click', () => applyPreset(p.pattern, p.duration));
      bar.appendChild(btn);
    });
  }

  function currentRoomFromForm() {
    const sel = $('slot-room-select');
    const opt = sel.selectedOptions[0];
    return {
      room: sel.value || 'TBA',
      room_id: (opt && opt.dataset.id) || null,
      room_capacity: opt && opt.dataset.cap ? parseInt(opt.dataset.cap, 10) : null,
    };
  }

  function applyPreset(pattern, durationMinutes) {
    const subject = currentSubject();
    if (!subject) {
      showError('Pick a subject first.');
      return;
    }
    const startsAt = $('slot-start').value || '08:00';
    const startMins = toMins(startsAt);
    const endMins = startMins + durationMinutes;
    if (endMins > 24 * 60) {
      showError('That preset would end after midnight. Pick an earlier start time.');
      return;
    }
    const endsAt = fromMins(endMins);
    const roomInfo = currentRoomFromForm();
    const slotType = subject.is_lab ? 'LABORATORY' : 'LECTURE';

    let days = [];
    if (pattern === 'MWF') days = [0, 2, 4];
    else if (pattern === 'TTH') days = [1, 3];
    else if (pattern === 'MW') days = [0, 2];
    else if (pattern === 'SAT') days = [5];

    for (const d of days) {
      const overlap = state.slots.some(
        (s) => s.weekday === d && toMins(s.starts_at) < endMins && startMins < toMins(s.ends_at),
      );
      if (overlap) {
        showError('Preset overlaps an existing meeting on ' + WEEKDAYS[d] + '.');
        return;
      }
    }

    days.forEach((weekday) => {
      state.slots.push({
        weekday,
        starts_at: startsAt,
        ends_at: endsAt,
        room: roomInfo.room,
        room_id: roomInfo.room_id,
        slot_type: slotType,
        room_capacity: roomInfo.room_capacity,
      });
    });
    state.slots.sort((a, b) => a.weekday - b.weekday || toMins(a.starts_at) - toMins(b.starts_at));
    showError('');
    $('slot-end').value = endsAt;
    renderSlots();
    updateTally();
    renderWeekGrid();
    queueConflictCheck();
  }

  function autoSuggestEndTime() {
    const subject = currentSubject();
    const startInput = $('slot-start');
    if (!subject || !startInput.value) return;
    const needed = requiredMinutes() - totalMinutes();
    if (needed <= 0) return;
    const startMins = toMins(startInput.value);
    const endMins = startMins + Math.min(needed, 180);
    $('slot-end').value = fromMins(endMins);
    $('slot-end-hint').textContent = 'auto: ' + fmtMinutes(endMins - startMins);
    setTimeout(() => { $('slot-end-hint').textContent = ''; }, 2500);
  }

  /* ── Slots ──────────────────────────────────────────────────── */
  function addSlot() {
    const subject = currentSubject();
    if (!subject) {
      showError('Pick a subject first.');
      return;
    }
    const weekday = parseInt($('slot-weekday').value, 10);
    const startsAt = $('slot-start').value;
    const endsAt = $('slot-end').value;
    if (!startsAt || !endsAt) {
      showError('Start and end times are required.');
      return;
    }
    if (toMins(startsAt) >= toMins(endsAt)) {
      showError('End time must be after the start time.');
      return;
    }
    const overlap = state.slots.some(
      (s) => s.weekday === weekday && toMins(s.starts_at) < toMins(endsAt) && toMins(startsAt) < toMins(s.ends_at),
    );
    if (overlap) {
      showError('That window overlaps another meeting in this list.');
      return;
    }
    const roomInfo = currentRoomFromForm();
    state.slots.push({
      weekday,
      starts_at: startsAt,
      ends_at: endsAt,
      room: roomInfo.room,
      room_id: roomInfo.room_id,
      slot_type: subject.is_lab ? 'LABORATORY' : 'LECTURE',
      room_capacity: roomInfo.room_capacity,
    });
    state.slots.sort((a, b) => a.weekday - b.weekday || toMins(a.starts_at) - toMins(b.starts_at));
    showError('');
    renderSlots();
    updateTally();
    renderWeekGrid();
    queueConflictCheck();
  }

  function removeSlot(index) {
    state.slots.splice(index, 1);
    state.conflicts = [];
    renderSlots();
    updateTally();
    renderWeekGrid();
    queueConflictCheck();
  }

  function clearSlots() {
    if (!state.slots.length) return;
    state.slots = [];
    state.conflicts = [];
    renderSlots();
    updateTally();
    renderWeekGrid();
  }

  function renderSlots() {
    const list = $('slot-list');
    list.innerHTML = '';
    if (!state.slots.length) {
      const p = document.createElement('p');
      p.className = 'field-hint';
      p.textContent = 'No meetings yet. Use a preset above, or pick a day/time/room and click Add.';
      list.appendChild(p);
      return;
    }
    state.slots.forEach((slot, index) => {
      const row = document.createElement('div');
      row.className = 'slot-row';

      const when = document.createElement('span');
      when.className = 'slot-when';
      when.textContent = WEEKDAYS[slot.weekday] + ' · ' + fmtTime(slot.starts_at) + ' – ' + fmtTime(slot.ends_at);
      row.appendChild(when);

      const dur = document.createElement('span');
      dur.className = 'slot-dur';
      dur.textContent = fmtMinutes(toMins(slot.ends_at) - toMins(slot.starts_at));
      row.appendChild(dur);

      if (slot.slot_type === 'LABORATORY') {
        const b = document.createElement('span');
        b.className = 'badge badge--teal badge--xs';
        b.textContent = 'Lab';
        row.appendChild(b);
      }
      if (slot.room && slot.room !== 'TBA') {
        const b = document.createElement('span');
        b.className = 'badge badge--dark badge--xs';
        b.textContent = slot.room;
        row.appendChild(b);
        const cap = parseInt(($('wiz-capacity') && $('wiz-capacity').value) || '0', 10);
        if (slot.room_capacity && cap > slot.room_capacity) {
          const w = document.createElement('span');
          w.className = 'slot-warn slot-warn--room';
          w.title = 'Section capacity exceeds room capacity';
          w.textContent = 'Over room cap';
          row.appendChild(w);
        }
      }

      const conflicts = state.conflicts[index] || { teacher: [], room: [] };
      (conflicts.teacher || []).forEach((text) => {
        const b = document.createElement('span');
        b.className = 'slot-warn slot-warn--teacher';
        b.textContent = 'Teacher clash: ' + text;
        row.appendChild(b);
      });
      (conflicts.room || []).forEach((text) => {
        const b = document.createElement('span');
        b.className = 'slot-warn slot-warn--room';
        b.textContent = 'Room used: ' + text;
        row.appendChild(b);
      });

      const rm = document.createElement('button');
      rm.type = 'button';
      rm.className = 'slot-remove';
      rm.textContent = 'Remove';
      rm.setAttribute('aria-label', 'Remove ' + WEEKDAYS[slot.weekday] + ' meeting');
      rm.addEventListener('click', () => removeSlot(index));
      row.appendChild(rm);

      list.appendChild(row);
    });
  }

  function renderWeekGrid() {
    const grid = $('week-grid');
    grid.innerHTML = '';
    for (let d = 0; d < 6; d++) {
      const col = document.createElement('div');
      const daySlots = state.slots.filter((s) => s.weekday === d);
      col.className = 'week-col' + (daySlots.length ? ' has-slots' : '');
      const head = document.createElement('div');
      head.className = 'week-head';
      head.textContent = WEEKDAYS_SHORT[d];
      col.appendChild(head);
      if (daySlots.length) {
        daySlots.forEach((s) => {
          const pill = document.createElement('div');
          pill.className = 'week-pill';
          pill.textContent = fmtTime(s.starts_at) + ' – ' + fmtTime(s.ends_at);
          col.appendChild(pill);
        });
      } else {
        const empty = document.createElement('div');
        empty.className = 'week-empty';
        empty.textContent = '—';
        col.appendChild(empty);
      }
      grid.appendChild(col);
    }
  }

  /* ── Conflict preview ───────────────────────────────────────── */
  function queueConflictCheck() {
    clearTimeout(state.checkTimer);
    state.checkTimer = setTimeout(checkConflicts, 350);
  }

  async function checkConflicts() {
    const teacher = $('wiz-teacher').value;
    if (!state.slots.length || !teacher) {
      state.conflicts = [];
      renderSlots();
      return true;
    }
    try {
      const body = new URLSearchParams();
      body.set('teacher_profile_id', teacher);
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

  function hasTeacherConflicts() {
    return state.conflicts.some((c) => c.teacher && c.teacher.length);
  }

  /* ── Save ───────────────────────────────────────────────────── */
  async function createSection() {
    const subject = currentSubject();
    const sectionCode = $('wiz-code').value.trim().toUpperCase();

    if (!$('wiz-program').value || !$('wiz-year').value) {
      showError('Pick a program and year level.');
      return;
    }
    if (!sectionCode) {
      showError('Enter a section code (e.g. BSIT-3A).');
      return;
    }
    if (!subject) {
      showError('Pick a subject.');
      return;
    }
    if (!$('wiz-teacher').value) {
      showError('Pick a teacher.');
      return;
    }
    if (!state.slots.length) {
      showError('Add at least one weekly meeting. A preset button fills this in one click.');
      return;
    }
    const total = totalMinutes();
    const required = requiredMinutes();
    if (total !== required) {
      showError(
        subject.code + ' needs ' + fmtMinutes(required) + ' per week. Your meetings total ' +
        fmtMinutes(total) + '. Use a preset or adjust the times.',
      );
      return;
    }
    const free = await checkCodeAvailability();
    if (!free) {
      showError((state.codeStatus && state.codeStatus.message) || 'That section code is already taken.');
      return;
    }
    const cleanConflicts = await checkConflicts();
    if (!cleanConflicts) return;
    if (hasTeacherConflicts()) {
      const first = state.conflicts.find((c) => c.teacher && c.teacher.length);
      showError('Schedule conflict: ' + first.teacher[0] + '. Move this meeting to a free time.');
      return;
    }

    setBusy(true);
    showError('');
    try {
      const body = new URLSearchParams();
      body.set('program_id', $('wiz-program').value);
      body.set('year_level', $('wiz-year').value);
      body.set('semester', $('wiz-semester').value);
      body.set('ay_id', $('wiz-ay').value);
      body.set('class_code', sectionCode);
      body.set('capacity', $('wiz-capacity').value);
      body.set('grace_minutes', $('wiz-grace').value || '10');
      body.set('override_conflicts', '0');
      body.set('offerings', JSON.stringify([{
        subject_id: subject.id,
        teacher_profile_id: $('wiz-teacher').value,
        slots: state.slots.map((s) => ({
          weekday: s.weekday,
          starts_at: s.starts_at,
          ends_at: s.ends_at,
          room: s.room,
          room_id: s.room_id,
          slot_type: s.slot_type,
        })),
      }]));
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

      state.lastSavedSection = data.section_code || sectionCode;
      const first = (data.classes && data.classes[0]) || {};
      const count = (data.classes || []).length;
      showSuccess(
        'Saved ' + (first.class_code || sectionCode) +
        ' (' + subject.code + ') with ' + (first.slots ? first.slots.length : state.slots.length) +
        ' weekly meeting(s). ' +
        (count > 1 ? count + ' offerings were created.' : 'Add the next subject to ' + state.lastSavedSection + ' below.'),
      );
      renderSuccessActions(data);
      if ((data.warnings || []).length) {
        showError('Saved, but: ' + data.warnings[0]);
      }

      // Keep section identity; clear the subject so the next one can be added.
      state.slots = [];
      state.conflicts = [];
      $('wiz-subject').value = '';
      $('wiz-teacher').value = '';
      $('wiz-subject-units').textContent = '';
      renderSlots();
      updateTally();
      renderPresets();
      renderWeekGrid();
      // Refresh existing chips / suggested next letter without wiping the code.
      refreshExistingQuietly();
      $('wiz-subject').focus();
    } catch (err) {
      showError('Network error while saving. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  function renderSuccessActions(data) {
    const box = $('wiz-success-classes');
    if (!box) return;
    box.innerHTML = '';
    const classesUrl = boot.dataset.classesUrl || '/classes/';
    const items = (data && data.classes) || [];
    if (!items.length) {
      box.style.display = 'none';
      return;
    }
    box.style.display = 'flex';
    items.forEach((item) => {
      if (!item.class_id) return;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:8px 12px;background:rgba(255,255,255,0.06);border-radius:8px;';
      const label = document.createElement('span');
      label.textContent = (item.class_code || '') + (item.subject ? ' · ' + item.subject : '');
      row.appendChild(label);
      const actions = document.createElement('div');
      actions.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;';
      const slotsLink = document.createElement('a');
      slotsLink.className = 'btn btn-outline btn-xs';
      slotsLink.href = classesUrl + '?setup_class=' + item.class_id + '&setup_action=schedule';
      slotsLink.innerHTML = '<i class="fas fa-clock"></i> Schedule';
      actions.appendChild(slotsLink);
      const rosterLink = document.createElement('a');
      rosterLink.className = 'btn btn-outline btn-xs';
      rosterLink.href = classesUrl + '?setup_class=' + item.class_id + '&setup_action=roster';
      rosterLink.innerHTML = '<i class="fas fa-users"></i> Enlist';
      actions.appendChild(rosterLink);
      row.appendChild(actions);
      box.appendChild(row);
    });
  }

  async function refreshExistingQuietly() {
    if (!$('wiz-program').value || !$('wiz-year').value) return;
    try {
      const params = new URLSearchParams({
        program_id: $('wiz-program').value,
        year_level: $('wiz-year').value,
        semester: $('wiz-semester').value,
        ay_id: $('wiz-ay').value,
      });
      const res = await fetch(boot.dataset.optionsUrl + '?' + params.toString());
      const data = await res.json();
      if (res.ok && data.success) {
        state.options = data;
        state.step1Key = step1Key();
        const prevSubject = $('wiz-subject').value;
        const prevTeacher = $('wiz-teacher').value;
        populateSubjects();
        populateTeachers();
        populateExisting(data);
        if (prevSubject) $('wiz-subject').value = prevSubject;
        if (prevTeacher) $('wiz-teacher').value = prevTeacher;
      }
    } catch (err) {
      /* silent: chips are a convenience */
    }
  }

  /* ── Wire-up ────────────────────────────────────────────────── */
  function on(id, event, handler) {
    const el = $(id);
    if (el) el.addEventListener(event, handler);
    return el;
  }

  function init() {
    fillDepartments();
    fillPrograms();
    fillRooms();

    on('wiz-department', 'change', () => {
      fillPrograms();
      resetOptions();
    });
    on('wiz-program', 'change', onProgramChange);
    on('wiz-year', 'change', () => {
      state.step1Key = '';
      loadOptions();
    });
    on('wiz-semester', 'change', () => {
      state.step1Key = '';
      loadOptions();
    });
    on('wiz-ay', 'change', () => {
      state.step1Key = '';
      loadOptions();
    });

    on('wiz-subject', 'change', () => {
      const subject = currentSubject();
      if (subject) {
        $('wiz-subject-units').textContent =
          'Requires ' + fmtMinutes(subject.units * 60) + ' per week (' +
          subject.units + ' credit unit' + (subject.units !== 1 ? 's' : '') + ').';
        // Nudge the room list toward the right kind of room.
        const sel = $('slot-room-select');
        if (sel && (!sel.value || sel.value === 'TBA')) {
          const wanted = subject.is_lab ? 'LABORATORY' : 'LECTURE';
          const match = rooms.find((r) => (r.room_type === wanted) || (subject.is_lab && r.is_lab));
          if (match) {
            sel.value = match.code;
            onRoomChange();
          }
        }
      } else {
        const units = $('wiz-subject-units');
        if (units) units.textContent = '';
      }
      state.slots = [];
      state.conflicts = [];
      renderSlots();
      updateTally();
      renderPresets();
      renderWeekGrid();
      checkCodeAvailability();
    });

    on('wiz-teacher', 'change', queueConflictCheck);

    const codeInput = $('wiz-code');
    if (codeInput) {
      codeInput.addEventListener('blur', checkCodeAvailability);
      codeInput.addEventListener('input', () => {
        codeInput.value = codeInput.value.toUpperCase();
        state.codeStatus = { available: true, message: '' };
        renderCodeStatus();
      });
    }

    on('slot-add', 'click', addSlot);
    on('slot-room-select', 'change', onRoomChange);
    on('slot-start', 'change', autoSuggestEndTime);
    on('wiz-create', 'click', createSection);
    on('wiz-add-another', 'click', () => {
      showSuccess('');
      const subject = $('wiz-subject');
      if (subject) subject.focus();
    });

    // Pre-fill from Classes → Add Section links.
    const params = new URLSearchParams(window.location.search);
    const presetProgram = params.get('program_id');
    const presetYear = params.get('year_level');
    const presetSection = (params.get('section') || '').trim().toUpperCase();
    if (presetProgram) $('wiz-program').value = presetProgram;
    onProgramChange();
    if (presetSection) {
      state.pinnedSection = presetSection;
      $('wiz-code').value = presetSection;
    }
    if (presetYear) {
      $('wiz-year').value = presetYear;
      loadOptions();
    }

    renderSlots();
    updateTally();
    renderWeekGrid();

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      if (e.target.tagName === 'TEXTAREA') return;
      if (e.target.closest('.slot-form')) {
        e.preventDefault();
        e.stopPropagation();
        const addBtn = $('slot-add');
        if (addBtn) addBtn.click();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
