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

  /* Filter section accordions */
  document.querySelectorAll('[data-filter-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    });
  });

  /* View toggle */
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

  /* Mobile sort sync */
  var mobileSort = document.querySelector('.results-sort-mobile');
  var desktopSort = document.querySelector('.cat-sort-select');
  if (mobileSort && desktopSort) {
    mobileSort.addEventListener('change', function () {
      desktopSort.value = mobileSort.value;
    });
  }

  /* AJAX filter reload */
  function reloadResults(url) {
    if (!host || !window.TFSkeleton) return;
    TFSkeleton.show(host);
    fetch(url + (url.indexOf('?') >= 0 ? '&' : '?') + 'partial=1', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var content = host.querySelector('.tf-skeleton-content');
        if (content) content.innerHTML = html;
        if (window.TFSkeleton && TFSkeleton.refresh) TFSkeleton.refresh(host);
        else if (window.TFSkeleton) TFSkeleton.ready(host);
        if (window.history && window.history.replaceState) {
          window.history.replaceState({}, '', url);
        }
        bindInquiryButtons();
      })
      .catch(function () {
        window.location.href = url;
      });
  }

  if (filtersForm && host) {
    filtersForm.addEventListener('submit', function (e) {
      if (!window.fetch) return;
      e.preventDefault();
      var params = new URLSearchParams(new FormData(filtersForm));
      params.delete('page');
      params.delete('export_docs');
      params.delete('intl_orders');
      params.delete('orden-mobile');
      var qs = params.toString();
      var base = filtersForm.getAttribute('action') || window.location.pathname;
      setSidebarOpen(false);
      reloadResults(base + (qs ? '?' + qs : ''));
    });
  }

  /* Inquiry counter */
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
