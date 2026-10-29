/**
 * KCC ClassStamp — Inline Editable Records Utility
 * Supports fast inline editing for Department & Program names and codes
 * without requiring full modal interactions.
 */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) return metaTag.getAttribute('content');
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function showToast(msg, type) {
    if (window.toast && typeof window.toast[type] === 'function') {
      window.toast[type](msg);
      return;
    }
    const toast = document.createElement('div');
    toast.className = 'toast toast--' + (type === 'error' ? 'error' : 'success');
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.zIndex = '99999';
    toast.style.padding = '10px 18px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 8px 24px rgba(0,0,0,0.5)';
    toast.style.background = type === 'error' ? 'rgba(239,68,68,0.92)' : 'rgba(34,197,94,0.92)';
    toast.style.color = '#fff';
    toast.style.fontSize = '0.85rem';
    toast.style.fontWeight = '600';
    toast.innerHTML = (type === 'error' ? '<i class="fas fa-triangle-exclamation"></i> ' : '<i class="fas fa-check"></i> ') + msg;
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 3500);
  }

  document.querySelectorAll('.js-inline-editable').forEach(function (wrapper) {
    const row = wrapper.closest('tr');
    if (!row) return;

    wrapper.style.cursor = 'pointer';
    wrapper.setAttribute('title', 'Double-click or click pencil to edit inline');

    // Add subtle pencil icon if not present
    if (!wrapper.querySelector('.js-inline-pencil')) {
      const pencil = document.createElement('i');
      pencil.className = 'fas fa-pencil text-muted js-inline-pencil';
      pencil.style.fontSize = '0.7rem';
      pencil.style.marginLeft = '6px';
      pencil.style.opacity = '0.4';
      pencil.style.transition = 'opacity 0.2s';
      wrapper.appendChild(pencil);
      wrapper.addEventListener('mouseenter', function () { pencil.style.opacity = '1'; });
      wrapper.addEventListener('mouseleave', function () { pencil.style.opacity = '0.4'; });
    }

    function startEdit(e) {
      if (e) e.stopPropagation();
      if (wrapper.classList.contains('is-editing')) return;

      wrapper.classList.add('is-editing');
      const currentVal = wrapper.getAttribute('data-value') || wrapper.textContent.trim();
      const field = wrapper.getAttribute('data-field'); // 'code' or 'name'
      const type = wrapper.getAttribute('data-type');   // 'department' or 'program'
      const recordId = wrapper.getAttribute('data-id');

      const originalHtml = wrapper.innerHTML;

      const editWrap = document.createElement('span');
      editWrap.className = 'inline-edit-group';
      editWrap.style.display = 'inline-flex';
      editWrap.style.alignItems = 'center';
      editWrap.style.gap = '4px';

      const input = document.createElement('input');
      input.type = 'text';
      input.value = currentVal;
      input.className = 'form-control';
      input.style.padding = '3px 8px';
      input.style.fontSize = '0.75rem';
      input.style.height = '28px';
      input.style.width = field === 'code' ? '80px' : '220px';
      input.style.background = 'rgba(11, 15, 25, 0.95)';
      input.style.border = '1px solid var(--accent-gold)';
      input.style.borderRadius = '4px';
      input.style.color = '#fff';

      const saveBtn = document.createElement('button');
      saveBtn.type = 'button';
      saveBtn.className = 'btn btn-primary btn-xs';
      saveBtn.style.padding = '3px 8px';
      saveBtn.style.height = '28px';
      saveBtn.innerHTML = '<i class="fas fa-check"></i>';
      saveBtn.title = 'Save (Enter)';

      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'btn btn-ghost btn-xs text-muted';
      cancelBtn.style.padding = '3px 6px';
      cancelBtn.style.height = '28px';
      cancelBtn.innerHTML = '<i class="fas fa-xmark"></i>';
      cancelBtn.title = 'Cancel (Esc)';

      editWrap.appendChild(input);
      editWrap.appendChild(saveBtn);
      editWrap.appendChild(cancelBtn);

      wrapper.innerHTML = '';
      wrapper.appendChild(editWrap);
      input.focus();
      input.select();

      function cancel() {
        wrapper.classList.remove('is-editing');
        wrapper.innerHTML = originalHtml;
      }

      function save() {
        const newVal = input.value.trim();
        if (!newVal) {
          showToast('Value cannot be empty', 'error');
          input.focus();
          return;
        }

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        const formData = new FormData();
        formData.append('id', recordId);

        let url = '';
        if (type === 'department') {
          url = '/departments/save/';
          // Extract the sibling field
          const codeEl = row.querySelector('[data-field="code"]');
          const nameEl = row.querySelector('[data-field="name"]');
          const finalCode = (field === 'code') ? newVal : (codeEl ? codeEl.getAttribute('data-value') : '');
          const finalName = (field === 'name') ? newVal : (nameEl ? nameEl.getAttribute('data-value') : '');

          formData.append('code', finalCode);
          formData.append('name', finalName);
          formData.append('is_active', 'true');
        } else if (type === 'program') {
          url = '/programs/save/';
          const codeEl = row.querySelector('[data-field="code"]');
          const nameEl = row.querySelector('[data-field="name"]');
          const deptId = row.getAttribute('data-department-id') || wrapper.getAttribute('data-department-id') || '1';
          const yearsTotal = row.getAttribute('data-years') || '4';

          const finalCode = (field === 'code') ? newVal : (codeEl ? codeEl.getAttribute('data-value') : '');
          const finalName = (field === 'name') ? newVal : (nameEl ? nameEl.getAttribute('data-value') : '');

          formData.append('code', finalCode);
          formData.append('name', finalName);
          formData.append('department_id', deptId);
          formData.append('years_total', yearsTotal);
          formData.append('is_active', 'true');
        }

        fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: formData,
        })
          .then(function (res) {
            return res.json().then(function (data) {
              return { ok: res.ok, status: res.status, data: data };
            });
          })
          .then(function (resObj) {
            if (!resObj.ok || resObj.data.error) {
              throw new Error(resObj.data.error || 'Failed to update record');
            }

            wrapper.classList.remove('is-editing');
            wrapper.setAttribute('data-value', newVal);

            if (field === 'code') {
              wrapper.innerHTML =
                '<span class="badge ' + (type === 'department' ? 'badge--purple' : 'badge--gold') + ' font-semibold" style="letter-spacing: 0.5px;">' +
                newVal.toUpperCase() +
                '</span>';
            } else {
              wrapper.innerHTML = '<span class="font-semibold text-primary">' + newVal + '</span>';
            }

            // Re-attach subtle pencil icon
            const pencil = document.createElement('i');
            pencil.className = 'fas fa-pencil text-muted js-inline-pencil';
            pencil.style.fontSize = '0.7rem';
            pencil.style.marginLeft = '6px';
            pencil.style.opacity = '0.4';
            pencil.style.transition = 'opacity 0.2s';
            wrapper.appendChild(pencil);

            showToast('Updated successfully!', 'success');
          })
          .catch(function (err) {
            console.error('Inline edit error:', err);
            showToast(err.message || 'Update failed', 'error');
            cancel();
          });
      }

      saveBtn.addEventListener('click', save);
      cancelBtn.addEventListener('click', cancel);

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          save();
        } else if (e.key === 'Escape') {
          cancel();
        }
      });
    }

    wrapper.addEventListener('dblclick', startEdit);
    const pencilBtn = wrapper.querySelector('.js-inline-pencil');
    if (pencilBtn) pencilBtn.addEventListener('click', startEdit);
  });
});
