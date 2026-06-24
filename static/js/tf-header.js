/**
 * TradeFlow Colón — tf-header.js
 * Mobile search expand, sticky bar on scroll, drawer, dropdowns, click-outside.
 */
(function (global) {
  'use strict';

  function closeAll(except) {
    document.querySelectorAll('.tf-hdr-cat-wrap.is-open').forEach(function (el) {
      if (el !== except) el.classList.remove('is-open');
    });
    document.querySelectorAll('.tf-hdr-account.is-open').forEach(function (el) {
      if (el !== except) el.classList.remove('is-open');
    });
  }

  function initShell(shell) {
    if (!shell || shell.dataset.tfHeaderInit === '1') return;
    shell.dataset.tfHeaderInit = '1';

    var hamburger = shell.querySelector('.tf-hdr-hamburger');
    var drawer = shell.querySelector('.tf-hdr-drawer');
    var backdrop = shell.querySelector('.tf-hdr-drawer-backdrop');
    var searchToggle = shell.querySelector('.tf-hdr-search-toggle');
    var mobileSearch = shell.querySelector('.tf-hdr-mobile-search');
    var stickyBar = shell.querySelector('.tf-hdr-sticky-bar');
    var catWrap = shell.querySelector('.tf-hdr-cat-wrap');
    var catBtn = shell.querySelector('.tf-hdr-cat-btn');
    var accountWrap = shell.querySelector('.tf-hdr-account');
    var accountBtn = shell.querySelector('.tf-hdr-account-btn');

    function setDrawer(open) {
      if (!drawer) return;
      drawer.classList.toggle('is-open', open);
      if (backdrop) backdrop.classList.toggle('is-open', open);
      if (hamburger) hamburger.setAttribute('aria-expanded', open ? 'true' : 'false');
      document.body.style.overflow = open ? 'hidden' : '';
    }

    if (hamburger && drawer) {
      hamburger.addEventListener('click', function () {
        setDrawer(!drawer.classList.contains('is-open'));
      });
    }
    if (backdrop) {
      backdrop.addEventListener('click', function () { setDrawer(false); });
    }

    if (searchToggle && mobileSearch) {
      searchToggle.addEventListener('click', function () {
        var open = mobileSearch.classList.toggle('is-visible');
        searchToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
          var input = mobileSearch.querySelector('.tf-hdr-search-input');
          if (input) input.focus();
        }
      });
    }

    if (catBtn && catWrap) {
      catBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = !catWrap.classList.contains('is-open');
        closeAll(catWrap);
        catWrap.classList.toggle('is-open', open);
        catBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }

    if (accountBtn && accountWrap) {
      accountBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = !accountWrap.classList.contains('is-open');
        closeAll(accountWrap);
        accountWrap.classList.toggle('is-open', open);
        accountBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }

    document.addEventListener('click', function () { closeAll(null); });

    if (stickyBar && window.matchMedia('(max-width: 991px)').matches) {
      var scrollThreshold = 120;
      window.addEventListener('scroll', function () {
        var show = window.scrollY > scrollThreshold;
        stickyBar.classList.toggle('is-visible', show);
        stickyBar.style.display = show ? 'block' : '';
      }, { passive: true });
    }
  }

  function initAll() {
    document.querySelectorAll('.tf-hdr-shell').forEach(initShell);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  global.TFHeader = { init: initAll };
})(window);
