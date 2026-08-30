(function () {
  'use strict';

  var root = document.getElementById('cv-status-root');
  if (!root) return;

  var pollUrl = root.getAttribute('data-poll-url');
  if (!pollUrl) return;

  var i18n = window.TF_I18N || {};
  var initialStatus = root.getAttribute('data-initial-status') || 'pending';
  if (initialStatus !== 'pending' && initialStatus !== 'draft') return;

  var inFlight = false;
  var stopped = false;
  var intervalMs = 10000;
  var timerId = null;
  var notified = false;
  var lastStatus = initialStatus;

  function t(key, fallback) {
    return i18n[key] || fallback;
  }

  function notifyOnce(message, type) {
    if (notified) return;
    notified = true;
    if (window.TF && typeof window.TF.notify === 'function') {
      window.TF.notify(message, type || 'success');
    }
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderVerified(data) {
    var block = data.access_block;
    var html = ''
      + '<span class="cv-status cv-status--verified"><span class="material-symbols-rounded" aria-hidden="true">verified</span> '
      + escapeHtml(t('cvVerifiedTitle', 'Verified company')) + '</span>'
      + '<h1 id="cv-title">' + escapeHtml(t('cvVerifiedHeading', 'Business identity approved')) + '</h1>';

    if (block) {
      html += '<p class="cv-lead">' + escapeHtml(block.message) + '</p>';
    } else {
      html += '<p class="cv-lead">' + escapeHtml(t('cvVerifiedLead', 'TradeFlow recorded the review and will enable only the capabilities approved for this company.')) + '</p>';
    }

    html += '<div class="cv-actions">';
    if (data.continue_url) {
      html += '<a class="tf-btn-primary" href="' + escapeHtml(data.continue_url) + '">' + escapeHtml(t('cvContinue', 'Continue')) + '</a>';
    }
    html += '</div>';

    root.innerHTML = html;
    var footer = document.getElementById('cv-actions-footer');
    if (footer) footer.style.display = 'none';
    notifyOnce(
      block
        ? t('cvVerifiedPendingStep', 'Your company was verified. One more access step is still pending.')
        : t('cvVerifiedToast', 'Your company was verified.'),
      block ? 'info' : 'success',
    );
    stopped = true;
  }

  function renderRejected(data) {
    root.innerHTML = ''
      + '<span class="cv-status cv-status--rejected"><span class="material-symbols-rounded" aria-hidden="true">error</span> '
      + escapeHtml(t('cvRejectedStatus', 'Requires correction')) + '</span>'
      + '<h1 id="cv-title">' + escapeHtml(t('cvRejectedHeading', 'We could not approve the information')) + '</h1>'
      + '<p class="cv-lead">' + escapeHtml(data.rejection_message) + '</p>'
      + '<div class="cv-actions">'
      + '<a class="tf-btn-primary" href="' + escapeHtml(data.continue_url) + '">' + escapeHtml(t('cvFixInformation', 'Correct information')) + '</a>'
      + '</div>';
    var footer = document.getElementById('cv-actions-footer');
    if (footer) footer.style.display = 'none';
    notifyOnce(t('cvRejectedToast', 'Your application requires correction.'), 'warning');
    stopped = true;
  }

  function poll() {
    if (stopped || inFlight || document.hidden) return;
    inFlight = true;
    fetch(pollUrl, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
      .then(function (resp) {
        if (resp.status === 401 || resp.status === 403) {
          stopped = true;
          return null;
        }
        if (!resp.ok) throw new Error('poll_failed');
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        if (data.verification_status !== lastStatus) {
          lastStatus = data.verification_status;
          if (data.verification_status === 'verified') {
            renderVerified(data);
            return;
          }
          if (data.verification_status === 'rejected') {
            renderRejected(data);
            return;
          }
        }
        if (!data.poll_active) {
          stopped = true;
          return;
        }
        intervalMs = 10000;
      })
      .catch(function () {
        intervalMs = Math.min(intervalMs * 2, 60000);
      })
      .finally(function () {
        inFlight = false;
        schedule();
      });
  }

  function schedule() {
    if (stopped) return;
    clearTimeout(timerId);
    timerId = setTimeout(poll, intervalMs);
  }

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && !stopped) poll();
  });

  schedule();
})();
