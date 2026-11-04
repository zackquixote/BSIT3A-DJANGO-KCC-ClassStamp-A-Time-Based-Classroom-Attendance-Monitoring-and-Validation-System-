/* KCC ClassStamp — Class join-code administration */
(function () {
  'use strict';

  function notify(type, text) {
    if (window.App && window.App.toast) {
      window.App.toast(type, text);
    } else {
      window.alert(text);
    }
  }

  async function postCodeAction(button, action) {
    var body = new URLSearchParams();
    body.set('action', action);
    var csrf = window.ClassesApp && window.ClassesApp.getCSRFToken
      ? window.ClassesApp.getCSRFToken()
      : (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    body.set('csrfmiddlewaretoken', csrf);

    var response = await fetch(button.dataset.codeUrl, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: body
    });
    var data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.message || 'Unable to update the class join code.');
    }
    return data;
  }

  document.addEventListener('click', async function (event) {
    var approveButton = event.target.closest('.js-approve-join-request');
    var declineButton = event.target.closest('.js-reject-join-request');
    var requestButton = approveButton || declineButton;
    if (requestButton && requestButton.closest('.teacher-classes')) {
      var approve = Boolean(approveButton);
      if (!approve) {
        var confirmed = window.App && window.App.confirm
          ? await window.App.confirm({
              title: 'Decline Join Request',
              message: 'Decline this student request? The student will need a new code to request enrollment again.',
              confirmText: 'Decline Request',
              confirmClass: 'btn-danger',
              type: 'danger'
            })
          : window.confirm('Decline this student request?');
        if (!confirmed) return;
      }

      requestButton.disabled = true;
      try {
        var requestBody = new URLSearchParams();
        requestBody.set('csrfmiddlewaretoken', (
          window.ClassesApp && window.ClassesApp.getCSRFToken
            ? window.ClassesApp.getCSRFToken()
            : (document.querySelector('meta[name="csrf-token"]') || {}).content || ''
        ));
        if (approve) requestBody.set('profile_id', approveButton.dataset.profileId);
        var requestResponse = await fetch(requestButton.dataset.actionUrl, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: requestBody
        });
        var requestResult = await requestResponse.json();
        if (!requestResponse.ok || !requestResult.success) {
          throw new Error(requestResult.message || 'Unable to update the join request.');
        }
        notify('success', approve ? 'Enrollment request approved.' : 'Join request declined.');
        window.location.reload();
      } catch (error) {
        notify('error', error.message || 'Request failed.');
        requestButton.disabled = false;
      }
      return;
    }

    var rotateButton = event.target.closest('.js-manage-join-code');
    var revokeButton = event.target.closest('.js-revoke-join-code');
    var button = rotateButton || revokeButton;
    if (!button) return;

    var action = rotateButton ? 'rotate' : 'revoke';
    if (action === 'rotate' && button.dataset.codeActive === 'true') {
      var rotateConfirmed = window.App && window.App.confirm
        ? await window.App.confirm({
            title: 'Rotate Student Join Code',
            message: 'The current code will stop working. Students with pending requests will keep their requests.',
            confirmText: 'Rotate Code',
            confirmClass: 'btn-primary',
            type: 'warning'
          })
        : window.confirm('The current code will stop working. Rotate it?');
      if (!rotateConfirmed) return;
    }
    if (action === 'revoke') {
      var revokeConfirmed = window.App && window.App.confirm
        ? await window.App.confirm({
            title: 'Disable Student Join Code',
            message: 'Students will no longer be able to request enrollment with this code.',
            confirmText: 'Disable Code',
            confirmClass: 'btn-danger',
            type: 'danger'
          })
        : window.confirm('Disable student enrollment with this code?');
      if (!revokeConfirmed) return;
    }

    button.disabled = true;
    try {
      var data = await postCodeAction(button, action);
      if (action === 'rotate') {
        window.prompt(
          'Copy this code and share it with students in ' + data.class_code + '. It will not be shown again.',
          data.join_code
        );
        window.location.reload();
      } else {
        notify('success', data.message);
        window.location.reload();
      }
    } catch (error) {
      notify('error', error.message || 'Request failed.');
      button.disabled = false;
    }
  });
})();
