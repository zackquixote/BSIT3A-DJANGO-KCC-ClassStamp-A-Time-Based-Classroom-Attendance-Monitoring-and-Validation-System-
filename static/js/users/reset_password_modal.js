/* KCC ClassStamp — Users: Reset Password Modal Controller */
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

  function initResetPasswordModal() {
    var resetForm           = getEl('resetPasswordForm');
    var resetUserIdInput    = getEl('reset_user_id');
    var resetUserName       = getEl('reset_user_name');
    var resetUserIdent      = getEl('reset_user_ident');
    var modeAuto            = getEl('mode_auto');
    var modeManual          = getEl('mode_manual');
    var customPasswordWrap  = getEl('customPasswordWrap');
    var customResetPassword = getEl('custom_reset_password');
    var resetResultCard     = getEl('resetResultCard');
    var newTempPasswordText = getEl('newTempPasswordText');
    var copyPasswordBtn     = getEl('copyPasswordBtn');
    var copyBtnText         = getEl('copyBtnText');
    var resetPasswordAlert  = getEl('resetPasswordAlert');
    var submitResetBtn      = getEl('submitResetPasswordBtn');

    if (modeAuto && modeManual) {
      modeAuto.addEventListener('change', function () {
        if (customPasswordWrap) customPasswordWrap.style.display = 'none';
        if (customResetPassword) customResetPassword.value = '';
      });
      modeManual.addEventListener('change', function () {
        if (customPasswordWrap) customPasswordWrap.style.display = 'block';
      });
    }

    // Open reset modal (event delegation)
    document.addEventListener('click', function (e) {
      var resetBtn = e.target.closest('[data-modal-target="resetPasswordModal"]');
      if (!resetBtn) return;

      if (resetPasswordAlert) resetPasswordAlert.style.display = 'none';
      if (resetResultCard) resetResultCard.style.display = 'none';
      if (submitResetBtn) submitResetBtn.style.display = 'inline-flex';
      if (modeAuto) modeAuto.checked = true;
      if (customPasswordWrap) customPasswordWrap.style.display = 'none';
      if (customResetPassword) customResetPassword.value = '';

      var uId = resetBtn.getAttribute('data-id');
      var uName = resetBtn.getAttribute('data-name');
      var uIdent = resetBtn.getAttribute('data-username');

      if (resetUserIdInput) resetUserIdInput.value = uId;
      if (resetUserName) resetUserName.textContent = uName;
      if (resetUserIdent) resetUserIdent.textContent = 'Account ID / Username: ' + uIdent;

      var App = getApp();
      if (App) App.showModal('resetPasswordModal');
      else if (typeof window.openModal === 'function') window.openModal('resetPasswordModal');
      else {
        var m = getEl('resetPasswordModal');
        if (m) m.classList.add('is-active');
      }
    });

    // Reset password submission
    if (resetForm) {
      resetForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var uId = resetUserIdInput ? resetUserIdInput.value : '';
        if (!uId) return;

        var isManual = modeManual && modeManual.checked;
        var customPwd = isManual ? (customResetPassword.value || '').trim() : '';

        if (isManual && (!customPwd || customPwd.length < 6)) {
          if (resetPasswordAlert) {
            resetPasswordAlert.textContent = 'Custom password must be at least 6 characters.';
            resetPasswordAlert.style.display = 'flex';
          }
          return;
        }

        var postData = new FormData();
        if (customPwd) {
          postData.append('password', customPwd);
        }

        var App = getApp();

        fetch('/users/ajax/reset-password/' + uId + '/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRF() },
          body: postData
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'success') {
            if (newTempPasswordText) newTempPasswordText.textContent = data.temporary_password;
            if (resetResultCard) resetResultCard.style.display = 'block';
            if (submitResetBtn) submitResetBtn.style.display = 'none';
            if (resetPasswordAlert) resetPasswordAlert.style.display = 'none';
            if (App) App.showAlert(data.message || 'Password reset successfully.');
          } else {
            if (resetPasswordAlert) {
              resetPasswordAlert.textContent = data.error || 'Failed to reset password.';
              resetPasswordAlert.style.display = 'flex';
            }
          }
        })
        .catch(function () {
          if (resetPasswordAlert) {
            resetPasswordAlert.textContent = 'Network error while resetting password.';
            resetPasswordAlert.style.display = 'flex';
          }
        });
      });
    }

    // Copy Temporary Password to Clipboard
    if (copyPasswordBtn && newTempPasswordText) {
      copyPasswordBtn.addEventListener('click', function () {
        var pwd = newTempPasswordText.textContent;
        if (!pwd) return;
        var App = getApp();
        navigator.clipboard.writeText(pwd).then(function () {
          if (copyBtnText) copyBtnText.textContent = 'Copied!';
          if (App) App.showAlert('Temporary password copied to clipboard!');
          setTimeout(function () {
            if (copyBtnText) copyBtnText.textContent = 'Copy';
          }, 2500);
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initResetPasswordModal);
  } else {
    initResetPasswordModal();
  }
})(window);
