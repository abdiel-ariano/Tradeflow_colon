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

      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
      setInstallButtonsVisible(false);
      setMenuOpen(false);
    });
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    setInstallButtonsVisible(false);
  });
}());
