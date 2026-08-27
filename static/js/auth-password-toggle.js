/**
 * TradeFlow — show/hide password toggles for auth forms.
 * Binds all `.js-password-toggle` buttons; does not read or store values.
 */
(function () {
  'use strict';

  function labelsFor(btn) {
    return {
      show: btn.getAttribute('data-label-show') || 'Show password',
      hide: btn.getAttribute('data-label-hide') || 'Hide password',
    };
  }

  function syncPasswordToggle(btn, visible) {
    var inputId = btn.getAttribute('data-target');
    var input = inputId ? document.getElementById(inputId) : null;
    if (!input) return;

    var labels = labelsFor(btn);
    var start = input.selectionStart;
    var end = input.selectionEnd;

    input.type = visible ? 'text' : 'password';
    btn.setAttribute('aria-pressed', visible ? 'true' : 'false');
    btn.setAttribute('aria-label', visible ? labels.hide : labels.show);

    var icon = btn.querySelector('.js-pw-icon');
    if (icon) {
      icon.textContent = visible ? 'visibility_off' : 'visibility';
    }

    if (typeof start === 'number' && typeof end === 'number') {
      try {
        input.setSelectionRange(start, end);
      } catch (err) {
        /* Some inputs may not support selection while toggling type. */
      }
    }
  }

  function bindPasswordToggle(btn) {
    if (btn.dataset.pwToggleBound === '1') return;
    btn.dataset.pwToggleBound = '1';

    btn.addEventListener('click', function () {
      var inputId = btn.getAttribute('data-target');
      var input = inputId ? document.getElementById(inputId) : null;
      if (!input) return;
      syncPasswordToggle(btn, input.type !== 'text');
    });

    btn.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        btn.click();
      }
    });
  }

  function initPasswordToggles(root) {
    var scope = root || document;
    scope.querySelectorAll('.js-password-toggle').forEach(bindPasswordToggle);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initPasswordToggles(document);
    });
  } else {
    initPasswordToggles(document);
  }

  window.TradeFlowPasswordToggle = {
    init: initPasswordToggles,
    sync: syncPasswordToggle,
  };
})();
