/**
 * Global scroll reveal animations.
 * Usage: data-reveal="up|scale" and optional data-reveal-delay="1-5"
 */
(function () {
  'use strict';

  var revealElements = document.querySelectorAll('[data-reveal]');
  if (!revealElements.length) return;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    revealElements.forEach(function (el) {
      el.classList.add('is-revealed');
    });
    return;
  }

  if (!('IntersectionObserver' in window)) {
    revealElements.forEach(function (el) {
      el.classList.add('is-revealed');
    });
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      var delay = el.dataset.revealDelay;
      if (delay) {
        el.style.transitionDelay = (parseInt(delay, 10) * 0.08) + 's';
      }
      el.classList.add('is-revealed');
      observer.unobserve(el);
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  });

  revealElements.forEach(function (el) {
    observer.observe(el);
  });
})();
