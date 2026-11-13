/* KCC ClassStamp — Dark select (registration form)
   -----------------------------------------------------------------------------
   Android renders <select> options in a system sheet that ignores our stylesheet:
   on a dark auth page it flashes a full-white panel with pale grey text, which
   is exactly the "sakit sa mata" students report. Chrome's dark form-control
   support depends on the browser and is ignored inside in-app browsers
   (Messenger, Facebook), so the picker is drawn here instead.

   The native <select> stays in the DOM: it keeps the value the form posts, the
   department → program cascade keeps working through its `change` event, and
   server-side/HTML5 required validation still sees a real control. It is made
   invisible and non-interactive; this module renders the visible button and the
   dark listbox, then writes the choice back into the select. */

(function (window, document) {
  'use strict';

  var OPEN_CLASS = 'is-open';
  var registry = [];

  // The department → program cascade rewrites options AND flips the program
  // select from disabled to enabled without firing a change on it, so every
  // picker re-reads its native select once the cascade has finished.
  function refreshAll() {
    window.setTimeout(function () {
      registry.forEach(function (entry) { entry.render(); });
    }, 0);
  }

  function optionLabel(select) {
    var chosen = select.options[select.selectedIndex];
    if (!chosen || !chosen.value) {
      var placeholder = select.options[0];
      return { text: placeholder ? placeholder.text : '', empty: true };
    }
    return { text: chosen.text, empty: false };
  }

  function setup(select) {
    if (select.dataset.kccSelect === '1') return;
    select.dataset.kccSelect = '1';

    var wrap = select.closest('.input-wrap') || select.parentNode;
    wrap.classList.add('has-kcc-select');

    // keep the real control for the form, but out of the way of the pointer
    select.classList.add('kcc-select-native');
    select.setAttribute('tabindex', '-1');
    select.setAttribute('aria-hidden', 'true');

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'kcc-select-display';
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.innerHTML =
      '<span class="kcc-select-value"></span>' +
      '<i class="fas fa-chevron-down kcc-select-chevron" aria-hidden="true"></i>';

    var panel = document.createElement('div');
    panel.className = 'kcc-select-panel';
    panel.setAttribute('role', 'listbox');
    panel.hidden = true;

    wrap.appendChild(button);
    wrap.appendChild(panel);

    var valueEl = button.querySelector('.kcc-select-value');

    function render() {
      var state = optionLabel(select);
      valueEl.textContent = state.text;
      button.classList.toggle('is-placeholder', state.empty);
      button.disabled = select.disabled;
      button.classList.toggle('is-disabled', select.disabled);
    }

    function buildPanel() {
      panel.innerHTML = '';
      Array.prototype.forEach.call(select.options, function (opt) {
        if (opt.disabled && !opt.value) {
          // the "choose…" prompt is shown by the button itself
          return;
        }
        var item = document.createElement('button');
        item.type = 'button';
        item.className = 'kcc-select-option';
        item.dataset.value = opt.value;
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
        if (opt.disabled) {
          item.classList.add('is-disabled');
          item.disabled = true;
        }
        if (opt.selected && opt.value) item.classList.add('is-selected');
        item.innerHTML =
          '<span class="kcc-select-option-label"></span>' +
          '<i class="fas fa-check kcc-select-tick" aria-hidden="true"></i>';
        item.querySelector('.kcc-select-option-label').textContent = opt.text;
        item.addEventListener('click', function (event) {
          event.preventDefault();
          if (opt.disabled) return;
          select.value = opt.value;
          select.dispatchEvent(new window.Event('input', { bubbles: true }));
          select.dispatchEvent(new window.Event('change', { bubbles: true }));
          render();
          close();
          button.focus();
        });
        panel.appendChild(item);
      });
    }

    function open() {
      if (select.disabled) return;
      buildPanel();
      panel.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      wrap.classList.add(OPEN_CLASS);
      var selected = panel.querySelector('.kcc-select-option.is-selected');
      if (selected && selected.scrollIntoView) {
        selected.scrollIntoView({ block: 'nearest' });
      }
    }

    function close() {
      panel.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      wrap.classList.remove(OPEN_CLASS);
    }

    function toggle() {
      if (panel.hidden) open(); else close();
    }

    button.addEventListener('click', function (event) {
      event.preventDefault();
      toggle();
    });

    button.addEventListener('keydown', function (event) {
      var items = panel.hidden ? [] : Array.prototype.slice.call(panel.querySelectorAll('.kcc-select-option:not(.is-disabled)'));
      var index = items.indexOf(document.activeElement);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (panel.hidden) { open(); return; }
        if (!items.length) return;
        var next = event.key === 'ArrowDown'
          ? (index + 1) % items.length
          : (index <= 0 ? items.length - 1 : index - 1);
        items[next].focus();
      } else if (event.key === 'Enter' || event.key === ' ') {
        if (panel.hidden) { event.preventDefault(); open(); }
      } else if (event.key === 'Escape') {
        if (!panel.hidden) { event.preventDefault(); close(); }
      }
    });

    document.addEventListener('click', function (event) {
      if (!wrap.contains(event.target)) close();
    });

    select.addEventListener('change', function () {
      render();
      refreshAll();
    });

    registry.push({ render: render });
    render();
  }

  function init() {
    var form = document.getElementById('registerForm');
    if (!form) return;
    Array.prototype.forEach.call(form.querySelectorAll('select.kcc-input'), setup);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window, document);
