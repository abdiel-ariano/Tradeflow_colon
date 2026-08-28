(function () {
  'use strict';

  var shell = document.getElementById('adm-companies-shell');
  if (!shell) return;

  var watchUrl = shell.getAttribute('data-pending-watch-url');
  if (!watchUrl) return;

  var alertEl = document.getElementById('adm-companies-new-alert');
  var alertText = alertEl ? alertEl.querySelector('.adm-companies-new-alert__text') : null;
  var dismissBtn = alertEl ? alertEl.querySelector('.adm-companies-new-alert__dismiss') : null;
  var railBadge = document.querySelector('[data-adm-nav="empresas"] .adm-rail-badge');

  var knownKeys = new Set();
  var inFlight = false;
  var stopped = false;
  var initialized = false;
  var intervalMs = 15000;
  var timerId = null;
  var userInteracting = false;

  function submissionKey(item) {
    return String(item.id) + ':' + (item.submitted_at || '');
  }

  function updateRailBadge(count) {
    if (!railBadge) {
      var link = document.querySelector('[data-adm-nav="empresas"]');
      if (!link || !count) return;
      railBadge = document.createElement('span');
      railBadge.className = 'adm-rail-badge';
      link.appendChild(railBadge);
    }
    if (!count) {
      if (railBadge && railBadge.parentNode) railBadge.parentNode.removeChild(railBadge);
      railBadge = null;
      return;
    }
    railBadge.textContent = String(count);
  }

  function showNewAlert(count, names) {
    if (!alertEl || !alertText) return;
    var label = count === 1
      ? '1 nueva solicitud pendiente: ' + names[0]
      : count + ' nuevas solicitudes pendientes';
    alertText.textContent = label;
    alertEl.hidden = false;
  }

  function poll() {
    if (stopped || inFlight || document.hidden || userInteracting) return;
    inFlight = true;
    fetch(watchUrl, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
      .then(function (resp) {
        if (resp.status === 401 || resp.status === 403) {
          stopped = true;
          return null;
        }
        if (!resp.ok) throw new Error('watch_failed');
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        updateRailBadge(data.pending_count);

        var submissions = data.submissions || [];
        if (!initialized) {
          submissions.forEach(function (item) {
            knownKeys.add(submissionKey(item));
          });
          initialized = true;
          return;
        }

        var fresh = [];
        submissions.forEach(function (item) {
          var key = submissionKey(item);
          if (!knownKeys.has(key)) {
            fresh.push(item);
            knownKeys.add(key);
          }
        });

        if (fresh.length) {
          showNewAlert(
            fresh.length,
            fresh.map(function (item) { return item.name; }),
          );
        }

        intervalMs = 15000;
      })
      .catch(function () {
        intervalMs = Math.min(intervalMs * 2, 60000);
      })
      .finally(function () {
        inFlight = false;
        schedule();
      });
  }

  function schedule() {
    if (stopped) return;
    clearTimeout(timerId);
    timerId = setTimeout(poll, intervalMs);
  }

  function markInteracting() {
    userInteracting = true;
    clearTimeout(timerId);
    setTimeout(function () {
      userInteracting = false;
      schedule();
    }, 8000);
  }

  if (dismissBtn) {
    dismissBtn.addEventListener('click', function () {
      if (alertEl) alertEl.hidden = true;
    });
  }

  var table = document.getElementById('adm-companies-table');
  if (table) {
    table.addEventListener('focusin', markInteracting);
    table.addEventListener('pointerdown', markInteracting);
  }

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) poll();
  });

  poll();
})();
