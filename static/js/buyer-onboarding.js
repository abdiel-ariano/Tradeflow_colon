/**
 * TradeFlow Colón — buyer-onboarding.js
 * Habilita botones «Siguiente», multi-select de categorías y «Mostrar más».
 */
(function () {
  'use strict';

  /** Sincroniza clase .is-selected en tarjetas con radio/checkbox oculto */
  function bindSelectableCards(root, inputSelector, cardSelector) {
    if (!root) return;

    function sync() {
      root.querySelectorAll(cardSelector).forEach(function (card) {
        var input = card.querySelector(inputSelector);
        if (input) {
          card.classList.toggle('is-selected', input.checked);
        }
      });
    }

    root.addEventListener('change', function (event) {
      if (!event.target.matches(inputSelector)) return;
      if (inputSelector.indexOf('radio') >= 0 || inputSelector === 'input[type="radio"]') {
        root.querySelectorAll(cardSelector).forEach(function (card) {
          card.classList.remove('is-selected');
        });
      }
      sync();
      root.dispatchEvent(new CustomEvent('bo-selection-change'));
    });

    sync();
  }

  /** Paso 1 — requiere intención de compra */
  function initStep1() {
    var form = document.getElementById('bo-step1-form');
    if (!form) return;

    var nextBtn = document.getElementById('bo-step1-next');
    var grid = form.querySelector('.bo-intent-grid');

    bindSelectableCards(grid, 'input[type="radio"]', '.bo-intent-card');

    function updateNext() {
      var checked = form.querySelector('input[name="purchase_intent"]:checked');
      if (nextBtn) nextBtn.disabled = !checked;
    }

    grid.addEventListener('bo-selection-change', updateNext);
    updateNext();
  }

  /** Paso 2 — al menos una categoría */
  function initStep2() {
    var form = document.getElementById('bo-step2-form');
    if (!form) return;

    var nextBtn = document.getElementById('bo-step2-next');
    var grid = form.querySelector('.bo-category-grid');
    var showMoreBtn = document.getElementById('bo-show-more-cats');

    bindSelectableCards(grid, 'input[type="checkbox"]', '.bo-category-card');

    /* Ocultar categorías extra hasta «Mostrar más» */
    if (showMoreBtn && grid) {
      var cards = grid.querySelectorAll('.bo-category-card');
      cards.forEach(function (card, index) {
        if (index >= 4) card.classList.add('bo-category-card--hidden');
      });
      showMoreBtn.addEventListener('click', function () {
        cards.forEach(function (card) {
          card.classList.remove('bo-category-card--hidden');
        });
        showMoreBtn.hidden = true;
      });
    }

    function updateNext() {
      var checked = form.querySelectorAll('input[name="categories"]:checked');
      if (nextBtn) nextBtn.disabled = checked.length === 0;
    }

    grid.addEventListener('bo-selection-change', updateNext);
    updateNext();
  }

  function init() {
    initStep1();
    initStep2();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
