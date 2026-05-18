/**
 * TradeFlow Colón — inicialización Chart.js del panel admin (/dashboard/).
 * Lee payload desde #adm-charts-initial (json_script de Django).
 */
(function () {
  'use strict';

  function showChartsError(msg) {
    var el = document.getElementById('adm-charts-error');
    if (!el) return;
    if (msg) el.textContent = msg;
    el.classList.add('is-visible');
  }

  function hideChartsError() {
    var el = document.getElementById('adm-charts-error');
    if (el) el.classList.remove('is-visible');
  }

  function emptyPayload(len) {
    var n = len || 7;
    var labels = [];
    var i;
    for (i = 0; i < n; i += 1) labels.push('');
    return {
      chart_labels: labels,
      ordenes_por_dia: Array(n).fill(0),
      ingresos_por_dia: Array(n).fill(0),
      estados_data: { pending: 0, paid: 0, shipped: 0, delivered: 0, cancelled: 0 },
      ventas_por_categoria: [],
      ventas_por_empresa: [],
      productos_top: [],
      ordenes_por_tipo: { b2b: 0, b2c: 0 },
    };
  }

  function payloadLooksValid(p) {
    if (!p || !Array.isArray(p.chart_labels)) return false;
    var n = p.chart_labels.length;
    if (n < 1) return false;
    return (
      Array.isArray(p.ordenes_por_dia) && p.ordenes_por_dia.length === n &&
      Array.isArray(p.ingresos_por_dia) && p.ingresos_por_dia.length === n
    );
  }

  function parseInitialPayload(pillsRoot) {
    var diasDefault = 7;
    if (pillsRoot) {
      var dAttr = parseInt(pillsRoot.getAttribute('data-dias-activo'), 10);
      if (dAttr === 7 || dAttr === 30 || dAttr === 90) diasDefault = dAttr;
    }
    var raw = document.getElementById('adm-charts-initial');
    if (!raw || !raw.textContent) {
      return { payload: emptyPayload(diasDefault), ok: false, reason: 'missing-script' };
    }
    try {
      var parsed = JSON.parse(raw.textContent);
      if (payloadLooksValid(parsed)) {
        return { payload: parsed, ok: true };
      }
      return { payload: emptyPayload(diasDefault), ok: false, reason: 'invalid-shape' };
    } catch (e) {
      return { payload: emptyPayload(diasDefault), ok: false, reason: 'parse-error' };
    }
  }

  function i18n(key, fallback) {
    var bag = window.TF_I18N || {};
    return bag[key] || fallback;
  }

  function boot() {
    if (typeof Chart === 'undefined') {
      showChartsError(i18n('chartLoadError', 'No se pudo cargar Chart.js. Recarga la página.'));
      return;
    }

    var pillsRoot = document.getElementById('adm-dias-pills');
    var parsed = parseInitialPayload(pillsRoot);
    if (!parsed.ok) {
      showChartsError(i18n('chartDataError', 'Datos de gráficos incompletos. Recarga o cambia el período (7/30/90).'));
    } else {
      hideChartsError();
    }

    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var animDuration = reduced ? 0 : 400;

    var catColors = ['#F26522', '#2E5B8A', '#1B3B63', '#FF7A3D', '#6B7A88', '#FFA15A'];
    var estadoLabels = [
      i18n('chartPending', 'Pendiente'),
      i18n('chartPaid', 'Pagado'),
      i18n('chartShipped', 'Enviado'),
      i18n('chartDelivered', 'Entregado'),
      i18n('chartCancelled', 'Cancelado'),
    ];
    var estadoColors = ['#FEF3C7', '#DBEAFE', '#D1FAE5', '#065F46', '#FEE2E2'];
    var estadoKeys = ['pending', 'paid', 'shipped', 'delivered', 'cancelled'];

    function estadosSeries(ed) {
      return estadoKeys.map(function (k) {
        var v = ed && ed[k] !== undefined && ed[k] !== null ? Number(ed[k]) : 0;
        return isNaN(v) ? 0 : v;
      });
    }

    function sumArr(a) {
      return a.reduce(function (s, v) { return s + Number(v || 0); }, 0);
    }

    function createLineGradient(ctx) {
      var g = ctx.createLinearGradient(0, 0, 0, 240);
      g.addColorStop(0, 'rgba(46, 91, 138, 0.35)');
      g.addColorStop(1, 'rgba(46, 91, 138, 0.02)');
      return g;
    }

    function toggleEmpty(el, canvasWrap, showEmptyMsg) {
      if (el) el.classList.toggle('is-visible', showEmptyMsg);
      if (canvasWrap) canvasWrap.style.display = showEmptyMsg ? 'none' : 'block';
    }

    var barChart = null;
    var lineChart = null;
    var doughnutChart = null;
    var catChart = null;
    var empChart = null;
    var prodChart = null;

    function destroyCharts() {
      [barChart, lineChart, doughnutChart, catChart, empChart, prodChart].forEach(function (c) {
        if (c) c.destroy();
      });
      barChart = lineChart = doughnutChart = catChart = empChart = prodChart = null;
    }

    function updateMetaTipo(tipo) {
      var b2b = document.getElementById('adm-meta-b2b');
      var b2c = document.getElementById('adm-meta-b2c');
      if (!tipo) return;
      if (b2b) b2b.textContent = String(tipo.b2b || 0);
      if (b2c) b2c.textContent = String(tipo.b2c || 0);
    }

    function chartBaseOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: animDuration },
      };
    }

    function createCharts(payload) {
      destroyCharts();
      var labels = payload.chart_labels || [];
      var ordenesDia = (payload.ordenes_por_dia || []).map(function (v) { return Number(v || 0); });
      var ingresosDia = (payload.ingresos_por_dia || []).map(function (v) { return Number(v || 0); });
      var ed = payload.estados_data || {};
      var estVals = estadosSeries(ed);

      var barCtx = document.getElementById('admBarChart');
      if (barCtx) {
        try {
          barChart = new Chart(barCtx, {
            type: 'bar',
            data: {
              labels: labels,
              datasets: [{
                label: i18n('chartOrders', 'Órdenes'),
                data: ordenesDia,
                backgroundColor: '#F26522',
                borderRadius: 6,
              }],
            },
            options: Object.assign({}, chartBaseOptions(), {
              plugins: { legend: { display: false } },
              scales: {
                x: { grid: { display: false }, ticks: { color: '#6B7A88', maxRotation: 45 } },
                y: {
                  beginAtZero: true,
                  ticks: { precision: 0, color: '#6B7A88' },
                  grid: { color: 'rgba(209,213,219,0.6)' },
                },
              },
            }),
          });
        } catch (e) {
          showChartsError('Error al dibujar gráfico de órdenes: ' + e.message);
        }
      }

      var lineCtx = document.getElementById('admLineChart');
      if (lineCtx) {
        try {
          var lCtx = lineCtx.getContext('2d');
          lineChart = new Chart(lineCtx, {
            type: 'line',
            data: {
              labels: labels,
              datasets: [{
                label: i18n('chartUsd', 'USD'),
                data: ingresosDia,
                borderColor: '#0F2A44',
                backgroundColor: createLineGradient(lCtx),
                fill: true,
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
              }],
            },
            options: Object.assign({}, chartBaseOptions(), {
              plugins: { legend: { display: false } },
              scales: {
                x: { ticks: { color: '#6B7A88', maxRotation: 45 } },
                y: {
                  beginAtZero: true,
                  ticks: {
                    color: '#6B7A88',
                    callback: function (v) { return 'US$' + Number(v).toFixed(0); },
                  },
                },
              },
            }),
          });
        } catch (e) {
          showChartsError('Error al dibujar gráfico de ingresos: ' + e.message);
        }
      }

      var donutCtx = document.getElementById('admDoughnutChart');
      var totalEst = sumArr(estVals);
      toggleEmpty(
        document.getElementById('adm-doughnut-empty'),
        donutCtx ? donutCtx.parentElement : null,
        totalEst === 0
      );
      if (donutCtx && totalEst > 0) {
        doughnutChart = new Chart(donutCtx, {
          type: 'doughnut',
          data: {
            labels: estadoLabels,
            datasets: [{ data: estVals, backgroundColor: estadoColors, borderWidth: 2, borderColor: '#fff' }],
          },
          options: Object.assign({}, chartBaseOptions(), {
            plugins: { legend: { position: 'bottom', labels: { color: '#374151', font: { size: 11 } } } },
          }),
        });
      }

      var cats = payload.ventas_por_categoria || [];
      var catCtx = document.getElementById('admCatDoughnut');
      toggleEmpty(document.getElementById('adm-cat-empty'), catCtx ? catCtx.parentElement : null, cats.length === 0);
      if (catCtx && cats.length) {
        catChart = new Chart(catCtx, {
          type: 'doughnut',
          data: {
            labels: cats.map(function (c) { return c.label; }),
            datasets: [{
              data: cats.map(function (c) { return Number(c.pct || 0); }),
              backgroundColor: catColors.slice(0, cats.length),
              borderWidth: 2,
              borderColor: '#fff',
            }],
          },
          options: Object.assign({}, chartBaseOptions(), {
            plugins: { legend: { position: 'bottom', labels: { font: { size: 10 } } } },
          }),
        });
      }

      var emps = payload.ventas_por_empresa || [];
      var empCtx = document.getElementById('admEmpChart');
      toggleEmpty(document.getElementById('adm-emp-empty'), empCtx ? empCtx.parentElement : null, emps.length === 0);
      if (empCtx && emps.length) {
        empChart = new Chart(empCtx, {
          type: 'bar',
          data: {
            labels: emps.map(function (e) { return e.label; }),
            datasets: [{
              data: emps.map(function (e) { return Number(e.total || 0); }),
              backgroundColor: '#2E5B8A',
              borderRadius: 4,
            }],
          },
          options: Object.assign({}, chartBaseOptions(), {
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, ticks: { callback: function (v) { return 'US$' + v; } } } },
          }),
        });
      }

      var prods = payload.productos_top || [];
      var prodCtx = document.getElementById('admProdChart');
      toggleEmpty(document.getElementById('adm-prod-empty'), prodCtx ? prodCtx.parentElement : null, prods.length === 0);
      if (prodCtx && prods.length) {
        prodChart = new Chart(prodCtx, {
          type: 'bar',
          data: {
            labels: prods.map(function (p) { return p.label; }),
            datasets: [{
              data: prods.map(function (p) { return Number(p.units || 0); }),
              backgroundColor: '#F26522',
              borderRadius: 4,
            }],
          },
          options: Object.assign({}, chartBaseOptions(), {
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
          }),
        });
      }

      updateMetaTipo(payload.ordenes_por_tipo);

      requestAnimationFrame(function () {
        [barChart, lineChart, doughnutChart, catChart, empChart, prodChart].forEach(function (c) {
          if (c && typeof c.resize === 'function') c.resize();
        });
      });
    }

    try {
      createCharts(parsed.payload);
    } catch (e) {
      showChartsError(i18n('chartInitError', 'No se pudieron inicializar los gráficos.') + ' ' + e.message);
      return;
    }

    if (pillsRoot) {
      var diasActivo = pillsRoot.getAttribute('data-dias-activo') || '7';
      pillsRoot.querySelectorAll('.js-dias-pill').forEach(function (btn) {
        if (btn.getAttribute('data-dias') === diasActivo) btn.classList.add('is-active');
      });

      var apiUrl = pillsRoot.getAttribute('data-api-url') || '';
      pillsRoot.querySelectorAll('.js-dias-pill').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var d = btn.getAttribute('data-dias');
          if (!d || !apiUrl) return;
          pillsRoot.querySelectorAll('.js-dias-pill').forEach(function (b) { b.classList.remove('is-active'); });
          btn.classList.add('is-active');
          var url = apiUrl + (apiUrl.indexOf('?') >= 0 ? '&' : '?') + 'dias=' + encodeURIComponent(d);
          fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
            .then(function (r) {
              if (!r.ok) throw new Error('HTTP ' + r.status);
              return r.json();
            })
            .then(function (data) {
              if (!payloadLooksValid(data)) {
                showChartsError('La API devolvió datos incompletos.');
                return;
              }
              hideChartsError();
              createCharts(data);
            })
            .catch(function () {
              showChartsError(i18n('chartUpdateError', 'No se pudieron actualizar los gráficos.'));
            });
        });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
