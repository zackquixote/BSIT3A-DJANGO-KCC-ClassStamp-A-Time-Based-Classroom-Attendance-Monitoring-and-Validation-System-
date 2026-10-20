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

    if (importForm && submitBtn) {
      importForm.addEventListener('submit', function () {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ingesting Roster... Please wait';
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStudentImport);
  } else {
    initStudentImport();
  }
})(window);
