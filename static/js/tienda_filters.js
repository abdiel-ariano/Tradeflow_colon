/**
 * TradeFlow — filtros de tienda sin recarga completa (fetch + history).
 */
(function () {
  'use strict';

  var form = document.getElementById('filtros-form');
  var catalogRoot = document.getElementById('td-catalog-root');
  if (!form || !catalogRoot) return;

  var meta = document.getElementById('tf-tienda-meta');
  var searchTimer = null;
  var loading = false;

  function buildUrl(extra) {
    var params = new URLSearchParams(new FormData(form));
    if (extra) {
      Object.keys(extra).forEach(function (k) {
        if (extra[k] === null || extra[k] === '') params.delete(k);
        else params.set(k, extra[k]);
      });
    }
    params.delete('partial');
    var qs = params.toString();
    return (form.getAttribute('action') || '/tienda/') + (qs ? '?' + qs : '');
  }

  function syncMeta(partialEl) {
    if (!meta || !partialEl) return;
    meta.setAttribute('data-cat-active', partialEl.getAttribute('data-cat-active') || '');
    meta.setAttribute('data-empresa-active', partialEl.getAttribute('data-empresa-active') || '');
    meta.setAttribute('data-orden-active', partialEl.getAttribute('data-orden-active') || '');
    meta.setAttribute('data-buscar-active', partialEl.getAttribute('data-buscar-active') || '');
    meta.setAttribute('data-tab-active', partialEl.getAttribute('data-tab-active') || '');
    meta.setAttribute('data-cur-page', partialEl.getAttribute('data-cur-page') || '1');
  }

  function markPagination(curPage) {
    document.querySelectorAll('.td-pag-link').forEach(function (link) {
      link.toggleAttribute('data-active', link.getAttribute('data-page') === String(curPage));
    });
  }

  function bindCartForms() {
    if (typeof window.tfBindCartForms === 'function') {
      window.tfBindCartForms();
    }
    document.querySelectorAll('form.js-cart-add-form').forEach(function (f) {
      f.setAttribute('data-cart-bound', '0');
    });
    if (window.tfCartAjaxInit) window.tfCartAjaxInit();
  }

  function loadCatalog(url, pushState) {
    if (loading) return;
    loading = true;
    catalogRoot.classList.add('is-loading');

    var fetchUrl = url + (url.indexOf('?') >= 0 ? '&' : '?') + 'partial=1';

    fetch(fetchUrl, {
      headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'text/html' },
      credentials: 'same-origin',
    })
      .then(function (r) {
        if (!r.ok) throw new Error('fetch');
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var fresh = doc.getElementById('td-catalog-root');
        if (!fresh) throw new Error('partial');
        ['data-cat-active', 'data-empresa-active', 'data-orden-active',
          'data-buscar-active', 'data-tab-active', 'data-cur-page'].forEach(function (attr) {
          catalogRoot.setAttribute(attr, fresh.getAttribute(attr) || '');
        });
        catalogRoot.innerHTML = fresh.innerHTML;
        syncMeta(catalogRoot);
        markPagination(fresh.getAttribute('data-cur-page') || '1');
        bindCartForms();
        if (pushState !== false) {
          history.pushState({ tienda: true }, '', url);
        }
        var btnLimpiar = document.getElementById('btn-limpiar');
        if (btnLimpiar) {
          var hay = !!(
            meta.getAttribute('data-cat-active') ||
            meta.getAttribute('data-empresa-active') ||
            meta.getAttribute('data-buscar-active') ||
            meta.getAttribute('data-orden-active') !== 'nombre'
          );
          btnLimpiar.style.display = hay ? 'block' : 'none';
        }
        document.querySelectorAll('.td-spotlight').forEach(function (el) {
          el.style.display = 'none';
        });
      })
      .catch(function () {
        window.location.href = url;
      })
      .finally(function () {
        loading = false;
        catalogRoot.classList.remove('is-loading');
      });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    loadCatalog(buildUrl({ page: null }), true);
  });

  ['select-categoria', 'select-empresa', 'select-orden'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', function () {
        loadCatalog(buildUrl({ page: null }), true);
      });
    }
  });

  var inputBuscar = document.getElementById('input-buscar');
  if (inputBuscar) {
    inputBuscar.addEventListener('input', function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        loadCatalog(buildUrl({ page: null }), true);
      }, 450);
    });
  }

  catalogRoot.addEventListener('click', function (ev) {
    var link = ev.target.closest('.td-pag-ajax, .td-pag-link');
    if (!link || !link.href) return;
    ev.preventDefault();
    loadCatalog(link.getAttribute('href'), true);
  });

  window.addEventListener('popstate', function () {
    loadCatalog(window.location.pathname + window.location.search, false);
  });

  window.tfTiendaLoadCatalog = loadCatalog;
})();
