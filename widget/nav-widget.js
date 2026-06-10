/**
 * portal-nav-api — Auto-navigate widget
 *
 * Drop-in script. One line to add to any portal page:
 *   <script src="nav-widget.js" data-api-url="https://..." data-api-key="your-key"></script>
 *
 * Behaviour:
 *   - Opens a command-palette on Ctrl+K / Cmd+K (or programmatically via NavWidget.open())
 *   - Debounces keystrokes (300ms) then calls POST /query
 *   - If confidence >= AUTO_NAVIGATE_THRESHOLD: navigates immediately, no click needed
 *   - If confidence < threshold: shows top-3 candidates; keyboard-navigable (↑↓ Enter)
 *   - Learned paths stored in localStorage — repeat queries resolve locally in <1ms
 *   - MISS and error states display a clear, friendly message — never a blank panel
 *
 * LocalStorage keys:
 *   nav_learned_paths : { [normalisedQuery]: { path, label, confidence, ts } }
 *   nav_recent        : [{ query, path, label }]  (last 10 navigations)
 *
 * Configuration (data attributes on the <script> tag):
 *   data-api-url          required  Base URL of portal-nav-api (no trailing slash)
 *   data-api-key          required  API key for X-Api-Key header
 *   data-threshold        optional  Auto-navigate confidence threshold (default: 0.85)
 *   data-base-path        optional  Prepended to relative paths (default: "")
 *   data-hotkey           optional  Keyboard shortcut to open (default: "k")
 *   data-placeholder      optional  Input placeholder text
 *   data-cache-version    optional  Bump this string to wipe stale localStorage on next load
 */

(function (global) {
  'use strict';

  // ── Constants ────────────────────────────────────────────────────────────────

  var LEARN_KEY        = 'nav_learned_paths';
  var RECENT_KEY       = 'nav_recent';
  var DEBOUNCE_MS      = 300;
  var MAX_RECENT       = 10;
  var LEARN_THRESHOLD  = 0.90;   // only learn high-confidence results
  var LEARN_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;  // 7 days before a learned path expires

  // ── Config from script tag ───────────────────────────────────────────────────

  var scriptEl = document.currentScript ||
    (function () {
      var scripts = document.getElementsByTagName('script');
      return scripts[scripts.length - 1];
    })();

  // Merge order: data attributes (highest) > window.PORTAL_NAV_CONFIG > defaults
  var _rc = global.PORTAL_NAV_CONFIG || {};
  var cfg = {
    apiUrl:       (scriptEl.getAttribute('data-api-url')      || _rc.apiUrl      || '').replace(/\/$/, ''),
    apiKey:       (scriptEl.getAttribute('data-api-key')      || _rc.apiKey      || ''),
    threshold:    parseFloat(scriptEl.getAttribute('data-threshold')     || _rc.threshold     || '0.85'),
    basePath:     (scriptEl.getAttribute('data-base-path')    || _rc.basePath    || '').replace(/\/$/, ''),
    hotkey:       (scriptEl.getAttribute('data-hotkey')       || _rc.hotkey      || 'k'),
    placeholder:  (scriptEl.getAttribute('data-placeholder')  || _rc.placeholder || 'Where do you want to go? (e.g. "submit a claim")'),
    cacheVersion: (scriptEl.getAttribute('data-cache-version')|| String(_rc.cacheVersion || '1')),
  };

  if (!cfg.apiUrl || !cfg.apiKey) {
    console.warn('[NavWidget] API URL and key required (data-api-url/data-api-key or window.PORTAL_NAV_CONFIG). Widget disabled.');
    return;
  }

  // ── Cache version guard ───────────────────────────────────────────────────────
  // When data-cache-version changes (e.g. after a portal path restructure), wipe
  // all stale learned paths and recent history so old routes don't reappear.
  var VERSION_KEY = 'nav_cache_version';
  var storedVersion = lsGet(VERSION_KEY);
  if (storedVersion !== cfg.cacheVersion) {
    try {
      localStorage.removeItem(LEARN_KEY);
      localStorage.removeItem(RECENT_KEY);
      lsSet(VERSION_KEY, cfg.cacheVersion);
    } catch (e) { /* storage unavailable — ignore */ }
  }

  // ── LocalStorage helpers ─────────────────────────────────────────────────────

  function lsGet(key) {
    try { return JSON.parse(localStorage.getItem(key) || 'null'); }
    catch (e) { return null; }
  }

  function lsSet(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); }
    catch (e) { /* storage quota — silently skip */ }
  }

  /**
   * Normalise a query string for use as a cache key.
   * Lowercases, trims, collapses whitespace.
   * @param {string} q
   * @returns {string}
   */
  function normalise(q) {
    return q.toLowerCase().trim().replace(/\s+/g, ' ');
  }

  /**
   * Look up a learned path for the given query.
   * Expired entries (> LEARN_MAX_AGE_MS) are treated as misses and pruned.
   * @param {string} q  Raw query string
   * @returns {{ path: string, label: string, confidence: number }|null}
   */
  function learnedLookup(q) {
    var map = lsGet(LEARN_KEY) || {};
    var key = normalise(q);
    var entry = map[key];
    if (!entry) return null;
    if (Date.now() - entry.ts > LEARN_MAX_AGE_MS) {
      delete map[key];
      lsSet(LEARN_KEY, map);
      return null;
    }
    return entry;
  }

  /**
   * Persist a high-confidence result so future identical queries skip the API.
   * @param {string} q     Raw query
   * @param {string} path  Matched path
   * @param {string} label Human-readable label
   * @param {number} confidence
   */
  function learnPath(q, path, label, confidence) {
    if (confidence < LEARN_THRESHOLD) return;
    var map = lsGet(LEARN_KEY) || {};
    map[normalise(q)] = { path: path, label: label, confidence: confidence, ts: Date.now() };
    lsSet(LEARN_KEY, map);
  }

  /**
   * Record a successful navigation in the recent history list.
   * Keeps the last MAX_RECENT entries, deduped by path.
   * @param {string} query
   * @param {string} path
   * @param {string} label
   */
  function recordRecent(query, path, label) {
    var recent = lsGet(RECENT_KEY) || [];
    // Remove any existing entry for the same path (move-to-front)
    recent = recent.filter(function (r) { return r.path !== path; });
    recent.unshift({ query: query, path: path, label: label });
    if (recent.length > MAX_RECENT) recent = recent.slice(0, MAX_RECENT);
    lsSet(RECENT_KEY, recent);
  }

  // ── DOM / styles ─────────────────────────────────────────────────────────────

  var CSS = [
    '#nav-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:99998;display:flex;align-items:flex-start;justify-content:center;padding-top:12vh}',
    '#nav-overlay.nav-hidden{display:none}',
    '#nav-palette{background:#fff;border-radius:12px;width:min(600px,92vw);box-shadow:0 24px 64px rgba(0,0,0,.22);overflow:hidden;font-family:system-ui,-apple-system,sans-serif}',
    '#nav-input-wrap{display:flex;align-items:center;padding:16px 18px;border-bottom:1px solid #eee;gap:10px}',
    '#nav-search-icon{color:#aaa;flex-shrink:0}',
    '#nav-input{flex:1;border:none;outline:none;font-size:17px;color:#111;background:transparent;min-width:0}',
    '#nav-input::placeholder{color:#bbb}',
    '#nav-spinner{width:18px;height:18px;border:2px solid #ddd;border-top-color:#555;border-radius:50%;animation:nav-spin .6s linear infinite;flex-shrink:0;display:none}',
    '#nav-spinner.nav-visible{display:block}',
    '#nav-mic{border:none;background:transparent;cursor:pointer;color:#888;padding:4px;border-radius:6px;display:flex;align-items:center;flex-shrink:0}',
    '#nav-mic:hover{background:#f0f0f0;color:#333}',
    '#nav-mic.nav-listening{color:#d33;animation:nav-pulse 1.2s ease-in-out infinite}',
    '#nav-mic.nav-unsupported{display:none}',
    '@keyframes nav-pulse{0%,100%{opacity:1}50%{opacity:.35}}',
    '@keyframes nav-spin{to{transform:rotate(360deg)}}',
    '#nav-results{max-height:340px;overflow-y:auto}',
    '.nav-result{display:flex;align-items:center;padding:12px 18px;cursor:pointer;gap:12px;border-bottom:1px solid #f5f5f5;transition:background .1s}',
    '.nav-result:last-child{border-bottom:none}',
    '.nav-result:hover,.nav-result.nav-active{background:#f0f4ff}',
    '.nav-result-icon{width:32px;height:32px;border-radius:8px;background:#e8eeff;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px}',
    '.nav-result-body{flex:1;min-width:0}',
    '.nav-result-label{font-size:14px;font-weight:600;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.nav-result-path{font-size:12px;color:#888;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}',
    '.nav-result-badge{font-size:11px;padding:2px 7px;border-radius:20px;background:#e8eeff;color:#4466cc;flex-shrink:0;font-weight:600}',
    '.nav-result-badge.nav-badge-go{background:#e6f9f0;color:#1a8a4a}',
    '#nav-status{padding:20px 18px;font-size:14px;color:#777;display:flex;align-items:center;gap:10px}',
    '#nav-status-icon{font-size:22px}',
    '#nav-status-text{line-height:1.4}',
    '#nav-footer{padding:8px 18px;border-top:1px solid #f0f0f0;display:flex;gap:16px;font-size:11px;color:#bbb}',
    '#nav-footer kbd{background:#f5f5f5;border:1px solid #ddd;border-radius:4px;padding:1px 5px;font-size:10px;color:#888}',
    '.nav-section-label{padding:8px 18px 4px;font-size:11px;font-weight:700;color:#bbb;text-transform:uppercase;letter-spacing:.06em}',
  ].join('');

  var styleEl = document.createElement('style');
  styleEl.textContent = CSS;
  document.head.appendChild(styleEl);

  var overlay = document.createElement('div');
  overlay.id = 'nav-overlay';
  overlay.className = 'nav-hidden';
  overlay.innerHTML = [
    '<div id="nav-palette">',
    '  <div id="nav-input-wrap">',
    '    <svg id="nav-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>',
    '    <input id="nav-input" type="text" autocomplete="off" spellcheck="false" />',
    '    <button id="nav-mic" type="button" title="Search by voice" aria-label="Search by voice" aria-pressed="false">',
    '      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>',
    '    </button>',
    '    <div id="nav-spinner"></div>',
    '  </div>',
    '  <div id="nav-results"></div>',
    '  <div id="nav-footer">',
    '    <span><kbd>↑↓</kbd> navigate</span>',
    '    <span><kbd>Enter</kbd> go</span>',
    '    <span><kbd>Esc</kbd> close</span>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);

  var input    = document.getElementById('nav-input');
  var results  = document.getElementById('nav-results');
  var spinner  = document.getElementById('nav-spinner');

  input.placeholder = cfg.placeholder;

  // ── State ────────────────────────────────────────────────────────────────────

  var debounceTimer  = null;
  var activeIndex    = -1;
  var currentItems   = [];   // { path, label, score, source }
  var isOpen         = false;

  // ── Rendering ────────────────────────────────────────────────────────────────

  /**
   * Render a status message (loading hint, MISS, error) in the results panel.
   * @param {string} icon  Emoji or character
   * @param {string} html  Inner HTML for the message text
   */
  function showStatus(icon, html) {
    currentItems = [];
    activeIndex = -1;
    results.innerHTML =
      '<div id="nav-status">' +
      '<span id="nav-status-icon">' + icon + '</span>' +
      '<span id="nav-status-text">' + html + '</span>' +
      '</div>';
  }

  /**
   * Render a list of navigation results.
   * @param {Array<{path:string,label:string,score:number,source:string}>} items
   * @param {boolean} autoNav  If true the first item was auto-navigated (show "navigating…")
   */
  function showResults(items, autoNav) {
    currentItems = items;
    activeIndex = 0;

    if (autoNav) {
      showStatus('🚀', '<strong>Navigating you there…</strong>');
      return;
    }

    var html = '';
    items.forEach(function (item, i) {
      var badgeClass = i === 0 ? 'nav-result-badge nav-badge-go' : 'nav-result-badge';
      var badgeText  = i === 0 ? '↵ Go' : Math.round(item.score * 100) + '%';
      var activeClass = i === 0 ? ' nav-active' : '';
      html +=
        '<div class="nav-result' + activeClass + '" data-index="' + i + '">' +
        '  <div class="nav-result-icon">📄</div>' +
        '  <div class="nav-result-body">' +
        '    <div class="nav-result-label">' + escHtml(item.label) + '</div>' +
        '    <div class="nav-result-path">' + escHtml(item.path) + '</div>' +
        '  </div>' +
        '  <span class="' + badgeClass + '">' + badgeText + '</span>' +
        '</div>';
    });
    results.innerHTML = html;

    // Click handler
    results.querySelectorAll('.nav-result').forEach(function (el) {
      el.addEventListener('mousedown', function (e) {
        e.preventDefault();
        var idx = parseInt(el.getAttribute('data-index'), 10);
        navigate(items[idx]);
      });
    });
  }

  /**
   * Show the recent history list when the input is empty.
   */
  function showRecent() {
    var recent = lsGet(RECENT_KEY) || [];
    if (!recent.length) {
      showStatus('💡', 'Type to find any page. <kbd style="background:#f5f5f5;border:1px solid #ddd;border-radius:4px;padding:1px 5px;font-size:11px">Esc</kbd> to close.');
      return;
    }
    var items = recent.map(function (r) {
      return { path: r.path, label: r.label, score: 1, source: 'recent' };
    });
    currentItems = items;
    activeIndex = 0;
    var html = '<div class="nav-section-label">Recent</div>';
    items.forEach(function (item, i) {
      var activeClass = i === 0 ? ' nav-active' : '';
      html +=
        '<div class="nav-result' + activeClass + '" data-index="' + i + '">' +
        '  <div class="nav-result-icon">🕐</div>' +
        '  <div class="nav-result-body">' +
        '    <div class="nav-result-label">' + escHtml(item.label) + '</div>' +
        '    <div class="nav-result-path">' + escHtml(item.path) + '</div>' +
        '  </div>' +
        '</div>';
    });
    results.innerHTML = html;
    results.querySelectorAll('.nav-result').forEach(function (el) {
      el.addEventListener('mousedown', function (e) {
        e.preventDefault();
        var idx = parseInt(el.getAttribute('data-index'), 10);
        navigate(items[idx]);
      });
    });
  }

  function setActiveIndex(idx) {
    var els = results.querySelectorAll('.nav-result');
    if (!els.length) return;
    idx = Math.max(0, Math.min(els.length - 1, idx));
    activeIndex = idx;
    els.forEach(function (el, i) {
      el.classList.toggle('nav-active', i === idx);
    });
    els[idx].scrollIntoView({ block: 'nearest' });
  }

  function escHtml(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Navigation ───────────────────────────────────────────────────────────────

  /**
   * Navigate to a resolved item.
   * Records in recent history, learned-path cache, and fires POST /navigate
   * so the server can promote popular results to the L0 hot-path registry.
   * Uses sendBeacon (fire-and-forget, survives page unload) with fetch fallback.
   * @param {{ path: string, label: string, score: number }} item
   */
  function navigate(item) {
    var query    = input.value.trim();
    var fullPath = cfg.basePath + item.path;

    recordRecent(query, item.path, item.label);
    learnPath(query, item.path, item.label, item.score);

    // Feedback to server — closes the loop so L1/L2 hits auto-promote to L0.
    // Fire-and-forget: navigation must not be blocked by this request.
    var payload = JSON.stringify({
      query:      query,
      path:       item.path,
      label:      item.label,
      confidence: item.score,
    });
    var url = cfg.apiUrl + '/navigate';
    try {
      if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
        // sendBeacon survives page unload; Content-Type must be text/plain for
        // CORS preflight-free delivery (server accepts and parses as JSON).
        navigator.sendBeacon(url, new Blob([payload], { type: 'text/plain' }));
      } else {
        fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Api-Key': cfg.apiKey },
          body: payload,
          keepalive: true,
        }).catch(function () { /* non-critical — swallow silently */ });
      }
    } catch (e) { /* non-critical */ }

    close();
    window.location.href = fullPath;
  }

  // ── API call ─────────────────────────────────────────────────────────────────

  /**
   * Call POST /query with the current input value.
   * Checks the learned-path cache first — if a confident match exists, navigates
   * immediately without an API round-trip.
   * @param {string} q
   */
  function query(q) {
    // L0 — local learned-path cache (< 1ms, no network)
    var learned = learnedLookup(q);
    if (learned) {
      showResults([{ path: learned.path, label: learned.label, score: learned.confidence, source: 'learned' }], false);
      if (learned.confidence >= cfg.threshold) {
        showResults([{ path: learned.path, label: learned.label, score: learned.confidence, source: 'learned' }], true);
        setTimeout(function () { navigate(learned); }, 400);
      }
      return;
    }

    spinner.classList.add('nav-visible');

    var xhr = new XMLHttpRequest();
    xhr.open('POST', cfg.apiUrl + '/query', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-Api-Key', cfg.apiKey);
    xhr.timeout = 10000;

    xhr.onload = function () {
      spinner.classList.remove('nav-visible');

      if (xhr.status === 401 || xhr.status === 403) {
        showStatus('🔒', '<strong>Authentication error.</strong><br>The widget API key is invalid or has been revoked. Please contact your administrator.');
        return;
      }

      if (xhr.status === 429) {
        showStatus('⏳', '<strong>Too many requests.</strong><br>The navigation service is temporarily rate-limited. Please wait a moment and try again.');
        return;
      }

      if (xhr.status >= 500) {
        showStatus('⚠️', '<strong>Navigation service unavailable.</strong><br>This is a temporary issue. You can still browse manually — try the main menu or use the search bar.');
        return;
      }

      var data;
      try { data = JSON.parse(xhr.responseText); }
      catch (e) {
        showStatus('⚠️', '<strong>Unexpected response from navigation service.</strong><br>Please try again or browse manually.');
        return;
      }

      // MISS — API found nothing confident.
      // If suggest already populated the panel with candidates, keep them —
      // a partial-word MISS must never wipe useful prefix matches.
      // Only show the "no match" message if the panel is empty or showing a
      // loading/status placeholder (currentItems.length === 0).
      if (data.layer === 'MISS' || !data.path) {
        if (currentItems.length > 0) {
          // Suggest results are showing — leave them, just stop the spinner
          return;
        }
        var suggestionHtml = data.suggestion
          ? '<br><span style="color:#aaa">' + escHtml(data.suggestion) + '</span>'
          : '';
        showStatus('🔍',
          '<strong>No matching page found</strong> for <em>"' + escHtml(q) + '"</em>.' + suggestionHtml +
          '<br><span style="color:#aaa;font-size:12px;margin-top:4px;display:block">Try different words, or browse using the main menu.</span>'
        );
        return;
      }

      // Build result list: top result + any candidates
      var items = [{ path: data.path, label: data.label, score: data.confidence, source: data.layer }];
      (data.candidates || []).forEach(function (c) {
        if (c.path !== data.path) {
          items.push({ path: c.path, label: c.label, score: c.score, source: 'candidate' });
        }
      });

      // Auto-navigate if confidence clears the threshold
      if (data.confidence >= cfg.threshold) {
        learnPath(q, data.path, data.label, data.confidence);
        showResults(items, true);
        setTimeout(function () { navigate(items[0]); }, 400);
        return;
      }

      // Below threshold — show results for user to choose
      showResults(items, false);
    };

    xhr.onerror = function () {
      spinner.classList.remove('nav-visible');
      showStatus('📡',
        '<strong>Could not reach the navigation service.</strong><br>' +
        'Check your internet connection. You can still use the main menu to browse.'
      );
    };

    xhr.ontimeout = function () {
      spinner.classList.remove('nav-visible');
      showStatus('⏱️',
        '<strong>Navigation service took too long to respond.</strong><br>' +
        'This is likely a temporary issue. Please try again in a moment.'
      );
    };

    xhr.send(JSON.stringify({ query: q }));
  }

  // ── Open / close ─────────────────────────────────────────────────────────────

  function open() {
    if (isOpen) return;
    isOpen = true;
    overlay.classList.remove('nav-hidden');
    input.value = '';
    showRecent();
    setTimeout(function () { input.focus(); }, 20);
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;
    overlay.classList.add('nav-hidden');
    clearTimeout(debounceTimer);
    spinner.classList.remove('nav-visible');
    stopVoice();
    input.blur();
  }

  // ── Event wiring ─────────────────────────────────────────────────────────────

  // Global hotkey
  document.addEventListener('keydown', function (e) {
    var mod = e.ctrlKey || e.metaKey;
    if (mod && e.key === cfg.hotkey) {
      e.preventDefault();
      isOpen ? close() : open();
      return;
    }
    if (e.key === 'Escape' && isOpen) {
      close();
    }
  });

  // ── Input handler — 3-tier typing experience ────────────────────────────────
  // Tier 1 (0–2 chars): show "keep typing" hint — never fire API on stubs
  // Tier 2 (3+ chars, typing): call /query/suggest (LIKE prefix, instant DB hit)
  //   → shows candidates immediately with no auto-navigate
  // Tier 3 (3+ chars, debounce fired): call /query (full AI cascade)
  //   → auto-navigates if confidence >= threshold
  // This eliminates the "typed 2 chars, got MISS error" inconsistency.

  var suggestXhr = null;   // track in-flight suggest request so we can abort on new keystroke

  function suggest(q) {
    // Cancel any pending suggest request
    if (suggestXhr) { try { suggestXhr.abort(); } catch (e) {} suggestXhr = null; }

    var xhr = new XMLHttpRequest();
    suggestXhr = xhr;
    xhr.open('GET', cfg.apiUrl + '/query/suggest?q=' + encodeURIComponent(q), true);
    xhr.timeout = 4000;

    xhr.onload = function () {
      if (xhr !== suggestXhr) return;   // superseded by a newer keystroke
      suggestXhr = null;
      var data;
      try { data = JSON.parse(xhr.responseText); } catch (e) { data = []; }
      if (!Array.isArray(data) || !data.length) return;  // leave "searching…" state until debounce fires
      // Show suggestions as selectable list — no auto-navigate on partial input
      var items = data.map(function (r) {
        return { path: r.path, label: r.label, score: 0.5, source: 'suggest' };
      });
      showResults(items, false);
    };
    xhr.onerror = xhr.ontimeout = function () { suggestXhr = null; };
    xhr.send();
  }

  input.addEventListener('input', function () {
    var q = input.value.trim();
    clearTimeout(debounceTimer);
    if (suggestXhr) { try { suggestXhr.abort(); } catch (e) {} suggestXhr = null; }

    if (!q) {
      showRecent();
      return;
    }

    if (q.length < 3) {
      // Too short to search — give a clear hint instead of a confusing MISS error
      showStatus('⌨️', 'Keep typing… <span style="color:#bbb">(' + q.length + '/3 chars)</span>');
      return;
    }

    // 3+ chars: show "searching" and kick off suggest immediately for fast feedback
    showStatus('⌨️', 'Searching…');
    suggest(q);

    // Full AI query fires after debounce — this one can auto-navigate
    debounceTimer = setTimeout(function () { query(q); }, DEBOUNCE_MS);
  });

  // Keyboard navigation inside results
  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(activeIndex + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(activeIndex - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (currentItems[activeIndex]) navigate(currentItems[activeIndex]);
    }
  });

  // ── Voice navigation — browser Web Speech API, zero cost ────────────────────
  // Spoken queries land in the input and flow through the exact same NLU
  // pipeline as typed ones. Button hides itself where unsupported (Firefox).

  var micBtn = document.getElementById('nav-mic');
  var SpeechRec = global.SpeechRecognition || global.webkitSpeechRecognition;
  var recognizer = null;
  var listening = false;

  if (!SpeechRec) {
    micBtn.classList.add('nav-unsupported');
  } else {
    // Keep focus in the input so Esc/arrow keys keep working after a click
    micBtn.addEventListener('mousedown', function (e) { e.preventDefault(); });
    micBtn.addEventListener('click', function () {
      listening ? stopVoice() : startVoice();
    });
  }

  function startVoice() {
    recognizer = new SpeechRec();
    recognizer.lang = scriptEl.getAttribute('data-voice-lang') || 'en-ZA';
    recognizer.interimResults = true;
    recognizer.continuous = false;

    recognizer.onstart = function () {
      listening = true;
      micBtn.classList.add('nav-listening');
      micBtn.setAttribute('aria-pressed', 'true');
      showStatus('🎤', 'Listening… speak your question.');
    };
    recognizer.onresult = function (e) {
      var transcript = '';
      for (var i = 0; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript;
      }
      input.value = transcript;
      var q = transcript.trim();
      if (e.results[e.results.length - 1].isFinal && q.length >= 3) {
        // A final transcript is a complete question — skip the typing
        // debounce and query the cascade directly (can auto-navigate).
        showStatus('🎤', 'Heard: <em>"' + escHtml(q) + '"</em> — searching…');
        clearTimeout(debounceTimer);
        query(q);
      }
    };
    recognizer.onerror = function (e) {
      stopVoice();
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        showStatus('🎤', '<strong>Microphone access blocked.</strong><br>Allow microphone access in your browser to search by voice.');
      } else if (e.error !== 'aborted') {
        showStatus('🎤', '<strong>Could not hear you.</strong><br>Please try again, or type your question.');
      }
    };
    recognizer.onend = function () { stopVoice(); };

    try { recognizer.start(); }
    catch (err) { stopVoice(); }
  }

  function stopVoice() {
    listening = false;
    micBtn.classList.remove('nav-listening');
    micBtn.setAttribute('aria-pressed', 'false');
    if (recognizer) { try { recognizer.stop(); } catch (e) {} recognizer = null; }
  }

  // Close on overlay click (outside palette)
  overlay.addEventListener('mousedown', function (e) {
    if (e.target === overlay) close();
  });

  // ── Public API ───────────────────────────────────────────────────────────────

  global.NavWidget = {
    /** Open the palette programmatically */
    open: open,
    /** Close the palette programmatically */
    close: close,
    /**
     * Clear all learned paths and recent history from localStorage.
     * Call this if the portal structure changes significantly.
     */
    clearCache: function () {
      localStorage.removeItem(LEARN_KEY);
      localStorage.removeItem(RECENT_KEY);
    },
    /**
     * Return a copy of all currently learned paths.
     * @returns {Object}
     */
    getLearnedPaths: function () {
      return JSON.parse(JSON.stringify(lsGet(LEARN_KEY) || {}));
    },
  };

}(window));
