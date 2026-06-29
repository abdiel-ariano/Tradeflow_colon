/**
 * Trending products carousel — auto-scroll with hover/touch pause.
 */
(function () {
  'use strict';

  var track = document.querySelector('.trending-track');
  if (!track) return;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  var scrollInterval;
  var step = 176;

  function cardStep() {
    var card = track.querySelector('.trending-card');
    if (!card) return step;
    var gap = parseInt(window.getComputedStyle(track).gap, 10) || 16;
    return card.offsetWidth + gap;
  }

  function startScroll() {
    stopScroll();
    scrollInterval = window.setInterval(function () {
      var stride = cardStep();
      if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 10) {
        track.scrollTo({ left: 0, behavior: 'smooth' });
      } else {
        track.scrollBy({ left: stride, behavior: 'smooth' });
      }
    }, 4000);
  }

  function stopScroll() {
    if (scrollInterval) {
      window.clearInterval(scrollInterval);
      scrollInterval = null;
    }
  }

  startScroll();
  track.addEventListener('mouseenter', stopScroll);
  track.addEventListener('mouseleave', startScroll);
  track.addEventListener('touchstart', stopScroll, { passive: true });
  track.addEventListener('touchend', function () {
    window.setTimeout(startScroll, 3000);
  }, { passive: true });
})();
