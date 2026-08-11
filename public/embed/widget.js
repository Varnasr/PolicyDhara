/**
 * PolicyDhara Embed Widget
 * Lightweight, self-contained script that creates an embedded policy feed.
 *
 * Usage:
 *   <div id="policydhara-widget" data-sector="health" data-limit="5"></div>
 *   <script src="https://varnasr.github.io/PolicyDhara/embed/widget.js"></script>
 */
(function () {
  'use strict';

  var SITE_BASE = 'https://varnasr.github.io/PolicyDhara/';
  var EMBED_BASE = SITE_BASE + 'embed/feed/';

  // Detect if running locally (same origin)
  try {
    var scripts = document.getElementsByTagName('script');
    var currentScript = scripts[scripts.length - 1];
    var scriptSrc = currentScript && currentScript.src ? currentScript.src : '';
    if (scriptSrc) {
      // Extract base from script src: everything before /embed/widget.js
      var idx = scriptSrc.indexOf('/embed/widget.js');
      if (idx !== -1) {
        var detectedBase = scriptSrc.substring(0, idx) + '/';
        SITE_BASE = detectedBase;
        EMBED_BASE = detectedBase + 'embed/feed/';
      }
    }
  } catch (e) {
    // Ignore detection errors, use defaults
  }

  function init() {
    var containers = document.querySelectorAll('#policydhara-widget, [data-policydhara-widget]');
    if (!containers.length) return;

    for (var i = 0; i < containers.length; i++) {
      var el = containers[i];

      // Skip if already initialized
      if (el.getAttribute('data-pd-initialized') === 'true') continue;
      el.setAttribute('data-pd-initialized', 'true');

      var sector = el.getAttribute('data-sector') || '';
      var limit = el.getAttribute('data-limit') || '5';
      var theme = el.getAttribute('data-theme') || 'light';

      // Build iframe URL. Sectors are static routes (the site is statically
      // hosted, so a ?sector= query param can't select content server-side);
      // the limit is applied client-side inside the iframe.
      var iframeSrc = EMBED_BASE + (sector ? encodeURIComponent(sector) + '/' : '');
      if (limit && limit !== '5') iframeSrc += '?limit=' + encodeURIComponent(limit);

      // Calculate height based on limit
      var numItems = parseInt(limit, 10) || 5;
      var estimatedHeight = 60 + (numItems * 52) + 40; // header + items + footer

      // Create wrapper with subtle branding
      var wrapper = document.createElement('div');
      wrapper.style.cssText = 'position:relative;border-radius:10px;overflow:hidden;border:1px solid ' + (theme === 'dark' ? '#2d3748' : '#e2e8f0') + ';background:' + (theme === 'dark' ? '#1a202c' : '#ffffff') + ';';

      // Create iframe
      var iframe = document.createElement('iframe');
      iframe.src = iframeSrc;
      iframe.style.cssText = 'width:100%;border:none;display:block;';
      iframe.height = String(estimatedHeight);
      iframe.setAttribute('frameborder', '0');
      iframe.setAttribute('loading', 'lazy');
      iframe.setAttribute('title', 'PolicyDhara Policy Feed' + (sector ? ' - ' + sector : ''));

      wrapper.appendChild(iframe);
      el.appendChild(wrapper);
    }
  }

  // Run on DOM ready or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
