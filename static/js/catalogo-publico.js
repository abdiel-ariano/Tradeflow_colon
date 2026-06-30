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

  var currentController = null;
  var debounceTimer = null;

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
    document.body.style.overflow = open ? 'hidden' : '';
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

  document.querySelectorAll('.view-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var view = btn.getAttribute('data-view');
      document.querySelectorAll('.view-btn').forEach(function (b) {
        var active = b === btn;
        b.classList.toggle('view-btn--active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      if (grid) {
        grid.classList.toggle('is-list-view', view === 'list');
      }
    });
  });

  var mobileSort = document.querySelector('.results-sort-mobile');
  var desktopSort = document.querySelector('.cat-sort-select');
  if (mobileSort && desktopSort) {
    mobileSort.addEventListener('change', function () {
      desktopSort.value = mobileSort.value;
      applyFilters();
    });
  }

  function setLoading(loading) {
    if (filtersForm) filtersForm.classList.toggle('is-loading', loading);
    if (grid) grid.classList.toggle('is-loading', loading);
    if (sidebar) sidebar.classList.toggle('is-loading', loading);
    if (host && window.TFSkeleton) {
      if (loading) TFSkeleton.show(host);
    }
  }

  function updateResultsCount(doc) {
    if (!resultsCountEl || !doc) return;
    var meta = doc.getElementById('cat-results-root');
    if (meta && meta.dataset.total) {
      resultsCountEl.textContent = meta.dataset.total;
    }
  }

  function applyFilters() {
    if (!filtersForm || !host || !window.fetch) return;

    if (currentController) {
      currentController.abort();
    }
    currentController = new AbortController();

    setLoading(true);

    var params = new URLSearchParams(new FormData(filtersForm));
    params.delete('page');
    params.delete('export_docs');
    params.delete('intl_orders');
    params.delete('orden-mobile');
    var qs = params.toString();
    var base = filtersForm.getAttribute('action') || window.location.pathname;
    var url = base + (qs ? '?' + qs : '');

    fetch(url + (url.indexOf('?') >= 0 ? '&' : '?') + 'partial=1', {
      signal: currentController.signal,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var content = host.querySelector('.tf-skeleton-content');
        if (content) content.innerHTML = html;

        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        updateResultsCount(doc);

        if (window.TFSkeleton && TFSkeleton.refresh) TFSkeleton.refresh(host);
        else if (window.TFSkeleton) TFSkeleton.ready(host);

        if (window.history && window.history.pushState) {
          window.history.pushState({}, '', url);
        }

        grid = document.getElementById('cat-product-grid');
        var activeList = document.querySelector('.view-btn[data-view="list"].view-btn--active');
        if (grid && activeList) {
          grid.classList.add('is-list-view');
        }

        bindInquiryButtons();
        setSidebarOpen(false);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        window.location.href = url;
      })
      .finally(function () {
        setLoading(false);
      });
  }

  if (filtersForm) {
    filtersForm.addEventListener('submit', function (e) {
      e.preventDefault();
      clearTimeout(debounceTimer);
      applyFilters();
    });

    filtersForm.querySelectorAll('input[type="checkbox"], input[type="radio"], select').forEach(function (input) {
      input.addEventListener('change', function () {
        clearTimeout(debounceTimer);
        applyFilters();
      });
    });

    filtersForm.querySelectorAll('input[type="number"]').forEach(function (input) {
      input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(applyFilters, 500);
      });
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
