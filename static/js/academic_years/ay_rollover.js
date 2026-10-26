/* KCC ClassStamp — Academic Years: Term Rollover Wizard (A-08) */
(function (window) {
  'use strict';

  var App = window.AcademicYearsApp;
  var TOTAL_STEPS = 4;
  var step = 1;

  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || '';
  }

  function resetWizard() {
    step = 1;
    var modal = getEl('ayRolloverModal');
    var nameInput = getEl('rolloverName');
    if (nameInput) nameInput.value = '';
    var starts = getEl('rolloverStartsOn');
    var ends = getEl('rolloverEndsOn');
    if (modal && starts) {
      var activeEnds = modal.getAttribute('data-active-ends-on');
      if (activeEnds) {
        var next = new Date(activeEnds + 'T00:00:00');
        next.setDate(next.getDate() + 1);
        starts.value = next.toISOString().slice(0, 10);
        var end = new Date(next);
        end.setDate(end.getDate() + 150);
        ends.value = end.toISOString().slice(0, 10);
      } else {
        starts.value = '';
        ends.value = '';
      }
    }
    if (ends) ends.value = ends.value || '';

    var promote = getEl('rolloverPromote');
    if (promote) promote.checked = false;
    getEl('rolloverStep1Error').style.display = 'none';
    getEl('rolloverExecuteError').style.display = 'none';
    getEl('rolloverSuccess').style.display = 'none';
    getEl('rolloverExecuteBtn').disabled = false;

    if (modal) {
      var activeName = modal.getAttribute('data-active-name');
      getEl('rolloverActiveName').textContent = activeName || '(no active term)';
    }

    render();
  }

  function render() {
    var panels = document.querySelectorAll('#ayRolloverModal .rollover-panel');
    panels.forEach(function (panel) {
      panel.hidden = panel.getAttribute('data-panel') !== String(step);
    });

    var indicators = document.querySelectorAll('#rolloverSteps .rollover-step');
    indicators.forEach(function (ind) {
      var n = parseInt(ind.getAttribute('data-step'), 10);
      ind.classList.toggle('is-active', n === step);
      ind.classList.toggle('is-done', n < step);
    });

    getEl('rolloverBackBtn').style.display = step > 1 ? '' : 'none';
    getEl('rolloverNextBtn').style.display = step < TOTAL_STEPS ? '' : 'none';
    getEl('rolloverExecuteBtn').style.display = step === TOTAL_STEPS ? '' : 'none';
    getEl('rolloverDoneBtn').style.display = 'none';
  }

  function validateStep1() {
    var name = getEl('rolloverName').value.trim();
    var starts = getEl('rolloverStartsOn').value;
    var ends = getEl('rolloverEndsOn').value;
    var err = getEl('rolloverStep1Error');

    if (!name) {
      err.textContent = 'Term name is required.';
      err.style.display = 'block';
      return false;
    }
    if (!starts || !ends) {
      err.textContent = 'Both opening and closing dates are required.';
      err.style.display = 'block';
      return false;
    }
    if (ends <= starts) {
      err.textContent = 'Closing date must be after opening date.';
      err.style.display = 'block';
      return false;
    }
    err.style.display = 'none';
    return true;
  }

  function fillSummary() {
    var name = getEl('rolloverName').value.trim();
    var starts = getEl('rolloverStartsOn').value;
    var ends = getEl('rolloverEndsOn').value;
    var modal = getEl('ayRolloverModal');
    var promote = getEl('rolloverPromote').checked;

    getEl('rolloverSummaryName').textContent = name;
    getEl('rolloverSummaryDates').textContent = starts + ' to ' + ends;
    getEl('rolloverSummaryDeactivate').textContent =
      (modal.getAttribute('data-active-name') || '(no active term)');
    getEl('rolloverSummaryPromote').textContent = promote ? 'Yes — approved students advance one year level' : 'No';
  }

  function next() {
    if (step === 1 && !validateStep1()) return;
    if (step === 3) fillSummary();
    if (step < TOTAL_STEPS) {
      step += 1;
      render();
    }
  }

  function back() {
    if (step > 1) {
      step -= 1;
      render();
    }
  }

  function execute() {
    var errBox = getEl('rolloverExecuteError');
    var successBox = getEl('rolloverSuccess');
    errBox.style.display = 'none';
    successBox.style.display = 'none';

    var executeBtn = getEl('rolloverExecuteBtn');
    executeBtn.disabled = true;

    var modal = getEl('ayRolloverModal');
    var url = modal.getAttribute('data-rollover-url') || '/academic-years/rollover/';
    var body = new URLSearchParams();
    body.set('name', getEl('rolloverName').value.trim());
    body.set('starts_on', getEl('rolloverStartsOn').value);
    body.set('ends_on', getEl('rolloverEndsOn').value);
    body.set('promote', getEl('rolloverPromote').checked ? '1' : '0');

    fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCSRF()
      },
      body: body
    })
    .then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    })
    .then(function (result) {
      executeBtn.disabled = false;
      if (!result.data.ok) {
        errBox.textContent = result.data.error || 'Rollover failed.';
        errBox.style.display = 'block';
        return;
      }
      var msg = result.data.message || 'Rollover complete.';
      if (result.data.promoted_count) {
        msg += ' ' + result.data.promoted_count + ' student(s) promoted.';
      }
      getEl('rolloverSuccessMsg').textContent = msg;
      successBox.style.display = 'flex';
      getEl('rolloverNextBtn').style.display = 'none';
      getEl('rolloverBackBtn').style.display = 'none';
      getEl('rolloverExecuteBtn').style.display = 'none';
      getEl('rolloverDoneBtn').style.display = '';
      if (typeof window.toast === 'function') window.toast('success', msg);
    })
    .catch(function () {
      executeBtn.disabled = false;
      errBox.textContent = 'Network error — unable to reach the server.';
      errBox.style.display = 'block';
    });
  }

  function init() {
    var modal = getEl('ayRolloverModal');
    if (!modal) return;

    var openBtn = getEl('rolloverWizardBtn');
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        resetWizard();
        if (App && App.showModal) App.showModal('ayRolloverModal');
        else if (typeof window.openModal === 'function') window.openModal('ayRolloverModal');
        else modal.classList.add('is-active');
      });
    }

    getEl('rolloverNextBtn').addEventListener('click', next);
    getEl('rolloverBackBtn').addEventListener('click', back);
    getEl('rolloverExecuteBtn').addEventListener('click', execute);

    // "Done" closes and refreshes the registry
    getEl('rolloverDoneBtn').addEventListener('click', function () {
      window.location.reload();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
