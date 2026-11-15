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

    // 7. Live Password Requirements Checklist & Match Indicator
    // Four rules that mirror the server policy in
    // apps/core/views/helpers/auth_helpers.py. Each rule turns green the moment
    // it is satisfied, so the student can see exactly which one is still
    // missing instead of guessing why the form was rejected.
    var pwdInput = document.getElementById('id_password');
    var confirmInput = document.getElementById('id_confirm_password');
    var checklistWrap = document.getElementById('passwordChecklist');
    var pwdErrorBox = document.getElementById('passwordErrorBox');
    var matchStatus = document.getElementById('passwordMatchStatus');

    var PASSWORD_RULES = [
      {
        el: document.getElementById('ruleLength'),
        label: 'a minimum of 8 characters',
        test: function (value) { return value.length >= 8; }
      },
      {
        el: document.getElementById('ruleCase'),
        label: 'lower and uppercase letters (a-z and A-Z)',
        test: function (value) { return /[a-z]/.test(value) && /[A-Z]/.test(value); }
      },
      {
        el: document.getElementById('ruleNumber'),
        label: 'at least 1 number (0-9)',
        test: function (value) { return /\d/.test(value); }
      },
      {
        el: document.getElementById('ruleSymbol'),
        label: 'at least 1 symbol or special character (!@#$%^&*)',
        test: function (value) { return /[^A-Za-z0-9\s]/.test(value); }
      }
    ];

    function setRuleState(ruleEl, isSatisfied) {
      if (!ruleEl) return;
      var icon = ruleEl.querySelector('.rule-icon');
      if (isSatisfied) {
        ruleEl.classList.add('is-satisfied');
        if (icon) {
          icon.className = 'fas fa-circle-check rule-icon';
        }
      } else {
        ruleEl.classList.remove('is-satisfied');
        if (icon) {
          icon.className = 'far fa-circle rule-icon';
        }
      }
    }

    function unmetRules(value) {
      return PASSWORD_RULES.filter(function (rule) { return !rule.test(value); });
    }

    function showPasswordError(message) {
      if (!pwdErrorBox) return;
      pwdErrorBox.hidden = false;
      pwdErrorBox.innerHTML = '<i class="fas fa-circle-exclamation"></i> ' + message;
    }

    function hidePasswordError() {
      if (!pwdErrorBox) return;
      pwdErrorBox.hidden = true;
      pwdErrorBox.innerHTML = '';
    }

    function updatePasswordChecklist() {
      if (!pwdInput) return;
      var val = pwdInput.value;

      PASSWORD_RULES.forEach(function (rule) {
        setRuleState(rule.el, rule.test(val));
      });

      // The checklist stays visible at all times: it is the instruction, not a
      // reaction to typing, so a student sees the rules before choosing one.
      if (checklistWrap) {
        checklistWrap.style.display = 'flex';
      }

      if (val && unmetRules(val).length === 0) {
        hidePasswordError();
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
        matchStatus.innerHTML = '<span style="color: #10b981; display: inline-flex; align-items: center; gap: 5px;"><i class="fas fa-circle-check"></i> Passwords match</span>';
        confirmInput.style.borderColor = 'rgba(16, 185, 129, 0.6)';
      } else {
        matchStatus.innerHTML = '<span style="color: #ef4444; display: inline-flex; align-items: center; gap: 5px;"><i class="fas fa-circle-xmark"></i> Passwords do not match</span>';
        confirmInput.style.borderColor = 'rgba(239, 68, 68, 0.6)';
      }
    }

    if (pwdInput) {
      pwdInput.addEventListener('input', updatePasswordChecklist);
      pwdInput.addEventListener('focus', updatePasswordChecklist);
    }
    if (confirmInput) {
      confirmInput.addEventListener('input', updateMatch);
    }

    updatePasswordChecklist();

    // 8. Submit feedback the student can actually see.
    // Native validation bubbles are easy to miss on phones (they can appear
    // off-screen above the keyboard), and a failed server submit used to say
    // only "review the highlighted fields" — with the COR / ID upload, which
    // sits at the bottom of the form, being the usual culprit.
    function fieldLabel(el) {
      var group = el.closest ? el.closest('.form-group') : null;
      var label = group ? group.querySelector('.form-label') : null;
      return label ? label.textContent.replace(/\s+/g, ' ').trim() : 'This field';
    }

    function showFieldNotice(el, message) {
      var group = el.closest ? el.closest('.form-group') : null;
      if (!group) return null;
      var note = group.querySelector('.js-client-error');
      if (!note) {
        note = document.createElement('span');
        note.className = 'kcc-field-error js-client-error';
        group.appendChild(note);
      }
      note.innerHTML = '<i class="fas fa-circle-exclamation"></i> ' + message;
      return note;
    }

    function scrollToEl(el) {
      try {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } catch (err) {
        el.scrollIntoView();
      }
    }

    if (registerForm) {
      // Replace the browser's silent bubble with an inline message.
      registerForm.addEventListener('invalid', function (event) {
        var el = event.target;
        event.preventDefault();                 // suppress the native tooltip
        if (!el) return;
        el.classList.add('is-invalid');
        var isFile = el.type === 'file';
        var label = fieldLabel(el).replace(/\s*\*\s*$/, '');
        var msg = isFile
          ? 'Please attach your Certificate of Registration (COR) or school ID photo — this document is required.'
          : label + ' is required. Please fill in this field.';
        el.dataset.kccHint = msg;
        showFieldNotice(el, msg);
        scrollToEl(el);
      }, true);

      registerForm.addEventListener('input', function (event) {
        var el = event.target;
        if (!el || !el.classList) return;
        el.classList.remove('is-invalid');
        var note = el.closest && el.closest('.form-group')
          ? el.closest('.form-group').querySelector('.js-client-error') : null;
        if (note) note.remove();
      }, true);

      registerForm.addEventListener('change', function (event) {
        if (event.target && event.target.type === 'file') {
          event.target.classList.remove('is-invalid');
          var group = event.target.closest('.form-group');
          var note = group ? group.querySelector('.js-client-error') : null;
          if (note) note.remove();
        }
      }, true);

      // 9. Check the password rules, the match, and the COR / ID upload HERE,
      // before the form leaves the page. A server round-trip rejects the whole
      // submission and browsers deliberately drop the chosen file, which forced
      // students to pick their document again — that was the real reason the
      // upload felt strict.
      registerForm.addEventListener('submit', function (event) {
        var pwd = pwdInput ? pwdInput.value : '';

        if (pwd) {
          var missing = unmetRules(pwd);
          if (missing.length) {
            event.preventDefault();
            showPasswordError('Your password still needs ' + joinLabels(missing) + '.');
            scrollToEl(pwdInput);
            return;
          }
        }

        if (pwd && confirmInput && confirmInput.value !== pwd) {
          event.preventDefault();
          updateMatch();
          scrollToEl(confirmInput);
          return;
        }

        var file = proofInput && proofInput.files && proofInput.files[0];
        if (file) {
          var problem = uploadProblem(file);
          if (problem) {
            event.preventDefault();
            setUploadStatus(problem, 'error');
            scrollToEl(proofInput);
          }
        }
      });
    }

    // 10. COR / ID upload guard.
    // The server accepts JPG / PNG / WebP / PDF up to 5 MB and verifies the
    // real file contents. Two things made that feel strict to students:
    //   - a 12 MP phone photo is often 6–8 MB, so it was rejected only after the
    //     page reloaded;
    //   - iPhone HEIC files are not an accepted format at all.
    // Both are caught (and large photos are shrunk) before the form is sent.
    var MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
    var SHRINK_ABOVE_BYTES = 2.5 * 1024 * 1024;
    var MAX_PHOTO_EDGE = 1800;
    var ALLOWED_UPLOAD_EXTS = ['jpg', 'jpeg', 'png', 'webp', 'pdf'];
    var proofInput = document.getElementById('id_registration_proof');
    var proofStatus = document.getElementById('registrationProofStatus');

    function fileExt(name) {
      var parts = (name || '').toLowerCase().split('.');
      return parts.length > 1 ? parts.pop() : '';
    }

    function humanSize(bytes) {
      if (bytes >= 1024 * 1024) {
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
      }
      return Math.max(1, Math.round(bytes / 1024)) + ' KB';
    }

    function setUploadStatus(message, tone) {
      if (!proofStatus) return;
      if (!message) {
        proofStatus.innerHTML = '';
        proofStatus.style.display = 'none';
        return;
      }
      var color = tone === 'error' ? '#ef4444' : (tone === 'ok' ? '#10b981' : '#94a3b8');
      var icon = tone === 'error' ? 'fa-circle-exclamation' : (tone === 'ok' ? 'fa-circle-check' : 'fa-circle-info');
      proofStatus.style.display = 'block';
      proofStatus.innerHTML = '<i class="fas ' + icon + '"></i> <span style="color:' + color + '">' + message + '</span>';
    }

    function uploadProblem(file) {
      var ext = fileExt(file.name);
      if (ext === 'heic' || ext === 'heif') {
        return 'iPhone HEIC photos cannot be uploaded. Open Settings → Camera → Formats → Most Compatible, retake the photo, then attach it again.';
      }
      if (ALLOWED_UPLOAD_EXTS.indexOf(ext) === -1) {
        return 'Unsupported file type ".' + ext + '". Please attach a JPG, PNG, WebP, or PDF file.';
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        return 'This file is ' + humanSize(file.size) + ' — the limit is 5 MB. Please attach a smaller file.';
      }
      return '';
    }

    function joinLabels(rules) {
      var labels = rules.map(function (rule) { return rule.label; });
      if (labels.length === 1) return labels[0];
      return labels.slice(0, -1).join(', ') + ' and ' + labels[labels.length - 1];
    }

    function replaceFile(input, newFile) {
      try {
        var transfer = new DataTransfer();
        transfer.items.add(newFile);
        input.files = transfer.files;
        return true;
      } catch (err) {
        return false;
      }
    }

    // Downscale a phone photo in the browser so a 6–8 MB shot still fits under
    // the 5 MB cap. The server re-encodes to WebP anyway, so nothing is lost.
    function shrinkPhoto(file, done) {
      var objectUrl = URL.createObjectURL(file);
      var image = new Image();

      image.onload = function () {
        try {
          var scale = Math.min(1, MAX_PHOTO_EDGE / Math.max(image.width, image.height));
          var canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(image.width * scale));
          canvas.height = Math.max(1, Math.round(image.height * scale));
          var context = canvas.getContext('2d');
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(function (blob) {
            URL.revokeObjectURL(objectUrl);
            if (!blob || blob.size >= file.size) {
              done(null);
              return;
            }
            var stem = file.name.replace(/\.[^.]+$/, '') || 'registration-proof';
            done(new File([blob], stem + '.jpg', { type: 'image/jpeg', lastModified: Date.now() }));
          }, 'image/jpeg', 0.82);
        } catch (err) {
          URL.revokeObjectURL(objectUrl);
          done(null);
        }
      };

      image.onerror = function () {
        URL.revokeObjectURL(objectUrl);
        done(null);
      };

      image.src = objectUrl;
    }

    if (proofInput) {
      proofInput.addEventListener('change', function () {
        var file = this.files && this.files[0];
        setUploadStatus('');
        if (!file) return;

        var ext = fileExt(file.name);
        var problem = uploadProblem(file);

        if (ext === 'heic' || ext === 'heif' || ALLOWED_UPLOAD_EXTS.indexOf(ext) === -1) {
          setUploadStatus(problem, 'error');
          return;
        }

        if (ext === 'pdf') {
          if (problem) {
            setUploadStatus(problem, 'error');
            return;
          }
          setUploadStatus('Attached: ' + file.name + ' (' + humanSize(file.size) + ')', 'ok');
          return;
        }

        if (file.size <= SHRINK_ABOVE_BYTES) {
          setUploadStatus('Attached: ' + file.name + ' (' + humanSize(file.size) + ')', 'ok');
          return;
        }

        setUploadStatus('Optimising your photo for upload…');
        shrinkPhoto(file, function (shrunk) {
          if (shrunk && shrunk.size <= MAX_UPLOAD_BYTES && replaceFile(proofInput, shrunk)) {
            setUploadStatus('Photo optimised: ' + humanSize(file.size) + ' → ' + humanSize(shrunk.size), 'ok');
            return;
          }
          if (file.size > MAX_UPLOAD_BYTES) {
            setUploadStatus(
              'This photo is ' + humanSize(file.size) + ' and could not be shrunk automatically. '
              + 'Please retake it at a lower resolution or choose a smaller file (limit: 5 MB).',
              'error'
            );
            return;
          }
          setUploadStatus('Attached: ' + file.name + ' (' + humanSize(file.size) + ')', 'ok');
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRegister);
  } else {
    initRegister();
  }
})(window);
