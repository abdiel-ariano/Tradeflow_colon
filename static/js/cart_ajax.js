/**
 * TradeFlow Colón — agregar al carrito sin recargar la página (fetch + toast).
 */
(function () {
  'use strict';

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
    var badge = document.getElementById('tf-nav-cart-badge');
    var n = parseInt(count, 10) || 0;
    if (!badge) return;
    badge.textContent = String(n);
    if (n > 0) badge.classList.add('has-count');
    else badge.classList.remove('has-count');
    var meta = document.getElementById('tf-nav-meta');
    if (meta) meta.setAttribute('data-cart-count', String(n));
  }

  function showToast(message, level) {
    var root = document.getElementById('tf-toast-root');
    if (!root || !message) return;
    var row = document.createElement('div');
    row.className = 'tf-toast tf-toast-' + (level || 'success');
    var icon = level === 'error' ? 'error' : level === 'warning' ? 'warning' : 'check_circle';
    row.innerHTML =
      '<span class="material-symbols-rounded tf-toast-ico" aria-hidden="true">' + icon + '</span>' +
      '<span class="tf-toast-msg"></span>' +
      '<button type="button" class="tf-toast-close" aria-label="Cerrar">' +
      '<span class="material-symbols-rounded" style="font-size:18px;">close</span></button>';
    row.querySelector('.tf-toast-msg').textContent = message;
    root.appendChild(row);
    requestAnimationFrame(function () {
      row.classList.add('is-visible');
    });
    var closeBtn = row.querySelector('.tf-toast-close');
    function remove() {
      row.classList.remove('is-visible');
      setTimeout(function () {
        if (row.parentNode) row.parentNode.removeChild(row);
      }, 280);
    }
    if (closeBtn) closeBtn.addEventListener('click', remove);
    setTimeout(remove, 4200);
  }

  function bindCartForms() {
    document.querySelectorAll('form.js-cart-add-form').forEach(function (form) {
      if (form.getAttribute('data-cart-bound') === '1') return;
      form.setAttribute('data-cart-bound', '1');
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var btn = form.querySelector('button[type="submit"]');
        if (btn && btn.disabled) return;
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
          },
        })
          .then(function (r) {
            return r.json().then(function (data) {
              return { ok: r.ok, data: data };
            });
          })
          .then(function (res) {
            var data = res.data || {};
            if (!res.ok || data.ok === false) {
              showToast(data.message || 'No se pudo agregar al carrito.', 'error');
              return;
            }
            if (data.carrito_count !== undefined) {
              updateCartBadge(data.carrito_count);
            }
            showToast(data.message, data.level || 'success');
            if (btn) {
              btn.classList.add('is-added');
              setTimeout(function () {
                btn.classList.remove('is-added');
              }, 1200);
            }
          })
          .catch(function () {
            showToast('Error de conexión. Intenta de nuevo.', 'error');
          })
          .finally(function () {
            if (btn) {
              btn.disabled = false;
              btn.classList.remove('is-loading');
            }
          });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindCartForms);
  } else {
    bindCartForms();
  }
})();
