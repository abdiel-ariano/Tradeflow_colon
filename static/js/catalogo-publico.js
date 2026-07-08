/**
 * TradeFlow Colón — public catalog (/catalogo/) interactions
 */
(function () {
  'use strict';

  document.body.classList.add('cat-catalog-page');

  var openBtn = document.getElementById('cat-filter-open');
  var closeBtn = document.getElementById('cat-sidebar-close');
  var sidebar = document.getElementById('cat-sidebar');
  var backdrop = document.getElementById('cat-sidebar-backdrop');
  var host = document.getElementById('cat-results-host');
  var filtersForm = document.getElementById('cat-filters-form');
  var grid = document.getElementById('cat-product-grid');
  var resultsCountEl = document.querySelector('.results-count strong');
  var progressBar = document.getElementById('top-progress-bar');
  var activeFiltersEl = document.getElementById('cat-active-filters');
  var priceRange = document.getElementById('cat-price-range');
  var pageConfig = document.getElementById('cat-page-config');
  var navHamburger = document.getElementById('cat-nav-hamburger');
  var navSearchForm = document.getElementById('cat-nav-search-form');
  var navSearchInput = document.getElementById('cat-nav-search');
  var filterBuscar = document.getElementById('cat-filter-buscar');
  var filterEmpresa = document.getElementById('cat-filter-empresa');

  var currentController = null;
  var debounceTimer = null;
  var activeRequestId = 0;
  var inquiryUrlPattern = pageConfig ? pageConfig.getAttribute('data-inquiry-url') : '';

  var SPINNER_BY_INPUT = {
    categoria: 'categories',
    verificado: 'trust',
    stock: 'availability',
    stock_low: 'availability',
    on_sale: 'availability',
    precio_min: 'price',
    precio_max: 'price',
    empresa: null,
  };

  var SORT_LABELS = {
    relevancia: 'Mejor coincidencia',
    precio_asc: 'Precio ↑',
    precio_desc: 'Precio ↓',
    novedades: 'Más recientes',
  };

  function syncFilterLabels() {
    if (!filtersForm) return;
    filtersForm.querySelectorAll('.ali-filter-option').forEach(function (label) {
      var input = label.querySelector('input[type="checkbox"]');
      var text = label.querySelector('.ali-filter-option__label');
      if (input && text) {
        text.classList.toggle('is-active', input.checked);
      }
    });
  }

  function syncStickyOffset() {
    var nav = document.getElementById('cat-catalog-nav');
    var height = nav ? Math.ceil(nav.getBoundingClientRect().height) : 0;
    document.body.style.setProperty('--cat-nav-height', height + 'px');
  }

  function getCookie(name) {
    var parts = document.cookie ? document.cookie.split(';') : [];
    var i;
    for (i = 0; i < parts.length; i += 1) {
      var chunk = parts[i].trim();
      if (chunk.indexOf(name + '=') === 0) {
        return decodeURIComponent(chunk.substring(name.length + 1));
      }
    }
    return '';
  }

  function setSidebarOpen(open) {
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

  if (openBtn && sidebar) {
    openBtn.addEventListener('click', function () {
      setSidebarOpen(!sidebar.classList.contains('is-open'));
    });
  }

  if (navHamburger) {
    navHamburger.addEventListener('click', function () {
      setSidebarOpen(true);
    });
  }

  var allCategoriesBtn = document.querySelector('.btn-all-categories');
  if (allCategoriesBtn) {
    allCategoriesBtn.addEventListener('click', function () {
      setSidebarOpen(true);
    });
  }

  var cameraBtn = document.querySelector('.btn-camera');
  if (cameraBtn && navSearchInput) {
    cameraBtn.addEventListener('click', function () {
      navSearchInput.focus();
      showToast('Image search coming soon — use text search for now.');
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

  document.querySelectorAll('[data-filter-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    });
  });

  var progressSafetyTimer = null;

  function startProgressBar() {
    if (!progressBar) return;
    if (progressSafetyTimer) {
      clearTimeout(progressSafetyTimer);
      progressSafetyTimer = null;
    }
    progressBar.classList.remove('is-done', 'is-complete');
    progressBar.style.width = '0%';
    progressBar.setAttribute('aria-hidden', 'false');
    void progressBar.offsetWidth;
    progressBar.classList.add('is-active');
    progressSafetyTimer = setTimeout(function () {
      progressSafetyTimer = null;
      finishProgressBar();
    }, 8000);
  }

  function finishProgressBar() {
    if (!progressBar) return;
    if (progressSafetyTimer) {
      clearTimeout(progressSafetyTimer);
      progressSafetyTimer = null;
    }
    progressBar.classList.remove('is-active');
    progressBar.classList.add('is-complete');
    setTimeout(function () {
      progressBar.classList.add('is-done');
      progressBar.setAttribute('aria-hidden', 'true');
    }, 250);
  }

  function getSkeletonCount() {
    var w = window.innerWidth;
    if (w >= 1280) return 12;
    if (w >= 768) return 9;
    if (w >= 480) return 8;
    return 4;
  }

  function buildSkeletonCard() {
    var card = document.createElement('article');
    card.className = 'product-card product-card--skeleton';
    card.innerHTML =
      '<div class="skeleton-shimmer card-image"></div>' +
      '<div class="card-body">' +
      '<span class="skeleton-shimmer skeleton-line skeleton-line--title"></span>' +
      '<span class="skeleton-shimmer skeleton-line skeleton-line--title-2"></span>' +
      '<span class="skeleton-shimmer skeleton-line skeleton-line--price"></span>' +
      '<span class="skeleton-shimmer skeleton-line skeleton-line--meta"></span>' +
      '<span class="skeleton-shimmer skeleton-line skeleton-line--footer"></span>' +
      '</div>';
    return card;
  }

  function ensureProductGrid() {
    var gridEl = document.getElementById('cat-product-grid');
    if (gridEl) return gridEl;

    var root = document.getElementById('cat-results-root');
    if (!root) return null;

    gridEl = document.createElement('div');
    gridEl.className = 'product-grid cat-grid tf-pcard-grid';
    gridEl.id = 'cat-product-grid';
    root.innerHTML = '';
    root.appendChild(gridEl);
    return gridEl;
  }

  function showSkeletonGrid(count) {
    var gridEl = ensureProductGrid();
    if (!gridEl) return;

    gridEl.classList.remove('is-skeleton-exiting');

    var pagination = document.querySelector('.pagination');
    if (pagination) pagination.remove();

    gridEl.innerHTML = '';
    var fragment = document.createDocumentFragment();
    var total = count || getSkeletonCount();
    var i;
    for (i = 0; i < total; i += 1) {
      fragment.appendChild(buildSkeletonCard());
    }
    gridEl.appendChild(fragment);
  }

  function renderResultsWithFade(gridEl, newGridHTML) {
    if (!gridEl) return;
    if (typeof newGridHTML === 'string') {
      gridEl.innerHTML = newGridHTML;
    }
    gridEl.querySelectorAll('.product-card').forEach(function (card, index) {
      card.style.opacity = '0';
      card.classList.add('is-entering');
      card.style.animationDelay = Math.min(index * 25, 200) + 'ms';
    });
  }

  function transitionToResults(gridEl, newGridHTML) {
    if (!gridEl) return;
    var hasSkeleton = gridEl.querySelector('.product-card--skeleton');
    if (!hasSkeleton) {
      renderResultsWithFade(gridEl, newGridHTML);
      return;
    }
    gridEl.classList.add('is-skeleton-exiting');
    setTimeout(function () {
      gridEl.classList.remove('is-skeleton-exiting');
      renderResultsWithFade(gridEl, newGridHTML);
    }, 220);
  }

  function flashMiniSpinner(sectionKey) {
    if (!sectionKey) return;
    var spinner = document.querySelector('[data-spinner="' + sectionKey + '"]');
    if (!spinner) return;
    spinner.classList.add('is-visible');
    setTimeout(function () {
      spinner.classList.remove('is-visible');
    }, 600);
  }

  function updateResultsCount(doc) {
    if (!resultsCountEl || !doc) return;
    var meta = doc.getElementById('cat-results-root');
    if (meta && meta.dataset.total) {
      resultsCountEl.textContent = meta.dataset.total;
    }
  }

  function syncCompanyButtons() {
    /* empresa is now a <select> — no button sync needed */
  }

  function renderActiveFilters() {
    if (!activeFiltersEl || !filtersForm) return;

    var chips = [];
    var buscar = filterBuscar ? filterBuscar.value.trim() : '';
    if (buscar) {
      chips.push({ key: 'buscar', label: 'Search: ' + buscar });
    }

    filtersForm.querySelectorAll('input[name="categoria"]:checked').forEach(function (input) {
      var label = input.closest('label');
      var text = label ? label.querySelector('.ali-filter-option__label') : null;
      var chipLabel = text ? text.childNodes[0].textContent.trim() : 'Categoría';
      chips.push({ key: 'categoria:' + input.value, label: chipLabel });
    });

    if (filterEmpresa && filterEmpresa.value) {
      var opt = filterEmpresa.options[filterEmpresa.selectedIndex];
      chips.push({ key: 'empresa', label: opt ? opt.textContent.trim() : 'Proveedor' });
    }

    var precioMin = filtersForm.querySelector('input[name="precio_min"]');
    var precioMax = filtersForm.querySelector('input[name="precio_max"]');
    if (precioMin && precioMin.value) {
      chips.push({ key: 'precio_min', label: 'Min $' + precioMin.value });
    }
    if (precioMax && precioMax.value) {
      chips.push({ key: 'precio_max', label: 'Max $' + precioMax.value });
    }

    ['verificado', 'stock', 'stock_low', 'on_sale'].forEach(function (name) {
      var input = filtersForm.querySelector('input[name="' + name + '"]:checked');
      if (!input) return;
      var label = input.closest('label');
      var text = label ? label.querySelector('.ali-filter-option__label') : null;
      chips.push({ key: name, label: text ? text.textContent.trim() : name });
    });

    var ordenSelect = document.getElementById('cat-sort-select');
    if (ordenSelect && ordenSelect.value && ordenSelect.value !== 'relevancia') {
      chips.push({ key: 'orden', label: SORT_LABELS[ordenSelect.value] || ordenSelect.value });
    }

    activeFiltersEl.innerHTML = '';
    if (!chips.length) {
      activeFiltersEl.hidden = true;
      return;
    }

    activeFiltersEl.hidden = false;
    chips.forEach(function (chip) {
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'filter-chip';
      el.setAttribute('data-chip-key', chip.key);
      el.innerHTML = chip.label + ' <span aria-hidden="true">×</span>';
      el.addEventListener('click', function () {
        clearFilterChip(chip.key);
      });
      activeFiltersEl.appendChild(el);
    });

    var clearAll = document.createElement('button');
    clearAll.type = 'button';
    clearAll.className = 'filter-chip filter-chip--clear';
    clearAll.textContent = 'Clear all';
    clearAll.addEventListener('click', function () {
      window.location.href = pageConfig ? pageConfig.getAttribute('data-catalog-url') : '/catalogo/';
    });
    activeFiltersEl.appendChild(clearAll);
  }

  function clearFilterChip(key) {
    if (!filtersForm) return;
    if (key === 'buscar') {
      if (filterBuscar) filterBuscar.value = '';
      if (navSearchInput) navSearchInput.value = '';
    } else if (key === 'empresa') {
      if (filterEmpresa) filterEmpresa.value = '';
    } else if (key.indexOf('categoria:') === 0) {
      var catId = key.split(':')[1];
      var catInput = filtersForm.querySelector('input[name="categoria"][value="' + catId + '"]');
      if (catInput) catInput.checked = false;
    } else if (key === 'precio_min' || key === 'precio_max') {
      var priceInput = filtersForm.querySelector('input[name="' + key + '"]');
      if (priceInput) priceInput.value = '';
      if (key === 'precio_max' && priceRange) priceRange.value = '250';
    } else if (key === 'orden') {
      var ordenSelect = document.getElementById('cat-sort-select');
      if (ordenSelect) ordenSelect.value = 'relevancia';
    } else {
      var toggle = filtersForm.querySelector('input[name="' + key + '"]');
      if (toggle) toggle.checked = false;
    }
    applyFilters();
  }

  function syncFormFromUrl() {
    if (!filtersForm) return;
    var params = new URLSearchParams(window.location.search);

    if (filterBuscar) {
      filterBuscar.value = params.get('buscar') || '';
      if (navSearchInput) navSearchInput.value = filterBuscar.value;
    }

    if (filterEmpresa) {
      filterEmpresa.value = params.get('empresa') || '';
    }

    filtersForm.querySelectorAll('input[name="categoria"]').forEach(function (input) {
      input.checked = params.getAll('categoria').indexOf(input.value) >= 0;
    });

    ['verificado', 'stock', 'stock_low', 'on_sale'].forEach(function (name) {
      var input = filtersForm.querySelector('input[name="' + name + '"]');
      if (input) input.checked = params.get(name) === '1';
    });

    var precioMin = filtersForm.querySelector('input[name="precio_min"]');
    var precioMax = filtersForm.querySelector('input[name="precio_max"]');
    if (precioMin) precioMin.value = params.get('precio_min') || '';
    if (precioMax) precioMax.value = params.get('precio_max') || '';

    if (priceRange) {
      priceRange.value = precioMax && precioMax.value ? precioMax.value : '250';
    }

    var orden = params.get('orden') || 'relevancia';
    var ordenSelect = document.getElementById('cat-sort-select');
    if (ordenSelect) ordenSelect.value = orden;

    syncCompanyButtons();
    syncFilterLabels();
  }

  function applyFiltersFromLink(href) {
    var linkUrl = new URL(href, window.location.origin);
    window.history.pushState({}, '', linkUrl.pathname + linkUrl.search);
    syncFormFromUrl();
    var page = linkUrl.searchParams.get('page');
    applyFilters({ page: page || null, skipHistory: true });
  }

  function applyFilters(options) {
    if (!filtersForm || !host || !window.fetch) return;

    options = options || {};

    if (currentController) {
      currentController.abort();
    }
    var controller = new AbortController();
    currentController = controller;
    var requestId = ++activeRequestId;

    startProgressBar();
    if (options.spinner) {
      flashMiniSpinner(options.spinner);
    }

    showSkeletonGrid(getSkeletonCount());

    var params = new URLSearchParams(new FormData(filtersForm));
    if (options.page) {
      params.set('page', options.page);
    } else if (!options.keepPage) {
      params.delete('page');
    }
    params.delete('export_docs');
    params.delete('intl_orders');
    params.delete('orden-mobile');

    if (filterBuscar && !filterBuscar.value.trim()) {
      params.delete('buscar');
    }
    if (filterEmpresa && !filterEmpresa.value.trim()) {
      params.delete('empresa');
    }

    var qs = params.toString();
    var base = filtersForm.getAttribute('action') || window.location.pathname;
    var url = base + (qs ? '?' + qs : '');

    fetch(url + (url.indexOf('?') >= 0 ? '&' : '?') + 'partial=1', {
      signal: controller.signal,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        if (requestId !== activeRequestId || controller.signal.aborted) return;

        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var newGrid = doc.getElementById('cat-product-grid');

        if (newGrid) {
          var currentGrid = ensureProductGrid();
          transitionToResults(currentGrid, newGrid.innerHTML);

          var newPagination = doc.querySelector('.pagination');
          var currentPagination = document.querySelector('.pagination');
          if (newPagination && currentPagination) {
            currentPagination.innerHTML = newPagination.innerHTML;
          } else if (newPagination && !currentPagination) {
            var root = document.getElementById('cat-results-root');
            if (root) root.appendChild(newPagination.cloneNode(true));
          } else if (!newPagination && currentPagination) {
            currentPagination.remove();
          }

          var newEmpty = doc.getElementById('cat-empty-state');
          var currentEmpty = document.getElementById('cat-empty-state');
          if (newEmpty && !currentEmpty) {
            var resultsRoot = document.getElementById('cat-results-root');
            if (resultsRoot) resultsRoot.appendChild(newEmpty.cloneNode(true));
          } else if (!newEmpty && currentEmpty) {
            currentEmpty.remove();
          }
        } else {
          host.innerHTML = html;
          grid = document.getElementById('cat-product-grid');
          if (grid) {
            renderResultsWithFade(grid);
          }
        }

        updateResultsCount(doc);
        syncCompanyButtons();
        renderActiveFilters();

        if (!options.skipHistory && window.history && window.history.pushState) {
          window.history.pushState({}, '', url);
        }

        grid = document.getElementById('cat-product-grid');
        bindInquiryButtons();
        bindPaginationLinks();
        bindAjaxChips();
        finishProgressBar();
      })
      .catch(function (err) {
        if (requestId !== activeRequestId) return;
        finishProgressBar();
        if (err && err.name === 'AbortError') return;
        window.location.href = url;
      });
  }

  function spinnerForInput(input) {
    return SPINNER_BY_INPUT[input.name] || null;
  }

  if (filtersForm) {
    filtersForm.addEventListener('submit', function (e) {
      e.preventDefault();
      clearTimeout(debounceTimer);
      applyFilters({ spinner: null });
    });

    filtersForm.querySelectorAll('input[type="checkbox"], input[type="radio"], select').forEach(function (input) {
      input.addEventListener('change', function () {
        syncFilterLabels();
        clearTimeout(debounceTimer);
        applyFilters({ spinner: spinnerForInput(input) });
      });
    });

    var sortSelect = document.getElementById('cat-sort-select');
    if (sortSelect) {
      sortSelect.addEventListener('change', function () {
        clearTimeout(debounceTimer);
        applyFilters({ spinner: null });
      });
    }

    filtersForm.querySelectorAll('input[type="number"]').forEach(function (input) {
      input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        var spinner = spinnerForInput(input);
        debounceTimer = setTimeout(function () {
          if (input.name === 'precio_max' && priceRange && input.value) {
            priceRange.value = input.value;
          }
          applyFilters({ spinner: spinner });
        }, 500);
      });
    });
  }

  if (priceRange) {
    priceRange.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      var maxInput = filtersForm ? filtersForm.querySelector('input[name="precio_max"]') : null;
      if (maxInput) maxInput.value = priceRange.value;
      debounceTimer = setTimeout(function () {
        applyFilters({ spinner: 'price' });
      }, 300);
    });
  }

  document.querySelectorAll('.cat-nav-ajax-link').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      applyFiltersFromLink(link.href);
    });
  });

  if (navSearchForm) {
    navSearchForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (filterBuscar && navSearchInput) {
        filterBuscar.value = navSearchInput.value.trim();
      }
      applyFilters({ spinner: null });
    });
  }

  function bindPaginationLinks() {
    document.querySelectorAll('.pagination a.page-btn').forEach(function (link) {
      if (link.dataset.bound) return;
      link.dataset.bound = '1';
      link.addEventListener('click', function (e) {
        e.preventDefault();
        var pageUrl = new URL(link.href, window.location.origin);
        var page = pageUrl.searchParams.get('page');
        if (!page) return;
        applyFilters({ page: page, keepPage: true });
      });
    });
  }

  function bindAjaxChips() {
    document.querySelectorAll('.cat-ajax-chip').forEach(function (chip) {
      if (chip.dataset.bound) return;
      chip.dataset.bound = '1';
      chip.addEventListener('click', function (e) {
        e.preventDefault();
        if (filterBuscar) {
          var term = new URL(chip.href, window.location.origin).searchParams.get('buscar') || '';
          filterBuscar.value = term;
          if (navSearchInput) navSearchInput.value = term;
        }
        applyFilters();
      });
    });
  }

  window.addEventListener('popstate', function () {
    syncFormFromUrl();
    var page = new URLSearchParams(window.location.search).get('page');
    applyFilters({ page: page, skipHistory: true, keepPage: true });
  });

  function showToast(message) {
    var toast = document.createElement('div');
    toast.className = 'inquiry-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(function () {
      toast.classList.add('is-visible');
    });
    setTimeout(function () {
      toast.classList.remove('is-visible');
      setTimeout(function () { toast.remove(); }, 300);
    }, 2500);
  }

  function updateCartBadges(count) {
    var n = parseInt(count, 10) || 0;
    document.querySelectorAll('#cat-inquiry-badge, #tf-nav-cart-badge, [data-cart-badge]').forEach(function (badge) {
      badge.textContent = String(n);
      badge.classList.toggle('has-count', n > 0);
    });
  }

  function inquiryUrlFor(productId) {
    if (!inquiryUrlPattern) return '/catalogo/inquiry/agregar/' + productId + '/';
    return inquiryUrlPattern.replace('/0/', '/' + productId + '/');
  }

  function addToInquiry(productId, btn) {
    if (!productId) return;

    if (btn) {
      btn.disabled = true;
    }

    fetch(inquiryUrlFor(productId), {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: 'cantidad=1',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          updateCartBadges(data.carrito_count);
          showToast(data.message || 'Added to inquiry cart');
        } else {
          showToast(data.message || 'Could not add to inquiry cart');
        }
      })
      .catch(function () {
        showToast('Connection error — try again');
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  window.addToInquiry = addToInquiry;

  function bindInquiryButtons() {
    document.querySelectorAll('.btn-inquiry').forEach(function (btn) {
      if (btn.dataset.bound) return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var productId = btn.getAttribute('data-product-id') ||
          (btn.closest('[data-product-id]') && btn.closest('[data-product-id]').getAttribute('data-product-id'));
        addToInquiry(productId, btn);
      });
    });
  }

  syncFormFromUrl();
  syncFilterLabels();
  renderActiveFilters();
  bindInquiryButtons();
  bindPaginationLinks();
  bindAjaxChips();
  syncStickyOffset();
  window.addEventListener('resize', syncStickyOffset);
  if (window.ResizeObserver) {
    var catalogNav = document.getElementById('cat-catalog-nav');
    if (catalogNav) {
      new ResizeObserver(syncStickyOffset).observe(catalogNav);
    }
  }
})();
