/*
 * TradeFlow Colón — compact marketplace navigation and PWA installation.
 *
 * The module deliberately no-ops outside public marketplace pages. It keeps
 * Android and tablet navigation accessible and exposes the browser install
 * prompt only when the current device reports that installation is available.
 */
(function () {
  'use strict';

  var header = document.getElementById('cat-catalog-nav');
  var menuButton = document.getElementById('cat-nav-hamburger');
  var menu = document.getElementById('cat-nav-secondary');
  var compactQuery = window.matchMedia(
    '(max-width: 1199px), ' +
      '(pointer: coarse) and (max-width: 1366px)'
  );

  function setMenuOpen(isOpen) {
    if (!menuButton || !menu) {
      return;
    }

    menu.classList.toggle('is-open', isOpen);
    menuButton.setAttribute('aria-expanded', String(isOpen));
    document.body.classList.toggle('tf-market-menu-open', isOpen);
  }

  if (header && menuButton && menu) {
    menuButton.addEventListener('click', function () {
      setMenuOpen(!menu.classList.contains('is-open'));
    });

    menu.addEventListener('click', function (event) {
      if (event.target.closest('a, [data-cat-modal-open]')) {
        setMenuOpen(false);
      }
    });

    document.addEventListener('click', function (event) {
      if (
        compactQuery.matches &&
        menu.classList.contains('is-open') &&
        !header.contains(event.target)
      ) {
        setMenuOpen(false);
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        menuButton.focus();
      }
    });

    compactQuery.addEventListener('change', function (event) {
      if (!event.matches) {
        setMenuOpen(false);
      }
    });
  }

  var deferredInstallPrompt = null;
  var installButtons = document.querySelectorAll(
    '[data-tf-install-app]'
  );

  function runsAsInstalledApp() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true
    );
  }

  function setInstallButtonsVisible(isVisible) {
    installButtons.forEach(function (button) {
      button.hidden = !isVisible;
    });
  }

  setInstallButtonsVisible(false);

  if (runsAsInstalledApp()) {
    deferredInstallPrompt = null;
    setInstallButtonsVisible(false);
  }

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredInstallPrompt = event;

    if (!runsAsInstalledApp()) {
      setInstallButtonsVisible(true);
    }
  });

  installButtons.forEach(function (button) {
    button.addEventListener('click', async function () {
      if (!deferredInstallPrompt) {
        return;
      }

      try {
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
      } catch (error) {
        /* Browser blocked or cancelled the install prompt. */
      }

      deferredInstallPrompt = null;
      setInstallButtonsVisible(false);
      setMenuOpen(false);
    });
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    setInstallButtonsVisible(false);
  });

  /* ── Android horizontal overscroll guard (marketplace pages only) ── */
  var marketplaceCompactQuery = window.matchMedia(
    '(max-width: 1199px), (pointer: coarse) and (max-width: 1366px)'
  );

  function isMarketplaceCompact() {
    return (
      document.body.classList.contains('cat-catalog-page') &&
      marketplaceCompactQuery.matches
    );
  }

  function isHorizontalScrollContainer(el) {
    while (el && el !== document.body && el !== document.documentElement) {
      var style = window.getComputedStyle(el);
      var overflowX = style.overflowX;
      if (
        overflowX === 'auto' ||
        overflowX === 'scroll' ||
        overflowX === 'overlay'
      ) {
        return el;
      }
      el = el.parentElement;
    }
    return null;
  }

  function canScrollHorizontally(el, deltaX) {
    if (!el) {
      return false;
    }
    if (deltaX < 0 && el.scrollLeft > 1) {
      return true;
    }
    if (deltaX > 0 && el.scrollLeft + el.clientWidth < el.scrollWidth - 1) {
      return true;
    }
    return false;
  }

  var touchStartX = 0;
  var touchStartY = 0;

  document.addEventListener(
    'touchstart',
    function (event) {
      if (!isMarketplaceCompact() || !event.touches.length) {
        return;
      }
      touchStartX = event.touches[0].clientX;
      touchStartY = event.touches[0].clientY;
    },
    { passive: true }
  );

  function isInteractiveTarget(target) {
    return (
      target &&
      target.closest(
        '#cat-catalog-nav, button, a, input, textarea, select, label, [role="button"], [data-cat-modal-open]'
      )
    );
  }

  function hasDocumentHorizontalOverflow() {
    var root = document.documentElement;
    return root.scrollWidth > root.clientWidth + 1;
  }

  document.addEventListener(
    'touchmove',
    function (event) {
      if (!isMarketplaceCompact() || !event.touches.length) {
        return;
      }
      if (isInteractiveTarget(event.target)) {
        return;
      }
      if (document.body.classList.contains('tf-market-menu-open')) {
        return;
      }
      var deltaX = event.touches[0].clientX - touchStartX;
      var deltaY = event.touches[0].clientY - touchStartY;
      if (Math.abs(deltaX) <= Math.abs(deltaY)) {
        return;
      }
      var scrollHost = isHorizontalScrollContainer(event.target);
      if (canScrollHorizontally(scrollHost, deltaX)) {
        return;
      }
      if (Math.abs(deltaX) > 6 && hasDocumentHorizontalOverflow()) {
        event.preventDefault();
      }
    },
    { passive: false }
  );

  function resetHorizontalScroll() {
    if (!isMarketplaceCompact()) {
      return;
    }
    if (window.scrollX !== 0) {
      window.scrollTo(0, window.scrollY);
    }
    var root = document.documentElement;
    if (root && root.scrollLeft) {
      root.scrollLeft = 0;
    }
    if (document.body && document.body.scrollLeft) {
      document.body.scrollLeft = 0;
    }
  }

  window.addEventListener('scroll', resetHorizontalScroll, { passive: true });
  window.addEventListener('resize', resetHorizontalScroll);
  window.addEventListener('orientationchange', function () {
    window.setTimeout(resetHorizontalScroll, 0);
  });
  window.setTimeout(resetHorizontalScroll, 0);
}());
