/* KCC ClassStamp — A-19 Section Builder Wizard (5 steps) */
(function () {
  'use strict';

  const boot = document.getElementById('wizard-boot');
  if (!boot) return;

  const $ = (id) => document.getElementById(id);
  const programs = JSON.parse($('wizard-programs').textContent || '[]');
  const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrf = csrfMeta ? csrfMeta.content : '';

  const state = { step: 1, options: null, slots: [], conflicts: [] };

  function showError(msg) {
    const el = $('wiz-error');
    if (!el) return;
    el.textContent = msg || '';
    el.style.display = msg ? 'block' : 'none';
  }

  function toMins(hhmm) {
    const parts = String(hhmm).split(':').map(Number);
    return parts[0] * 60 + parts[1];
  }

  function fmtMinutes(mins) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? h + 'h ' + m + 'm' : h + 'h';
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

  function setStep(n) {
    state.step = n;
    for (let i = 1; i <= 5; i++) {
      $('wizard-step-' + i).style.display = i === n ? '' : 'none';
    }
    document.querySelectorAll('[data-step-indicator]').forEach((el) => {
      const s = parseInt(el.dataset.stepIndicator, 10);
      el.classList.toggle('badge--blue', s === n);
      el.classList.toggle('badge--success', s < n);
    });
    $('wiz-back').style.visibility = n === 1 ? 'hidden' : 'visible';
    $('wiz-next').style.display = n < 5 ? '' : 'none';
    $('wiz-create').style.display = n === 5 ? '' : 'none';
    showError('');
    if (n === 4) {
      renderSlots();
      updateTally();
      checkConflicts();
    }
    if (n === 5) buildReview();
  }

  // ── Step 1: program/year cascade + options fetch ──────────────
  function onProgramChange() {
    const yearSel = $('wiz-year');
    const program = programs.find((p) => String(p.id) === $('wiz-program').value);
    yearSel.innerHTML = '';
    if (!program) {
      yearSel.disabled = true;
      yearSel.appendChild(new Option('— select program first —', ''));
      return;
    }
    yearSel.disabled = false;
    for (let y = 1; y <= program.years_total; y++) {
      yearSel.appendChild(new Option('Year ' + y, String(y)));
    }
  }

  async function loadOptions() {
    if (!$('wiz-program').value || !$('wiz-year').value) {
      showError('Select a program and year level first.');
      return;
    }
    showError('');
    $('wiz-next').disabled = true;
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
      state.slots = [];
      state.conflicts = [];
      populateSubjects();
      populateTeachers();
      $('wiz-code').value = data.suggested_code || '';
      setStep(2);
    } catch (err) {
      showError('Network error while loading options.');
    } finally {
      $('wiz-next').disabled = false;
    }
  }

  function populateSubjects() {
    const sel = $('wiz-subject');
    sel.innerHTML = '';
    const subjects = state.options.subjects;
    if (!subjects.length) {
      sel.appendChild(new Option('No curriculum subjects for this selection', ''));
      updateUnitsHint();
      return;
    }
    sel.appendChild(new Option('— select subject —', ''));
    subjects.forEach((s) => {
      sel.appendChild(new Option(s.code + ' — ' + s.name + ' (' + s.units + 'u = ' + s.units + 'h/week)', String(s.id)));
    });
    updateUnitsHint();
  }

  function populateTeachers() {
    const sel = $('wiz-teacher');
    sel.innerHTML = '';
    const teachers = state.options.teachers;
    if (!teachers.length) {
      sel.appendChild(new Option('No active teachers in this department', ''));
      return;
    }
    sel.appendChild(new Option('— select teacher —', ''));
    teachers.forEach((t) => {
      const load = t.active_classes + ' class(es), ' + t.active_slots + ' slot(s)/week';
      sel.appendChild(new Option(t.name + ' — ' + load, String(t.profile_id)));
    });
  }

  function updateUnitsHint() {
    const subject = currentSubject();
    $('wiz-subject-units').textContent = subject
      ? 'Requires exactly ' + fmtMinutes(requiredMinutes()) + ' of schedule per week (' + subject.units + ' unit(s)).'
      : '';
  }

  // ── Step 4: slot builder, hours tally, conflict scan ──────────
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
    state.slots.push({ weekday: weekday, starts_at: startsAt, ends_at: endsAt, room: room });
    state.slots.sort((a, b) => a.weekday - b.weekday || toMins(a.starts_at) - toMins(b.starts_at));
    showError('');
    $('slot-room').value = '';
    renderSlots();
    updateTally();
    checkConflicts();
  }

  function removeSlot(index) {
    state.slots.splice(index, 1);
    renderSlots();
    updateTally();
    checkConflicts();
  }

  function updateTally() {
    const total = totalMinutes();
    const required = requiredMinutes();
    const el = $('hours-tally');
    el.textContent = 'Scheduled: ' + fmtMinutes(total) + ' / Required: ' + fmtMinutes(required);
    el.classList.toggle('badge--success', total === required);
    el.classList.toggle('badge--gold', total !== required);
  }

  function renderSlots() {
    const list = $('slot-list');
    list.innerHTML = '';
    if (!state.slots.length) {
      const empty = document.createElement('p');
      empty.className = 'text-muted text-sm';
      empty.textContent = 'No slots yet — add the weekly meetings above.';
      list.appendChild(empty);
      return;
    }
    state.slots.forEach((slot, index) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid var(--glass-border);';

      const label = document.createElement('span');
      label.className = 'font-semibold text-primary';
      label.textContent = WEEKDAYS[slot.weekday] + ' ' + slot.starts_at + '–' + slot.ends_at + ' · ' + (slot.room || 'TBA');
      row.appendChild(label);

      const conflicts = state.conflicts[index] || { teacher: [], room: [] };
      (conflicts.teacher || []).forEach((text) => {
        const badge = document.createElement('span');
        badge.className = 'badge badge--danger';
        badge.textContent = 'Teacher clash: ' + text;
        row.appendChild(badge);
      });
      (conflicts.room || []).forEach((text) => {
        const badge = document.createElement('span');
        badge.className = 'badge badge--gold';
        badge.textContent = 'Room also used: ' + text;
        row.appendChild(badge);
      });

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-outline';
      removeBtn.style.cssText = 'margin-left:auto;padding:4px 10px;';
      removeBtn.textContent = 'Remove';
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

  // ── Step 5: review + create ───────────────────────────────────
  function buildReview() {
    const summary = $('review-summary');
    summary.innerHTML = '';
    const subject = currentSubject();
    const teacher = (state.options.teachers || []).find((t) => String(t.profile_id) === $('wiz-teacher').value);
    const rows = [
      ['Academic Year', $('wiz-ay').selectedOptions[0].textContent],
      ['Program', $('wiz-program').selectedOptions[0].textContent],
      ['Year Level', 'Year ' + $('wiz-year').value],
      ['Semester', $('wiz-semester').selectedOptions[0].textContent],
      ['Subject', subject ? subject.code + ' — ' + subject.name : ''],
      ['Required Hours', fmtMinutes(requiredMinutes()) + ' per week'],
      ['Teacher', teacher ? teacher.name : ''],
      ['Section Code', $('wiz-code').value.trim().toUpperCase()],
      ['Capacity', $('wiz-capacity').value || 'Unlimited'],
      ['Grace Minutes', $('wiz-grace').value || '10'],
      ['Schedule', state.slots.map((s) => WEEKDAYS[s.weekday] + ' ' + s.starts_at + '–' + s.ends_at + ' (' + (s.room || 'TBA') + ')').join('  |  ')],
    ];
    const dl = document.createElement('dl');
    dl.style.cssText = 'display:grid;grid-template-columns:180px 1fr;gap:8px 14px;margin:0;';
    rows.forEach(([term, value]) => {
      const dt = document.createElement('dt');
      dt.className = 'text-muted text-sm';
      dt.textContent = term;
      const dd = document.createElement('dd');
      dd.className = 'font-semibold text-primary';
      dd.style.margin = '0';
      dd.textContent = value;
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    summary.appendChild(dl);

    const warnings = $('review-warnings');
    warnings.innerHTML = '';
    state.conflicts.forEach((c) => {
      (c.room || []).forEach((text) => {
        const div = document.createElement('div');
        div.className = 'badge badge--gold';
        div.style.cssText = 'display:block;margin:8px 0 0;padding:8px 12px;';
        div.textContent = 'Room warning (allowed): ' + text;
        warnings.appendChild(div);
      });
    });
  }

  async function createSection() {
    const btn = $('wiz-create');
    btn.disabled = true;
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
      $('wizard-card').style.display = 'none';
      $('wizard-progress').style.display = 'none';
      $('wizard-success').style.display = '';
      $('success-code').textContent =
        'Section ' + data.class_code + ' created with ' + data.slots.length + ' schedule slot(s).';
      const warnBox = $('success-warnings');
      warnBox.innerHTML = '';
      (data.warnings || []).forEach((text) => {
        const div = document.createElement('div');
        div.className = 'badge badge--gold';
        div.style.cssText = 'display:block;margin:4px 0;padding:8px 12px;';
        div.textContent = 'Room warning: ' + text;
        warnBox.appendChild(div);
      });
    } catch (err) {
      showError('Network error while creating the section.');
    } finally {
      btn.disabled = false;
    }
  }

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
      if (totalMinutes() !== requiredMinutes()) {
        showError(
          'This subject needs exactly ' + fmtMinutes(requiredMinutes()) +
          ' per week; your slots total ' + fmtMinutes(totalMinutes()) + '.'
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

  function init() {
    $('wiz-program').addEventListener('change', onProgramChange);
    $('wiz-subject').addEventListener('change', updateUnitsHint);
    $('wiz-next').addEventListener('click', onNext);
    $('wiz-back').addEventListener('click', () => {
      if (state.step > 1) setStep(state.step - 1);
    });
    $('slot-add').addEventListener('click', addSlot);
    $('wiz-create').addEventListener('click', createSection);
    setStep(1);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
