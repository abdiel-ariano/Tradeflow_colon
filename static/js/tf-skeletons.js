/**
 * TradeFlow Colón — skeleton loading states (no external deps).
 *
 * Usage:
 *   <div class="tf-skeleton-host" data-tf-skeleton aria-busy="true">...</div>
 *   TFSkeleton.ready(host) — manual ready
 *   TFSkeleton.show(host)  — show skeleton again (AJAX reload)
 */
(function (global) {
  'use strict';

  var FALLBACK_MS = 4500;

  function ready(host) {
    if (!host || host.classList.contains('is-ready')) return;
    host.classList.add('is-ready');
    host.setAttribute('aria-busy', 'false');
  }

  function show(host) {
    if (!host) return;
    host.classList.remove('is-ready');
    host.setAttribute('aria-busy', 'true');
  }

  function waitForImages(content, cb) {
    var imgs = content.querySelectorAll('img');
    if (!imgs.length) {
      cb();
      return;
    }
    var pending = imgs.length;
    var called = false;
    function finish() {
      pending -= 1;
      if (!called && pending <= 0) {
        called = true;
        cb();
      }
    }
    imgs.forEach(function (img) {
      if (img.complete) finish();
      else {
        img.addEventListener('load', finish, { once: true });
        img.addEventListener('error', finish, { once: true });
      }
    });
    setTimeout(function () {
      if (!called) {
        called = true;
        cb();
      }
    }, FALLBACK_MS);
  }

  function initHost(host) {
    if (host.classList.contains('is-ready')) return;
    var content = host.querySelector('.tf-skeleton-content');
    if (!content) {
      ready(host);
      return;
    }
    var run = function () {
      waitForImages(content, function () {
        requestAnimationFrame(function () { ready(host); });
      });
    };
    if (document.readyState === 'complete') run();
    else window.addEventListener('load', run, { once: true });
  }

  function initAll(root) {
    (root || document).querySelectorAll('[data-tf-skeleton]').forEach(initHost);
  }

  function refresh(host) {
    show(host);
    initHost(host);
  }

  global.TFSkeleton = {
    ready: ready,
    show: show,
    init: initAll,
    refresh: refresh,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initAll(); });
  } else {
    initAll();
  }
})(window);
