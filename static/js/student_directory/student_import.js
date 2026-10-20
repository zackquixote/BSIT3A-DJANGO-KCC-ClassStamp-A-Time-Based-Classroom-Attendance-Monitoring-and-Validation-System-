/* KCC ClassStamp — Student Directory: Student Import CSV Dropzone & Controller */
(function (window) {
  'use strict';

  function initStudentImport() {
    var fileInput       = document.getElementById('csvFileInput');
    var filenameDisplay = document.getElementById('selectedFilename');
    var dropzone        = document.getElementById('dropzoneBox');
    var importForm      = document.getElementById('importForm');
    var submitBtn       = document.getElementById('submitBtn');

    if (fileInput && filenameDisplay) {
      fileInput.addEventListener('change', function () {
        if (this.files && this.files[0]) {
          filenameDisplay.style.display = 'block';
          var sizeKb = (this.files[0].size / 1024).toFixed(1);
          filenameDisplay.innerHTML = '<i class="fas fa-file-csv"></i> Selected: <strong>' + this.files[0].name + '</strong> (' + sizeKb + ' KB)';
        }
      });
    }

    if (dropzone) {
      ['dragenter', 'dragover'].forEach(function (eventName) {
        dropzone.addEventListener(eventName, function (e) {
          e.preventDefault();
          dropzone.classList.add('dragover');
        });
      });

      ['dragleave', 'drop'].forEach(function (eventName) {
        dropzone.addEventListener(eventName, function (e) {
          e.preventDefault();
          dropzone.classList.remove('dragover');
        });
      });
    }

    var progressWrap   = document.getElementById('importProgressWrap');
    var progressBar    = document.getElementById('importProgressBar');
    var progressStatus  = document.getElementById('progressStatusText');
    var progressPercent = document.getElementById('progressPercent');
    var progressSub    = document.getElementById('progressSubText');

    if (importForm && submitBtn) {
      importForm.addEventListener('submit', function () {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ingesting Roster... Please wait';

        if (progressWrap) progressWrap.style.display = 'block';

        var steps = [
          { pct: 20, status: 'Parsing CSV spreadsheet...', sub: 'Reading rows, columns, and validating encodings...', delay: 100 },
          { pct: 48, status: 'Validating student records...', sub: 'Checking student ID formats and collegiate programs...', delay: 380 },
          { pct: 76, status: 'Provisioning accounts...', sub: 'Generating 64-character dynamic QR credentials...', delay: 750 },
          { pct: 94, status: 'Writing atomic transaction...', sub: 'Committing roster entries to database...', delay: 1200 }
        ];

        steps.forEach(function (step) {
          setTimeout(function () {
            if (progressBar) progressBar.style.width = step.pct + '%';
            if (progressPercent) progressPercent.textContent = step.pct + '%';
            if (progressStatus) progressStatus.textContent = step.status;
            if (progressSub) progressSub.textContent = step.sub;
          }, step.delay);
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStudentImport);
  } else {
    initStudentImport();
  }
})(window);
