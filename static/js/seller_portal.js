/**
 * TradeFlow Seller Portal — charts, toggles, timeline, security helpers
 */
(function (global) {
  'use strict';

  var navy = '#0F2A44';
  var blue = '#2E5B8A';
  var orange = '#F26522';
  var muted = '#6B7A88';

  function csrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function chartDefaults() {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.font.family = "'Montserrat', sans-serif";
    Chart.defaults.color = muted;
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.maintainAspectRatio = true;
    Chart.defaults.aspectRatio = 2.2;
  }

  function lineChart(el, labels, values, color) {
    if (!el || typeof Chart === 'undefined' || !labels || !labels.length) return;
    return new Chart(el, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          borderColor: color || orange,
          backgroundColor: 'rgba(242,101,34,0.08)',
          fill: true,
          tension: 0.35,
          pointRadius: 2,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 450 },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(209,213,219,0.5)' } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  function compactDoughnut(el, labels, values) {
    if (!el || typeof Chart === 'undefined' || !values || !values.length) return null;
    var total = values.reduce(function (s, v) { return s + Number(v || 0); }, 0);
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
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1,
        cutout: '68%',
        animation: { duration: 400 },
        layout: { padding: 4 },
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true },
        },
      },
      plugins: total ? [{
        id: 'spDoughnutCenter',
        beforeDraw: function (chart) {
          var ctx = chart.ctx;
          var meta = chart.getDatasetMeta(0);
          if (!meta || !meta.data || !meta.data[0]) return;
          var center = meta.data[0];
          var x = center.x;
          var y = center.y;
          ctx.save();
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = navy;
          ctx.font = '700 18px Inter, sans-serif';
          ctx.fillText(String(total), x, y - 4);
          ctx.fillStyle = '#6B7A88';
          ctx.font = '500 10px Inter, sans-serif';
          ctx.fillText('units', x, y + 12);
          ctx.restore();
        },
      }] : [],
    });
  }

  function horizontalBar(el, labels, values) {
    if (!el || typeof Chart === 'undefined') return;
    return new Chart(el, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: blue,
          borderRadius: 4,
          barThickness: 14,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { beginAtZero: true }, y: { grid: { display: false } } },
        animation: { duration: 400 },
      },
    });
  }

  function renderStatusLegend(container, labels, values) {
    if (!container || !labels) return;
    var colors = [orange, blue, navy, '#FFA15A', '#D1D5DB', '#c62828'];
    container.innerHTML = labels.map(function (lbl, i) {
      return '<span><i style="background:' + (colors[i % colors.length]) + '"></i>' +
        lbl + ' (' + (values[i] || 0) + ')</span>';
    }).join('');
  }

  function initTimers() {
    document.querySelectorAll('[data-sp-plazo]').forEach(function (el) {
      function tick() {
        var end = new Date(el.getAttribute('data-sp-plazo'));
        var diff = end - new Date();
        if (diff <= 0) {
          el.textContent = el.getAttribute('data-expired') || 'Expired';
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
          titulo: accion === 'aceptar' ? 'Accept order' : 'Reject order',
          mensaje: (accion === 'aceptar' ? 'Accept ' : 'Reject ') + num + '?',
          onAceptar: function () { window.location.href = href; },
        });
      });
    });
  }

  function notify(msg, type) {
    if (global.TF && TF.notify) TF.notify(msg, type || 'success');
    else if (type === 'error') console.error(msg);
  }

  var SP_IMG_FALLBACK = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'%3E%3Crect fill='%23f3f4f6' width='80' height='80' rx='10'/%3E%3Ctext x='50%25' y='52%25' dominant-baseline='middle' text-anchor='middle' fill='%239CA3AF' font-family='Inter,sans-serif' font-size='10'%3ENo image%3C/text%3E%3C/svg%3E";

  function bindProductImageFallback() {
    document.querySelectorAll('.sp-product-img').forEach(function (img) {
      function applyFallback() {
        img.onerror = null;
        img.src = SP_IMG_FALLBACK;
        img.classList.add('is-fallback');
      }
      img.addEventListener('error', applyFallback);
      if (img.complete && img.naturalWidth === 0 && img.src) applyFallback();
    });
  }

  function bindProductToggles() {
    document.querySelectorAll('[data-sp-product-toggle]').forEach(function (wrap) {
      var input = wrap.querySelector('input[type="checkbox"]');
      if (!input || input.dataset.bound) return;
      input.dataset.bound = '1';
      input.addEventListener('change', function () {
        var url = wrap.getAttribute('data-toggle-url');
        var row = wrap.closest('[data-product-id]');
        var next = input.checked;
        var prev = !next;
        wrap.classList.add('is-busy');
        fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
            Accept: 'application/json',
          },
        })
          .then(function (r) {
            if (!r.ok) throw new Error('toggle_failed');
            return r.json();
          })
          .then(function (data) {
            if (!data.ok) throw new Error('toggle_failed');
            input.checked = data.is_active;
            if (row) {
              var badge = row.querySelector('[data-sp-active-badge]');
              if (badge) {
                badge.textContent = data.is_active ? badge.dataset.labelOn : badge.dataset.labelOff;
                badge.className = 'sp-status ' + (data.is_active ? 'sp-status-delivered' : 'sp-status-cancelled');
              }
            }
            var kpiRoot = document.getElementById('sp-product-kpis');
            if (kpiRoot && typeof data.kpi_activos === 'number') {
              var elTotal = kpiRoot.querySelector('[data-sp-kpi="total"]');
              var elActivos = kpiRoot.querySelector('[data-sp-kpi="activos"]');
              if (elTotal) elTotal.textContent = String(data.kpi_total);
              if (elActivos) elActivos.textContent = String(data.kpi_activos);
            }
            var listFilter = kpiRoot && kpiRoot.getAttribute('data-filter-estado');
            if (row && listFilter === 'activo' && !data.is_active) {
              row.remove();
            }
            if (row && listFilter === 'inactivo' && data.is_active) {
              row.remove();
            }
            notify(data.message || 'Updated', 'success');
          })
          .catch(function () {
            input.checked = prev;
            notify('Could not update the product', 'error');
          })
          .finally(function () {
            wrap.classList.remove('is-busy');
          });
      });
    });
  }

  function renderTimeline(listEl, payload) {
    if (!listEl || !payload || !payload.steps) return;
    listEl.innerHTML = '';
    payload.steps.forEach(function (step) {
      var li = document.createElement('li');
      li.className = 'is-' + step.state;
      if (step.key === 'cancelled') li.classList.add('is-cancelled');
      li.innerHTML =
        '<div class="sp-timeline-icon"><span class="material-symbols-rounded" style="font-size:18px;">' +
        (step.icon || 'circle') + '</span></div>' +
        '<p class="sp-timeline-label">' + step.label + '</p>';
      listEl.appendChild(li);
    });
  }

  function initOrderTimeline(cfg) {
    var listEl = document.getElementById('sp-order-timeline');
    if (!listEl || !cfg.pollUrl) return;
    var lastUpdated = cfg.initial && cfg.initial.updated_at;

    function apply(data) {
      renderTimeline(listEl, data);
      if (data.updated_at && data.updated_at !== lastUpdated && global.TF && TF.notify) {
        TF.notify('Logistics status updated', 'info');
      }
      lastUpdated = data.updated_at;
    }

    if (cfg.initial) apply(cfg.initial);

    function poll() {
      fetch(cfg.pollUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(apply)
        .catch(function () {});
    }
    setInterval(poll, cfg.pollMs || 5000);

    function trySupabase() {
      if (!cfg.supabaseUrl || !cfg.supabaseKey || !cfg.orderId || !global.supabase) return;
      try {
        var client = global.supabase.createClient(cfg.supabaseUrl, cfg.supabaseKey);
        client
          .channel('tf-order-' + cfg.orderId)
          .on(
            'postgres_changes',
            {
              event: 'UPDATE',
              schema: 'public',
              table: 'core_order',
              filter: 'id=eq.' + cfg.orderId,
            },
            function () { poll(); }
          )
          .subscribe();
      } catch (e) { /* fallback polling only */ }
    }
    trySupabase();
    if (cfg.supabaseUrl && cfg.supabaseKey && !global.supabase) {
      global.addEventListener('load', trySupabase);
    }
  }

  function pollDashboard(url) {
    if (!url) return;
    setInterval(function () {
      fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.updated && global.TF && TF.notify) TF.notify('Panel updated', 'info');
        })
        .catch(function () {});
    }, 90000);
  }

  global.TFSeller = {
    initPortal: function (cfg) {
      chartDefaults();
      lineChart(
        document.getElementById('sp-chart-revenue'),
        cfg.revenueLabels,
        cfg.revenueValues,
        orange
      );
      lineChart(
        document.getElementById('sp-chart-week'),
        cfg.weekLabels,
        cfg.weekOrders,
        blue
      );
      var statusEl = document.getElementById('sp-chart-status');
      if (statusEl && cfg.statusLabels && cfg.statusLabels.length) {
        horizontalBar(statusEl, cfg.statusLabels, cfg.statusValues);
        renderStatusLegend(
          document.getElementById('sp-chart-status-legend'),
          cfg.statusLabels,
          cfg.statusValues
        );
      }
      var catEl = document.getElementById('sp-chart-cat');
      if (catEl && cfg.catLabels && cfg.catLabels.length) {
        compactDoughnut(catEl, cfg.catLabels, cfg.catValues);
      }
      pollDashboard(cfg.pollUrl);
    },
    initProductsPage: function (cfg) {
      chartDefaults();
      var catEl = document.getElementById('sd-chart-cat');
      if (catEl && cfg.catLabels && cfg.catLabels.length) {
        compactDoughnut(catEl, cfg.catLabels, cfg.catValues);
      }
      bindProductToggles();
      bindProductImageFallback();
    },
    initTimers: initTimers,
    bindConfirmLinks: bindConfirmLinks,
    bindProductToggles: bindProductToggles,
    initOrderTimeline: initOrderTimeline,
  };

  document.addEventListener('DOMContentLoaded', function () {
    initTimers();
    bindConfirmLinks();
    bindProductToggles();
  });
})(window);
