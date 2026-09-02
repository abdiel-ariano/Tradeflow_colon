/**
 * TradeFlow Colón — product image fallback chain (global).
 * primary → category icon → optional Picsum → branded SVG.
 */
(function () {
  'use strict';

  function finishWithStatic(img, staticSrc, wrap) {
    if (!staticSrc) {
      return;
    }
    img.setAttribute('data-hm-fallback-stage', '3');
    img.src = staticSrc;
    img.classList.add('is-placeholder');
    if (wrap) {
      wrap.classList.add('is-error');
      wrap.classList.add('is-loaded');
    }
  }

  function mediaFallback(img) {
    var stage = img.getAttribute('data-hm-fallback-stage') || '0';
    var categoryIcon = img.getAttribute('data-hm-category-icon');
    var picsum = img.getAttribute('data-hm-picsum');
    var staticSrc = img.getAttribute('data-hm-static');
    var wrap = img.closest('[data-hm-media]');

    if (stage === '0' && categoryIcon && img.src !== categoryIcon) {
      img.setAttribute('data-hm-fallback-stage', '1');
      img.src = categoryIcon;
      return;
    }
    if ((stage === '0' || stage === '1') && picsum && img.src !== picsum) {
      img.setAttribute('data-hm-fallback-stage', '2');
      img.src = picsum;
      return;
    }
    finishWithStatic(img, staticSrc, wrap);
  }

  window.TFHomeMediaFallback = mediaFallback;
})();

