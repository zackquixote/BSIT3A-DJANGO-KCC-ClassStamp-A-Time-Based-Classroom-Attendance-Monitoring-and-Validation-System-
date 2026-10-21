/* KCC ClassStamp — Core: Document & Image Lightbox Inspector (#7) */
(function (window) {
  'use strict';

  window.App = window.App || {};

  var LIGHTBOX_HTML =
    '<div id="appLightboxModal" class="modal app-lightbox-modal" role="dialog" aria-modal="true" aria-label="Document Lightbox" style="z-index:9999;">' +
    '  <div class="lightbox-toolbar">' +
    '    <div class="lightbox-title-wrap">' +
    '      <i class="fas fa-id-card text-gold" style="margin-right:8px;"></i>' +
    '      <span id="lightboxCaption" class="font-semibold text-primary" style="font-size:0.9rem;">Document Preview</span>' +
    '    </div>' +
    '    <div class="lightbox-tools">' +
    '      <button type="button" class="btn btn-outline btn-sm" id="lightboxRotateBtn" title="Rotate 90° Clockwise">' +
    '        <i class="fas fa-rotate-right"></i> Rotate' +
    '      </button>' +
    '      <button type="button" class="btn btn-outline btn-sm" id="lightboxZoomOutBtn" title="Zoom Out">' +
    '        <i class="fas fa-magnifying-glass-minus"></i>' +
    '      </button>' +
    '      <span id="lightboxZoomLevel" class="text-xs font-mono text-muted" style="min-width:44px;text-align:center;">100%</span>' +
    '      <button type="button" class="btn btn-outline btn-sm" id="lightboxZoomInBtn" title="Zoom In">' +
    '        <i class="fas fa-magnifying-glass-plus"></i>' +
    '      </button>' +
    '      <button type="button" class="btn btn-outline btn-sm" id="lightboxResetBtn" title="Reset">' +
    '        <i class="fas fa-arrows-rotate"></i>' +
    '      </button>' +
    '      <a href="#" target="_blank" class="btn btn-outline btn-sm" id="lightboxOpenTabBtn" title="Open original in new tab">' +
    '        <i class="fas fa-arrow-up-right-from-square"></i>' +
    '      </a>' +
    '      <button type="button" class="btn btn-danger btn-sm" id="lightboxCloseBtn" title="Close (Esc)">' +
    '        <i class="fas fa-xmark"></i>' +
    '      </button>' +
    '    </div>' +
    '  </div>' +
    '  <div class="lightbox-stage" id="lightboxStage">' +
    '    <img src="" id="lightboxImg" alt="Document Preview" class="lightbox-img">' +
    '  </div>' +
    '</div>';

  var currentScale = 1;
  var currentRotation = 0;

  function ensureLightbox() {
    var lb = document.getElementById('appLightboxModal');
    if (!lb) {
      document.body.insertAdjacentHTML('beforeend', LIGHTBOX_HTML);
      lb = document.getElementById('appLightboxModal');
      bindControls(lb);
    }
    return lb;
  }

  function applyTransform(img) {
    if (!img) return;
    img.style.transform = 'scale(' + currentScale + ') rotate(' + currentRotation + 'deg)';
    var zoomLabel = document.getElementById('lightboxZoomLevel');
    if (zoomLabel) zoomLabel.textContent = Math.round(currentScale * 100) + '%';
  }

  function bindControls(lb) {
    var img = lb.querySelector('#lightboxImg');
    var rotateBtn = lb.querySelector('#lightboxRotateBtn');
    var zoomInBtn = lb.querySelector('#lightboxZoomInBtn');
    var zoomOutBtn = lb.querySelector('#lightboxZoomOutBtn');
    var resetBtn = lb.querySelector('#lightboxResetBtn');
    var closeBtn = lb.querySelector('#lightboxCloseBtn');
    var stage = lb.querySelector('#lightboxStage');

    if (rotateBtn) {
      rotateBtn.addEventListener('click', function () {
        currentRotation = (currentRotation + 90) % 360;
        applyTransform(img);
      });
    }

    if (zoomInBtn) {
      zoomInBtn.addEventListener('click', function () {
        if (currentScale < 3.5) {
          currentScale = Math.min(3.5, currentScale + 0.25);
          applyTransform(img);
        }
      });
    }

    if (zoomOutBtn) {
      zoomOutBtn.addEventListener('click', function () {
        if (currentScale > 0.4) {
          currentScale = Math.max(0.4, currentScale - 0.25);
          applyTransform(img);
        }
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        currentScale = 1;
        currentRotation = 0;
        applyTransform(img);
      });
    }

    function closeLightbox() {
      lb.classList.remove('is-active');
      document.body.style.overflow = '';
      currentScale = 1;
      currentRotation = 0;
      applyTransform(img);
    }

    if (closeBtn) closeBtn.addEventListener('click', closeLightbox);

    if (stage) {
      stage.addEventListener('click', function (e) {
        if (e.target === stage) closeLightbox();
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && lb.classList.contains('is-active')) {
        closeLightbox();
      }
    });
  }

  function openLightbox(src, caption) {
    var lb = ensureLightbox();
    var img = lb.querySelector('#lightboxImg');
    var captionEl = lb.querySelector('#lightboxCaption');
    var openTabBtn = lb.querySelector('#lightboxOpenTabBtn');

    if (img) img.src = src;
    if (captionEl) captionEl.textContent = caption || 'Document Preview';
    if (openTabBtn) openTabBtn.href = src;

    currentScale = 1;
    currentRotation = 0;
    applyTransform(img);

    lb.classList.add('is-active');
    document.body.style.overflow = 'hidden';
  }

  // Delegated click handler on [data-lightbox] or .js-lightbox-trigger
  document.addEventListener('click', function (e) {
    var trigger = e.target.closest('[data-lightbox], .js-lightbox-trigger');
    if (!trigger) return;
    e.preventDefault();
    var src = trigger.getAttribute('data-lightbox') || trigger.getAttribute('href') || (trigger.tagName === 'IMG' ? trigger.src : '');
    var caption = trigger.getAttribute('data-caption') || trigger.getAttribute('title') || 'Document Preview';
    if (src) openLightbox(src, caption);
  });

  window.App.openLightbox = openLightbox;
})(window);
