/**
 * TradeFlow AI Search — Google-style suggestions for all search bars.
 */
(function (global) {
  'use strict';

  var DEBOUNCE_MS = 220;
  var MIN_CHARS = 1;

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

  function groupLabel(type) {
    var map = {
      product: 'Products',
      category: 'Categories',
      company: 'Companies',
      order: 'Orders',
      quote: 'Quotes',
      customer: 'Customers',
      action: 'Quick actions',
    };
    return map[type] || 'Suggestions';
  }

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

  function buildPanel(wrap) {
    var panel = document.createElement('div');
    panel.className = 'tf-ai-search-panel';
    panel.setAttribute('role', 'listbox');
    panel.id = 'tf-ai-panel-' + Math.random().toString(36).slice(2, 8);
    wrap.appendChild(panel);
    return panel;
  }

  function renderPanel(panel, data, onPick) {
    panel.innerHTML = '';
    var suggestions = (data && data.suggestions) || [];
    var related = (data && data.related) || [];
    var tip = data && data.tip;

    if (tip) {
      var tipEl = document.createElement('div');
      tipEl.className = 'tf-ai-search-tip';
      tipEl.innerHTML =
        '<span class="material-symbols-rounded" aria-hidden="true">auto_awesome</span><span>' +
        tip.replace(/</g, '&lt;') +
        '</span>';
      panel.appendChild(tipEl);
    }

    if (!suggestions.length) {
      var empty = document.createElement('div');
      empty.className = 'tf-ai-search-empty';
      empty.textContent = data && data.query
        ? 'No suggestions — press Enter to search.'
        : 'Start typing to see AI recommendations.';
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
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'tf-ai-search-item';
          btn.setAttribute('role', 'option');
          btn.innerHTML =
            '<span class="material-symbols-rounded" aria-hidden="true">' +
            (item.icon || 'search') +
            '</span><div><strong>' +
            (item.label || '').replace(/</g, '&lt;') +
            '</strong>' +
            (item.subtitle
              ? '<span>' + String(item.subtitle).replace(/</g, '&lt;') + '</span>'
              : '') +
            '</div>';
          btn.addEventListener('mousedown', function (ev) {
            ev.preventDefault();
            onPick(item);
          });
          panel.appendChild(btn);
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
  }

  function attach(input) {
    if (!input || input.dataset.tfAiBound === '1') return;
    input.dataset.tfAiBound = '1';

    var scope = input.getAttribute('data-tf-ai-search') || 'public';
    var endpoint =
      input.getAttribute('data-tf-ai-endpoint') ||
      (global.TF_AI_SEARCH_URL || '/api/search/suggest/');
    var wrap = ensureWrap(input);
    if (!wrap) return;
    var panel = buildPanel(wrap);
    var timer = null;
    var controller = null;
    var activeIndex = -1;

    function closePanel() {
      panel.classList.remove('is-open');
      activeIndex = -1;
    }

    function openPanel() {
      panel.classList.add('is-open');
    }

    function navigate(item) {
      if (item._phrase) {
        input.value = item._phrase;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.form && input.form.requestSubmit ? input.form.requestSubmit() : input.form && input.form.submit();
        closePanel();
        return;
      }
      if (item.url) {
        global.location.href = item.url;
      }
    }

    function fetchSuggestions(q) {
      if (controller) controller.abort();
      controller = new AbortController();
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
          return r.json();
        })
        .then(function (data) {
          renderPanel(panel, data, navigate);
          openPanel();
        })
        .catch(function () {
          /* silent */
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
      var items = panel.querySelectorAll('.tf-ai-search-item');
      if (!items.length) return;
      if (ev.key === 'ArrowDown') {
        ev.preventDefault();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault();
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
      if (!wrap.contains(ev.target)) closePanel();
    });
  }

  function initAll(root) {
    (root || document)
      .querySelectorAll('[data-tf-ai-search]')
      .forEach(attach);
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
