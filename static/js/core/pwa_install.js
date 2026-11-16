/* KCC ClassStamp — PWA "Install app" affordance
 *
 * Chrome/Edge (Android + desktop) fire `beforeinstallprompt` once the manifest,
 * the service worker and HTTPS are in place. We hold that event and show our own
 * button, so the install offer is visible instead of buried in the browser menu.
 *
 * iOS never fires the event: Safari only offers Share → Add to Home Screen, so
 * the button opens a short instruction sheet there instead.
 *
 * The chip stays out of the way: it is dismissible, remembered for 30 days, and
 * hidden entirely in in-app browsers (Messenger, Instagram, …) that cannot
 * install a PWA, and once the app already runs standalone.
 */
(function (window, document) {
  'use strict';

  var DISMISS_KEY = 'kcc_pwa_install_dismissed_at';
  var DISMISS_DAYS = 30;
  var deferredPrompt = null;
  var host = null;
  var styleInjected = false;

  function standalone() {
    return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
      window.navigator.standalone === true;
  }

  function isIos() {
    var ua = window.navigator.userAgent || '';
    return /iPad|iPhone|iPod/.test(ua) ||
      (window.navigator.platform === 'MacIntel' && window.navigator.maxTouchPoints > 1);
  }

  function isInAppBrowser() {
    var ua = window.navigator.userAgent || '';
    return /FBAN|FBAV|FB_IAB|Instagram|Messenger|Line\/|Twitter|Telegram/i.test(ua);
  }

  function recentlyDismissed() {
    try {
      var raw = window.localStorage.getItem(DISMISS_KEY);
      if (!raw) { return false; }
      var age = Date.now() - parseInt(raw, 10);
      return age < DISMISS_DAYS * 24 * 60 * 60 * 1000;
    } catch (error) {
      return false;
    }
  }

  function rememberDismiss() {
    try { window.localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (error) { /* private mode */ }
  }

  function injectStyle() {
    if (styleInjected) { return; }
    styleInjected = true;
    var style = document.createElement('style');
    style.textContent = [
      // A top-centred pill, so it reads like a notification instead of a floating
      // button that covers the form. On app pages it drops below the sticky header.
      '.kcc-install{position:fixed;left:50%;transform:translateX(-50%);z-index:1400;display:flex;align-items:center;gap:6px;',
      'top:calc(env(safe-area-inset-top, 0px) + 12px);max-width:calc(100vw - 24px);',
      'padding:6px 6px 6px 8px;border-radius:999px;border:1px solid rgba(245,158,11,0.45);',
      'background:rgba(15,23,42,0.94);box-shadow:0 10px 24px rgba(0,0,0,0.45);backdrop-filter:blur(6px);',
      'animation:kccInstallDrop 0.32s ease-out;}',
      'html:not(.kcc-auth-html) .kcc-install{top:calc(env(safe-area-inset-top, 0px) + 72px);}',
      '@keyframes kccInstallDrop{from{opacity:0;transform:translate(-50%,-10px);}to{opacity:1;transform:translate(-50%,0);}}',
      '@media (prefers-reduced-motion: reduce){.kcc-install{animation:none;}}',
      '.kcc-install-btn{display:inline-flex;align-items:center;gap:8px;border:0;background:transparent;',
      'white-space:nowrap;',
      'color:#f8fafc;font-size:0.8rem;font-weight:600;padding:6px 10px;border-radius:999px;cursor:pointer;}',
      '.kcc-install-btn:hover{background:rgba(245,158,11,0.14);}',
      '.kcc-install-btn i{color:#f5c518;}',
      '.kcc-install-close{border:0;background:transparent;color:rgba(226,232,240,0.6);font-size:1rem;',
      'line-height:1;padding:2px 8px;border-radius:999px;cursor:pointer;}',
      '.kcc-install-close:hover{color:#fff;background:rgba(255,255,255,0.08);}',
      // The login page starts with the KCC seal, so the pill gets its own strip of
      // space instead of floating on top of the logo.
      'body.kcc-auth-page.kcc-install-active{padding-top:56px;}',
      '@media (max-width:900px){.kcc-install{top:calc(env(safe-area-inset-top, 0px) + 10px);}}',
      '@media (max-width:900px){html:not(.kcc-auth-html) .kcc-install{top:calc(env(safe-area-inset-top, 0px) + 64px);}}',
      '.kcc-install-sheet{position:fixed;inset:0;z-index:2001;display:flex;align-items:flex-end;',
      'justify-content:center;background:rgba(2,6,23,0.72);padding:18px;}',
      '.kcc-install-sheet__card{width:min(420px,100%);background:#111c31;border:1px solid rgba(255,255,255,0.12);',
      'border-radius:16px;padding:18px 18px 14px;color:#e2e8f0;box-shadow:0 18px 50px rgba(0,0,0,0.5);}',
      '.kcc-install-sheet__card h3{margin:0 0 8px;font-size:1rem;color:#fff;}',
      '.kcc-install-sheet__card ol{margin:0 0 14px 18px;padding:0;font-size:0.86rem;line-height:1.6;}',
      '.kcc-install-sheet__card button{width:100%;border:0;border-radius:10px;padding:10px 12px;',
      'background:#f5c518;color:#0f172a;font-weight:700;cursor:pointer;}'
    ].join('');
    document.head.appendChild(style);
  }

  function remove() {
    if (host && host.parentNode) { host.parentNode.removeChild(host); }
    host = null;
    document.body.classList.remove('kcc-install-active');
  }

  function show(label, onActivate) {
    if (host || standalone() || recentlyDismissed()) { return; }
    injectStyle();
    host = document.createElement('div');
    host.className = 'kcc-install';
    host.setAttribute('role', 'region');
    host.setAttribute('aria-label', 'Install KCC ClassStamp');

    var action = document.createElement('button');
    action.type = 'button';
    action.className = 'kcc-install-btn';
    action.innerHTML = '<i class="fas fa-download" aria-hidden="true"></i><span></span>';
    action.querySelector('span').textContent = label;
    action.addEventListener('click', onActivate);

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'kcc-install-close';
    close.setAttribute('aria-label', 'Dismiss install prompt');
    close.innerHTML = '&times;';
    close.addEventListener('click', function () { rememberDismiss(); remove(); });

    host.appendChild(action);
    host.appendChild(close);
    document.body.appendChild(host);
    document.body.classList.add('kcc-install-active');
  }

  function showIosInstructions() {
    injectStyle();
    var sheet = document.createElement('div');
    sheet.className = 'kcc-install-sheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.innerHTML =
      '<div class="kcc-install-sheet__card">' +
      '<h3>Install KCC ClassStamp</h3>' +
      '<ol><li>Tap the <strong>Share</strong> button in Safari.</li>' +
      '<li>Choose <strong>Add to Home Screen</strong>.</li>' +
      '<li>Tap <strong>Add</strong> — the app opens like a native one.</li></ol>' +
      '<button type="button">Got it</button></div>';
    sheet.querySelector('button').addEventListener('click', function () {
      sheet.parentNode.removeChild(sheet);
    });
    sheet.addEventListener('click', function (event) {
      if (event.target === sheet) { sheet.parentNode.removeChild(sheet); }
    });
    document.body.appendChild(sheet);
  }

  // Chrome / Edge / Samsung Internet: the browser tells us it can install.
  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredPrompt = event;
    if (isInAppBrowser() || standalone()) { return; }
    show('Install ClassStamp', function () {
      if (!deferredPrompt) { return; }
      deferredPrompt.prompt();
      var choice = deferredPrompt.userChoice;
      if (choice && typeof choice.then === 'function') {
        choice.then(function (result) {
          if (result && result.outcome === 'accepted') { remove(); }
        });
      }
      deferredPrompt = null;
    });
  });

  window.addEventListener('appinstalled', function () {
    rememberDismiss();
    remove();
  });

  // iOS has no install event at all — offer the Share → Add to Home Screen steps.
  if (isIos() && !isInAppBrowser() && !standalone()) {
    show('Install app', showIosInstructions);
  }
})(window, document);
