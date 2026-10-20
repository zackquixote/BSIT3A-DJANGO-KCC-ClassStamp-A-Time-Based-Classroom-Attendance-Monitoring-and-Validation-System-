/* KCC ClassStamp — Auth: Login Controller */
(function (window) {
  'use strict';

  function initLogin() {
    // Show/Hide password toggle
    var toggleBtn = document.getElementById('togglePassword');
    var passwordInput = document.getElementById('id_password');
    if (toggleBtn && passwordInput) {
      toggleBtn.addEventListener('click', function () {
        var isPassword = passwordInput.type === 'password';
        passwordInput.type = isPassword ? 'text' : 'password';
        toggleBtn.textContent = isPassword ? 'Hide' : 'Show';
      });
    }

    // Account lockout countdown timer
    var messageBox = document.getElementById('status-message');
    var lockDataEl = document.getElementById('lockoutData');
    if (lockDataEl) {
      var remaining = parseInt(lockDataEl.getAttribute('data-remaining') || '0', 10);
      var loginUrl = lockDataEl.getAttribute('data-login-url') || '/login/';
      var interval = setInterval(function () {
        remaining--;
        if (remaining > 0) {
          if (messageBox && messageBox.querySelector('span')) {
            messageBox.querySelector('span').textContent =
              'Too many failed attempts. Try again in ' + remaining + ' seconds.';
          }
        } else {
          clearInterval(interval);
          window.location.href = loginUrl;
        }
      }, 1000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLogin);
  } else {
    initLogin();
  }
})(window);
