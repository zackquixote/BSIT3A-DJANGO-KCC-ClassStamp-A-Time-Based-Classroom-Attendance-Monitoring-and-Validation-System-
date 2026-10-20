/* KCC ClassStamp — Teacher Scanner: Audio Engine & Chimes */
(function (window) {
  'use strict';

  window.ScannerApp = window.ScannerApp || {};

  var audioContext = null;
  var isMuted = false;

  function initAudio() {
    if (!audioContext) {
      try {
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioCtx();
      } catch (e) {
        console.warn('Web Audio not supported');
      }
    }
    if (audioContext && audioContext.state === 'suspended') {
      audioContext.resume();
    }
  }

  function playTone(freq, duration, type) {
    if (isMuted || !audioContext) return;
    if (!type) type = 'sine';
    try {
      var osc = audioContext.createOscillator();
      var gain = audioContext.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioContext.currentTime);
      gain.gain.setValueAtTime(0.2, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioContext.destination);
      osc.start();
      osc.stop(audioContext.currentTime + duration);
    } catch (_) {}
  }

  function playChime(outcome) {
    initAudio();
    if (outcome === 'PRESENT') {
      playTone(880, 0.15, 'sine'); // High A
      setTimeout(function () { playTone(1320, 0.25, 'sine'); }, 120); // High E harmonic
    } else if (outcome === 'LATE') {
      playTone(660, 0.2, 'triangle');
      setTimeout(function () { playTone(550, 0.25, 'triangle'), 150; });
    } else {
      // Error / Duplicate Buzz
      playTone(220, 0.2, 'sawtooth');
      setTimeout(function () { playTone(180, 0.25, 'sawtooth'); }, 120);
    }
  }

  function initAudioControls() {
    var toggleAudioBtn = document.getElementById('toggleAudioBtn');
    var audioIcon = document.getElementById('audioIcon');
    var audioText = document.getElementById('audioText');
    if (toggleAudioBtn) {
      toggleAudioBtn.addEventListener('click', function () {
        isMuted = !isMuted;
        if (isMuted) {
          if (audioIcon) audioIcon.className = 'fas fa-volume-xmark text-muted';
          if (audioText) audioText.textContent = 'Audio Muted';
        } else {
          if (audioIcon) audioIcon.className = 'fas fa-volume-high text-gold';
          if (audioText) audioText.textContent = 'Audio On';
          initAudio();
          playTone(900, 0.1);
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAudioControls);
  } else {
    initAudioControls();
  }

  window.ScannerApp.initAudio = initAudio;
  window.ScannerApp.playTone = playTone;
  window.ScannerApp.playChime = playChime;
})(window);
