/**
 * TradeFlow Buyer Dashboard — charts, timers, Supabase Realtime (opcional)
 */
(function (global) {
  'use strict';

  var navy = '#0F2A44';
  var blue = '#2E5B8A';
  var orange = '#F26522';
  var muted = '#6B7A88';

  function chartDefaults() {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.font.family = "'Montserrat', sans-serif";
    Chart.defaults.color = muted;
    Chart.defaults.plugins.legend.display = false;
  }

  function makeLine(el, labels, values) {
    if (!el || typeof Chart === 'undefined') return;
    return new Chart(el, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          borderColor: orange,
          backgroundColor: 'rgba(242,101,34,0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: orange,
        }],
      },
      options: {
        animation: { duration: 600 },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  function makeDoughnut(el, labels, values) {
    if (!el || typeof Chart === 'undefined') return;
    return new Chart(el, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: [orange, blue, navy, '#FFA15A', '#D1D5DB', '#c62828'],
          borderWidth: 0,
        }],
      },
      options: {
        animation: { duration: 500 },
        cutout: '68%',
      },
    });
  }

  function makeBar(el, labels, values) {
    if (!el || typeof Chart === 'undefined') return;
    return new Chart(el, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: blue,
          borderRadius: 6,
        }],
      },
      options: {
        animation: { duration: 500 },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  function initTimers() {
    document.querySelectorAll('[data-bp-plazo]').forEach(function (el) {
      function tick() {
        var end = new Date(el.getAttribute('data-bp-plazo'));
        var diff = end - new Date();
        if (diff <= 0) {
          el.textContent = el.getAttribute('data-expired-label') || 'Expirado';
          el.classList.add('warn');
          return;
        }
        var h = Math.floor(diff / 3600000);
        var m = Math.floor((diff % 3600000) / 60000);
        el.textContent = h + 'h ' + m + 'm';
        el.classList.toggle('warn', h < 6);
        el.classList.toggle('ok', h >= 6);
        setTimeout(tick, 30000);
      }
      tick();
    });
  }

  function initTransportTabs() {
    var tabs = document.querySelectorAll('[data-bp-mode]');
    var cards = document.querySelectorAll('[data-carrier-mode], .bp-carrier-card[data-carrier-mode]');
    if (!tabs.length) return;
    function filter(mode) {
      cards.forEach(function (c) {
        var m = c.getAttribute('data-carrier-mode');
        c.style.display = !mode || m === mode ? '' : 'none';
      });
    }
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('is-on'); });
        tab.classList.add('is-on');
        filter(tab.getAttribute('data-bp-mode') || '');
      });
    });
    var first = tabs[0];
    if (first) { first.classList.add('is-on'); filter(first.getAttribute('data-bp-mode')); }
  }

  function pollDashboard(url) {
    if (!url) return;
    setInterval(function () {
      fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.updated && global.TF && TF.notify) {
            TF.notify(data.message || 'Actualización', 'info');
          }
        })
        .catch(function () {});
    }, 60000);
  }

  function initRealtime() {
    var cfg = global.TF_SUPABASE;
    if (!cfg || !cfg.url || !cfg.anonKey || typeof global.supabase === 'undefined') return;
    try {
      var client = global.supabase.createClient(cfg.url, cfg.anonKey);
      client.channel('tf-orders')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'core_order' }, function () {
          if (global.TF && TF.notify) TF.notify(global.TF_I18N && TF_I18N.orderUpdated || 'Actualizado', 'info');
        })
        .subscribe();
    } catch (e) { /* Realtime opcional */ }
  }

  var api = {
    initDashboard: function (cfg) {
      chartDefaults();
      makeLine(document.getElementById('bp-chart-orders'), cfg.lineLabels || [], cfg.lineValues || []);
      makeDoughnut(document.getElementById('bp-chart-status'), cfg.statusLabels || [], cfg.statusValues || []);
      makeBar(document.getElementById('bp-chart-companies'), cfg.companyLabels || [], cfg.companyValues || []);
      pollDashboard(cfg.pollUrl);
    },
    initTimers: initTimers,
    initTransportTabs: initTransportTabs,
  };

  document.addEventListener('DOMContentLoaded', function () {
    initTimers();
    initTransportTabs();
    initRealtime();
  });

  global.TFBuyer = api;
})(window);
