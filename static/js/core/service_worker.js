(function () {
  'use strict';

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
        console.error('Unable to register the offline fallback:', error);
      });
    });
  }

  var banner;
  function showOfflineNotice() {
    if (!banner) {
      banner = document.createElement('div');
      banner.setAttribute('role', 'status');
      banner.setAttribute('aria-live', 'polite');
      banner.style.cssText = [
        'position:fixed',
        'z-index:2000',
        'left:12px',
        'right:12px',
        'bottom:12px',
        'padding:12px 16px',
        'border:1px solid rgba(245,184,46,.55)',
        'border-radius:10px',
        'background:#17243b',
        'color:#f8fafc',
        'box-shadow:0 8px 28px rgba(0,0,0,.35)',
        'font:500 14px/1.5 "Segoe UI",Arial,sans-serif'
      ].join(';');
      banner.textContent = 'Connection lost. Changes may not be saved until ClassStamp is back online.';
      document.body.appendChild(banner);
    }
  }

  function hideOfflineNotice() {
    if (banner) {
      banner.remove();
      banner = null;
    }
  }

  window.addEventListener('offline', showOfflineNotice);
  window.addEventListener('online', hideOfflineNotice);
  if (!navigator.onLine) showOfflineNotice();
})();
