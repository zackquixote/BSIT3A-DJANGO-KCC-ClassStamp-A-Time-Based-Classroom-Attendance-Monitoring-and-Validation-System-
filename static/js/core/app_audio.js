/* KCC ClassStamp — Core: Universal Web Audio Engine (Chimes & Feedback) */
(function (window) {
  'use strict';

  window.App = window.App || {};

  var audioCtx = null;

  /* ── Universal Web Audio Tone Synthesizer ─────────────────────── */
  window.App.playTone = function (freq, duration, type) {
    type = type || 'sine';
    duration = duration || 0.2;
    try {
      if (!audioCtx) {
        var AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) audioCtx = new AudioContextClass();
      }
      if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      if (!audioCtx) return;

      var osc = audioCtx.createOscillator();
      var gain = audioCtx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + duration);
    } catch (_) {}
  };

  /* ── Harmonic QR Validation Chime Synthesizer ────────────────── */
  window.App.playChime = function (outcome) {
    outcome = (outcome || '').toUpperCase();
    if (outcome === 'PRESENT' || outcome === 'SUCCESS') {
      window.App.playTone(880, 0.15, 'sine');
      setTimeout(function () { window.App.playTone(1320, 0.25, 'sine'); }, 110);
      if (navigator.vibrate) navigator.vibrate(80);
    } else if (outcome === 'LATE' || outcome === 'WARNING') {
      window.App.playTone(660, 0.18, 'triangle');
      setTimeout(function () { window.App.playTone(550, 0.22, 'triangle'); }, 130);
      if (navigator.vibrate) navigator.vibrate([60, 40, 60]);
    } else {
      window.App.playTone(220, 0.22, 'sawtooth');
      setTimeout(function () { window.App.playTone(180, 0.25, 'sawtooth'); }, 110);
      if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
    }
  };
})(window);
