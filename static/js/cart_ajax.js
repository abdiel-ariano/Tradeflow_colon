/**
 * TradeFlow Colón — agregar al carrito sin recargar la página (fetch + toast).
 */
(function () {
  'use strict';

  var BADGE_SELECTORS = [
    '#cat-inquiry-badge',
    '#bn-cart-badge',
    '.cart-badge',
    '#tf-nav-cart-badge',
    '.tf-cart-badge',
    '#td-hero-cart-badge',
    '[data-cart-badge]',
  ].join(', ');

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

  function updateCartBadge(count) {
    var n = parseInt(count, 10) || 0;
    document.querySelectorAll(BADGE_SELECTORS).forEach(function (badge) {
      badge.textContent = String(n);
      badge.classList.toggle('is-empty', n < 1);
      if (n > 0) badge.classList.add('has-count');
      else badge.classList.remove('has-count');
    });
    var meta = document.getElementById('tf-nav-meta');
    if (meta) meta.setAttribute('data-cart-count', String(n));
  }

  function showToast(message, level) {
    if (!message) return;
    if (window.tfNotify) {
      window.tfNotify(message, level, { critical: level === 'error' });
      return;
    }
    var toast = document.createElement('div');
    toast.className = 'inquiry-toast is-visible';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function () {
      toast.classList.remove('is-visible');
      setTimeout(function () { toast.remove(); }, 300);
    }, 2500);
  }

  function parseJsonResponse(r) {
    var contentType = r.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      throw new Error('non-json');
    }
    return r.json().then(function (data) {
      return { ok: r.ok, data: data };
    });
  }

  window.tfUpdateCartBadge = updateCartBadge;
  window.tfCartAjaxInit = bindCartForms;

  function submitCartForm(form) {
    if (!form || form.getAttribute('data-cart-busy') === '1') return;
    form.setAttribute('data-cart-busy', '1');
    var btn = form.querySelector('button[type="submit"]');
    if (btn) {
      btn.disabled = true;
      btn.classList.add('is-loading');
    }
    var body = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      body: body,
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
    })
      .then(parseJsonResponse)
      .then(function (res) {
        var data = res.data || {};
        if (!res.ok || data.ok === false) {
          showToast(
            data.message
              || (window.TF_I18N && window.TF_I18N.cartError)
              || 'Could not add to cart.',
            'error'
          );
          return;
        }
        if (data.carrito_count !== undefined) {
          updateCartBadge(data.carrito_count);
        }
        var msg = data.message || '';
        if (msg.length > 48) {
          msg = (window.TF_I18N && window.TF_I18N.cartAddedShort) || 'Added to cart';
        }
        showToast(msg, data.level || 'success');
        if (btn) {
          btn.classList.add('is-added');
          setTimeout(function () {
            btn.classList.remove('is-added');
          }, 1200);
        }
      })
      .catch(function () {
        showToast(
          (window.TF_I18N && window.TF_I18N.networkError)
            || (window.TF_I18N && window.TF_I18N.catalogNetworkError)
            || 'Connection error. Please try again.',
          'error'
        );
      })
      .finally(function () {
        form.removeAttribute('data-cart-busy');
        if (btn) {
          btn.disabled = false;
          btn.classList.remove('is-loading');
        }
      });
  }

  function bindCartForms() {
    /* Legacy hook for pages that call tfCartAjaxInit after AJAX swaps. */
  }

  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form || !form.matches || !form.matches('form.js-cart-add-form')) return;
    ev.preventDefault();
    ev.stopPropagation();
    submitCartForm(form);
  }, true);
})();
