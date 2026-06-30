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

  var currentController = null;
  var debounceTimer = null;
  var activeRequestId = 0;

  var SPINNER_BY_INPUT = {
    categoria: 'categories',
    verificado: 'trust',
    stock: 'availability',
    stock_low: 'availability',
    on_sale: 'availability',
    precio_min: 'price',
    precio_max: 'price',
  };

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

  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      setSidebarOpen(false);
    });
  }

  document.querySelectorAll('[data-filter-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    });
  });

  function startProgressBar() {
    if (!progressBar) return;
    progressBar.classList.remove('is-done', 'is-complete');
    progressBar.style.width = '0%';
    progressBar.setAttribute('aria-hidden', 'false');
    void progressBar.offsetWidth;
    progressBar.classList.add('is-active');
  }

  function finishProgressBar() {
    if (!progressBar) return;
    progressBar.classList.remove('is-active');
    progressBar.classList.add('is-complete');
    setTimeout(function () {
      progressBar.classList.add('is-done');
      progressBar.setAttribute('aria-hidden', 'true');
    }, 250);
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

    var pagination = document.querySelector('.pagination');
    if (pagination) pagination.remove();

    gridEl.innerHTML = '';
    var fragment = document.createDocumentFragment();
    for (var i = 0; i < count; i++) {
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

    if (options.skeleton !== false) {
      showSkeletonGrid(8);
    }

    var params = new URLSearchParams(new FormData(filtersForm));
    params.delete('page');
    params.delete('export_docs');
    params.delete('intl_orders');
    params.delete('orden-mobile');
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

        if (options.skeleton !== false && newGrid) {
          var currentGrid = ensureProductGrid();
          renderResultsWithFade(currentGrid, newGrid.innerHTML);

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

        if (window.history && window.history.pushState) {
          window.history.pushState({}, '', url);
        }

        grid = document.getElementById('cat-product-grid');
        bindInquiryButtons();
        finishProgressBar();
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        if (requestId !== activeRequestId) return;
        finishProgressBar();
        window.location.href = url;
      });
  }

  function spinnerForInput(input) {
    return SPINNER_BY_INPUT[input.name] || null;
  }

  function isSortInput(input) {
    return input.name === 'orden' || input.name === 'orden-mobile';
  }

  if (filtersForm) {
    filtersForm.addEventListener('submit', function (e) {
      e.preventDefault();
      clearTimeout(debounceTimer);
      applyFilters({ skeleton: true });
    });

    filtersForm.querySelectorAll('input[type="checkbox"], input[type="radio"], select').forEach(function (input) {
      input.addEventListener('change', function () {
        clearTimeout(debounceTimer);
        if (isSortInput(input)) {
          applyFilters({ skeleton: false });
        } else {
          applyFilters({
            skeleton: true,
            spinner: spinnerForInput(input),
          });
        }
      });
    });

    filtersForm.querySelectorAll('input[type="number"]').forEach(function (input) {
      input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        var spinner = spinnerForInput(input);
        debounceTimer = setTimeout(function () {
          applyFilters({ skeleton: true, spinner: spinner });
        }, 500);
      });
    });
  }

  var mobileSort = document.querySelector('.results-sort-mobile');
  var desktopSort = document.querySelector('.cat-sort-select');
  if (mobileSort && desktopSort) {
    mobileSort.addEventListener('change', function () {
      desktopSort.value = mobileSort.value;
      applyFilters({ skeleton: false });
    });
  }

  window.addEventListener('popstate', function () {
    window.location.reload();
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

  function addToInquiry() {
    var badge = document.getElementById('cat-inquiry-badge');
    if (badge) {
      var current = parseInt(badge.textContent, 10) || 0;
      badge.textContent = String(current + 1);
    }
    showToast('Added to inquiry cart');
  }

  window.addToInquiry = addToInquiry;

  function bindInquiryButtons() {
    document.querySelectorAll('.btn-inquiry').forEach(function (btn) {
      if (btn.dataset.bound) return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        addToInquiry();
      });
    });
  }

  bindInquiryButtons();
})();
