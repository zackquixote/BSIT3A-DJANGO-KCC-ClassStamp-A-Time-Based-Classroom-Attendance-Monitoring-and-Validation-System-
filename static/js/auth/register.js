/* KCC ClassStamp — Auth: Registration Controller */
(function (window) {
  'use strict';

  function initRegister() {
    var registerForm = document.getElementById('registerForm');
    var checkUrl = (registerForm && registerForm.getAttribute('data-check-url')) || '/auth/check-availability/';

    // 1. Cascading Department -> Program Dropdown
    var deptSelect = document.getElementById('id_department');
    var progSelect = document.getElementById('id_program');
    var defaultOption = document.getElementById('programDefaultOption');
    var allProgOptions = progSelect ? Array.from(progSelect.querySelectorAll('option:not(#programDefaultOption)')) : [];

    function updatePrograms() {
      if (!deptSelect || !progSelect || !defaultOption) return;
      var deptId = deptSelect.value;
      if (!deptId) {
        progSelect.disabled = true;
        defaultOption.textContent = 'First select your College Department above';
        defaultOption.selected = true;
        allProgOptions.forEach(function (opt) { opt.remove(); });
        return;
      }

      progSelect.disabled = false;
      defaultOption.textContent = 'Select your academic program';

      var currentSelected = progSelect.value;
      progSelect.innerHTML = '';
      progSelect.appendChild(defaultOption);

      var hasSelected = false;
      allProgOptions.forEach(function (opt) {
        if (opt.getAttribute('data-department') === deptId) {
          progSelect.appendChild(opt);
          if (opt.value === currentSelected || opt.hasAttribute('selected')) {
            opt.selected = true;
            hasSelected = true;
          }
        }
      });

      if (!hasSelected) {
        defaultOption.selected = true;
      }
    }

    if (deptSelect && progSelect) {
      deptSelect.addEventListener('change', function () {
        allProgOptions.forEach(function (opt) { opt.removeAttribute('selected'); });
        progSelect.value = '';
        updatePrograms();
      });

      if (deptSelect.value) {
        updatePrograms();
      }
    }

    // 2. Password toggles
    function setupToggle(toggleId, inputId) {
      var toggle = document.getElementById(toggleId);
      var input = document.getElementById(inputId);
      if (toggle && input) {
        toggle.addEventListener('click', function () {
          var isPassword = input.type === 'password';
          input.type = isPassword ? 'text' : 'password';
          toggle.textContent = isPassword ? 'Hide' : 'Show';
        });
      }
    }

    setupToggle('togglePassword', 'id_password');
    setupToggle('toggleConfirm', 'id_confirm_password');

    // 3. Real-Time Availability Checking (Debounced)
    var checkTimers = {};
    function scheduleAvailabilityCheck(type, value, statusEl) {
      if (!statusEl) return;
      clearTimeout(checkTimers[type]);

      if (!value || value.length < 3) {
        statusEl.style.display = 'none';
        return;
      }

      checkTimers[type] = setTimeout(function () {
        var url = checkUrl + '?type=' + encodeURIComponent(type) + '&value=' + encodeURIComponent(value);
        fetch(url)
          .then(function (res) { return res.json(); })
          .then(function (data) {
            statusEl.style.display = 'block';
            if (data.available) {
              statusEl.innerHTML = '<span style="color: #22c55e;"><i class="fas fa-circle-check"></i> ' + data.message + '</span>';
            } else {
              statusEl.innerHTML = '<span style="color: #ef4444;"><i class="fas fa-circle-xmark"></i> ' + data.message + '</span>';
            }
          })
          .catch(function () {});
      }, 350);
    }

    // 4. Student ID Format Masking (e.g. 2024-0145)
    var studentIdInput = document.getElementById('id_student_number');
    if (studentIdInput) {
      studentIdInput.addEventListener('input', function () {
        var val = this.value.replace(/[^\d]/g, '');
        if (val.length > 4) {
          val = val.substring(0, 4) + '-' + val.substring(4, 10);
        }
        this.value = val;
        scheduleAvailabilityCheck('student_number', val, document.getElementById('studentNumberStatus'));
      });
    }

    // 5. Contact Phone Auto-Format (09XX-XXX-XXXX)
    var phoneInput = document.getElementById('id_phone_number');
    if (phoneInput) {
      phoneInput.addEventListener('input', function () {
        var val = this.value.replace(/[^\d]/g, '');
        if (val.length > 4 && val.length <= 7) {
          val = val.substring(0, 4) + '-' + val.substring(4);
        } else if (val.length > 7) {
          val = val.substring(0, 4) + '-' + val.substring(4, 7) + '-' + val.substring(7, 11);
        }
        this.value = val;
      });
    }

    var emailInput = document.getElementById('id_email');
    if (emailInput) {
      emailInput.addEventListener('input', function () {
        scheduleAvailabilityCheck('email', this.value.trim(), document.getElementById('emailStatus'));
      });
    }

    // 6. Student Classification notice update
    var studentTypeSelect = document.getElementById('id_student_type');
    var studentTypeNoticeText = document.getElementById('studentTypeNoticeText');
    if (studentTypeSelect && studentTypeNoticeText) {
      studentTypeSelect.addEventListener('change', function () {
        if (this.value === 'IRREGULAR') {
          studentTypeNoticeText.innerHTML = '<strong style="color: #fbbf24;">Irregular / Returnee:</strong> Please upload your official COR below so the Admin can map your cross-enrolled subjects.';
        } else if (this.value === 'TRANSFEREE') {
          studentTypeNoticeText.innerHTML = '<strong style="color: #c084fc;">Transferee:</strong> Please upload your official crediting evaluation / COR below to verify your eligible subjects.';
        } else {
          studentTypeNoticeText.textContent = 'Regular students are enrolled into standard departmental block schedules.';
        }
      });

      if (studentTypeSelect.value !== 'REGULAR') {
        studentTypeSelect.dispatchEvent(new Event('change'));
      }
    }

    // 7. Live Password Strength & Match Indicator
    var pwdInput = document.getElementById('id_password');
    var confirmInput = document.getElementById('id_confirm_password');
    var strWrap = document.getElementById('passwordStrengthWrap');
    var strBars = [
      document.getElementById('strBar1'),
      document.getElementById('strBar2'),
      document.getElementById('strBar3'),
      document.getElementById('strBar4')
    ];
    var strText = document.getElementById('passwordStrengthText');
    var matchStatus = document.getElementById('passwordMatchStatus');

    function checkPasswordStrength(val) {
      if (!val) return 0;
      var score = 0;
      if (val.length >= 8) score++;
      if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score++;
      if (/\d/.test(val)) score++;
      if (/[^A-Za-z0-9]/.test(val)) score++;
      return Math.max(1, score);
    }

    function updateStrength() {
      if (!pwdInput || !strWrap) return;
      var val = pwdInput.value;
      if (!val) {
        strWrap.style.display = 'none';
        updateMatch();
        return;
      }

      strWrap.style.display = 'block';
      var score = checkPasswordStrength(val);

      var colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981'];
      var labels = ['Weak (needs 8+ chars)', 'Fair', 'Good', 'Strong & Secure'];

      strBars.forEach(function (bar, idx) {
        if (bar) {
          bar.style.background = idx < score ? colors[score - 1] : 'transparent';
        }
      });

      if (strText) {
        strText.textContent = labels[score - 1];
        strText.style.color = colors[score - 1];
      }

      updateMatch();
    }

    function updateMatch() {
      if (!confirmInput || !matchStatus) return;
      var pVal = pwdInput ? pwdInput.value : '';
      var cVal = confirmInput.value;

      if (!cVal) {
        matchStatus.style.display = 'none';
        confirmInput.style.borderColor = '';
        return;
      }

      matchStatus.style.display = 'block';
      if (pVal === cVal) {
        matchStatus.innerHTML = '<span style="color: #10b981;"><i class="fas fa-circle-check"></i> Passwords match</span>';
        confirmInput.style.borderColor = 'rgba(16, 185, 129, 0.6)';
      } else {
        matchStatus.innerHTML = '<span style="color: #f87171;"><i class="fas fa-circle-xmark"></i> Passwords do not match</span>';
        confirmInput.style.borderColor = 'rgba(239, 68, 68, 0.6)';
      }
    }

    if (pwdInput) {
      pwdInput.addEventListener('input', updateStrength);
    }
    if (confirmInput) {
      confirmInput.addEventListener('input', updateMatch);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRegister);
  } else {
    initRegister();
  }
})(window);
