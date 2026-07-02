/**
 * TradeFlow Colón — homepage interactions
 * Count-up stats, scroll reveals, transform sliders, supplier carousels, navbar shadow.
 */
(function () {
  'use strict';

  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Product image fallback: primary → picsum → branded SVG ── */
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

  function markMediaLoaded(img) {
    var wrap = img.closest('[data-hm-media]');
    if (!wrap) return;
    wrap.classList.add('is-loaded');
    if (img.classList.contains('is-placeholder')) {
      wrap.classList.add('is-error');
    }
  }

  function bindMediaImage(img) {
    function onLoad() {
      markMediaLoaded(img);
    }

    function onError() {
      var prev = img.src;
      mediaFallback(img);
      if (img.src !== prev) {
        img.addEventListener('load', onLoad, { once: true });
        img.addEventListener('error', function () {
          markMediaLoaded(img);
        }, { once: true });
        return;
      }
      markMediaLoaded(img);
    }

    if (img.complete && img.naturalWidth > 0) {
      onLoad();
      return;
    }

    img.addEventListener('load', onLoad, { once: true });
    img.addEventListener('error', onError, { once: true });
  }

  function initProductMedia() {
    document.querySelectorAll('[data-hm-media] img').forEach(bindMediaImage);
  }

  /* ── Count-up (hero stats) ── */
  function animateCount(el, target, suffix, duration) {
    if (REDUCED) {
      el.textContent = target.toLocaleString() + (suffix || '');
      return;
    }
    var parsed = parseInt(String(el.textContent).replace(/[^0-9]/g, ''), 10);
    var start = isNaN(parsed) ? 0 : parsed;
    if (start >= target) {
      el.textContent = target.toLocaleString() + (suffix || '');
      return;
    }
    var startTime = null;
    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = Math.floor(start + (target - start) * eased);
      el.textContent = value.toLocaleString() + (suffix || '');
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function initCountUp() {
    var stats = document.querySelectorAll('[data-hm-count]');
    if (!stats.length) return;

    var observer = new IntersectionObserver(
      function (entries, obs) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var el = entry.target;
          var target = parseInt(el.getAttribute('data-hm-count'), 10) || 0;
          var suffix = el.getAttribute('data-hm-suffix') || '';
          animateCount(el, target, suffix, 900);
          obs.unobserve(el);
        });
      },
      { threshold: 0.15 }
    );

    stats.forEach(function (el) { observer.observe(el); });
  }

  /* ── Scroll reveal (individual elements) ── */
  function initReveal() {
    var items = document.querySelectorAll('[data-hm-reveal]');
    if (!items.length) return;

    if (REDUCED) {
      items.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -6% 0px' }
    );

    items.forEach(function (el) { observer.observe(el); });
  }

  /* ── Section choreography (staggered groups) ── */
  function initSectionReveal() {
    var sections = document.querySelectorAll('[data-hm-section]');
    if (!sections.length) return;

    if (REDUCED) {
      sections.forEach(function (el) { el.classList.add('is-inview'); });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-inview');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -8% 0px' }
    );

    sections.forEach(function (el) { observer.observe(el); });
  }

  /* ── Top companies rotator ── */
  function initCompanyRotator() {
    document.querySelectorAll('[data-hm-company-rotator]').forEach(function (root) {
      var panels = root.querySelectorAll('.hm-company-rotator__panel');
      var tabs = root.querySelectorAll('[data-hm-company-tab]');
      if (!panels.length) return;

      var autoMs = parseInt(root.getAttribute('data-hm-company-autoplay'), 10);
      if (isNaN(autoMs)) autoMs = 0;
      var current = 0;
      var interval = null;

      function markSpotlightReady(panel) {
        var host = panel.querySelector('[data-hm-spotlight-products]');
        if (host) host.classList.add('is-ready');
      }

      function syncRotatorHeight() {
        var track = root.querySelector('.hm-company-rotator__track');
        if (track) track.style.minHeight = '';
      }

      function goTo(index) {
        if (index >= panels.length) index = 0;
        if (index < 0) index = panels.length - 1;
        current = index;
        panels.forEach(function (p, i) {
          var host = p.querySelector('[data-hm-spotlight-products]');
          if (host && i !== current) {
            host.classList.remove('is-ready');
          }
        });
        panels.forEach(function (p, i) {
          p.classList.toggle('is-active', i === current);
        });
        tabs.forEach(function (t, i) {
          t.classList.toggle('is-active', i === current);
          t.setAttribute('aria-selected', i === current ? 'true' : 'false');
        });
        window.requestAnimationFrame(function () {
          markSpotlightReady(panels[current]);
          syncRotatorHeight();
          window.setTimeout(function () {
            syncRotatorHeight();
            window.dispatchEvent(new Event('resize'));
          }, 60);
        });
      }

      function stopAutoplay() {
        if (interval) {
          clearInterval(interval);
          interval = null;
        }
      }

      function startAutoplay() {
        if (REDUCED || panels.length <= 1 || autoMs <= 0) return;
        stopAutoplay();
        interval = setInterval(function () {
          goTo(current + 1);
        }, autoMs);
      }

      function restartAutoplay() {
        stopAutoplay();
        if (autoMs > 0) startAutoplay();
      }

      tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
          var idx = parseInt(tab.getAttribute('data-hm-company-tab'), 10) || 0;
          goTo(idx);
          restartAutoplay();
        });
      });

      if (autoMs > 0) {
        root.addEventListener('mouseenter', stopAutoplay);
        root.addEventListener('mouseleave', startAutoplay);
      }

      window.addEventListener('resize', syncRotatorHeight);

      goTo(0);
      syncRotatorHeight();
      if (autoMs > 0) startAutoplay();
    });
  }

  /* ── Transform sliders (trending, testimonials) ── */
  function initSliders() {
    document.querySelectorAll('[data-hm-slider]').forEach(function (root) {
      var track = root.querySelector('.hm-slider__track');
      var viewport = root.querySelector('.hm-slider__viewport');
      var dotsWrap = root.querySelector('.hm-slider__dots');
      var prev = root.querySelector('.hm-slider__arrow--prev');
      var next = root.querySelector('.hm-slider__arrow--next');
      if (!track || !viewport || !dotsWrap) return;

      var slides = Array.prototype.slice.call(track.children).filter(function (el) {
        return el.nodeType === 1;
      });
      if (!slides.length) return;

      var visible = parseInt(root.getAttribute('data-hm-slider-visible'), 10) || 4;
      var current = 0;
      var maxIndex = 0;
      var interval = null;
      var autoMsAttr = root.getAttribute('data-hm-slider-autoplay');
      var autoMs = autoMsAttr === null || autoMsAttr === '' ? 0 : parseInt(autoMsAttr, 10);
      if (isNaN(autoMs)) autoMs = 0;

      function stride() {
        if (!slides[0]) return 280;
        var gap = parseInt(window.getComputedStyle(track).gap, 10) || 16;
        return slides[0].offsetWidth + gap;
      }

      function applyStaticMode() {
        var isStatic = slides.length <= visible || maxIndex <= 0;
        root.classList.toggle('hm-slider--static', isStatic);
        if (isStatic) {
          track.style.transform = 'none';
          track.style.transition = 'none';
        }
      }

      function recalc() {
        var vpWidth = viewport.offsetWidth;
        var slideW = slides[0] ? slides[0].offsetWidth : 0;
        var gap = parseInt(window.getComputedStyle(track).gap, 10) || 16;
        if (slideW > 0) {
          visible = Math.max(1, Math.floor((vpWidth + gap) / (slideW + gap)));
        }
        maxIndex = Math.max(0, slides.length - visible);
        if (current > maxIndex) current = maxIndex;
        applyStaticMode();
        buildDots();
        goTo(current, false);
        updateArrows();
      }

      function buildDots() {
        dotsWrap.innerHTML = '';
        if (root.classList.contains('hm-slider--static')) return;
        for (var i = 0; i <= maxIndex; i++) {
          var dot = document.createElement('button');
          dot.type = 'button';
          dot.className = 'hm-slider__dot' + (i === current ? ' is-active' : '');
          dot.setAttribute('aria-label', 'Slide ' + (i + 1));
          dot.addEventListener('click', (function (idx) {
            return function () {
              goTo(idx);
              restartAutoplay();
            };
          })(i));
          dotsWrap.appendChild(dot);
        }
      }

      function getDots() {
        return dotsWrap.querySelectorAll('.hm-slider__dot');
      }

      function goTo(index, animate) {
        if (root.classList.contains('hm-slider--static')) {
          track.style.transform = 'none';
          return;
        }
        if (index > maxIndex) index = 0;
        if (index < 0) index = maxIndex;
        current = index;
        var offset = current * stride();
        track.style.transition = animate === false || REDUCED ? 'none' : '';
        track.style.transform = 'translateX(-' + offset + 'px)';
        getDots().forEach(function (d, i) {
          d.classList.toggle('is-active', i === current);
        });
        updateArrows();
      }

      function updateArrows() {
        if (!prev || !next) return;
        prev.disabled = current <= 0;
        next.disabled = current >= maxIndex;
      }

      function nextSlide() {
        goTo(current + 1 > maxIndex ? 0 : current + 1);
      }

      function stopAutoplay() {
        if (interval) {
          clearInterval(interval);
          interval = null;
        }
      }

      function startAutoplay() {
        if (REDUCED || maxIndex <= 0 || autoMs <= 0) return;
        stopAutoplay();
        interval = setInterval(nextSlide, autoMs);
      }

      function restartAutoplay() {
        stopAutoplay();
        if (autoMs > 0) startAutoplay();
      }

      if (prev) {
        prev.addEventListener('click', function () {
          goTo(current - 1);
          restartAutoplay();
        });
      }

      if (next) {
        next.addEventListener('click', function () {
          goTo(current + 1);
          restartAutoplay();
        });
      }

      if (autoMs > 0) {
        root.addEventListener('mouseenter', stopAutoplay);
        root.addEventListener('mouseleave', startAutoplay);
      }

      var touchStart = 0;
      track.addEventListener('touchstart', function (e) {
        touchStart = e.touches[0].clientX;
        if (autoMs > 0) stopAutoplay();
      }, { passive: true });

      track.addEventListener('touchend', function (e) {
        var diff = touchStart - e.changedTouches[0].clientX;
        if (Math.abs(diff) > 40) {
          if (diff > 0) goTo(current + 1);
          else goTo(current - 1);
        }
        if (autoMs > 0) {
          setTimeout(startAutoplay, 3000);
        }
      }, { passive: true });

      window.addEventListener('resize', recalc);
      recalc();
      if (autoMs > 0) startAutoplay();
    });
  }

  /* ── Supplier scroll carousels ── */
  function initCarousels() {
    document.querySelectorAll('[data-hm-carousel]').forEach(function (root) {
      var track = root.querySelector('.hm-carousel__track');
      var prev = root.querySelector('.hm-carousel__arrow--prev');
      var next = root.querySelector('.hm-carousel__arrow--next');
      if (!track || !prev || !next) return;

      function scrollByDir(dir) {
        var card = track.querySelector('.hm-sp-card, .hm-trend-card');
        var amount = card ? card.offsetWidth + 12 : 280;
        track.scrollBy({ left: dir * amount, behavior: REDUCED ? 'auto' : 'smooth' });
      }

      prev.addEventListener('click', function () { scrollByDir(-1); });
      next.addEventListener('click', function () { scrollByDir(1); });

      function updateArrows() {
        var max = track.scrollWidth - track.clientWidth - 2;
        prev.disabled = track.scrollLeft <= 2;
        next.disabled = track.scrollLeft >= max;
      }

      track.addEventListener('scroll', updateArrows, { passive: true });
      updateArrows();
    });
  }

  /* ── Navbar shadow on scroll ── */
  function initNavShadow() {
    var shell = document.getElementById('hm-public-nav');
    if (!shell) return;

    function onScroll() {
      shell.classList.toggle('is-scrolled', window.scrollY > 8);
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ── Rankings tooltip ── */
  function initRankingsTooltip() {
    var btn = document.getElementById('hm-rankings-info');
    var tip = document.getElementById('hm-rankings-tooltip');
    if (!btn || !tip) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = tip.hasAttribute('hidden');
      if (open) {
        tip.removeAttribute('hidden');
        btn.setAttribute('aria-expanded', 'true');
      } else {
        tip.setAttribute('hidden', '');
        btn.setAttribute('aria-expanded', 'false');
      }
    });

    document.addEventListener('click', function () {
      tip.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
    });
  }

  function initMotion() {
    var root = document.querySelector('.hm-root');
    if (!root || REDUCED) return;
    root.classList.add('hm-root--motion');
  }

  function init() {
    initMotion();
    initCompanyRotator();
    initCountUp();
    initSectionReveal();
    initReveal();
    initProductMedia();
    initSliders();
    initCarousels();
    initNavShadow();
    initRankingsTooltip();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
