/* =============================================================
   KCC ClassStamp — Table Action Dropdowns
   Menus are lifted into a body-level layer while open so table
   and card overflow rules can never clip them, and they flip
   above the trigger when there is no room below.
   ============================================================= */
(function () {
  'use strict';
  if (window.__actionDropdownsReady) return;
  window.__actionDropdownsReady = true;

  var layer = null;
  var openState = null;

  function getLayer() {
    if (!layer) {
      layer = document.createElement('div');
      layer.id = 'action-dropdown-layer';
      document.body.appendChild(layer);
    }
    return layer;
  }

  function close() {
    if (!openState) return;
    var state = openState;
    openState = null;
    state.menu.classList.remove('action-dropdown-menu--portal');
    state.menu.removeAttribute('style');
    state.dropdown.classList.remove('open');
    state.dropdown.appendChild(state.menu);
  }

  function place(anchor, menu) {
    var rect = anchor.getBoundingClientRect();
    var width = menu.offsetWidth;
    var height = menu.offsetHeight;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var margin = 8;

    var left = rect.right - width;
    if (left + width > vw - margin) left = vw - width - margin;
    if (left < margin) left = margin;

    var top = rect.bottom + 6;
    if (top + height > vh - margin) {
      var above = rect.top - height - 6;
      top = above >= margin ? above : Math.max(margin, vh - height - margin);
    }

    menu.style.position = 'fixed';
    menu.style.left = Math.round(left) + 'px';
    menu.style.top = Math.round(top) + 'px';
    menu.style.right = 'auto';
    menu.style.bottom = 'auto';
  }

  function open(dropdown, anchor) {
    var menu = dropdown.querySelector('.action-dropdown-menu');
    if (!menu) return;
    openState = { dropdown: dropdown, menu: menu, anchor: anchor };
    dropdown.classList.add('open');
    menu.classList.add('action-dropdown-menu--portal');
    getLayer().appendChild(menu);
    place(anchor, menu);
  }

  function isOpenFor(dropdown) {
    return !!(openState && openState.dropdown === dropdown);
  }

  document.addEventListener('click', function (event) {
    var target = event.target;
    if (!target || typeof target.closest !== 'function') return;

    var toggle = target.closest('.action-dropdown-toggle');
    if (toggle) {
      event.preventDefault();
      event.stopPropagation();
      var dropdown = toggle.closest('.action-dropdown');
      if (!dropdown) return;
      if (isOpenFor(dropdown)) {
        close();
      } else {
        close();
        open(dropdown, toggle);
      }
      return;
    }

    if (!openState) return;
    if (target.closest('.action-dropdown-menu--portal')) {
      if (target.closest('.action-dropdown-item')) close();
      return;
    }
    close();
  }, true);

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') close();
  });

  window.addEventListener('resize', close);

  /* Re-anchor instead of closing: clicking a trigger can make the browser
     scroll its table wrapper by a few pixels to reveal it, which would
     otherwise dismiss the menu the instant it opened. */
  window.addEventListener('scroll', function (event) {
    if (!openState) return;
    var target = event.target;
    if (target && target.nodeType === 1 && target.closest && target.closest('.action-dropdown-menu--portal')) return;
    var rect = openState.anchor.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) {
      close();
      return;
    }
    place(openState.anchor, openState.menu);
  }, true);
})();
