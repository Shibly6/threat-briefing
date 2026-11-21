/**
 * Threat Intelligence Dashboard - Client Interactions
 * Universal Cross-Briefing Search, In-Page Severity Filtering, Theme Toggle, and Clipboard Actions.
 */

(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // 1. Theme Management (Dark / Light Mode)
  // -------------------------------------------------------------------------
  const THEME_STORAGE_KEY = 'threat_briefing_theme';

  function initTheme() {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');

    applyTheme(initialTheme);

    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
        localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      });
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
      const isDark = theme === 'dark';
      toggleBtn.setAttribute('title', isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');
      toggleBtn.setAttribute('aria-label', isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');

      const sunIcon = toggleBtn.querySelector('.icon-sun');
      const moonIcon = toggleBtn.querySelector('.icon-moon');
      if (sunIcon && moonIcon) {
        sunIcon.style.display = isDark ? 'block' : 'none';
        moonIcon.style.display = isDark ? 'none' : 'block';
      }
    }
  }

  // -------------------------------------------------------------------------
  // 2. Universal Global Search System (Across all briefings past & present)
  // -------------------------------------------------------------------------
  let searchIndex = [];

  function loadSearchIndex() {
    // 1. Check window globals from assets/search_index.js
    if (Array.isArray(window.__THREAT_SEARCH_INDEX__) && window.__THREAT_SEARCH_INDEX__.length > 0) {
      searchIndex = window.__THREAT_SEARCH_INDEX__;
      return;
    }

    // 2. Fallback: Fetch search_index.json asynchronously if available
    const isReportSubdir = window.location.pathname.includes('/202') || document.querySelector('.articles-stack') !== null;
    const fetchPath = isReportSubdir ? '../assets/search_index.json' : './assets/search_index.json';

    fetch(fetchPath)
      .then((res) => {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then((data) => {
        if (Array.isArray(data)) {
          searchIndex = data;
          window.__THREAT_SEARCH_INDEX__ = data;
        }
      })
      .catch(() => {
        // Fallback retry root level
        const rootPath = isReportSubdir ? '../search_index.json' : './search_index.json';
        fetch(rootPath)
          .then((r) => r.json())
          .then((data) => {
            if (Array.isArray(data)) {
              searchIndex = data;
              window.__THREAT_SEARCH_INDEX__ = data;
            }
          })
          .catch(() => {});
      });
  }

  function initGlobalSearch() {
    loadSearchIndex();

    const searchInput = document.getElementById('global-search-input');
    const clearBtn = document.getElementById('global-search-clear-btn');
    const resultsContainer = document.getElementById('global-search-results');
    if (!searchInput || !resultsContainer) return;

    let debounceTimer = null;

    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      const query = (e.target.value || '').trim();

      if (clearBtn) {
        clearBtn.style.display = query ? 'block' : 'none';
      }

      if (!query) {
        resultsContainer.style.display = 'none';
        resultsContainer.innerHTML = '';
        return;
      }

      debounceTimer = setTimeout(() => {
        executeGlobalSearch(query, resultsContainer);
      }, 120);
    });

    searchInput.addEventListener('focus', () => {
      const query = (searchInput.value || '').trim();
      if (query && resultsContainer.children.length > 0) {
        resultsContainer.style.display = 'flex';
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        resultsContainer.style.display = 'none';
        resultsContainer.innerHTML = '';
        searchInput.focus();
      });
    }

    // Keyboard Shortcuts: '/' to focus search, 'Escape' to close dropdown
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== searchInput && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      } else if (e.key === 'Escape') {
        if (resultsContainer.style.display !== 'none') {
          resultsContainer.style.display = 'none';
        }
        if (document.activeElement === searchInput) {
          searchInput.blur();
        }
      }
    });

    // Close results dropdown on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.global-search-container')) {
        resultsContainer.style.display = 'none';
      }
    });
  }

  function executeGlobalSearch(query, resultsContainer) {
    if (!searchIndex || searchIndex.length === 0) {
      // If index not yet ready, try pulling from window again
      if (Array.isArray(window.__THREAT_SEARCH_INDEX__)) {
        searchIndex = window.__THREAT_SEARCH_INDEX__;
      }
    }

    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (tokens.length === 0) {
      resultsContainer.style.display = 'none';
      return;
    }

    const isReportSubdir = window.location.pathname.includes('/202') || document.querySelector('.articles-stack') !== null;
    const currentPath = window.location.pathname;

    const matches = searchIndex.filter((item) => {
      const searchTarget = [
        item.title || '',
        item.summary_bn || '',
        item.source_name || '',
        item.category || '',
        item.date || '',
        item.date_pretty || '',
        (item.cves || []).join(' '),
        (item.vendors || []).join(' ')
      ].join(' ').toLowerCase();

      return tokens.every((token) => searchTarget.includes(token));
    });

    // Sort by score descending, then date descending
    matches.sort((a, b) => {
      const scoreDiff = (b.score || 0) - (a.score || 0);
      if (scoreDiff !== 0) return scoreDiff;
      return (b.date || '').localeCompare(a.date || '');
    });

    const displayMatches = matches.slice(0, 20);

    if (displayMatches.length === 0) {
      resultsContainer.innerHTML = `
        <div class="global-search-header">
          <span>0 RESULTS FOUND ACROSS BRIEFINGS</span>
          <span>ESC TO CLOSE</span>
        </div>
        <div class="search-no-results">
          No threat intelligence matches "<strong>${escapeHtml(query)}</strong>" in the repository.
        </div>
      `;
      resultsContainer.style.display = 'flex';
      return;
    }

    const htmlList = [];
    htmlList.push(`
      <div class="global-search-header">
        <span>FOUND ${matches.length} THREATS ACROSS REPOSITORY</span>
        <span>ESC TO CLOSE</span>
      </div>
    `);

    displayMatches.forEach((item) => {
      // Determine link target URL
      let linkHref = '';
      const isSameDate = isReportSubdir && currentPath.includes(item.date);

      if (isSameDate) {
        const anchorId = item.id ? item.id.split('_')[1] : '';
        linkHref = anchorId ? `#${anchorId}` : '#';
      } else if (isReportSubdir) {
        linkHref = `../${item.report_url}`;
      } else {
        linkHref = `./${item.report_url}`;
      }

      const sev = (item.severity || 'medium').toLowerCase();
      const score = item.score || 50;
      const kevBadge = item.has_kev ? `<span class="badge badge-kev" style="font-size:0.62rem; padding:1px 5px;">🔥 KEV</span>` : '';
      const dateDisplay = item.date_pretty || item.date || '';

      const cveTags = (item.cves || []).slice(0, 3).map((c) => `<span class="result-tag-cve">${escapeHtml(c)}</span>`).join('');
      const vendorTags = (item.vendors || []).slice(0, 2).map((v) => `<span class="result-tag-vendor">${escapeHtml(v)}</span>`).join('');

      htmlList.push(`
        <a href="${linkHref}" class="search-result-item" data-date="${escapeHtml(item.date)}" data-anchor="${escapeHtml(item.id || '')}">
          <div class="result-top-row">
            <span class="result-date-badge">📅 ${escapeHtml(dateDisplay)}</span>
            <div style="display:flex; align-items:center; gap:4px;">
              <span class="badge badge-${sev}" style="font-size:0.62rem; padding:2px 5px;">${sev.toUpperCase()} (${score})</span>
              ${kevBadge}
            </div>
          </div>
          <div class="result-title">${escapeHtml(item.title)}</div>
          <div class="result-summary">${escapeHtml(item.summary_bn || '')}</div>
          <div class="result-tags">
            ${cveTags}
            ${vendorTags}
            <span class="result-tag-vendor" style="margin-left:auto;">${escapeHtml(item.source_name || '')}</span>
          </div>
        </a>
      `);
    });

    resultsContainer.innerHTML = htmlList.join('');
    resultsContainer.style.display = 'flex';

    // Click handler for internal smooth scrolling if navigating within current page
    resultsContainer.querySelectorAll('.search-result-item').forEach((link) => {
      link.addEventListener('click', (ev) => {
        const href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
          ev.preventDefault();
          const targetCard = document.querySelector(href);
          if (targetCard) {
            resultsContainer.style.display = 'none';
            // Reset any filter so target card is visible
            document.querySelectorAll('.article-card').forEach((c) => c.classList.remove('is-hidden'));
            targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            targetCard.style.outline = '2px solid var(--accent-primary)';
            targetCard.style.outlineOffset = '4px';
            setTimeout(() => {
              targetCard.style.outline = 'none';
            }, 2500);
          }
        }
      });
    });
  }

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // -------------------------------------------------------------------------
  // 3. Severity & Attribute Filtering (Report Page)
  // -------------------------------------------------------------------------
  let currentFilter = 'all';

  function initReportFilterPills() {
    const filterPills = document.querySelectorAll('.filter-pill');
    const telemetryCards = document.querySelectorAll('.telemetry-card');
    if (filterPills.length === 0) return;

    // Filter pill buttons
    filterPills.forEach((pill) => {
      pill.addEventListener('click', () => {
        filterPills.forEach((p) => p.classList.remove('is-active'));
        pill.classList.add('is-active');
        currentFilter = pill.getAttribute('data-filter') || 'all';
        syncTelemetryState(currentFilter);
        applyReportFilters();
      });
    });

    // Telemetry metric cards act as interactive filters
    telemetryCards.forEach((card) => {
      card.addEventListener('click', () => {
        const targetFilter = card.getAttribute('data-telemetry-filter');
        if (!targetFilter) return;

        if (currentFilter === targetFilter && targetFilter !== 'all') {
          currentFilter = 'all';
        } else {
          currentFilter = targetFilter;
        }

        filterPills.forEach((p) => {
          if (p.getAttribute('data-filter') === currentFilter) {
            p.classList.add('is-active');
          } else {
            p.classList.remove('is-active');
          }
        });

        syncTelemetryState(currentFilter);
        applyReportFilters();
      });
    });
  }

  function syncTelemetryState(filter) {
    const telemetryCards = document.querySelectorAll('.telemetry-card');
    telemetryCards.forEach((card) => {
      const cardFilter = card.getAttribute('data-telemetry-filter');
      if (cardFilter && cardFilter === filter && filter !== 'all') {
        card.classList.add('is-active');
      } else {
        card.classList.remove('is-active');
      }
    });
  }

  function applyReportFilters() {
    const cards = document.querySelectorAll('.article-card');
    const emptyState = document.getElementById('no-results-state');
    const statsElem = document.getElementById('results-stats');
    let visibleCount = 0;

    cards.forEach((card) => {
      const sev = (card.getAttribute('data-severity') || '').toLowerCase();
      const hasKev = card.getAttribute('data-has-kev') === 'true';
      const cvesCount = parseInt(card.getAttribute('data-cves-count') || '0', 10);

      let matchesFilter = true;
      if (currentFilter === 'critical') {
        matchesFilter = sev === 'critical';
      } else if (currentFilter === 'high') {
        matchesFilter = sev === 'high';
      } else if (currentFilter === 'medium') {
        matchesFilter = sev === 'medium';
      } else if (currentFilter === 'low') {
        matchesFilter = sev === 'low';
      } else if (currentFilter === 'kev') {
        matchesFilter = hasKev;
      } else if (currentFilter === 'cve') {
        matchesFilter = cvesCount > 0;
      }

      if (matchesFilter) {
        card.classList.remove('is-hidden');
        visibleCount++;
      } else {
        card.classList.add('is-hidden');
      }
    });

    if (emptyState) {
      emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
    }

    if (statsElem) {
      statsElem.textContent = `Showing ${visibleCount} of ${cards.length} threats`;
    }
  }

  // -------------------------------------------------------------------------
  // 4. Clipboard Actions (Copy Bengali Summary)
  // -------------------------------------------------------------------------
  function initClipboard() {
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.copy-btn');
      if (!btn) return;

      const targetId = btn.getAttribute('data-copy-target');
      let textToCopy = '';

      if (targetId) {
        const targetElem = document.getElementById(targetId);
        if (targetElem) {
          textToCopy = targetElem.innerText || targetElem.textContent || '';
        }
      } else if (btn.getAttribute('data-copy-text')) {
        textToCopy = btn.getAttribute('data-copy-text');
      }

      if (textToCopy) {
        navigator.clipboard.writeText(textToCopy.trim()).then(() => {
          const originalText = btn.innerHTML;
          btn.classList.add('is-copied');
          btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!`;

          setTimeout(() => {
            btn.classList.remove('is-copied');
            btn.innerHTML = originalText;
          }, 1800);
        }).catch((err) => {
          console.error('Clipboard copy failed:', err);
        });
      }
    });
  }

  // -------------------------------------------------------------------------
  // DOM Ready Initialization
  // -------------------------------------------------------------------------
  function init() {
    initTheme();
    initGlobalSearch();
    initReportFilterPills();
    initClipboard();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
