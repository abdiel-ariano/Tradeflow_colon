/**
 * About TradeFlow — cinematic motion
 * Progressive enhancement: content remains visible without JS / reduced motion.
 */
(function () {
  var root = document.querySelector('[data-about-root]');
  if (!root) return;

  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var revealSelector = '[data-about-reveal]';
  var countSelector = '[data-about-count]';
  var anchorNav = root.querySelector('[data-about-anchors]');
  var anchors = anchorNav ? Array.prototype.slice.call(anchorNav.querySelectorAll('[data-about-anchor]')) : [];
  var sections = anchors
    .map(function (a) {
      var id = (a.getAttribute('href') || '').replace(/^#/, '');
      return id ? document.getElementById(id) : null;
    })
    .filter(Boolean);

  function showAllReveals() {
    root.querySelectorAll(revealSelector).forEach(function (el) {
      el.classList.add('is-visible');
    });
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function animateCount(el) {
    var target = parseFloat(el.getAttribute('data-about-count') || '0');
    if (!isFinite(target)) return;
    var suffix = el.getAttribute('data-about-count-suffix') || '';
    var duration = 1100;
    var start = null;

    function frame(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / duration);
      var value = Math.round(target * easeOutCubic(p));
      el.textContent = String(value) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }

    el.textContent = '0' + suffix;
    requestAnimationFrame(frame);
  }

  function initCounts() {
    var nodes = root.querySelectorAll(countSelector);
    if (!nodes.length) return;
    if (reduce || !('IntersectionObserver' in window)) {
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        if (el.getAttribute('data-about-counted') === '1') return;
        el.setAttribute('data-about-counted', '1');
        animateCount(el);
        io.unobserve(el);
      });
    }, { threshold: 0.45 });
    nodes.forEach(function (n) { io.observe(n); });
  }

  function initReveals() {
    var nodes = Array.prototype.slice.call(root.querySelectorAll(revealSelector));
    if (!nodes.length) return;
    if (reduce || !('IntersectionObserver' in window)) {
      showAllReveals();
      return;
    }

    root.classList.add('about-motion');

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });

    nodes.forEach(function (el) {
      var rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.92) {
        el.classList.add('is-visible');
      } else {
        io.observe(el);
      }
    });

    window.setTimeout(showAllReveals, 2800);
  }

  function initHero() {
    if (reduce) {
      root.classList.add('is-hero-in');
      return;
    }
    root.classList.add('about-motion');
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        root.classList.add('is-hero-in');
      });
    });
  }

  function initParallax() {
    if (reduce) return;
    var orbs = Array.prototype.slice.call(root.querySelectorAll('[data-about-parallax]'));
    if (!orbs.length) return;
    var ticking = false;

    function update() {
      ticking = false;
      var y = window.scrollY || window.pageYOffset || 0;
      orbs.forEach(function (orb) {
        var factor = parseFloat(orb.getAttribute('data-about-parallax') || '0.1');
        if (!isFinite(factor)) factor = 0.1;
        orb.style.transform = 'translate3d(0,' + (y * factor) + 'px,0)';
      });
    }

    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    }, { passive: true });
    update();
  }

  function setActiveAnchor(id) {
    anchors.forEach(function (a) {
      var href = (a.getAttribute('href') || '').replace(/^#/, '');
      a.classList.toggle('is-active', href === id);
    });
  }

  function initScrollSpy() {
    if (!sections.length || !('IntersectionObserver' in window)) return;
    var io = new IntersectionObserver(function (entries) {
      var visible = entries
        .filter(function (e) { return e.isIntersecting; })
        .sort(function (a, b) { return b.intersectionRatio - a.intersectionRatio; });
      if (!visible.length) return;
      setActiveAnchor(visible[0].target.id);
    }, { rootMargin: '-25% 0px -55% 0px', threshold: [0.1, 0.35, 0.6] });
    sections.forEach(function (s) { io.observe(s); });

    anchors.forEach(function (a) {
      a.addEventListener('click', function () {
        var id = (a.getAttribute('href') || '').replace(/^#/, '');
        if (id) setActiveAnchor(id);
      });
    });
  }

  initHero();
  initReveals();
  initCounts();
  initParallax();
  initScrollSpy();
})();
