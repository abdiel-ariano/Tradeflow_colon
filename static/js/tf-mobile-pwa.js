/*
 * TradeFlow Colón — compact marketplace navigation and PWA installation.
 *
 * Supports the public marketplace navbar (#cat-catalog-nav) and the buyer shell
 * (#bn-buyer-shell). Both share the tf-market-menu-open body class so mobile
 * CSS can reveal the fixed secondary panel without clipping.
 */
(function () {
  'use strict';

  var compactQuery = window.matchMedia(
    '(max-width: 1199px), ' +
      '(pointer: coarse) and (max-width: 1366px)'
  );

  var menuConfigs = [
    {
      header: document.getElementById('cat-catalog-nav'),
      menuButton: document.getElementById('cat-nav-hamburger'),
      menu: document.getElementById('cat-nav-secondary'),
    },
    {
      header: document.getElementById('bn-buyer-shell'),
      menuButton: document.getElementById('bn-mobile-toggle'),
      menu: document.getElementById('bn-l2'),
    },
  ];

  var activeMenu = null;

  function syncNavHeight(header) {
    if (!header) {
      return;
    }
    var height = Math.ceil(header.getBoundingClientRect().height);
    document.body.style.setProperty('--cat-nav-height', height + 'px');
  }

  function setMenuOpen(config, isOpen) {
    if (!config || !config.menuButton || !config.menu) {
      return;
    }

    if (isOpen && activeMenu && activeMenu !== config) {
      setMenuOpen(activeMenu, false);
    }

    config.menu.classList.toggle('is-open', isOpen);
    config.menuButton.setAttribute('aria-expanded', String(isOpen));
    document.body.classList.toggle('tf-market-menu-open', isOpen);
    activeMenu = isOpen ? config : null;
  }

  function initCompactMenu(config) {
    var header = config.header;
    var menuButton = config.menuButton;
    var menu = config.menu;

    if (!header || !menuButton || !menu) {
      return;
    }

    syncNavHeight(header);

    menuButton.addEventListener('click', function (event) {
      event.preventDefault();
      setMenuOpen(config, !menu.classList.contains('is-open'));
    });

    menu.addEventListener('click', function (event) {
      if (event.target.closest('a, [data-cat-modal-open]')) {
        setMenuOpen(config, false);
      }
    });

    document.addEventListener('click', function (event) {
      if (
        compactQuery.matches &&
        menu.classList.contains('is-open') &&
        !header.contains(event.target)
      ) {
        setMenuOpen(config, false);
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && menu.classList.contains('is-open')) {
        setMenuOpen(config, false);
        menuButton.focus();
      }
    });

    compactQuery.addEventListener('change', function (event) {
      if (!event.matches) {
        setMenuOpen(config, false);
      }
    });

    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(function () {
        syncNavHeight(header);
      }).observe(header);
    } else {
      window.addEventListener('resize', function () {
        syncNavHeight(header);
      });
    }
  }

  menuConfigs.forEach(initCompactMenu);

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
      if (activeMenu) {
        setMenuOpen(activeMenu, false);
      }
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
      (document.body.classList.contains('cat-catalog-page') ||
        document.querySelector('.hm-marketplace, .hm-alibaba')) &&
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
        '#cat-catalog-nav, #bn-buyer-shell, button, a, input, textarea, select, label, [role="button"], [data-cat-modal-open]'
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
