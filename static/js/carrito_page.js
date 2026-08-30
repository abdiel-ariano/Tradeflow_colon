/**
 * TradeFlow Colón — /carrito/ quantity controls (AJAX, no full reload).
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

  var inflight = new Map();

  function getCookie(name) {
    var parts = document.cookie ? document.cookie.split(';') : [];
    for (var i = 0; i < parts.length; i += 1) {
      var chunk = parts[i].trim();
      if (chunk.indexOf(name + '=') === 0) {
        return decodeURIComponent(chunk.substring(name.length + 1));
      }
    }
    return '';
  }

  function parseJsonResponse(response) {
    var contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      throw new Error('non-json');
    }
    return response.json().then(function (data) {
      return { ok: response.ok, data: data };
    });
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

  function formatCountLabel(count) {
    var n = parseInt(count, 10) || 0;
    if (window.TF_I18N && window.TF_I18N.cartItemCount) {
      return window.TF_I18N.cartItemCount.replace('__COUNT__', String(n));
    }
    return n === 1 ? '1 item' : n + ' items';
  }

  function setSummarySubtotal(value) {
    var el = document.querySelector('[data-cart-summary-subtotal]');
    if (el) el.textContent = 'USD ' + value;
  }

  function setPageCount(count) {
    var el = document.querySelector('[data-cart-page-count]');
    if (el) el.textContent = formatCountLabel(count);
  }

  function getLineElements(item) {
    return {
      item: item,
      input: item.querySelector('[data-cart-qty-input]'),
      decrease: item.querySelector('[data-cart-qty-decrease]'),
      increase: item.querySelector('[data-cart-qty-increase]'),
      subtotal: item.querySelector('[data-cart-line-subtotal]'),
      error: item.querySelector('[data-cart-line-error]'),
      qtyWrap: item.querySelector('[data-cart-qty]'),
      form: item.querySelector('[data-cart-qty-form]'),
    };
  }

  function showLineError(els, message) {
    if (!els.error) return;
    if (message) {
      els.error.textContent = message;
      els.error.hidden = false;
    } else {
      els.error.textContent = '';
      els.error.hidden = true;
    }
  }

  function setQtyPending(els, pending) {
    if (els.qtyWrap) els.qtyWrap.classList.toggle('cart-qty--pending', pending);
    if (els.decrease) els.decrease.disabled = pending || parseInt(els.input.value, 10) <= 1;
    if (els.increase) {
      var max = parseInt(els.input.getAttribute('max') || '9999', 10);
      els.increase.disabled = pending || parseInt(els.input.value, 10) >= max;
    }
  }

  function applyLineState(els, line) {
    if (!line) return;
    var qty = parseInt(line.cantidad, 10);
    var max = parseInt(line.disponible || els.input.getAttribute('max') || '9999', 10);
    els.input.value = String(qty);
    els.input.setAttribute('max', String(max));
    if (els.subtotal) els.subtotal.textContent = 'USD ' + line.subtotal;
    if (els.decrease) els.decrease.disabled = qty <= 1;
    if (els.increase) els.increase.disabled = qty >= max;
    showLineError(els, '');
  }

  function removeLineItem(item) {
    var section = document.querySelector('.cart-items');
    item.remove();
    if (section && !section.querySelector('[data-cart-item]')) {
      window.location.reload();
    }
  }

  function postCartForm(form, body, productId) {
    var state = inflight.get(productId) || { seq: 0, controller: null };
    state.seq += 1;
    var seq = state.seq;
    if (state.controller) state.controller.abort();
    state.controller = new AbortController();
    inflight.set(productId, state);

    return fetch(form.action, {
      method: 'POST',
      body: body,
      credentials: 'same-origin',
      signal: state.controller.signal,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
    })
      .then(parseJsonResponse)
      .then(function (result) {
        if (seq !== inflight.get(productId).seq) return null;
        return result;
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return null;
        throw err;
      });
  }

  function handleQtyUpdate(item, nextQty) {
    var els = getLineElements(item);
    if (!els.form || !els.input) return;

    var min = parseInt(els.input.getAttribute('min') || '1', 10);
    var max = parseInt(els.input.getAttribute('max') || '9999', 10);
    var qty = parseInt(nextQty, 10);
    if (!Number.isFinite(qty)) qty = min;
    qty = Math.min(Math.max(qty, min), max);

    var previous = els.input.value;
    els.input.value = String(qty);
    setQtyPending(els, true);
    showLineError(els, '');

    var body = new FormData(els.form);
    body.set('cantidad', String(qty));
    var productId = item.getAttribute('data-product-id');

    postCartForm(els.form, body, productId)
      .then(function (result) {
        if (!result) return;
        var data = result.data || {};
        if (!result.ok || data.ok === false) {
          if (data.line) {
            applyLineState(els, data.line);
          } else {
            els.input.value = previous;
          }
          showLineError(els, data.message || (window.TF_I18N && window.TF_I18N.cartQtyError) || 'Could not update quantity.');
          return;
        }
        if (data.removed) {
          removeLineItem(item);
        } else if (data.line) {
          applyLineState(els, data.line);
        }
        if (data.carrito_count !== undefined) {
          updateCartBadge(data.carrito_count);
          setPageCount(data.carrito_count);
        }
        if (data.subtotal !== undefined) setSummarySubtotal(data.subtotal);
        if (data.carrito_empty) window.location.reload();
      })
      .catch(function () {
        els.input.value = previous;
        showLineError(els, (window.TF_I18N && window.TF_I18N.cartNetworkRetry) || (window.TF_I18N && window.TF_I18N.networkError) || 'Connection error. Please try again.');
      })
      .finally(function () {
        setQtyPending(els, false);
        var current = inflight.get(productId);
        if (current && current.seq === seq) current.controller = null;
      });
  }

  function handleRemove(item, form) {
    var els = getLineElements(item);
    var productId = item.getAttribute('data-product-id');
    setQtyPending(els, true);
    showLineError(els, '');

    var body = new FormData(form);
    postCartForm(form, body, productId)
      .then(function (result) {
        if (!result) return;
        var data = result.data || {};
        if (!result.ok || data.ok === false) {
          showLineError(els, data.message || (window.TF_I18N && window.TF_I18N.cartRemoveError) || 'Could not remove product.');
          return;
        }
        removeLineItem(item);
        if (data.carrito_count !== undefined) {
          updateCartBadge(data.carrito_count);
          setPageCount(data.carrito_count);
        }
        if (data.subtotal !== undefined) setSummarySubtotal(data.subtotal);
        if (data.carrito_empty) window.location.reload();
      })
      .catch(function () {
        showLineError(els, (window.TF_I18N && window.TF_I18N.cartNetworkRetry) || (window.TF_I18N && window.TF_I18N.networkError) || 'Connection error. Please try again.');
      })
      .finally(function () {
        setQtyPending(els, false);
      });
  }

  document.querySelectorAll('[data-cart-item]').forEach(function (item) {
    var els = getLineElements(item);
    if (!els.input || !els.form) return;

    if (els.decrease) {
      els.decrease.addEventListener('click', function () {
        var current = parseInt(els.input.value, 10) || 1;
        if (current <= 1) return;
        handleQtyUpdate(item, current - 1);
      });
    }

    if (els.increase) {
      els.increase.addEventListener('click', function () {
        var current = parseInt(els.input.value, 10) || 1;
        var max = parseInt(els.input.getAttribute('max') || '9999', 10);
        if (current >= max) return;
        handleQtyUpdate(item, current + 1);
      });
    }

    els.input.addEventListener('change', function () {
      handleQtyUpdate(item, els.input.value);
    });

    var removeForm = item.querySelector('[data-cart-remove-form]');
    if (removeForm) {
      removeForm.addEventListener('submit', function (ev) {
        ev.preventDefault();
        handleRemove(item, removeForm);
      });
    }

    els.form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      handleQtyUpdate(item, els.input.value);
    });
  });
})();
