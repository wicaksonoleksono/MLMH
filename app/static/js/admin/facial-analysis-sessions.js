// Facial Analysis Sessions - Image Viewer
// Lists all sessions with camera captures for image viewing
// Now with pagination and search support

// Global state
let currentPage = 1;
let currentPerPage = 15;
let currentSearchQuery = "";
let searchDebounceTimer = null;

document.addEventListener('DOMContentLoaded', function() {
  // Get URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const urlSearchQuery = urlParams.get('q') || '';
  const urlPage = parseInt(urlParams.get('page')) || 1;
  const urlPerPage = parseInt(urlParams.get('per_page')) || 15;

  // Set initial state from URL parameters
  currentPage = urlPage;
  currentPerPage = urlPerPage;
  currentSearchQuery = urlSearchQuery;

  // Update search input with URL value
  const searchInput = document.getElementById('search-input');
  if (searchInput && urlSearchQuery) {
    searchInput.value = urlSearchQuery;
  }

  // Update per page select with URL value
  const perPageSelect = document.getElementById('per-page-select');
  if (perPageSelect) {
    perPageSelect.value = currentPerPage;
  }

  // Load sessions
  loadSessions();

  // Initialize search functionality
  initializeSearch();
});

// Initialize search functionality
function initializeSearch() {
  const searchInput = document.getElementById('search-input');
  if (!searchInput) return;

  searchInput.addEventListener('input', function(e) {
    const query = e.target.value.trim();

    // Clear previous timer
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }

    // Set new timer with 300ms debounce
    searchDebounceTimer = setTimeout(() => {
      performSearch(query);
    }, 300);
  });
}

// Perform search with debounce
function performSearch(query) {
  currentSearchQuery = query;
  currentPage = 1; // Reset to first page when searching

  // Update URL without refresh
  updateUrlParams();

  // Load data
  loadSessions();
}

// Update URL parameters without refresh
function updateUrlParams() {
  const urlParams = new URLSearchParams(window.location.search);

  // Update search parameter
  if (currentSearchQuery && currentSearchQuery.length > 0) {
    urlParams.set('q', currentSearchQuery);
  } else {
    urlParams.delete('q');
  }

  // Update page parameter
  if (currentPage > 1) {
    urlParams.set('page', currentPage);
  } else {
    urlParams.delete('page');
  }

  // Update per_page parameter
  if (currentPerPage !== 15) {
    urlParams.set('per_page', currentPerPage);
  } else {
    urlParams.delete('per_page');
  }

  // Update URL
  const newUrl = urlParams.toString()
    ? `${window.location.pathname}?${urlParams.toString()}`
    : window.location.pathname;

  window.history.replaceState({}, '', newUrl);
}

async function loadSessions() {
  showLoading();
  hideError();

  try {
    // Build URL with pagination and search
    let url = `/admin/facial-analysis/sessions-data?page=${currentPage}&per_page=${currentPerPage}`;
    if (currentSearchQuery) {
      url += `&q=${encodeURIComponent(currentSearchQuery)}`;
    }

    const response = await fetch(url);
    const result = await response.json();

    // Handle @api_response decorator wrapper
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      hideLoading();
      renderSessions(data.sessions);
      updateStats(data.pagination.total, currentSearchQuery);
      updatePagination(data.pagination);
    } else {
      hideLoading();
      showError(data.message || 'Failed to load sessions');
    }
  } catch (error) {
    hideLoading();
    showError('Error loading sessions: ' + error.message);
  }
}

function renderSessions(sessions) {
  const tbody = document.getElementById('sessions-table-body');
  const emptyState = document.getElementById('empty-state');
  const contentArea = document.getElementById('content-area');

  contentArea.classList.remove('hidden');

  if (!sessions || sessions.length === 0) {
    tbody.innerHTML = '';
    emptyState.classList.remove('hidden');
    return;
  }

  emptyState.classList.add('hidden');

  // Group sessions by user for visual styling
  let html = '';
  let previousUserId = null;

  sessions.forEach((session, index) => {
    const isNewUser = session.user_id !== previousUserId;
    const isLastOfUser = (index === sessions.length - 1) || (sessions[index + 1].user_id !== session.user_id);

    // Determine row classes for grouping effect
    let rowClasses = 'transition-colors';

    if (isNewUser && isLastOfUser) {
      // Single session for this user
      rowClasses += ' bg-white hover:bg-gray-50';
    } else if (isNewUser) {
      // First session of multiple for this user
      rowClasses += ' bg-indigo-50/30 hover:bg-indigo-50/50 border-t-2 border-indigo-200';
    } else if (isLastOfUser) {
      // Last session for this user
      rowClasses += ' bg-indigo-50/30 hover:bg-indigo-50/50 border-b-2 border-indigo-200';
    } else {
      // Middle session for this user
      rowClasses += ' bg-indigo-50/30 hover:bg-indigo-50/50';
    }

    html += `
      <tr class="${rowClasses}">
        <td class="px-6 py-4">
          <div>
            <div class="text-sm font-medium text-gray-900">${session.username}</div>
            <div class="text-sm text-gray-500">${session.email}</div>
          </div>
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
            Session ${session.session_number}
          </span>
        </td>
        <td class="px-6 py-4 text-sm text-gray-500">
          ${session.end_time ? new Date(session.end_time).toLocaleDateString() : 'N/A'}
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            ${session.phq_images}
          </span>
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
            ${session.llm_images}
          </span>
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            ${session.total_images}
          </span>
        </td>
        <td class="px-6 py-4">
          <a href="/admin/facial-analysis/session/${session.session_id}/images"
             class="inline-flex items-center px-3 py-2 bg-indigo-600 text-white text-xs font-medium rounded-md hover:bg-indigo-700 transition-colors">
            <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
            </svg>
            View Images
          </a>
        </td>
      </tr>
    `;

    previousUserId = session.user_id;
  });

  tbody.innerHTML = html;
}

function updateStats(total, searchQuery) {
  const countElement = document.getElementById('total-count');
  if (countElement) {
    const countText = searchQuery
      ? `${total} sessions found for "${searchQuery}"`
      : `${total} sessions`;
    countElement.textContent = countText;
  }
}

// Update pagination
function updatePagination(pagination) {
  const containerEl = document.getElementById('pagination-container');
  const infoEl = document.getElementById('pagination-info');
  const controlsEl = document.getElementById('pagination-controls');

  if (pagination.total === 0) {
    containerEl.classList.add('hidden');
    return;
  }

  containerEl.classList.remove('hidden');

  // Update info text
  const start = (pagination.page - 1) * pagination.per_page + 1;
  const end = Math.min(start + pagination.per_page - 1, pagination.total);
  infoEl.textContent = `Showing ${start} to ${end} of ${pagination.total} results`;

  // Build pagination controls
  let controls = '';

  // Previous button
  if (pagination.has_prev) {
    controls += `<button onclick="changePage(${pagination.prev_num})" class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">Previous</button>`;
  } else {
    controls += `<button disabled class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">Previous</button>`;
  }

  // Page numbers
  for (let i = 1; i <= pagination.pages; i++) {
    if (i === pagination.page) {
      controls += `<button onclick="changePage(${i})" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-indigo-50 text-sm font-medium text-indigo-600">${i}</button>`;
    } else {
      controls += `<button onclick="changePage(${i})" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">${i}</button>`;
    }
  }

  // Next button
  if (pagination.has_next) {
    controls += `<button onclick="changePage(${pagination.next_num})" class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">Next</button>`;
  } else {
    controls += `<button disabled class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">Next</button>`;
  }

  controlsEl.innerHTML = controls;
}

// Change page
function changePage(page) {
  currentPage = page;

  // Update URL parameters
  updateUrlParams();

  loadSessions();
}

// Change per page
function changePerPage(perPage) {
  currentPerPage = parseInt(perPage);
  currentPage = 1; // Reset to first page

  // Update URL parameters
  updateUrlParams();

  loadSessions();
}

// UI Helper functions
function showLoading() {
  document.getElementById('loading-state').classList.remove('hidden');
  document.getElementById('content-area').classList.add('hidden');
  document.getElementById('error-state').classList.add('hidden');
}

function hideLoading() {
  document.getElementById('loading-state').classList.add('hidden');
}

function showError(message) {
  document.getElementById('error-message').textContent = message;
  document.getElementById('error-state').classList.remove('hidden');
  document.getElementById('content-area').classList.add('hidden');
}

function hideError() {
  document.getElementById('error-state').classList.add('hidden');
}
