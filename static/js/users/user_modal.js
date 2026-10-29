/* KCC ClassStamp — Users: Add / Edit User Modal & Save Controller */
(function (window) {
  'use strict';

  function getApp() { return window.UsersApp || null; }
  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    var App = getApp();
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return (input && input.value) || '';
  }

  function syncRoleFields(role) {
    var roleVal = (role || 'STUDENT').toUpperCase();
    var userLabel  = getEl('edit_username_label');
    var userHint   = getEl('edit_username_hint');
    var userInput  = getEl('edit_username');
    var studentRow = getEl('row_academic_student');
    var teacherRow = getEl('row_academic_teacher');

    if (roleVal === 'STUDENT') {
      if (userLabel) userLabel.innerHTML = 'Student ID Number <span class="text-danger">*</span>';
      if (userInput) userInput.placeholder = 'e.g. 2024-110755';
      if (userHint)  userHint.textContent = 'Institutional Student ID from badge (used for login and attendance).';
      if (studentRow) studentRow.style.display = 'flex';
      if (teacherRow) teacherRow.style.display = 'none';
    } else if (roleVal === 'TEACHER') {
      if (userLabel) userLabel.innerHTML = 'Faculty Username / ID <span class="text-danger">*</span>';
      if (userInput) userInput.placeholder = 'e.g. msantos or FAC-102';
      if (userHint)  userHint.textContent = 'Faculty username or employee number for portal access.';
      if (studentRow) studentRow.style.display = 'none';
      if (teacherRow) teacherRow.style.display = 'block';
    } else {
      if (userLabel) userLabel.innerHTML = 'Admin Username <span class="text-danger">*</span>';
      if (userInput) userInput.placeholder = 'e.g. admin_office';
      if (userHint)  userHint.textContent = 'Institutional administrator login username.';
      if (studentRow) studentRow.style.display = 'none';
      if (teacherRow) teacherRow.style.display = 'none';
    }
  }

  function initUserModal() {
    var form               = getEl('editUserForm');
    var errorBox           = getEl('editUserFormError');
    var modalTitle         = getEl('editUserModalTitle');
    var passwordHint       = getEl('edit_password_hint');
    var roleSelect         = getEl('edit_role');
    var togglePasswordBtn  = getEl('togglePasswordBtn');
    var togglePasswordIcon = getEl('togglePasswordIcon');
    var passwordInput      = getEl('edit_password');

    if (roleSelect) {
      roleSelect.addEventListener('change', function () {
        syncRoleFields(this.value);
      });
    }

    if (togglePasswordBtn && passwordInput && togglePasswordIcon) {
      togglePasswordBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (passwordInput.type === 'password') {
          passwordInput.type = 'text';
          togglePasswordIcon.classList.remove('fa-eye');
          togglePasswordIcon.classList.add('fa-eye-slash');
        } else {
          passwordInput.type = 'password';
          togglePasswordIcon.classList.remove('fa-eye-slash');
          togglePasswordIcon.classList.add('fa-eye');
        }
      });
    }

    // Handle Edit / Create button click (event delegation)
    document.addEventListener('click', function (e) {
      var editBtn = e.target.closest('[data-modal-target="editUserModal"]');
      if (!editBtn) return;

      if (errorBox) errorBox.style.display = 'none';
      if (passwordInput) passwordInput.type = 'password';
      if (togglePasswordIcon) {
        togglePasswordIcon.classList.remove('fa-eye-slash');
        togglePasswordIcon.classList.add('fa-eye');
      }

      var mode = editBtn.getAttribute('data-mode');
      if (mode === 'edit') {
        if (modalTitle) modalTitle.textContent = 'Edit User Account';
        var idEl = getEl('edit_id');
        var uEl  = getEl('edit_username');
        var fnEl = getEl('edit_first_name');
        var lnEl = getEl('edit_last_name');
        var emEl = getEl('edit_email');
        var pwEl = getEl('edit_password');
        var actEl = getEl('edit_is_active');

        if (idEl)  idEl.value  = editBtn.getAttribute('data-id') || '';
        if (uEl)   uEl.value   = editBtn.getAttribute('data-username') || '';
        if (fnEl)  fnEl.value  = editBtn.getAttribute('data-first') || '';
        if (lnEl)  lnEl.value  = editBtn.getAttribute('data-last') || '';
        if (emEl)  emEl.value  = editBtn.getAttribute('data-email') || '';
        if (pwEl)  pwEl.value  = '';
        if (actEl) actEl.checked = editBtn.getAttribute('data-active') === 'true';

        var role = editBtn.getAttribute('data-role') || 'STUDENT';
        if (roleSelect) roleSelect.value = role;
        syncRoleFields(role);

        var progId = editBtn.getAttribute('data-program');
        var progEl = getEl('edit_program');
        if (progId && progEl) progEl.value = progId;

        var deptId = editBtn.getAttribute('data-department');
        var deptEl = getEl('edit_department');
        if (deptId && deptEl) deptEl.value = deptId;

        var yrLevel = editBtn.getAttribute('data-year');
        var yrEl = getEl('edit_year_level');
        if (yrLevel && yrEl) yrEl.value = yrLevel;

        if (passwordHint) passwordHint.style.display = 'inline';
      } else {
        if (modalTitle) modalTitle.textContent = 'Add New Account';
        if (form) form.reset();
        var idEl2 = getEl('edit_id');
        var actEl2 = getEl('edit_is_active');
        if (idEl2)  idEl2.value = '';
        if (actEl2) actEl2.checked = true;

        var defaultRole = 'STUDENT';
        if (roleSelect) {
          roleSelect.value = defaultRole;
          syncRoleFields(defaultRole);
        }

        if (passwordHint) passwordHint.style.display = 'none';
      }

      var App = getApp();
      if (App) App.showModal('editUserModal');
      else if (typeof window.openModal === 'function') window.openModal('editUserModal');
      else {
        var m = getEl('editUserModal');
        if (m) m.classList.add('is-active');
      }
    });

    // Form submission via AJAX
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var formData = new FormData(form);

        fetch('/users/ajax/save/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() },
          body: formData
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) {
            if (errorBox) {
              errorBox.textContent = data.error;
              errorBox.style.display = 'flex';
            }
            return;
          }
          window.location.reload();
        })
        .catch(function () {
          if (errorBox) {
            errorBox.textContent = 'Server communication error.';
            errorBox.style.display = 'flex';
          }
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUserModal);
  } else {
    initUserModal();
  }

  window.UsersApp = window.UsersApp || {};
  window.UsersApp.syncRoleFields = syncRoleFields;
})(window);
