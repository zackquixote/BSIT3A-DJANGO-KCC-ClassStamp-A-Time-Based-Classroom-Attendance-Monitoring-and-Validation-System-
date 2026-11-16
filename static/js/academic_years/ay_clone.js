/* KCC ClassStamp — Academic Years: Clone Class Structure (Req 12) */
(function (window) {
  'use strict';

  var App = window.AcademicYearsApp;
  var lastCloneMapping = [];

  function getEl(id) { return document.getElementById(id); }
  function getCSRF() {
    if (App && App.CSRF) return App.CSRF;
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return (input && input.value) || '';
  }

  function resetModal() {
    var error = getEl('cloneError');
    if (error) {
      error.style.display = 'none';
      error.textContent = '';
    }
    var results = getEl('cloneResults');
    if (results) results.style.display = 'none';
    var summary = getEl('cloneSummary');
    if (summary) summary.innerHTML = '';
    var errors = getEl('cloneErrors');
    if (errors) errors.innerHTML = '';
    var codesError = getEl('cloneCodesError');
    if (codesError) {
      codesError.style.display = 'none';
      codesError.textContent = '';
    }
    var codesBox = getEl('cloneCodesBox');
    if (codesBox) codesBox.style.display = 'none';
    var codesList = getEl('cloneCodesList');
    if (codesList) codesList.innerHTML = '';
    var genBtn = getEl('cloneGenCodesBtn');
    if (genBtn) genBtn.style.display = 'none';
    var btn = getEl('cloneExecuteBtn');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-copy"></i> Clone Classes';
    }
    lastCloneMapping = [];
  }

  function confirmClone() {
    var withCodes = getEl('cloneWithCodes');
    var codesNote = withCodes && withCodes.checked
      ? 'Join codes will be generated for the copied classes.'
      : 'Join codes are NOT copied.';
    var msg = (
      'Clone every active class section and weekly slot into the target term?\n\n' +
      'Enrollments, sessions, and attendance are NOT copied. ' +
      'Existing classes in the target term are never overwritten.\n' +
      codesNote
    );
    return window.confirm(msg);
  }

  function renderJoinCodes(rows) {
    var codesBox = getEl('cloneCodesBox');
    var codesList = getEl('cloneCodesList');
    if (!codesBox || !codesList) return;
    if (!rows || !rows.length) {
      codesBox.style.display = 'none';
      return;
    }
    var html = '<table class="table" style="margin:0;"><thead><tr>' +
      '<th>Class</th><th>Join Code</th></tr></thead><tbody>';
    rows.forEach(function (item) {
      html += '<tr><td class="font-semibold">' + (item.class_code || '?') + '</td>' +
        '<td><code class="text-primary">' + (item.join_code || '') + '</code></td></tr>';
    });
    html += '</tbody></table>';
    codesList.innerHTML = html;
    codesBox.style.display = 'block';
  }

  function enableJoinCodes(classIds, genBtn) {
    var codesError = getEl('cloneCodesError');
    var url = '/academic-years/enable-join-codes/';
    var body = new URLSearchParams();
    body.set('with_join_codes', '1');
    classIds.forEach(function (id) { body.append('class_ids', id); });

    if (genBtn) {
      genBtn.disabled = true;
      genBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
    }

    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCSRF(),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      },
      body: body.toString(),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (codesError) {
            codesError.style.display = 'block';
            codesError.textContent = res.data.error || 'Could not generate join codes.';
          }
          if (genBtn) {
            genBtn.disabled = false;
            genBtn.innerHTML = '<i class="fas fa-key"></i> Generate join codes for copied classes';
          }
          return;
        }
        if (codesError) codesError.style.display = 'none';
        renderJoinCodes(res.data.enabled || []);
        if (genBtn) genBtn.style.display = 'none';
      })
      .catch(function () {
        if (codesError) {
          codesError.style.display = 'block';
          codesError.textContent = 'Network error while generating join codes.';
        }
        if (genBtn) {
          genBtn.disabled = false;
          genBtn.innerHTML = '<i class="fas fa-key"></i> Generate join codes for copied classes';
        }
      });
  }

  function executeClone() {
    var source = getEl('cloneSource');
    var target = getEl('cloneTarget');
    var error = getEl('cloneError');
    var results = getEl('cloneResults');
    var summary = getEl('cloneSummary');
    var errorsBox = getEl('cloneErrors');
    var btn = getEl('cloneExecuteBtn');
    var modal = getEl('ayCloneModal');
    var withCodes = getEl('cloneWithCodes');
    var codesError = getEl('cloneCodesError');
    var codesBox = getEl('cloneCodesBox');
    var genBtn = getEl('cloneGenCodesBtn');
    var url = modal ? modal.getAttribute('data-clone-url') : '/academic-years/clone-classes/';

    var sourceId = source ? source.value : '';
    var targetId = target ? target.value : '';
    if (!sourceId || !targetId) {
      if (error) {
        error.style.display = 'block';
        error.textContent = 'Choose both a source term and a target term.';
      }
      return;
    }
    if (sourceId === targetId) {
      if (error) {
        error.style.display = 'block';
        error.textContent = 'Source and target terms must be different.';
      }
      return;
    }
    if (!confirmClone()) return;

    var generateCodes = !!(withCodes && withCodes.checked);

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cloning...';
    }
    if (error) error.style.display = 'none';
    if (results) results.style.display = 'none';
    if (codesError) codesError.style.display = 'none';
    if (codesBox) codesBox.style.display = 'none';
    if (genBtn) genBtn.style.display = 'none';

    var body = new URLSearchParams();
    body.set('source_year_id', sourceId);
    body.set('target_year_id', targetId);
    if (generateCodes) body.set('with_join_codes', '1');

    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCSRF(),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      },
      body: body.toString(),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (error) {
            error.style.display = 'block';
            error.textContent = res.data.error || 'Cloning failed.';
          }
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-copy"></i> Clone Classes';
          }
          return;
        }

        lastCloneMapping = res.data.class_mapping || [];
        var copied = res.data.copied_class_count || 0;
        var slots = res.data.copied_slot_count || 0;
        var failed = (res.data.errors || []).length;
        if (summary) {
          summary.innerHTML =
            '<i class="fas fa-circle-check"></i> ' +
            (res.data.message || ('Copied ' + copied + ' class(es) and ' + slots + ' slot(s).'));
        }
        if (errorsBox) {
          if (failed) {
            var html = '<p class="text-gold mb-1"><i class="fas fa-triangle-exclamation"></i> ' +
              failed + ' class(es) skipped or failed:</p><ul style="margin:0;padding-left:18px;">';
            res.data.errors.forEach(function (item) {
              html += '<li><strong>' + (item.class_code || '?') + '</strong>: ' +
                (item.reason || 'unknown reason') + '</li>';
            });
            html += '</ul>';
            errorsBox.innerHTML = html;
          } else {
            errorsBox.innerHTML = '';
          }
        }
        if (results) results.style.display = 'block';
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-copy"></i> Clone Again';
        }

        var codes = res.data.join_codes || [];
        if (res.data.join_codes_error) {
          if (codesError) {
            codesError.style.display = 'block';
            codesError.textContent = res.data.join_codes_error;
          }
          if (genBtn && lastCloneMapping.length) genBtn.style.display = 'inline-block';
        } else if (codes.length) {
          renderJoinCodes(codes);
        } else if (generateCodes && lastCloneMapping.length) {
          // Clone succeeded but no codes came back (e.g. all skipped).
          if (genBtn) genBtn.style.display = 'inline-block';
        }
      })
      .catch(function () {
        if (error) {
          error.style.display = 'block';
          error.textContent = 'Network error while cloning the class structure.';
        }
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-copy"></i> Clone Classes';
        }
      });
  }

  function copyJoinCodes() {
    var codesList = getEl('cloneCodesList');
    if (!codesList || !navigator.clipboard) return;
    var rows = codesList.querySelectorAll('tr');
    var lines = [];
    rows.forEach(function (tr, index) {
      if (index === 0) return; // header
      var cells = tr.querySelectorAll('td');
      if (cells.length >= 2) {
        lines.push(cells[0].textContent.trim() + ' — ' + cells[1].textContent.trim());
      }
    });
    if (lines.length) {
      navigator.clipboard.writeText(lines.join('\n'));
    }
  }

  function initClone() {
    var modal = getEl('ayCloneModal');
    if (!modal) return;
    var openBtn = getEl('cloneClassesBtn');
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        resetModal();
        if (App && App.showModal) App.showModal('ayCloneModal');
      });
    }
    var executeBtn = getEl('cloneExecuteBtn');
    if (executeBtn) {
      executeBtn.addEventListener('click', executeClone);
    }
    var genBtn = getEl('cloneGenCodesBtn');
    if (genBtn) {
      genBtn.addEventListener('click', function () {
        var ids = lastCloneMapping.map(function (item) { return item.target_class_id; });
        if (ids.length) enableJoinCodes(ids, genBtn);
      });
    }
    var copyBtn = getEl('copyJoinCodesBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', copyJoinCodes);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initClone);
  } else {
    initClone();
  }
})(window);
