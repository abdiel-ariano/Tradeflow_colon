/**
 * TradeFlow Seller Portal — charts, timers, polling
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

  function lineChart(el, labels, values, color) {
    if (!el || typeof Chart === 'undefined') return;
    return new Chart(el, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          borderColor: color || orange,
          backgroundColor: 'rgba(242,101,34,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
        }],
      },
      options: {
        animation: { duration: 550 },
        scales: { y: { beginAtZero: true }, x: { grid: { display: false } } },
      },
    });
  }

  function doughnutChart(el, labels, values) {
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
      options: { cutout: '65%', animation: { duration: 500 } },
    });
  }

  function barChart(el, labels, values) {
    if (!el || typeof Chart === 'undefined') return;
    return new Chart(el, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{ data: values, backgroundColor: blue, borderRadius: 6 }],
      },
      options: { scales: { y: { beginAtZero: true } }, animation: { duration: 500 } },
    });
  }

  function initTimers() {
    document.querySelectorAll('[data-sp-plazo]').forEach(function (el) {
      function tick() {
        var end = new Date(el.getAttribute('data-sp-plazo'));
        var diff = end - new Date();
        if (diff <= 0) {
          el.textContent = el.getAttribute('data-expired') || 'Expirado';
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

  function bindConfirmLinks() {
    document.querySelectorAll('.sp-confirm-orden').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        var href = link.href;
        var accion = link.dataset.accion;
        var num = link.dataset.num || '';
        if (!global.TF || !TF.confirm) {
          window.location.href = href;
          return;
        }
        TF.confirm({
          titulo: accion === 'aceptar' ? 'Aceptar pedido' : 'Rechazar pedido',
          mensaje: (accion === 'aceptar' ? '¿Aceptas ' : '¿Rechazas ') + num + '?',
          onAceptar: function () { window.location.href = href; },
        });
      });
    });
  }

  function poll(url) {
    if (!url) return;
    setInterval(function () {
      fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.updated && global.TF && TF.notify) TF.notify('Actualización', 'info');
        })
        .catch(function () {});
    }, 90000);
  }

  global.TFSeller = {
    initPortal: function (cfg) {
      chartDefaults();
      lineChart(document.getElementById('sp-chart-revenue'), cfg.revenueLabels, cfg.revenueValues, orange);
      lineChart(document.getElementById('sp-chart-week'), cfg.weekLabels, cfg.weekOrders, blue);
      doughnutChart(document.getElementById('sp-chart-status'), cfg.statusLabels, cfg.statusValues);
      barChart(document.getElementById('sp-chart-cat'), cfg.catLabels, cfg.catValues);
      poll(cfg.pollUrl);
    },
    initTimers: initTimers,
    bindConfirmLinks: bindConfirmLinks,
  };

  document.addEventListener('DOMContentLoaded', function () {
    initTimers();
    bindConfirmLinks();
  });
})(window);
