/**
 * Strop — Main Client-side Interactivity
 * Accessible, lightweight, zero-dependency.
 */

document.addEventListener('DOMContentLoaded', () => {
  initClipboardButtons();
  initMatrixFilter();
  initTabPanels();
});

/**
 * 1. Copy-to-Clipboard Functionality
 */
function initClipboardButtons() {
  const copyButtons = document.querySelectorAll('[data-copy-target]');

  copyButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const targetId = btn.getAttribute('data-copy-target');
      let textToCopy = '';

      if (targetId) {
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
          textToCopy = targetEl.textContent.trim();
        }
      } else if (btn.getAttribute('data-copy-text')) {
        textToCopy = btn.getAttribute('data-copy-text');
      }

      if (!textToCopy) return;

      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(textToCopy);
        } else {
          // Fallback for non-HTTPS / legacy
          const textArea = document.createElement('textarea');
          textArea.value = textToCopy;
          textArea.style.position = 'fixed';
          textArea.style.opacity = '0';
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();
          document.execCommand('copy');
          document.body.removeChild(textArea);
        }

        // Visual feedback
        const originalHtml = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>Copied!</span>
        `;

        setTimeout(() => {
          btn.classList.remove('copied');
          btn.innerHTML = originalHtml;
        }, 2200);
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
    });
  });
}

/**
 * 2. Hardware Compatibility Matrix Search & Category Filter
 */
function initMatrixFilter() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  const searchInput = document.getElementById('matrix-search');
  const tableRows = document.querySelectorAll('.matrix-table tbody tr:not(.empty-row)');
  const emptyRow = document.getElementById('matrix-empty-row');

  if (!tableRows.length) return;

  let currentCategory = 'all';
  let searchQuery = '';

  function applyFilters() {
    let visibleCount = 0;

    tableRows.forEach(row => {
      const rowCategory = row.getAttribute('data-category') || '';
      const rowText = row.textContent.toLowerCase();

      const matchesCategory = (currentCategory === 'all' || rowCategory === currentCategory);
      const matchesSearch = !searchQuery || rowText.includes(searchQuery);

      if (matchesCategory && matchesSearch) {
        row.style.display = '';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    });

    if (emptyRow) {
      emptyRow.style.display = visibleCount === 0 ? '' : 'none';
    }
  }

  // Filter Buttons
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');
      currentCategory = btn.getAttribute('data-filter') || 'all';
      applyFilters();
    });
  });

  // Search input
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.trim().toLowerCase();
      applyFilters();
    });
  }
}

/**
 * 3. Accessible Tab Panels
 */
function initTabPanels() {
  const tabLists = document.querySelectorAll('[role="tablist"]');

  tabLists.forEach(tabList => {
    const tabs = tabList.querySelectorAll('[role="tab"]');

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        switchTab(tabList, tab);
      });

      // Keyboard navigation: ArrowLeft / ArrowRight
      tab.addEventListener('keydown', (e) => {
        const tabArray = Array.from(tabs);
        const index = tabArray.indexOf(tab);

        if (e.key === 'ArrowRight') {
          e.preventDefault();
          const nextIndex = (index + 1) % tabArray.length;
          tabArray[nextIndex].focus();
          switchTab(tabList, tabArray[nextIndex]);
        } else if (e.key === 'ArrowLeft') {
          e.preventDefault();
          const prevIndex = (index - 1 + tabArray.length) % tabArray.length;
          tabArray[prevIndex].focus();
          switchTab(tabList, tabArray[prevIndex]);
        }
      });
    });
  });

  function switchTab(tabList, selectedTab) {
    const tabs = tabList.querySelectorAll('[role="tab"]');
    const targetPanelId = selectedTab.getAttribute('aria-controls');

    tabs.forEach(tab => {
      const isSelected = tab === selectedTab;
      tab.classList.toggle('active', isSelected);
      tab.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      tab.setAttribute('tabindex', isSelected ? '0' : '-1');
    });

    // Parent container holding tab panels
    const parentContainer = tabList.closest('.docs-hub') || document;
    const panels = parentContainer.querySelectorAll('[role="tabpanel"]');

    panels.forEach(panel => {
      if (panel.id === targetPanelId) {
        panel.classList.add('active');
        panel.removeAttribute('hidden');
      } else {
        panel.classList.remove('active');
        panel.setAttribute('hidden', '');
      }
    });
  }
}
