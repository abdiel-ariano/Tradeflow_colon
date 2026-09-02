/**
 * TradeFlow Colón — unified floating toasts (tfNotify / TF.notify).
 */
(function (global) {
  'use strict';

  var AUTO_DISMISS_MS = 5500;
  var FADE_MS = 180;
  var DEDUPE_WINDOW_MS = 2500;
  var recentKeys = new Map();

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

  function normalizeLevel(level) {
    if (level === 'danger') return 'error';
    if (level === 'success' || level === 'error' || level === 'warning' || level === 'info') return level;
    return 'info';
  }

  function defaultTitle(level) {
    var i18n = global.TF_I18N || {};
    if (level === 'success') return i18n.toastSuccess || 'Success';
    if (level === 'error') return i18n.toastError || 'Error';
    if (level === 'warning') return i18n.toastWarning || 'Warning';
    return i18n.toastInfo || 'Information';
  }

  function shouldPersist(level, options) {
    if (options && options.persist != null) return !!options.persist;
    return level === 'error' || level === 'warning';
  }

  function getRoot() {
    var root = document.getElementById('tf-toast-root');
    if (!root) {
      root = document.createElement('div');
      root.id = 'tf-toast-root';
      root.className = 'tf-toast-root';
      root.setAttribute('role', 'region');
      root.setAttribute('aria-label', 'Notifications');
      document.body.appendChild(root);
    }
    return root;
  }

  function getAnnouncer() {
    var node = document.getElementById('tf-toast-announcer');
    if (!node) {
      node = document.createElement('div');
      node.id = 'tf-toast-announcer';
      node.className = 'tf-toast-announcer';
      node.setAttribute('aria-live', 'polite');
      node.setAttribute('aria-atomic', 'true');
      document.body.appendChild(node);
    }
    return node;
  }

  function announce(text) {
    if (!text) return;
    var node = getAnnouncer();
    node.textContent = '';
    requestAnimationFrame(function () {
      node.textContent = text;
    });
  }

  function dismissToast(toast, root, onDone) {
    if (!toast || toast._tfClosing) return;
    toast._tfClosing = true;
    if (toast._tfTimer) {
      clearTimeout(toast._tfTimer);
      toast._tfTimer = null;
    }
    toast.classList.remove('is-visible');
    toast.classList.add('is-leaving');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
      if (typeof onDone === 'function') onDone();
    }, FADE_MS + 20);
  }

  function bindAutoDismiss(toast, root, persist) {
    if (persist) return;

    function start() {
      if (toast._tfTimer) clearTimeout(toast._tfTimer);
      toast._tfTimer = setTimeout(function () {
        dismissToast(toast, root);
      }, AUTO_DISMISS_MS);
    }

    function pause() {
      if (toast._tfTimer) {
        clearTimeout(toast._tfTimer);
        toast._tfTimer = null;
      }
    }

    toast.addEventListener('mouseenter', pause);
    toast.addEventListener('mouseleave', start);
    toast.addEventListener('focusin', pause);
    toast.addEventListener('focusout', start);
    start();
  }

  function buildToast(message, level, options) {
    options = options || {};
    level = normalizeLevel(level);
    var title = options.title || '';
    var description = options.description || '';
    if (!title && !description) {
      title = String(message || '');
    } else if (!description && message && !title) {
      title = String(message);
    } else if (!description && message && title) {
      description = String(message);
    }

    var toast = document.createElement('div');
    toast.className = 'tf-toast tf-toast--' + level;
    toast.setAttribute('role', level === 'error' ? 'alert' : 'status');

    var icon = document.createElement('span');
    icon.className = 'tf-toast__icon';
    icon.innerHTML = SVG_ICONS[level] || SVG_ICONS.info;

    var content = document.createElement('div');
    content.className = 'tf-toast__content';

    if (title) {
      var titleEl = document.createElement('p');
      titleEl.className = 'tf-toast__title';
      titleEl.textContent = title;
      content.appendChild(titleEl);
    }
    if (description) {
      var descEl = document.createElement('p');
      descEl.className = 'tf-toast__desc';
      descEl.textContent = description;
      content.appendChild(descEl);
    }

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'tf-toast__close';
    closeBtn.setAttribute('aria-label', (global.TF_I18N && global.TF_I18N.close) || 'Close');
    closeBtn.innerHTML = SVG_ICONS.close;

    toast.appendChild(icon);
    toast.appendChild(content);
    toast.appendChild(closeBtn);

    return { toast: toast, closeBtn: closeBtn, announceText: description || title };
  }

  function tfNotify(message, level, options) {
    options = options || {};
    if (!message && !options.title) return null;

    level = normalizeLevel(level || options.level);
    var dedupeKey = options.dedupeKey || (level + ':' + (options.title || message));
    if (options.dedupe !== false) {
      var last = recentKeys.get(dedupeKey);
      if (last && Date.now() - last < DEDUPE_WINDOW_MS) return null;
      recentKeys.set(dedupeKey, Date.now());
    }

    var root = getRoot();
    var built = buildToast(message, level, options);
    var toast = built.toast;
    var persist = shouldPersist(level, options);

    built.closeBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      dismissToast(toast, root);
    });

    root.appendChild(toast);
    requestAnimationFrame(function () {
      toast.classList.add('is-visible');
    });

    announce((defaultTitle(level) + ': ' + built.announceText).trim());
    bindAutoDismiss(toast, root, persist);
    return toast;
  }

  function initDjangoMessages() {
    var payload = global.TF_FLASH_MESSAGES;
    if (!payload || !payload.length) return;
    payload.forEach(function (msg, index) {
      setTimeout(function () {
        var level = 'info';
        var tags = (msg.tags || '').toLowerCase();
        if (tags.indexOf('success') !== -1) level = 'success';
        else if (tags.indexOf('error') !== -1 || tags.indexOf('danger') !== -1) level = 'error';
        else if (tags.indexOf('warning') !== -1) level = 'warning';
        tfNotify(msg.text, level, {
          dedupeKey: 'flash:' + level + ':' + msg.text,
        });
      }, index * 350);
    });
  }

  global.tfNotify = tfNotify;
  if (global.TF) {
    global.TF.notify = function (message, tipo) {
      return tfNotify(message, tipo);
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDjangoMessages);
  } else {
    initDjangoMessages();
  }
})(typeof window !== 'undefined' ? window : this);
