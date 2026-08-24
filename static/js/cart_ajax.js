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

  var CART_TOAST_SVG =
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
    '<path fill="currentColor" d="M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 0a2 2 0 1 0 .001 3.999A2 2 0 0 0 17 18ZM6.2 6h14.3l-1.4 7.2a1 1 0 0 1-1 .8H9.2L6.2 6Zm-1.2-2h16l2 10a3 3 0 0 1-3 2.4H8.4L6.7 4.6 4 2H1v2h2.2Z"/></svg>';

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

  function readBadgeCount() {
    var badge = document.querySelector(BADGE_SELECTORS);
    if (!badge) return 0;
    return parseInt(badge.textContent, 10) || 0;
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
    var shortMsg = message;
    if (shortMsg.length > 42) {
      shortMsg = (window.TF_I18N && window.TF_I18N.cartAddedShort) || 'Added to inquiry cart';
    }
    if (window.tfNotify) {
      window.tfNotify(shortMsg, level || 'success', { variant: 'cart' });
      return;
    }
    var toast = document.createElement('div');
    toast.className = 'tf-cart-snackbar is-visible';
    toast.innerHTML =
      '<span class="tf-cart-snackbar__ico">' + CART_TOAST_SVG + '</span>' +
      '<span class="tf-cart-snackbar__msg"></span>';
    toast.querySelector('.tf-cart-snackbar__msg').textContent = shortMsg;
    document.body.appendChild(toast);
    setTimeout(function () {
      toast.classList.remove('is-visible');
      setTimeout(function () { toast.remove(); }, 220);
    }, 2400);
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

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      if (!btn.dataset.tfCartLabel) {
        btn.dataset.tfCartLabel = btn.textContent.trim();
      }
      btn.textContent = (window.TF_I18N && window.TF_I18N.cartAdding) || 'Adding…';
      btn.disabled = true;
      btn.classList.add('is-loading');
      return;
    }
    if (btn.dataset.tfCartLabel) {
      btn.textContent = btn.dataset.tfCartLabel;
    }
    btn.disabled = false;
    btn.classList.remove('is-loading');
  }

  window.tfUpdateCartBadge = updateCartBadge;
  window.tfCartAjaxInit = function () {};

  function submitCartForm(form) {
    if (!form || form.getAttribute('data-cart-busy') === '1') return;
    form.setAttribute('data-cart-busy', '1');
    var btn = form.querySelector('button[type="submit"]');
    var qtyInput = form.querySelector('[name="cantidad"]');
    var qty = parseInt(qtyInput && qtyInput.value ? qtyInput.value : '1', 10) || 1;
    var prevCount = readBadgeCount();
    var optimistic = true;

    setButtonLoading(btn, true);
    updateCartBadge(prevCount + qty);

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
          if (optimistic) updateCartBadge(prevCount);
          showToast(
            data.message
              || (window.TF_I18N && window.TF_I18N.cartError)
              || 'Could not add to inquiry cart.',
            'error'
          );
          return;
        }
        if (data.carrito_count !== undefined) {
          updateCartBadge(data.carrito_count);
        }
        showToast(data.message || (window.TF_I18N && window.TF_I18N.cartAddedShort) || 'Added to inquiry cart', 'success');
        if (btn) {
          btn.classList.add('is-added');
          setTimeout(function () {
            btn.classList.remove('is-added');
          }, 900);
        }
      })
      .catch(function () {
        if (optimistic) updateCartBadge(prevCount);
        showToast(
          (window.TF_I18N && window.TF_I18N.networkError)
            || (window.TF_I18N && window.TF_I18N.catalogNetworkError)
            || 'Connection error. Please try again.',
          'error'
        );
      })
      .finally(function () {
        form.removeAttribute('data-cart-busy');
        setButtonLoading(btn, false);
      });
  }

  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form || !form.matches || !form.matches('form.js-cart-add-form')) return;
    ev.preventDefault();
    ev.stopPropagation();
    submitCartForm(form);
  }, true);
})();
