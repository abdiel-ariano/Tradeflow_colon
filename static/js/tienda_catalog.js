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
  var filteredLayout = document.querySelector('.td-wrap--sidebar-right');

  if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
  }

  function getCategoriaValue() {
    var sel = document.getElementById('select-categoria');
    if (sel) return sel.value;
    var checked = form.querySelector('input[name="categoria"]:checked');
    return checked ? checked.value : '';
  }

  function setCategoriaValue(value) {
    var sel = document.getElementById('select-categoria');
    if (sel) {
      sel.value = value || '';
      return;
    }
    form.querySelectorAll('input[name="categoria"]').forEach(function (radio) {
      radio.checked = radio.value === (value || '');
    });
    form.querySelectorAll('input[name="categoria"]').forEach(function (radio) {
      var span = radio.parentElement ? radio.parentElement.querySelector('span:not(.filter-count)') : null;
      if (span) span.classList.toggle('is-active', radio.checked);
    });
  }

  function getEmpresaValue() {
    var sel = document.getElementById('select-empresa');
    if (sel) return sel.value;
    var hidden = document.getElementById('tienda-filter-empresa');
    return hidden ? hidden.value : '';
  }

  function setEmpresaValue(value) {
    var val = value || '';
    var sel = document.getElementById('select-empresa');
    if (sel) sel.value = val;
    var hidden = document.getElementById('tienda-filter-empresa');
    if (hidden) hidden.value = val;
    document.querySelectorAll('.js-tienda-empresa-link').forEach(function (btn) {
      var id = btn.getAttribute('data-empresa-id') || '';
      btn.classList.toggle('is-active', id === val);
    });
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

    setCategoriaValue(root.getAttribute('data-cat-active') || '');
    setEmpresaValue(root.getAttribute('data-empresa-active') || '');
    markSelect(document.getElementById('select-orden'), root.getAttribute('data-orden-active') || 'nombre');
    var busInp = document.getElementById('input-buscar');
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

  function setSidebarOpen(open) {
    var sidebar = document.getElementById('tienda-sidebar');
    var backdrop = document.getElementById('tienda-sidebar-backdrop');
    var openBtn = document.getElementById('tienda-filter-open');
    if (!sidebar) return;
    sidebar.classList.toggle('is-open', open);
    if (backdrop) {
      backdrop.classList.toggle('is-visible', open);
      backdrop.hidden = !open;
    }
    if (openBtn) {
      openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
  }

  function initFilterSidebar() {
    if (!filteredLayout) return;

    document.querySelectorAll('[data-filter-toggle]').forEach(function (btn) {
      if (btn.dataset.tiendaBound) return;
      btn.dataset.tiendaBound = '1';
      btn.addEventListener('click', function () {
        var expanded = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      });
    });

    var openBtn = document.getElementById('tienda-filter-open');
    var closeBtn = document.getElementById('tienda-sidebar-close');
    var backdrop = document.getElementById('tienda-sidebar-backdrop');
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        var sidebar = document.getElementById('tienda-sidebar');
        setSidebarOpen(!(sidebar && sidebar.classList.contains('is-open')));
      });
    }
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        setSidebarOpen(false);
      });
    }
    if (backdrop) {
      backdrop.addEventListener('click', function () {
        setSidebarOpen(false);
      });
    }
  }

  var loadingSafetyTimer = null;

  function setLoading(on) {
    catalogRoot.classList.toggle('is-loading', on);
    catalogRoot.setAttribute('aria-busy', on ? 'true' : 'false');
    if (loadingSafetyTimer) {
      clearTimeout(loadingSafetyTimer);
      loadingSafetyTimer = null;
    }
    if (on) {
      loadingSafetyTimer = setTimeout(function () {
        loadingSafetyTimer = null;
        loading = false;
        setLoading(false);
      }, 12000);
    }
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
        setSidebarOpen(false);
      });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    loadCatalog(buildUrl({ page: null }), true, 'keep');
  });

  var ordSel = document.getElementById('select-orden');
  if (ordSel) {
    ordSel.addEventListener('change', function () {
      loadCatalog(buildUrl({ page: null }), true, 'keep');
    });
  }

  var selCategoria = document.getElementById('select-categoria');
  if (selCategoria) {
    selCategoria.addEventListener('change', function () {
      document.querySelectorAll('.td-cat-link, .tf-cat-link').forEach(function (lnk) {
        lnk.setAttribute('data-active', lnk.getAttribute('data-categoria-id') === selCategoria.value ? 'true' : 'false');
      });
      loadCatalog(buildUrl({ page: null }), true, 'keep');
    });
  }

  var selEmpresa = document.getElementById('select-empresa');
  if (selEmpresa) {
    selEmpresa.addEventListener('change', function () {
      loadCatalog(buildUrl({ page: null }), true, 'keep');
    });
  }

  form.querySelectorAll('input[name="categoria"]').forEach(function (radio) {
    radio.addEventListener('change', function () {
      setCategoriaValue(radio.value);
      loadCatalog(buildUrl({ categoria: radio.value || null, page: null }), true, 'keep');
    });
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
      setCategoriaValue(catId);
      loadCatalog(buildUrl({ categoria: catId || null, page: null }), true, 'keep');
      return;
    }

    var empLink = ev.target.closest('.js-tienda-empresa-link');
    if (empLink) {
      ev.preventDefault();
      var empId = empLink.getAttribute('data-empresa-id') || '';
      setEmpresaValue(empId);
      loadCatalog(buildUrl({ empresa: empId || null, page: null }), true, 'keep');
    }
  });

  var btnLimpiar = document.getElementById('btn-limpiar');
  if (btnLimpiar) {
    btnLimpiar.addEventListener('click', function (ev) {
      if (btnLimpiar.tagName === 'A') {
        ev.preventDefault();
      }
      setCategoriaValue('');
      setEmpresaValue('');
      markSelect(document.getElementById('select-orden'), 'nombre');
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
  initFilterSidebar();
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
