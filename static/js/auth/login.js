/* KCC ClassStamp — Auth: Login Controller */
(function (window, document) {
  'use strict';

  // // [Single Timer] initLogin can run again (a restored page, a partial
  // // re-render); a second setInterval would tick the same countdown twice and
  // // keep running after the first one finished.
  var countdownTimer = null;

  var SHOW_LABEL = 'Show';
  var HIDE_LABEL = 'Hide';

  // // [Password Toggle] A two-state control: the visible label flips, and
  // // aria-pressed reports which state it flipped to. Without it a screen
  // // reader announces "Show" for a field that is already revealed.
  function initPasswordToggle() {
    var toggleBtn = document.getElementById('togglePassword');
    var passwordInput = document.getElementById('id_password');
    if (!toggleBtn || !passwordInput) return;

    function paint(revealed) {
      toggleBtn.setAttribute('aria-pressed', revealed ? 'true' : 'false');
      toggleBtn.setAttribute('aria-label', revealed ? 'Hide password' : 'Show password');
      toggleBtn.textContent = revealed ? HIDE_LABEL : SHOW_LABEL;
    }

    toggleBtn.addEventListener('click', function () {
      var revealed = passwordInput.type === 'password';
      passwordInput.type = revealed ? 'text' : 'password';
      paint(revealed);
    });

    paint(passwordInput.type === 'text');
  }

  // // [Lockout Countdown] Presentation only: the lock itself is enforced in the
  // // cache by the server, so nothing here decides whether a retry is accepted.
  function initLockoutCountdown() {
    var lockData = document.getElementById('lockoutData');
    if (!lockData) return;

    var remaining = parseInt(lockData.getAttribute('data-remaining') || '0', 10);
    if (!isFinite(remaining) || remaining <= 0) return;

    var textNode = document.querySelector('[data-lockout-text]');
    var template = lockData.getAttribute('data-message-template') ||
      'Too many failed attempts. Try again in {seconds} seconds.';
    var readyText = lockData.getAttribute('data-ready-message') ||
      'You can try signing in again.';
    var form = document.getElementById('loginForm');

    function paint(seconds) {
      if (textNode) {
        textNode.textContent = template.replace('{seconds}', String(seconds));
      }
    }

    function release() {
      // // [Unlock In Place] Re-enabling the form beats window.location.href: the
      // // old redirect discarded the page — and whatever identifier the user had
      // // typed — and hid the message that explained the wait.
      if (form) {
        var fields = form.querySelectorAll('[disabled]');
        for (var i = 0; i < fields.length; i += 1) {
          fields[i].disabled = false;
        }
      }
      if (textNode) {
        // // The ticking span opted out of the live region so it would not be read
        // // aloud every second; hand the announcement back for the final line.
        textNode.removeAttribute('aria-live');
        textNode.textContent = readyText;
      }
      var box = document.getElementById('lockout-message');
      if (box) {
        box.classList.remove('auth-alert--warning');
        box.classList.add('auth-alert--success');
        var icon = box.querySelector('i');
        if (icon) icon.className = 'fas fa-circle-check';
      }
    }

    if (countdownTimer) window.clearInterval(countdownTimer);
    paint(remaining);
    countdownTimer = window.setInterval(function () {
      remaining -= 1;
      if (remaining > 0) {
        paint(remaining);
        return;
      }
      window.clearInterval(countdownTimer);
      countdownTimer = null;
      release();
    }, 1000);
  }

  function initLogin() {
    initPasswordToggle();
    initLockoutCountdown();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLogin);
  } else {
    initLogin();
  }
})(window, document);
