/**
 * Hero stats CountUp — easeOutExpo, 2.5s, scroll-triggered once.
 */
(function () {
  'use strict';

  var el = document.querySelector('.hero-stats-number');
  if (!el) return;

  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var target = parseFloat(el.dataset.target) || 0;
  var prefix = el.dataset.prefix || '';
  var duration = 2500;
  var started = false;

  function finish() {
    el.textContent = prefix + Math.floor(target).toLocaleString('en-US');
  }

  if (prefersReduced) {
    finish();
    return;
  }

  function update(now) {
    if (!started) return;
    var progress = Math.min((now - start) / duration, 1);
    var eased = 1 - Math.pow(2, -10 * progress);
    var current = Math.floor(target * eased);
    el.textContent = prefix + current.toLocaleString('en-US');
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  var start = 0;

  function run() {
    if (started) return;
    started = true;
    start = performance.now();
    requestAnimationFrame(update);
  }

  if (!('IntersectionObserver' in window)) {
    run();
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        run();
        observer.unobserve(el);
      }
    });
  }, { threshold: 0.5 });

  observer.observe(el);
})();
