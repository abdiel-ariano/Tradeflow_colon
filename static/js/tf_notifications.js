/**
 * TradeFlow — toasts y flashes unificados (3s estándar, 5s crítico, fade 200ms).
 */
(function () {
  'use strict';

  var DURATION = 4500;
  var CRITICAL_DURATION = 5000;
  var FADE_MS = 200;

  function iconFor(level) {
    if (level === 'success') return 'check_circle';
    if (level === 'error' || level === 'danger') return 'error';
    if (level === 'warning') return 'warning';
    return 'info';
  }

  function dismissRow(row, root) {
    if (!row || row._tfClosing) return;
    row._tfClosing = true;
    row.style.transition = 'opacity ' + FADE_MS + 'ms ease, transform ' + FADE_MS + 'ms ease';
    row.classList.remove('is-visible');
    row.style.opacity = '0';
    setTimeout(function () {
      if (row.parentNode) row.parentNode.removeChild(row);
    }, FADE_MS + 20);
  }

  function bindDismiss(row, root, opts) {
    opts = opts || {};
    var critical = opts.critical;
    var duration = critical ? CRITICAL_DURATION : DURATION;
    var closeBtn = row.querySelector('.tf-toast-close, .tf-flash-close');

    row.style.cursor = 'pointer';
    row.addEventListener('click', function (e) {
      if (e.target.closest('a, button, .tf-notif-dismiss-check')) return;
      dismissRow(row, root);
    });
    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        dismissRow(row, root);
      });
    }
    if (!critical) {
      setTimeout(function () { dismissRow(row, root); }, duration);
    } else {
      setTimeout(function () { dismissRow(row, root); }, duration);
    }
  }

  window.tfNotify = function (message, level, options) {
    options = options || {};
    var root = document.getElementById('tf-toast-root');
    if (!root || !message) return;
    var row = document.createElement('div');
    var lvl = level || 'success';
    var critical = lvl === 'error' || options.critical;
    row.className = 'tf-toast tf-toast-' + (critical ? 'error' : lvl);
    if (critical) row.classList.add('tf-toast-critical');
    row.innerHTML =
      '<span class="material-symbols-rounded tf-toast-ico" aria-hidden="true">' +
      iconFor(lvl) +
      '</span>' +
      '<span class="tf-toast-msg"></span>' +
      '<button type="button" class="tf-toast-close" aria-label="Close">' +
      '<span class="material-symbols-rounded" style="font-size:18px;">close</span></button>';
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
    requestAnimationFrame(function () {
      row.classList.add('is-visible');
      row.style.opacity = '1';
    });
    bindDismiss(row, root, { critical: critical });
  };

  function initFlashes() {
    var stack = document.getElementById('tf-flash-root');
    if (!stack) return;
    stack.querySelectorAll('.tf-flash').forEach(function (row) {
      var tags = (row.getAttribute('data-tf-tags') || '').toLowerCase();
      var ico = row.querySelector('.tf-flash-icon');
      var lvl = tags.indexOf('error') !== -1 || tags.indexOf('danger') !== -1 ? 'error' : tags.indexOf('success') !== -1 ? 'success' : tags.indexOf('warning') !== -1 ? 'warning' : 'info';
      if (ico) ico.textContent = iconFor(lvl);
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
    var chatOpen = false;

    function setChatOpen(open) {
      chatOpen = !!open;
      win.style.display = chatOpen ? 'flex' : 'none';
      toggle.setAttribute('aria-expanded', chatOpen ? 'true' : 'false');
      toggle.setAttribute('aria-label', chatOpen ? 'Close assistant' : 'Open assistant');
      if (chatOpen && input) {
        window.requestAnimationFrame(function () { input.focus(); });
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
