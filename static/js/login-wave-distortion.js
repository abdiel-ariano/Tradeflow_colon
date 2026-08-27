/**
 * Animate login wave distortion filter (baseFrequency + scale only).
 * Keeps the original image colors/position; no transforms on the image.
 */
(function () {
  'use strict';

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  var noise = document.getElementById('tradeflow-wave-noise');
  var displacement = document.getElementById('tradeflow-wave-displacement');
  if (!noise || !displacement) {
    return;
  }

  var freqValues = [
    [0.008, 0.012],
    [0.012, 0.008],
    [0.006, 0.014],
    [0.008, 0.012],
  ];
  var scaleValues = [8, 18, 12, 8];
  var freqDuration = 18000;
  var scaleDuration = 14000;
  var frameId = 0;

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function sampleKeyframes(values, elapsed, duration) {
    var segments = values.length - 1;
    var total = duration;
    var position = elapsed % total;
    var segDuration = total / segments;
    var index = Math.min(Math.floor(position / segDuration), segments - 1);
    var localT = (position - index * segDuration) / segDuration;
    var current = values[index];
    var next = values[index + 1];
    if (Array.isArray(current)) {
      return [
        lerp(current[0], next[0], localT),
        lerp(current[1], next[1], localT),
      ];
    }
    return lerp(current, next, localT);
  }

  function tick(now) {
    var freq = sampleKeyframes(freqValues, now, freqDuration);
    noise.setAttribute('baseFrequency', freq[0] + ' ' + freq[1]);
    displacement.setAttribute('scale', String(sampleKeyframes(scaleValues, now, scaleDuration)));
    frameId = window.requestAnimationFrame(tick);
  }

  frameId = window.requestAnimationFrame(tick);

  window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', function (event) {
    if (event.matches) {
      window.cancelAnimationFrame(frameId);
      noise.setAttribute('baseFrequency', '0.008 0.012');
      displacement.setAttribute('scale', '12');
    }
  });
})();
