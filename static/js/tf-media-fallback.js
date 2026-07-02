/**
 * TradeFlow Colón — product image fallback chain (global).
 * primary → category seed → optional picsum → branded SVG.
 */
(function () {
  'use strict';

  function mediaFallback(img) {
    var stage = img.getAttribute('data-hm-fallback-stage') || '0';
    var categorySeed = img.getAttribute('data-hm-category-seed');
    var picsum = img.getAttribute('data-hm-picsum');
    var staticSrc = img.getAttribute('data-hm-static');
    var wrap = img.closest('[data-hm-media]');

    if (stage === '0' && categorySeed && img.src !== categorySeed) {
      img.setAttribute('data-hm-fallback-stage', '1');
      img.src = categorySeed;
      return;
    }
    if (stage === '1' && picsum && img.src !== picsum) {
      img.setAttribute('data-hm-fallback-stage', '2');
      img.src = picsum;
      return;
    }
    if ((stage === '1' && !picsum) || stage === '2') {
      if (staticSrc) {
        img.setAttribute('data-hm-fallback-stage', '3');
        img.src = staticSrc;
        img.classList.add('is-placeholder');
        if (wrap) {
          wrap.classList.add('is-error');
          wrap.classList.add('is-loaded');
        }
      }
      return;
    }
    if (stage === '0' && picsum && !categorySeed && img.src !== picsum) {
      img.setAttribute('data-hm-fallback-stage', '2');
      img.src = picsum;
      return;
    }
    if (stage === '0' && !categorySeed && !picsum && staticSrc) {
      img.setAttribute('data-hm-fallback-stage', '3');
      img.src = staticSrc;
      img.classList.add('is-placeholder');
      if (wrap) {
        wrap.classList.add('is-error');
        wrap.classList.add('is-loaded');
      }
    }
  }

  window.TFHomeMediaFallback = mediaFallback;
})();
