/**
 * TradeFlow — toasts y flashes unificados (SVG icons, snackbar para carrito).
 */
(function () {
  'use strict';

  var DURATION = 4000;
  var CART_DURATION = 2400;
  var CRITICAL_DURATION = 5000;
  var FADE_MS = 200;

  var SVG_ICONS = {
    success:
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm-1.2 14.2-4.2-4.2 1.4-1.4 2.8 2.8 5.8-5.8 1.4 1.4Z"/></svg>',
    error:
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm1 5v6h-2V7Zm0 8v2h-2v-2Z"/></svg>',
    warning:
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 2 1 21h22L12 2Zm1 15h-2v-2h2Zm0-4h-2V9h2Z"/></svg>',
    info:
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm1 15h-2v-6h2Zm0-8h-2V7h2Z"/></svg>',
    close:
      '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M18.3 5.71a1 1 0 0 0-1.41 0L12 10.59 7.11 5.7A1 1 0 0 0 5.7 7.11L10.59 12l-4.89 4.89a1 1 0 1 0 1.41 1.41L12 13.41l4.89 4.89a1 1 0 0 0 1.41-1.41L13.41 12l4.89-4.89a1 1 0 0 0 0-1.4Z"/></svg>',
  };

  function iconSvg(level) {
    if (level === 'success') return SVG_ICONS.success;
    if (level === 'error' || level === 'danger') return SVG_ICONS.error;
    if (level === 'warning') return SVG_ICONS.warning;
    return SVG_ICONS.info;
  }

  function iconForFlash(level) {
    if (level === 'success') return 'check_circle';
    if (level === 'error' || level === 'danger') return 'error';
    if (level === 'warning') return 'warning';
    return 'info';
  }

  function syncSnackbarRoot(root) {
    if (!root) return;
    if (root.querySelector('.tf-toast-compact')) {
      root.classList.add('tf-toast-root--snackbar');
    } else {
      root.classList.remove('tf-toast-root--snackbar');
    }
  }

  function dismissRow(row, root, opts) {
    if (!row || row._tfClosing) return;
    row._tfClosing = true;
    row.style.transition = 'opacity ' + FADE_MS + 'ms ease, transform ' + FADE_MS + 'ms ease';
    row.classList.remove('is-visible');
    row.style.opacity = '0';
    setTimeout(function () {
      if (row.parentNode) row.parentNode.removeChild(row);
      syncSnackbarRoot(root);
      if (opts && typeof opts.onDismiss === 'function') opts.onDismiss();
    }, FADE_MS + 20);
  }

  function bindDismiss(row, root, opts) {
    opts = opts || {};
    var critical = opts.critical;
    var duration = opts.duration || (critical ? CRITICAL_DURATION : DURATION);
    var closeBtn = row.querySelector('.tf-toast-close, .tf-flash-close');

    row.addEventListener('click', function (e) {
      if (e.target.closest('a, button, .tf-notif-dismiss-check')) return;
      dismissRow(row, root, opts);
    });
    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        dismissRow(row, root, opts);
      });
    }
    setTimeout(function () { dismissRow(row, root, opts); }, duration);
  }

  window.tfNotify = function (message, level, options) {
    options = options || {};
    var root = document.getElementById('tf-toast-root');
    if (!root || !message) return;
    var row = document.createElement('div');
    var lvl = level || 'success';
    var critical = lvl === 'error' || options.critical;
    var isCart = options.variant === 'cart';
    row.className = 'tf-toast tf-toast-' + (critical ? 'error' : lvl);
    if (critical) row.classList.add('tf-toast-critical');
    if (isCart) row.classList.add('tf-toast-compact');
    row.innerHTML =
      '<span class="tf-toast-ico" aria-hidden="true">' + iconSvg(lvl) + '</span>' +
      '<span class="tf-toast-msg"></span>' +
      '<button type="button" class="tf-toast-close" aria-label="Close">' +
      SVG_ICONS.close + '</button>';
    row.querySelector('.tf-toast-msg').textContent = message;
    if (options.dismissKey) {
      var wrap = document.createElement('label');
      wrap.className = 'tf-notif-dismiss-check';
      wrap.style.cssText = 'display:block;font-size:11px;margin-top:6px;cursor:pointer;';
      wrap.innerHTML =
        '<input type="checkbox" style="margin-right:4px;"> Do not show again';
      wrap.querySelector('input').addEventListener('change', function (ev) {
        if (ev.target.checked) {
          try { localStorage.setItem('tf_hide_' + options.dismissKey, '1'); } catch (e) {}
        }
      });
      row.appendChild(wrap);
      try {
        if (localStorage.getItem('tf_hide_' + options.dismissKey) === '1') return;
      } catch (e) {}
    }
    root.appendChild(row);
    syncSnackbarRoot(root);
    requestAnimationFrame(function () {
      row.classList.add('is-visible');
      row.style.opacity = '1';
    });
    bindDismiss(row, root, {
      critical: critical,
      duration: isCart ? CART_DURATION : (critical ? CRITICAL_DURATION : DURATION),
    });
  };

  function initFlashes() {
    var stack = document.getElementById('tf-flash-root');
    if (!stack) return;
    stack.querySelectorAll('.tf-flash').forEach(function (row) {
      var tags = (row.getAttribute('data-tf-tags') || '').toLowerCase();
      var ico = row.querySelector('.tf-flash-icon');
      var lvl = tags.indexOf('error') !== -1 || tags.indexOf('danger') !== -1
        ? 'error'
        : tags.indexOf('success') !== -1
          ? 'success'
          : tags.indexOf('warning') !== -1
            ? 'warning'
            : 'info';
      if (ico) {
        if (ico.classList.contains('material-symbols-rounded')) {
          ico.textContent = iconForFlash(lvl);
        } else {
          ico.innerHTML = iconSvg(lvl);
        }
      }
      var critical = tags.indexOf('error') !== -1 || tags.indexOf('danger') !== -1;
      bindDismiss(row, stack, { critical: critical });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  var ASSISTANT_ICON_SVG =
    '<svg viewBox="0 0 24 24" fill="none" focusable="false" aria-hidden="true">' +
    '<path fill="currentColor" d="M12 2.75a8 8 0 0 0-8 8c0 2.74 1.38 5.17 3.48 6.62L6.25 20.75l4.1-2.05a8.02 8.02 0 0 0 1.65.17 8 8 0 1 0 0-16Zm-3.1 8.35a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Zm3.1 0a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Zm3.1 0a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Z"/>' +
    '<path fill="currentColor" d="M17.15 4.1a.55.55 0 0 1 .55.55v.95h.95a.55.55 0 0 1 0 1.1h-.95v.95a.55.55 0 0 1-1.1 0v-.95h-.95a.55.55 0 0 1 0-1.1h.95v-.95a.55.55 0 0 1 .55-.55Z"/>' +
    '</svg>';

  function renderAssistantIcon(el, sizeClass) {
    if (!el || el.getAttribute('data-tf-assistant-icon') === '1') return;
    el.setAttribute('data-tf-assistant-icon', '1');
    el.classList.add('tf-icon');
    if (sizeClass) el.classList.add(sizeClass);
    el.innerHTML = ASSISTANT_ICON_SVG;
  }

  function patchChatWidget() {
    var win = document.getElementById('tf-chat-window');
    var toggle = document.getElementById('tf-chat-toggle');
    if (!win || !toggle) return;

    renderAssistantIcon(toggle.querySelector('.tf-icon'), 'tf-icon--chat');
    renderAssistantIcon(
      document.querySelector('#tf-assistant .tf-chat-header-avatar .tf-icon'),
      'tf-icon--chat-header'
    );

    var closeBtn = document.getElementById('tf-chat-close');
    var input = document.getElementById('tf-chat-input');
    var assistant = document.getElementById('tf-assistant');
    var chatOpen = false;

    function setChatOpen(open) {
      chatOpen = !!open;
      win.style.display = chatOpen ? 'flex' : 'none';
      if (assistant) {
        assistant.classList.toggle('tf-assistant--open', chatOpen);
      }
      toggle.setAttribute('aria-expanded', chatOpen ? 'true' : 'false');
      toggle.setAttribute('aria-label', chatOpen ? 'Close assistant' : 'Open assistant');
      if (chatOpen && input) {
        window.requestAnimationFrame(function () { input.focus(); });
      } else if (!chatOpen && typeof window.TF_SYNC_ASSISTANT_DOCK === 'function') {
        window.requestAnimationFrame(window.TF_SYNC_ASSISTANT_DOCK);
      }
    }

    function onToggleClick(e) {
      e.preventDefault();
      e.stopImmediatePropagation();
      setChatOpen(!chatOpen);
    }

    var freshToggle = toggle.cloneNode(true);
    toggle.parentNode.replaceChild(freshToggle, toggle);
    toggle = freshToggle;
    toggle.addEventListener('click', onToggleClick);

    if (closeBtn) {
      var freshClose = closeBtn.cloneNode(true);
      closeBtn.parentNode.replaceChild(freshClose, closeBtn);
      freshClose.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopImmediatePropagation();
        setChatOpen(false);
      });
    }
  }

  function onReady() {
    initFlashes();
    patchChatWidget();
  }
})();
