/**
 * TradeFlow Colón — home marketplace (inquiry actions + product media loading)
 */
(function () {
  'use strict';

  var mediaFallback = window.TFHomeMediaFallback || function () {};

  function markMediaLoaded(img) {
    var wrap = img.closest('[data-hm-media]');
    if (!wrap) return;
    wrap.classList.add('is-loaded');
    if (img.classList.contains('is-placeholder')) {
      wrap.classList.add('is-error');
    }
  }

  function bindMediaImage(img) {
    function onLoad() {
      markMediaLoaded(img);
    }

    function onError() {
      var prev = img.src;
      mediaFallback(img);
      if (img.src !== prev) {
        img.addEventListener('load', onLoad, { once: true });
        img.addEventListener('error', function () {
          markMediaLoaded(img);
        }, { once: true });
        return;
      }
      markMediaLoaded(img);
    }

    if (img.complete && img.naturalWidth > 0) {
      onLoad();
      return;
    }

    img.addEventListener('load', onLoad, { once: true });
    img.addEventListener('error', onError, { once: true });
  }

  function initProductMedia() {
    var wraps = document.querySelectorAll('.hm-alibaba [data-hm-media], .hm-marketplace [data-hm-media]');
    wraps.forEach(function (wrap) {
      wrap.classList.add('is-loaded');
    });
    document.querySelectorAll('.hm-alibaba [data-hm-media] img, .hm-marketplace [data-hm-media] img').forEach(bindMediaImage);
  }

  function finalizeProductMedia() {
    document.querySelectorAll('.hm-alibaba [data-hm-media], .hm-marketplace [data-hm-media]').forEach(function (wrap) {
      wrap.classList.add('is-loaded');
    });
  }

  var config = document.getElementById('hm-marketplace-config');
  var inquiryUrlPattern = config ? config.getAttribute('data-inquiry-url') : '';

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

  function showToast(message, level) {
    if (window.tfNotify) {
      window.tfNotify(message, level || 'success', { variant: 'cart' });
      return;
    }
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
    }, 2400);
  }

  function updateCartBadges(count) {
    if (typeof window.tfUpdateCartBadge === 'function') {
      window.tfUpdateCartBadge(count);
      return;
    }
    var n = parseInt(count, 10) || 0;
    document.querySelectorAll('#cat-inquiry-badge, #bn-cart-badge, .cart-badge, #tf-nav-cart-badge, [data-cart-badge]').forEach(function (badge) {
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
    if (btn) btn.disabled = true;

    fetch(inquiryUrlFor(productId), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body: 'cantidad=1',
    })
      .then(function (r) {
        var contentType = r.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
          throw new Error('non-json');
        }
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        var data = res.data || {};
        if (!res.ok || data.ok === false) {
          showToast(data.message || (window.TF_I18N && window.TF_I18N.catalogCartError) || 'Could not add to inquiry cart', 'error');
          return;
        }
        updateCartBadges(data.carrito_count);
        showToast(data.message || (window.TF_I18N && window.TF_I18N.catalogAddedToCart) || 'Added to inquiry cart', 'success');
      })
      .catch(function () {
        showToast((window.TF_I18N && window.TF_I18N.catalogNetworkError) || 'Connection error — try again', 'error');
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  document.addEventListener('click', function (event) {
    var btn = event.target.closest('.hm-marketplace .btn-inquiry');
    if (!btn) return;
    if (btn.closest('form.js-cart-add-form')) return;
    if (btn.type === 'submit') return;
    if (!btn.getAttribute('data-product-id')) return;
    event.preventDefault();
    event.stopPropagation();
    addToInquiry(btn.getAttribute('data-product-id'), btn);
  });

  function init() {
    initProductMedia();
    window.addEventListener('load', finalizeProductMedia, { once: true });
    window.setTimeout(finalizeProductMedia, 400);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
