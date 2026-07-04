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
    document.querySelectorAll('.hm-alibaba [data-hm-media] img, .hm-marketplace [data-hm-media] img').forEach(bindMediaImage);
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
    if (btn) btn.disabled = true;

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
        showToast('Could not add to inquiry cart');
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  document.addEventListener('click', function (event) {
    var btn = event.target.closest('.hm-marketplace .btn-inquiry');
    if (!btn) return;
    event.preventDefault();
    event.stopPropagation();
    addToInquiry(btn.getAttribute('data-product-id'), btn);
  });

  function init() {
    initProductMedia();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
