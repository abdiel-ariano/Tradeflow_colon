/**
 * Trending carousel — transform-based scroll only (never touches page scroll).
 */
(function () {
  'use strict';

  var track = document.querySelector('.trending-track');
  var dotsContainer = document.querySelector('.trending-dots');
  if (!track || !dotsContainer) return;

  var cards = track.querySelectorAll('.trending-card');
  if (!cards.length) return;

  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var cardWidth = 140;
  var gap = 16;
  var wrap = track.parentElement;
  function recalc() {
    visible = Math.max(1, Math.floor((wrap ? wrap.offsetWidth : window.innerWidth) / stride()));
    maxIndex = Math.max(0, cards.length - visible);
    if (current > maxIndex) current = maxIndex;
    createDots();
    goTo(current);
  }

  var visible = 1;
  var maxIndex = 0;
  var current = 0;
  var interval = null;

  function createDots() {
    dotsContainer.innerHTML = '';
    for (var i = 0; i <= maxIndex; i++) {
      var dot = document.createElement('span');
      dot.className = 'trending-dot' + (i === 0 ? ' active' : '');
      dot.addEventListener('click', function (idx) {
        return function () {
          goTo(idx);
          stop();
          start();
        };
      }(i));
      dotsContainer.appendChild(dot);
    }
  }

  function getDots() {
    return dotsContainer.querySelectorAll('.trending-dot');
  }

  function stride() {
    if (!cards[0]) return cardWidth + gap;
    var g = parseInt(window.getComputedStyle(track).gap, 10) || gap;
    return cards[0].offsetWidth + g;
  }

  function goTo(index) {
    if (index > maxIndex) index = 0;
    if (index < 0) index = maxIndex;
    current = index;
    track.style.transform = 'translateX(-' + (current * stride()) + 'px)';
    getDots().forEach(function (d, i) {
      d.classList.toggle('active', i === current);
    });
  }

  function next() {
    goTo(current + 1 > maxIndex ? 0 : current + 1);
  }

  function start() {
    if (reducedMotion) return;
    stop();
    interval = window.setInterval(next, 5000);
  }

  function stop() {
    if (interval) {
      window.clearInterval(interval);
      interval = null;
    }
  }

  if (wrap) {
    wrap.addEventListener('mouseenter', stop);
    wrap.addEventListener('mouseleave', start);
    wrap.addEventListener('touchstart', stop, { passive: true });
  }

  var touchStart = 0;
  track.addEventListener('touchstart', function (e) {
    touchStart = e.touches[0].clientX;
    stop();
  }, { passive: true });

  track.addEventListener('touchend', function (e) {
    var diff = touchStart - e.changedTouches[0].clientX;
    if (Math.abs(diff) > 40) {
      if (diff > 0) next();
      else goTo(current - 1);
    }
    window.setTimeout(start, 3000);
  }, { passive: true });

  window.addEventListener('resize', recalc);

  recalc();
  start();
})();
