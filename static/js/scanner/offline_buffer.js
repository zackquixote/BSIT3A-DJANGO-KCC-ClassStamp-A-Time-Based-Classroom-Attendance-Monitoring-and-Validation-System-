/* KCC ClassStamp — Teacher Scanner: Offline Scan Buffer (T-12)
 *
 * Queues scans in IndexedDB when the network is unavailable and re-sends them
 * once connectivity returns. Server rejections (4xx except 429) are terminal —
 * e.g. an expired TOTP token can never become valid again — so those entries
 * are dropped instead of retried forever.
 */
(function (window) {
  'use strict';

  var DB_NAME = 'classstamp-offline';
  var DB_VERSION = 1;
  var STORE = 'pending_scans';
  var dbPromise = null;
  var flushing = false;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      if (!('indexedDB' in window)) {
        reject(new Error('IndexedDB unavailable'));
        return;
      }
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
    return dbPromise;
  }

  function storeOp(mode, fn) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, mode);
        var result = fn(tx.objectStore(STORE));
        tx.oncomplete = function () { resolve(result); };
        tx.onerror = function () { reject(tx.error); };
        tx.onabort = function () { reject(tx.error); };
      });
    });
  }

  function updatePendingBadge() {
    return storeOp('readonly', function (store) {
      var req = store.count();
      req.onsuccess = function () {
        var badge = document.getElementById('offlinePendingBadge');
        if (!badge) return;
        if (req.result > 0) {
          badge.style.display = 'inline-flex';
          badge.textContent = req.result + ' queued offline';
        } else {
          badge.style.display = 'none';
        }
      };
    });
  }

  function enqueue(scan) {
    return storeOp('readwrite', function (store) {
      store.add({
        session_id: scan.session_id,
        qr_payload: scan.qr_payload,
        queued_at: Date.now()
      });
    }).then(updatePendingBadge);
  }

  function flush() {
    if (flushing || !navigator.onLine) return Promise.resolve();
    flushing = true;

    var config = window.ScannerConfig || {};
    var App = window.ScannerApp || {};
    var url = config.scanApiUrl || '/teacher/session/scan/';

    return storeOp('readonly', function (store) {
      return new Promise(function (resolve) {
        var all = [];
        var cursorReq = store.openCursor();
        cursorReq.onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor) {
            all.push({ id: cursor.key, entry: cursor.value });
            cursor.continue();
          } else {
            resolve(all);
          }
        };
      });
    }).then(function (items) {
      var chain = Promise.resolve();
      items.forEach(function (item) {
        chain = chain.then(function () {
          return sendOne(url, config, item).then(function (dropped) {
            if (dropped) return removeOne(item.id);
            return Promise.resolve();
          });
        });
      });
      return chain;
    }).then(function () {
      flushing = false;
      return updatePendingBadge();
    }).catch(function () {
      flushing = false;
      return updatePendingBadge();
    });
  }

  // Resolves true when the entry should be removed permanently.
  function sendOne(url, config, item) {
    var postData = new FormData();
    postData.append('session_id', item.entry.session_id);
    postData.append('qr_payload', item.entry.qr_payload);

    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': config.csrfToken },
      body: postData
    })
    .then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    })
    .then(function (result) {
      var App = window.ScannerApp || {};
      if (result.data.status === 'success') {
        if (App.playChime) App.playChime(result.data.record_status);
        if (App.updateHeroCard) App.updateHeroCard(result.data);
        if (App.updateRosterRow) App.updateRosterRow(result.data);
        if (App.updateCounters) App.updateCounters(result.data.counts);
        return true;
      }
      if (result.status === 429) return false; // rate-limited: retry later
      // Server rejection is terminal (expired token, closed session, etc.)
      if (App.showAlert) {
        App.showAlert('Queued scan dropped: ' + (result.data.error || 'rejected by server'));
      }
      return true;
    })
    .catch(function () {
      return false; // still offline: keep queued
    });
  }

  function removeOne(id) {
    return storeOp('readwrite', function (store) {
      store.delete(id);
    });
  }

  function init() {
    window.addEventListener('online', function () {
      flush();
    });

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        setTimeout(function () {
          updatePendingBadge();
          flush();
        }, 1500);
      });
    } else {
      setTimeout(function () {
        updatePendingBadge();
        flush();
      }, 1500);
    }
  }

  init();

  var buffer = {
    enqueue: enqueue,
    flush: flush,
    updatePendingBadge: updatePendingBadge
  };
  window.ScannerApp = window.ScannerApp || {};
  window.ScannerApp.OfflineBuffer = buffer;
})(window);
