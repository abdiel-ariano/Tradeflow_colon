/**
 * TradeFlow AI Search — Google-style typeahead for every search input.
 *
 * Usage (templates)
 * -----------------
 *   <input type="search" data-tf-ai-search="public" …>
 *
 * Scopes: public | buyer | seller | admin  →  GET /api/search/suggest/?q=&scope=
 *
 * Include once per page:
 *   {% include "core/includes/tf_ai_search_assets.html" %}
 *
 * Programmatic re-init after dynamic DOM:
 *   window.TFAiSearch.init(document.getElementById('my-root'));
 *
 * See docs/AI_SEARCH.md for architecture and extension notes.
 */
(function (global) {
  'use strict';

  var DEBOUNCE_MS = 220;
  var MIN_CHARS = 1;
  var PANEL_Z_INDEX = 10050;

  function i18n(key, fallback) {
    var bag = global.TF_I18N || {};
    return bag[key] || fallback;
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function highlightQuery(label, query) {
    var text = String(label || '');
    var q = (query || '').trim();
    if (!q || q.length < 2) {
      return escapeHtml(text);
    }
    var lower = text.toLowerCase();
    var needle = q.toLowerCase();
    var idx = lower.indexOf(needle);
    if (idx === -1) {
      return escapeHtml(text);
    }
    return (
      escapeHtml(text.slice(0, idx)) +
      '<mark class="tf-ai-search-mark">' +
      escapeHtml(text.slice(idx, idx + needle.length)) +
      '</mark>' +
      escapeHtml(text.slice(idx + needle.length))
    );
  }

  function groupLabel(type) {
    var map = {
      product: i18n('aiSearchProducts', 'Products'),
      category: i18n('aiSearchCategories', 'Categories'),
      company: i18n('aiSearchCompanies', 'Companies'),
      order: i18n('aiSearchOrders', 'Orders'),
      quote: i18n('aiSearchQuotes', 'Quotes'),
      customer: i18n('aiSearchCustomers', 'Customers'),
      action: i18n('aiSearchActions', 'Quick actions'),
    };
    return map[type] || i18n('aiSearchSuggestions', 'Suggestions');
  }

  /** Wrap the native input so flex layouts in navbars keep working. */
  function ensureWrap(input) {
    var parent = input.parentElement;
    if (!parent) return null;
    if (parent.classList.contains('tf-ai-search-wrap')) {
      return parent;
    }
    var wrap = document.createElement('div');
    wrap.className = 'tf-ai-search-wrap';
    parent.insertBefore(wrap, input);
    wrap.appendChild(input);
    return wrap;
  }

  /** Outer orange shell (.search-bar or .tf-hdr-search) — used for connected dropdown layout. */
  function findSearchShell(input) {
    return (
      input.closest('.search-bar') ||
      input.closest('.tf-hdr-search') ||
      input.form
    );
  }

  /** Floating panel is portaled to <body> to escape overflow:hidden ancestors. */
  function buildPanel(input) {
    var panel = document.createElement('div');
    panel.className = 'tf-ai-search-panel tf-ai-search-panel--floating';
    panel.setAttribute('role', 'listbox');
    panel.id = 'tf-ai-panel-' + Math.random().toString(36).slice(2, 8);
    panel.setAttribute('data-tf-ai-for', input.id || '');
    panel.setAttribute('aria-hidden', 'true');
    document.body.appendChild(panel);
    return panel;
  }

  /** Align panel width to the full search shell (not just the text input). */
  function positionPanel(input, panel) {
    var shell = findSearchShell(input);
    var rect = shell ? shell.getBoundingClientRect() : input.getBoundingClientRect();
    var viewportWidth = global.innerWidth || document.documentElement.clientWidth || 0;
    var width = Math.max(Math.round(rect.width), 280);
    var left = Math.round(rect.left);
    if (left + width > viewportWidth - 8) {
      left = Math.max(8, viewportWidth - width - 8);
    }
    panel.style.position = 'fixed';
    panel.style.top = Math.round(rect.bottom) + 'px';
    panel.style.left = left + 'px';
    panel.style.width = width + 'px';
    panel.style.right = 'auto';
    panel.style.zIndex = String(PANEL_Z_INDEX);
    panel.classList.toggle('is-connected', !!shell);
  }

  function setShellActive(input, panel, active) {
    var shell = findSearchShell(input);
    if (shell) {
      shell.classList.toggle('is-suggesting', active);
    }
    panel.classList.toggle('is-connected', active && !!shell);
  }

  function openAssistantWithQuery(query) {
    if (typeof global.TF_OPEN_ASSISTANT === 'function') {
      global.TF_OPEN_ASSISTANT(query);
      return;
    }
    var toggle = document.getElementById('tf-chat-toggle');
    var chatInput = document.getElementById('tf-chat-input');
    if (toggle) toggle.click();
    if (chatInput && query) {
      chatInput.value = query;
      chatInput.focus();
    }
  }

  function buildSuggestionButton(item, query, onPick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tf-ai-search-item';
    btn.setAttribute('role', 'option');

    if (item.type === 'product') {
      btn.classList.add('tf-ai-search-item--product');
      var meta = item.meta || {};
      var thumb = item.image_url
        ? '<span class="tf-ai-search-thumb"><img src="' +
          escapeHtml(item.image_url) +
          '" alt="" loading="lazy" decoding="async"></span>'
        : '<span class="tf-ai-search-thumb tf-ai-search-thumb--icon" aria-hidden="true">' +
          '<span class="material-symbols-rounded">' +
          escapeHtml(item.icon || 'inventory_2') +
          '</span></span>';

      var chips = '';
      if (meta.company) {
        chips += '<span class="tf-ai-search-meta-chip">' + escapeHtml(meta.company) + '</span>';
      }
      if (meta.category) {
        chips += '<span class="tf-ai-search-meta-chip">' + escapeHtml(meta.category) + '</span>';
      }

      var price =
        meta.price
          ? '<span class="tf-ai-search-price">' +
            escapeHtml(meta.currency || 'USD') +
            ' ' +
            escapeHtml(meta.price) +
            '</span>'
          : '';

      btn.innerHTML =
        thumb +
        '<span class="tf-ai-search-item-body">' +
        '<span class="tf-ai-search-item-top">' +
        '<strong>' +
        highlightQuery(item.label, query) +
        '</strong>' +
        price +
        '</span>' +
        (meta.sku
          ? '<span class="tf-ai-search-sku">' + escapeHtml(meta.sku) + '</span>'
          : '') +
        (chips ? '<span class="tf-ai-search-meta">' + chips + '</span>' : '') +
        '</span>';
    } else {
      btn.classList.add('tf-ai-search-item--compact');
      btn.innerHTML =
        '<span class="tf-ai-search-thumb tf-ai-search-thumb--icon tf-ai-search-thumb--' +
        escapeHtml(item.type || 'action') +
        '" aria-hidden="true">' +
        '<span class="material-symbols-rounded">' +
        escapeHtml(item.icon || 'search') +
        '</span></span>' +
        '<span class="tf-ai-search-item-body">' +
        '<strong>' +
        highlightQuery(item.label, query) +
        '</strong>' +
        (item.subtitle
          ? '<span class="tf-ai-search-subtitle">' + escapeHtml(item.subtitle) + '</span>'
          : '') +
        '</span>';
    }

    btn.addEventListener('mousedown', function (ev) {
      ev.preventDefault();
      onPick(item);
    });
    return btn;
  }

  function renderPanel(panel, data, onPick, query) {
    panel.innerHTML = '';
    var suggestions = (data && data.suggestions) || [];
    var related = (data && data.related) || [];
    var tip = data && data.tip;
    var aiEnabled = data && data.ai_enabled !== false;
    var q = (query || (data && data.query) || '').trim();

    if (!q && suggestions.length) {
      var header = document.createElement('div');
      header.className = 'tf-ai-search-panel-header';
      header.textContent = i18n('aiSearchPopular', 'Popular right now');
      panel.appendChild(header);
    }

    if (tip && aiEnabled) {
      var tipEl = document.createElement('div');
      tipEl.className = 'tf-ai-search-tip';
      tipEl.innerHTML =
        '<span class="material-symbols-rounded" aria-hidden="true">auto_awesome</span><span>' +
        escapeHtml(tip) +
        '</span>';
      panel.appendChild(tipEl);
    }

    if (!suggestions.length) {
      var empty = document.createElement('div');
      empty.className = 'tf-ai-search-empty';
      empty.textContent = q
        ? i18n('aiSearchEmpty', 'No suggestions — press Enter to search.')
        : i18n('aiSearchStart', 'Start typing to see AI recommendations.');
      panel.appendChild(empty);
    } else {
      var groups = {};
      suggestions.forEach(function (item) {
        var key = item.type || 'action';
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
      });
      Object.keys(groups).forEach(function (key) {
        var title = document.createElement('div');
        title.className = 'tf-ai-search-group-title';
        title.textContent = groupLabel(key);
        panel.appendChild(title);
        groups[key].forEach(function (item) {
          panel.appendChild(buildSuggestionButton(item, q, onPick));
        });
      });
    }

    if (related.length) {
      var rel = document.createElement('div');
      rel.className = 'tf-ai-search-related';
      related.forEach(function (phrase) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = phrase;
        b.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          onPick({ label: phrase, url: null, _phrase: phrase });
        });
        rel.appendChild(b);
      });
      panel.appendChild(rel);
    }

    if (q.length >= 2) {
      var ask = document.createElement('button');
      ask.type = 'button';
      ask.className = 'tf-ai-search-ask';
      ask.innerHTML =
        '<span class="material-symbols-rounded" aria-hidden="true">smart_toy</span>' +
        '<span>' +
        i18n('aiSearchAskAbout', 'Ask AI about this search') +
        '</span>';
      ask.addEventListener('mousedown', function (ev) {
        ev.preventDefault();
        openAssistantWithQuery(q);
      });
      panel.appendChild(ask);
    }
  }

  /** Bind one search input: debounced fetch, keyboard nav, click-outside close. */
  function attach(input) {
    if (!input || input.dataset.tfAiBound === '1') return;
    input.dataset.tfAiBound = '1';

    var scope = input.getAttribute('data-tf-ai-search') || 'public';
    var endpoint =
      input.getAttribute('data-tf-ai-endpoint') ||
      (global.TF_AI_SEARCH_URL || '/api/search/suggest/');
    var wrap = ensureWrap(input);
    if (!wrap) return;
    var panel = buildPanel(input);
    var timer = null;
    var controller = null;
    var activeIndex = -1;
    var isOpen = false;

    function closePanel() {
      panel.classList.remove('is-open');
      panel.setAttribute('aria-hidden', 'true');
      setShellActive(input, panel, false);
      activeIndex = -1;
      isOpen = false;
    }

    function openPanel() {
      positionPanel(input, panel);
      panel.classList.add('is-open');
      panel.setAttribute('aria-hidden', 'false');
      setShellActive(input, panel, true);
      isOpen = true;
    }

    function syncPanelPosition() {
      if (!isOpen) return;
      positionPanel(input, panel);
    }

    function navigate(item) {
      if (item._phrase) {
        input.value = item._phrase;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        if (input.form && input.form.requestSubmit) {
          input.form.requestSubmit();
        } else if (input.form) {
          input.form.submit();
        }
        closePanel();
        return;
      }
      if (item.url) {
        global.location.href = item.url;
      }
    }

    function showLoading() {
      panel.innerHTML =
        '<div class="tf-ai-search-loading">' +
        '<div class="tf-ai-search-skeleton"></div>' +
        '<div class="tf-ai-search-skeleton"></div>' +
        '<div class="tf-ai-search-skeleton tf-ai-search-skeleton--short"></div>' +
        '</div>';
      openPanel();
    }

    function fetchSuggestions(q) {
      if (controller) controller.abort();
      controller = new AbortController();
      showLoading();
      var url =
        endpoint +
        '?q=' +
        encodeURIComponent(q) +
        '&scope=' +
        encodeURIComponent(scope);
      fetch(url, {
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        signal: controller.signal,
      })
        .then(function (r) {
          if (!r.ok) {
            if (r.status === 429) {
              return { ok: false, suggestions: [], related: [], query: q, _error: 'rate_limit' };
            }
            return r.json().catch(function () {
              return { ok: false, suggestions: [], related: [], query: q, _error: 'http_' + r.status };
            });
          }
          return r.json();
        })
        .then(function (data) {
          if (data && data._error) {
            var errMsg =
              data._error === 'rate_limit'
                ? i18n(
                    'aiSearchRateLimit',
                    'Too many searches — wait a moment and try again.'
                  )
                : i18n(
                    'aiSearchUnavailable',
                    'Suggestions unavailable — press Enter to search.'
                  );
            renderPanel(panel, { suggestions: [], related: [], query: q, tip: null }, navigate, q);
            var emptyEl = panel.querySelector('.tf-ai-search-empty');
            if (emptyEl) {
              emptyEl.textContent = errMsg;
            }
            openPanel();
            return;
          }
          renderPanel(panel, data, navigate, q);
          openPanel();
        })
        .catch(function (err) {
          if (err && err.name === 'AbortError') return;
          renderPanel(panel, { suggestions: [], related: [], query: q }, navigate, q);
          var emptyEl = panel.querySelector('.tf-ai-search-empty');
          if (emptyEl) {
            emptyEl.textContent = i18n(
              'aiSearchUnavailable',
              'Suggestions unavailable — press Enter to search.'
            );
          }
          openPanel();
        });
    }

    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = (input.value || '').trim();
      if (q.length < MIN_CHARS) {
        fetchSuggestions('');
        return;
      }
      timer = setTimeout(function () {
        fetchSuggestions(q);
      }, DEBOUNCE_MS);
    });

    input.addEventListener('focus', function () {
      fetchSuggestions((input.value || '').trim());
    });

    input.addEventListener('keydown', function (ev) {
      var items = panel.querySelectorAll('.tf-ai-search-item, .tf-ai-search-ask');
      if (!items.length) return;
      if (ev.key === 'ArrowDown') {
        ev.preventDefault();
        if (!isOpen) openPanel();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault();
        if (!isOpen) openPanel();
        activeIndex = Math.max(activeIndex - 1, 0);
      } else if (ev.key === 'Escape') {
        closePanel();
        return;
      } else {
        return;
      }
      items.forEach(function (el, idx) {
        el.classList.toggle('is-active', idx === activeIndex);
      });
      if (activeIndex >= 0 && ev.key === 'Enter') {
        ev.preventDefault();
        items[activeIndex].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      }
    });

    document.addEventListener('click', function (ev) {
      var shell = findSearchShell(input);
      var insideShell = shell && shell.contains(ev.target);
      if (!wrap.contains(ev.target) && !panel.contains(ev.target) && !insideShell) {
        closePanel();
      }
    });

    global.addEventListener('resize', syncPanelPosition);
    global.addEventListener('scroll', syncPanelPosition, true);
  }

  function initAll(root) {
    (root || document).querySelectorAll('[data-tf-ai-search]').forEach(attach);
  }

  global.TFAiSearch = { init: initAll, attach: attach };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initAll(document);
    });
  } else {
    initAll(document);
  }
})(window);
