/**
 * Hero ship and waves reveal animation.
 */
(function () {
  'use strict';

  var shipContainer = document.querySelector('.hero-ship-container') || document.getElementById('hero-ship-container');
  if (!shipContainer) return;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    shipContainer.classList.add('is-revealed');
    return;
  }

  if (!('IntersectionObserver' in window)) {
    shipContainer.classList.add('is-revealed');
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      shipContainer.classList.add('is-revealed');
      observer.unobserve(shipContainer);
    });
  }, { threshold: 0.2 });

  observer.observe(shipContainer);
})();
