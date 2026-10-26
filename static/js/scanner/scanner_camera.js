/* KCC ClassStamp — Teacher Scanner: Camera & QR Controller */
(function (window) {
  'use strict';

  window.ScannerApp = window.ScannerApp || {};

  var html5QrCode = null;
  var isScanningPaused = false;
  var lastScannedPayload = null;
  var lastScanTimestamp = 0;
  var DEBOUNCE_MS = 2500;

  function onQrCodeScanned(payload) {
    var now = Date.now();
    if (payload === lastScannedPayload && (now - lastScanTimestamp < DEBOUNCE_MS)) {
      return;
    }

    lastScannedPayload = payload;
    lastScanTimestamp = now;

    var config = window.ScannerConfig || {};
    var postData = new FormData();
    postData.append('session_id', config.sessionId);
    postData.append('qr_payload', payload);

    var App = window.ScannerApp;
    if (App.beginLocalOp) App.beginLocalOp();

    fetch(config.scanApiUrl || '/teacher/session/scan/', {
      method: 'POST',
      headers: { 'X-CSRFToken': config.csrfToken },
      body: postData
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (App.endLocalOp) App.endLocalOp();
      if (data.status === 'success') {
        if (App.playChime) App.playChime(data.record_status);
        if (App.updateHeroCard) App.updateHeroCard(data);
        if (App.updateRosterRow) App.updateRosterRow(data);
        if (App.updateCounters) App.updateCounters(data.counts);
      } else {
        if (App.playChime) App.playChime('ERROR');
        if (App.showAlert) App.showAlert(data.error || 'Attendance validation error.');
      }
    })
    .catch(function () {
      if (App.endLocalOp) App.endLocalOp();
      if (App.playChime) App.playChime('ERROR');
      if (App.showAlert) App.showAlert('Network transmission error while processing stamp.');
    });
  }

  function startCameraWithId(cameraId) {
    if (!cameraId || isScanningPaused || !html5QrCode) return;
    var config = {
      fps: 10,
      qrbox: { width: 230, height: 230 },
      aspectRatio: 1.0
    };

    html5QrCode.start(
      cameraId,
      config,
      function (decodedText) {
        onQrCodeScanned(decodedText);
      },
      function () {
        // scan frame in progress
      }
    ).catch(function (err) {
      console.warn('Failed to start camera:', err);
    });
  }

  function initCameraScanner() {
    var config = window.ScannerConfig || {};
    if (!config.isOpen) return;

    if (typeof Html5Qrcode === 'undefined') {
      console.warn('Html5Qrcode library not loaded.');
      return;
    }

    html5QrCode = new Html5Qrcode('reader');

    Html5Qrcode.getCameras().then(function (cameras) {
      var cameraSelect = document.getElementById('cameraSelect');
      if (!cameraSelect) return;
      cameraSelect.innerHTML = '';

      if (cameras && cameras.length) {
        cameras.forEach(function (cam, idx) {
          var opt = document.createElement('option');
          opt.value = cam.id;
          opt.text = cam.label || ('Camera ' + (idx + 1));
          if (cam.label.toLowerCase().includes('back') || cam.label.toLowerCase().includes('rear')) {
            opt.selected = true;
          }
          cameraSelect.appendChild(opt);
        });

        startCameraWithId(cameraSelect.value);

        cameraSelect.addEventListener('change', function () {
          if (html5QrCode && html5QrCode.isScanning) {
            html5QrCode.stop().then(function () {
              startCameraWithId(cameraSelect.value);
            });
          } else {
            startCameraWithId(cameraSelect.value);
          }
        });
      } else {
        cameraSelect.innerHTML = '<option value="">No cameras detected</option>';
      }
    }).catch(function (err) {
      console.warn('Camera enumeration error:', err);
      if (window.ScannerApp.showAlert) {
        window.ScannerApp.showAlert('Camera access not allowed or unavailable. Use manual input below.');
      }
    });

    // Camera Pause / Resume Toggle
    var toggleCameraBtn = document.getElementById('toggleCameraBtn');
    var camBtnText = document.getElementById('camBtnText');
    if (toggleCameraBtn) {
      toggleCameraBtn.addEventListener('click', function () {
        if (!html5QrCode) return;
        if (html5QrCode.isScanning) {
          html5QrCode.stop().then(function () {
            isScanningPaused = true;
            if (camBtnText) camBtnText.textContent = 'Resume';
            toggleCameraBtn.innerHTML = '<i class="fas fa-play"></i> <span class="text-xs">Resume</span>';
          });
        } else {
          var cameraSelect = document.getElementById('cameraSelect');
          var camId = cameraSelect ? cameraSelect.value : null;
          if (camId) {
            isScanningPaused = false;
            if (camBtnText) camBtnText.textContent = 'Pause';
            toggleCameraBtn.innerHTML = '<i class="fas fa-pause"></i> <span class="text-xs">Pause</span>';
            startCameraWithId(camId);
          }
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCameraScanner);
  } else {
    initCameraScanner();
  }

  window.ScannerApp.onQrCodeScanned = onQrCodeScanned;
  window.ScannerApp.initCameraScanner = initCameraScanner;
})(window);
