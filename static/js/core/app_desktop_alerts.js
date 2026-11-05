(function () {
  'use strict';

  const FLAG = 'kcc_desktop_alerts';
  const SEEN = 'kcc_desktop_alerts_seen';
  const POLL_MS = 60000;
  const MAX_PER_TICK = 3;

  function granted() {
    return 'Notification' in window && Notification.permission === 'granted';
  }

  function isActive() {
    return localStorage.getItem(FLAG) === '1' && granted();
  }

  async function registration() {
    if (!('serviceWorker' in navigator)) return null;
    return navigator.serviceWorker.getRegistration() || null;
  }

  async function alert(row) {
    const options = {
      body: row.message,
      tag: 'classstamp-' + row.id,
      icon: '/static/img/kcc_logo.png',
      badge: '/static/img/kcc_logo.png',
      data: {url: row.link},
    };
    const sw = await registration();
    if (sw) {
      // Routed through the worker so its notificationclick handler can open the link.
      sw.showNotification(row.title, options);
    } else {
      new Notification(row.title, options);
    }
  }

  async function unread() {
    const response = await fetch('/api/notifications/unread/', {credentials: 'same-origin'});
    if (!response.ok) return [];
    return (await response.json()).notifications || [];
  }

  async function poll() {
    if (!isActive() || document.hidden) return;
    let rows;
    try {
      rows = await unread();
    } catch (error) {
      return;
    }
    const seen = Number(localStorage.getItem(SEEN) || 0);
    const fresh = rows.filter((row) => row.id > seen).sort((a, b) => a.id - b.id);
    if (!fresh.length) return;
    localStorage.setItem(SEEN, String(fresh[fresh.length - 1].id));
    const shown = fresh.slice(0, MAX_PER_TICK);
    shown.forEach((row, index) => {
      if (index === shown.length - 1 && fresh.length > shown.length) {
        row.message += ' (+' + (fresh.length - shown.length) + ' pa)';
      }
      alert(row);
    });
  }

  // Seeded on enable so the backlog already sitting in the bell stays quiet.
  async function markBacklogSeen() {
    try {
      const rows = await unread();
      const newest = rows.reduce((max, row) => Math.max(max, row.id), 0);
      localStorage.setItem(SEEN, String(newest));
    } catch (error) {
      localStorage.setItem(SEEN, '0');
    }
  }

  function paint(button) {
    if (!button) return;
    const on = isActive();
    button.dataset.desktopAlerts = on ? 'on' : 'off';
    button.textContent = on ? 'Desktop alerts: ON' : 'Enable desktop alerts';
  }

  async function toggle(button) {
    if (isActive()) {
      localStorage.setItem(FLAG, '0');
      paint(button);
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      if (button) button.textContent = 'Blocked by browser settings';
      return;
    }
    await markBacklogSeen();
    localStorage.setItem(FLAG, '1');
    paint(button);
    poll();
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-desktop-alerts-toggle]');
    if (button) {
      event.preventDefault();
      toggle(button);
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    paint(document.querySelector('[data-desktop-alerts-toggle]'));
    if (!isActive()) return;
    setInterval(poll, POLL_MS);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) poll();
    });
  });
})();
