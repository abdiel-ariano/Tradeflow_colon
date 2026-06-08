/**
 * TradeFlow — catálogo /tienda/ sin recarga completa (fetch partial + scroll estable).
 */
(function () {
  'use strict';

  var form = document.getElementById('filtros-form');
  var catalogRoot = document.getElementById('t-prod-section');
  if (!form || !catalogRoot) return;

  var meta = document.getElementById('tf-tienda-meta');
  var searchTimer = null;
  var loading = false;
  var SCROLL_KEY = 'tf_tienda_scroll';

  if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
  }

  function buildUrl(extra) {
    var params = new URLSearchParams(new FormData(form));
    if (extra) {
      Object.keys(extra).forEach(function (k) {
        if (extra[k] === null || extra[k] === '') params.delete(k);
        else params.set(k, String(extra[k]));
      });
    }
    params.delete('partial');
    var qs = params.toString();
    var base = form.getAttribute('action') || '/tienda/';
    return base + (qs ? '?' + qs : '');
  }

  function saveScroll() {
    try {
      sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
    } catch (e) { /* ignore */ }
  }

  function restoreScroll() {
    var y = 0;
    try {
      y = parseInt(sessionStorage.getItem(SCROLL_KEY), 10);
      if (isNaN(y)) y = 0;
    } catch (e) { /* ignore */ }
    var anchor = document.getElementById('t-prod-section');
    if (anchor && y < 80) {
      var top = anchor.getBoundingClientRect().top + window.scrollY - 88;
      window.scrollTo({ top: Math.max(0, top), behavior: 'instant' in window ? 'instant' : 'auto' });
      return;
    }
    if (y > 0) {
      window.scrollTo({ top: y, behavior: 'auto' });
    }
  }

  function syncMetaFromRoot(root) {
    if (!meta || !root) return;
    meta.setAttribute('data-cat-active', root.getAttribute('data-cat-active') || '');
    meta.setAttribute('data-empresa-active', root.getAttribute('data-empresa-active') || '');
    meta.setAttribute('data-orden-active', root.getAttribute('data-orden-active') || '');
    meta.setAttribute('data-buscar-active', root.getAttribute('data-buscar-active') || '');
    meta.setAttribute('data-tab-active', root.getAttribute('data-tab-active') || '');
    meta.setAttribute('data-cur-page', root.getAttribute('data-cur-page') || '1');

    var catSel = document.getElementById('select-categoria');
    var empSel = document.getElementById('select-empresa');
    var ordSel = document.getElementById('select-orden');
    var busInp = document.getElementById('input-buscar');
    markSelect(catSel, root.getAttribute('data-cat-active') || '');
    markSelect(empSel, root.getAttribute('data-empresa-active') || '');
    markSelect(ordSel, root.getAttribute('data-orden-active') || 'nombre');
    if (busInp) busInp.value = root.getAttribute('data-buscar-active') || '';

    document.querySelectorAll('.td-cat-link, .tf-cat-link').forEach(function (lnk) {
      var id = lnk.getAttribute('data-categoria-id') || '';
      lnk.setAttribute('data-active', id === (root.getAttribute('data-cat-active') || '') ? 'true' : 'false');
    });
  }

  function markSelect(sel, value) {
    if (!sel) return;
    var i;
    for (i = 0; i < sel.options.length; i += 1) {
      if (sel.options[i].value === value) {
        sel.selectedIndex = i;
        return;
      }
    }
    if (!value) sel.selectedIndex = 0;
  }

  function markTabs(tabActive) {
    document.querySelectorAll('.td-tab[data-tab]').forEach(function (tab) {
      tab.setAttribute('data-active', tab.getAttribute('data-tab') === tabActive ? 'true' : 'false');
    });
  }

  function markPagination(curPage) {
    document.querySelectorAll('.td-pag-link').forEach(function (link) {
      var isCur = link.getAttribute('data-page') === String(curPage);
      link.toggleAttribute('data-active', isCur);
      if (isCur) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    });
  }

  function bindCartForms() {
    document.querySelectorAll('form.js-cart-add-form').forEach(function (f) {
      f.setAttribute('data-cart-bound', '0');
    });
    if (typeof window.tfCartAjaxInit === 'function') {
      window.tfCartAjaxInit();
    }
  }

  function setLoading(on) {
    catalogRoot.classList.toggle('is-loading', on);
    catalogRoot.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  function loadCatalog(url, pushState, scrollMode) {
    if (loading) return;
    loading = true;
    saveScroll();
    setLoading(true);

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
        var fresh = doc.getElementById('t-prod-section');
        if (!fresh) throw new Error('partial');
        ['data-cat-active', 'data-empresa-active', 'data-orden-active',
          'data-buscar-active', 'data-tab-active', 'data-cur-page'].forEach(function (attr) {
          catalogRoot.setAttribute(attr, fresh.getAttribute(attr) || '');
        });
        catalogRoot.innerHTML = fresh.innerHTML;
        syncMetaFromRoot(catalogRoot);
        markPagination(fresh.getAttribute('data-cur-page') || '1');
        markTabs(fresh.getAttribute('data-tab-active') || 'todos');
        bindCartForms();

        if (pushState !== false) {
          history.pushState({ tienda: true }, '', url);
        }

        var btnLimpiar = document.getElementById('btn-limpiar');
        if (btnLimpiar) {
          var hay = !!(
            catalogRoot.getAttribute('data-cat-active') ||
            catalogRoot.getAttribute('data-empresa-active') ||
            catalogRoot.getAttribute('data-buscar-active') ||
            (catalogRoot.getAttribute('data-orden-active') || 'nombre') !== 'nombre'
          );
          btnLimpiar.classList.toggle('is-visible', hay);
        }

        document.querySelectorAll('.td-spotlight').forEach(function (el) {
          el.style.display = 'none';
        });

        if (scrollMode === 'top') {
          var top = catalogRoot.getBoundingClientRect().top + window.scrollY - 88;
          window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        } else {
          requestAnimationFrame(restoreScroll);
        }
      })
      .catch(function () {
        window.location.href = url;
      })
      .finally(function () {
        loading = false;
        setLoading(false);
      });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    loadCatalog(buildUrl({ page: null }), true, 'keep');
  });

  ['select-categoria', 'select-empresa', 'select-orden'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', function () {
        if (id === 'select-categoria') {
          document.querySelectorAll('.td-cat-link, .tf-cat-link').forEach(function (lnk) {
            lnk.setAttribute('data-active', lnk.getAttribute('data-categoria-id') === el.value ? 'true' : 'false');
          });
        }
        loadCatalog(buildUrl({ page: null }), true, 'keep');
      });
    }
  });

  var inputBuscar = document.getElementById('input-buscar');
  if (inputBuscar) {
    inputBuscar.addEventListener('input', function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        loadCatalog(buildUrl({ page: null }), true, 'keep');
      }, 300);
    });
  }

  catalogRoot.addEventListener('click', function (ev) {
    var link = ev.target.closest('.td-pag-ajax, .td-pag-link');
    if (link && link.href) {
      ev.preventDefault();
      loadCatalog(link.getAttribute('href'), true, 'keep');
    }
  });

  document.addEventListener('click', function (ev) {
    var tab = ev.target.closest('.td-tab[data-tab]');
    if (tab && tab.href) {
      ev.preventDefault();
      var tabName = tab.getAttribute('data-tab') || 'todos';
      var tabInput = form.querySelector('input[name="tab"]');
      if (tabName === 'todos') {
        if (tabInput) tabInput.remove();
      } else {
        if (!tabInput) {
          tabInput = document.createElement('input');
          tabInput.type = 'hidden';
          tabInput.name = 'tab';
          form.appendChild(tabInput);
        }
        tabInput.value = tabName;
      }
      loadCatalog(tab.href, true, 'top');
      return;
    }

    var catLink = ev.target.closest('.td-cat-link, .tf-cat-link');
    if (catLink) {
      ev.preventDefault();
      var catId = catLink.getAttribute('data-categoria-id') || '';
      var sel = document.getElementById('select-categoria');
      if (sel) sel.value = catId;
      loadCatalog(buildUrl({ categoria: catId || null, page: null }), true, 'keep');
      return;
    }

    var empLink = ev.target.closest('.js-tienda-empresa-link');
    if (empLink) {
      ev.preventDefault();
      var empId = empLink.getAttribute('data-empresa-id') || '';
      var empSel = document.getElementById('select-empresa');
      if (empSel) empSel.value = empId;
      loadCatalog(buildUrl({ empresa: empId || null, page: null }), true, 'keep');
    }
  });

  var btnLimpiar = document.getElementById('btn-limpiar');
  if (btnLimpiar) {
    btnLimpiar.addEventListener('click', function (ev) {
      ev.preventDefault();
      var selC = document.getElementById('select-categoria');
      var selE = document.getElementById('select-empresa');
      var selO = document.getElementById('select-orden');
      if (selC) selC.value = '';
      if (selE) selE.value = '';
      if (selO) selO.value = 'nombre';
      if (inputBuscar) inputBuscar.value = '';
      var tabHidden = form.querySelector('input[name="tab"]');
      if (tabHidden) tabHidden.remove();
      loadCatalog(buildUrl({
        categoria: null,
        empresa: null,
        buscar: null,
        orden: null,
        tab: null,
        page: null,
      }), true, 'top');
    });
  }

  window.addEventListener('popstate', function () {
    loadCatalog(window.location.pathname + window.location.search, false, 'keep');
  });

  window.tfTiendaLoadCatalog = loadCatalog;
  bindCartForms();

  var btnLimpiarInit = document.getElementById('btn-limpiar');
  if (btnLimpiarInit && catalogRoot) {
    var hayInit = !!(
      catalogRoot.getAttribute('data-cat-active') ||
      catalogRoot.getAttribute('data-empresa-active') ||
      catalogRoot.getAttribute('data-buscar-active') ||
      (catalogRoot.getAttribute('data-orden-active') || 'nombre') !== 'nombre'
    );
    btnLimpiarInit.classList.toggle('is-visible', hayInit);
  }
  markPagination(catalogRoot.getAttribute('data-cur-page') || '1');
  markTabs(meta ? meta.getAttribute('data-tab-active') || 'todos' : 'todos');
})();
