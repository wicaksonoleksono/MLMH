// app/static/js/admin/dashboard.js
// Admin dashboard JavaScript functions using AJAX like session management

// Global state
let currentPage = 1;
let currentPerPage = 15;
let currentSearchQuery = "";
let searchDebounceTimer = null;
let currentSortBy = "user_id";
let currentSortOrder = "asc";
let currentTab = "overview"; // Default tab

function normalizeFacialStatus(status) {
  if (!status) {
    return "not_started";
  }
  return String(status).trim().toLowerCase();
}

// Initialize page
document.addEventListener("DOMContentLoaded", function () {
  // Get URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const urlSearchQuery = urlParams.get("q") || "";
  const urlPage = parseInt(urlParams.get("page")) || 1;
  const urlPerPage = parseInt(urlParams.get("per_page")) || 15;
  const urlSortBy = urlParams.get("sort_by") || "user_id";
  const urlSortOrder = urlParams.get("sort_order") || "asc";

  // Get tab from URL hash or default to 'overview'
  const urlHash = window.location.hash.substring(1); // Remove the '#'
  const initialTab = urlHash && document.getElementById(`tab-content-${urlHash}`) ? urlHash : "overview";

  // Set initial state from URL parameters
  currentPage = urlPage;
  currentPerPage = urlPerPage;
  currentSearchQuery = urlSearchQuery;
  currentSortBy = urlSortBy;
  currentSortOrder = urlSortOrder;
  currentTab = initialTab;

  // Update search input with URL value
  const searchInput = document.getElementById("userSearch");
  if (searchInput && urlSearchQuery) {
    searchInput.value = urlSearchQuery;
  }

  // Update per page select with URL value
  const perPageSelect = document.getElementById("per-page-select");
  if (perPageSelect) {
    perPageSelect.value = currentPerPage;
  }

  // Update sort selects with URL values
  const sortBySelect = document.getElementById("sortBySelect");
  const sortOrderSelect = document.getElementById("sortOrderSelect");
  if (sortBySelect) {
    sortBySelect.value = currentSortBy;
  }
  if (sortOrderSelect) {
    sortOrderSelect.value = currentSortOrder;
  }

  // Initialize tabs
  initializeTabs();
  
  // Load initial data
  loadDashboardData();

  // Initialize search functionality
  initializeSearch();

  // Initialize sort controls
  initializeSortControls();

  // Listen for hash changes (back/forward navigation)
  window.addEventListener("hashchange", function () {
    const newHash = window.location.hash.substring(1);
    const newTab = newHash && document.getElementById(`tab-content-${newHash}`) ? newHash : "overview";

    if (newTab !== currentTab) {
      currentTab = newTab;
      switchTab(currentTab);
    }
  });
});

// Initialize tab functionality
function initializeTabs() {
  // Show the default tab
  showTab(currentTab);
  
  // Add click listeners to all tab buttons
  document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', function(e) {
      e.preventDefault();
      const tabName = this.id.replace('tab-', '');
      switchTab(tabName);
    });
  });
}

// Switch between tabs
function switchTab(tabName) {
  if (currentTab === tabName) return;

  currentTab = tabName;
  
  // Update URL hash to make tab persistent
  window.location.hash = tabName;
  
  // Show the selected tab content
  showTab(tabName);
}

// Show the specified tab content
function showTab(tabName) {
  // Hide all tab content divs
  document.querySelectorAll('[id^="tab-content-"]').forEach(contentDiv => {
    contentDiv.classList.add('hidden');
  });
  
  // Remove active class from all tab buttons
  document.querySelectorAll('.tab-button').forEach(button => {
    button.className = 'tab-button whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300';
  });
  
  // Show the selected tab content
  const contentDiv = document.getElementById(`tab-content-${tabName}`);
  if (contentDiv) {
    contentDiv.classList.remove('hidden');
  }
  
  // Update the active tab button
  const activeButton = document.getElementById(`tab-${tabName}`);
  if (activeButton) {
    activeButton.className = 'tab-button whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm border-indigo-500 text-indigo-600';
  }
  
  // Load data based on the active tab
  if (tabName === 'user-sessions' || tabName === 'overview') {
    loadDashboardData();
  } else if (tabName === 'facial-analysis') {
    loadFacialAnalysisSessions();
    initializeFacialAnalysisControls();
  } else if (tabName === 'facial-analysis-exports') {
    loadFacialAnalysisExports();
    initializeFacialAnalysisExportsControls();
  }
}

// Initialize search functionality
function initializeSearch() {
  const searchInput = document.getElementById("userSearch");
  if (!searchInput) return;

  searchInput.addEventListener("input", function (e) {
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

  // Clear search when focused for easy clearing
  searchInput.addEventListener("focus", function () {
    this.select();
  });
}

// Perform search with debounce
function performSearch(query) {
  // Update search query state
  currentSearchQuery = query;
  currentPage = 1; // Reset to first page when searching

  // Update URL without refresh
  updateUrlParams();

  // ONLY update table data, not entire dashboard (like session-management.js)
  loadUserSessionsOnly();
}

// Load ONLY user sessions table data (without stats cards)
function loadUserSessionsOnly() {
  // Show loading on table only (don't hide entire content area)
  const tableBody = document.getElementById("table-body");
  if (tableBody) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6" class="px-6 py-8 text-center">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          <p class="mt-2 text-sm text-gray-500">Loading...</p>
        </td>
      </tr>
    `;
  }

  hideError();

  // Build URL with pagination, search, and sort
  let url = `/admin/ajax-dashboard-data?page=${currentPage}&per_page=${currentPerPage}`;
  if (currentSearchQuery) {
    url += `&q=${encodeURIComponent(currentSearchQuery)}`;
  }
  url += `&sort_by=${currentSortBy}&sort_order=${currentSortOrder}`;

  fetch(url, {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      console.log("[DEBUG] User sessions only response:", data);

      // Handle API response wrapper format from @api_response decorator
      const actualData = data.status === "OLKORECT" ? data.data : data;

      if (
        actualData.status === "success" ||
        actualData.user_sessions ||
        data.status === "OLKORECT"
      ) {
        const responseData = actualData.data || actualData;

        // ONLY update table and pagination - DO NOT update stats cards
        updateUserSessionTable(responseData.user_sessions.items);
        updatePagination(responseData.user_sessions.pagination);

        // Update search count display
        updateUserCount(responseData.user_sessions.pagination, currentSearchQuery);
      } else {
        console.error("[ERROR] User sessions load failed:", actualData);
        showError(actualData.message || data.error || "Unknown error");
      }
    })
    .catch((error) => {
      console.error("[ERROR] User sessions request failed:", error);
      showError(error.message);
    });
}

// Update URL parameters without refresh
function updateUrlParams() {
  const urlParams = new URLSearchParams(window.location.search);

  // Update search parameter
  if (currentSearchQuery && currentSearchQuery.length > 0) {
    urlParams.set("q", currentSearchQuery);
  } else {
    urlParams.delete("q");
  }

  // Update page parameter
  if (currentPage > 1) {
    urlParams.set("page", currentPage);
  } else {
    urlParams.delete("page");
  }

  // Update per_page parameter
  if (currentPerPage !== 15) { // 15 is default
    urlParams.set("per_page", currentPerPage);
  } else {
    urlParams.delete("per_page");
  }

  // Update sort parameters
  if (currentSortBy !== "user_id") {
    urlParams.set("sort_by", currentSortBy);
  } else {
    urlParams.delete("sort_by");
  }
  if (currentSortOrder !== "asc") {
    urlParams.set("sort_order", currentSortOrder);
  } else {
    urlParams.delete("sort_order");
  }

  // Update URL
  const newUrl = urlParams.toString()
    ? `${window.location.pathname}?${urlParams.toString()}`
    : window.location.pathname;

  window.history.replaceState({}, "", newUrl);
}

// Load dashboard data via AJAX
function loadDashboardData() {
  showLoading();
  hideError();

  // Build URL with pagination, search, and sort
  let url = `/admin/ajax-dashboard-data?page=${currentPage}&per_page=${currentPerPage}`;
  if (currentSearchQuery) {
    url += `&q=${encodeURIComponent(currentSearchQuery)}`;
  }
  url += `&sort_by=${currentSortBy}&sort_order=${currentSortOrder}`;

  fetch(url, {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      console.log("[DEBUG] Dashboard response:", data);

      // Handle API response wrapper format from @api_response decorator
      const actualData = data.status === "OLKORECT" ? data.data : data;

      if (
        actualData.status === "success" ||
        actualData.user_sessions ||
        data.status === "OLKORECT"
      ) {
        const responseData = actualData.data || actualData;

        // Update dashboard content
        updateDashboardContent(responseData);

        // Make sure content is visible and loading is hidden
        hideLoading();
        showContent();

        // Update search count display
        updateUserCount(responseData.user_sessions.pagination, currentSearchQuery);
      } else {
        hideLoading();
        console.error("[ERROR] Dashboard load failed:", actualData);
        showError(actualData.message || data.error || "Unknown error");
      }
    })
    .catch((error) => {
      hideLoading();
      console.error("[ERROR] Dashboard request failed:", error);
      showError(error.message);
    });
}

// Update dashboard content
function updateDashboardContent(data) {
  // Update stats cards (for overview tab)
  updateStatsCards(data.stats);
  
  // Update table content (for user-sessions tab)
  updateUserSessionTable(data.user_sessions.items);
  
  // Update pagination (for user-sessions tab)
  updatePagination(data.user_sessions.pagination);
  
  // Update assessment statistics (for statistics tab)
  updateAssessmentStats(data.phq_stats, data.session_stats, data.user_stats);
}

// Update stats cards
function updateStatsCards(stats) {
  if (stats && stats.users) {
    // Update user stats
    const userStatsCard = document.getElementById("user-stats-card");
    if (userStatsCard) {
      const userStats = userStatsCard.querySelectorAll("div > div.ml-4 > div");
      if (userStats.length > 0) {
        userStats[0].textContent = stats.users.total || 0; // Total users
      }
      const adminText = userStatsCard.querySelector(".mt-3.text-xs.text-blue-700 div:first-child .font-medium");
      if (adminText) adminText.textContent = stats.users.admins || 0;
      const regularText = userStatsCard.querySelector(".mt-3.text-xs.text-blue-700 div:last-child .font-medium");
      if (regularText) regularText.textContent = stats.users.regular || 0;
    }

    // Update assessment stats
    const assessmentStatsCard = document.getElementById("assessment-stats-card");
    if (assessmentStatsCard && stats.assessments) {
      const assessmentStats = assessmentStatsCard.querySelectorAll("div > div.ml-4 > div");
      if (assessmentStats.length > 0) {
        assessmentStats[0].textContent = stats.assessments.total_sessions || 0; // Total sessions
      }
      const completedText = assessmentStatsCard.querySelector(".mt-3.text-xs.text-green-700 div:first-child .font-medium");
      if (completedText) completedText.textContent = stats.assessments.completed_sessions || 0;
      const rateText = assessmentStatsCard.querySelector(".mt-3.text-xs.text-green-700 div:last-child .font-medium");
      if (rateText) rateText.textContent = `${stats.assessments.completion_rate || 0}%`;
    }

    // Update settings stats
    const settingsStatsCard = document.getElementById("settings-stats-card");
    if (settingsStatsCard && stats.settings) {
      const settingStats = settingsStatsCard.querySelectorAll("div > div.ml-4 > div");
      if (settingStats.length > 0) {
        settingStats[0].textContent = stats.settings.total_settings || 0; // Total settings
      }
      const assessmentConfigText = settingsStatsCard.querySelector(".mt-3.text-xs.text-purple-700 div:first-child .font-medium");
      if (assessmentConfigText) assessmentConfigText.textContent = stats.settings.assessment_configs || 0;
      const mediaSettingText = settingsStatsCard.querySelector(".mt-3.text-xs.text-purple-700 div:last-child .font-medium");
      if (mediaSettingText) mediaSettingText.textContent = stats.settings.media_settings || 0;
    }
  }
}

// Update user session table
function updateUserSessionTable(items) {
  const headerEl = document.getElementById("table-header");
  const bodyEl = document.getElementById("table-body");

  // Set up table header
  headerEl.innerHTML = `
    <tr>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Session</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">PHQ-Sum</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
    </tr>
  `;

  if (!items || items.length === 0) {
    bodyEl.innerHTML = `
      <tr>
        <td colspan="6" class="px-6 py-12 text-center text-sm text-gray-500">
          <div class="flex flex-col items-center justify-center">
            <svg class="w-12 h-12 text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <span class="text-lg font-medium text-gray-400">No user sessions found</span>
            <p class="text-sm text-gray-500 mt-1">Users will appear here once they start assessments</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  // Build table rows for each user session
  let rowsHtml = '';
  items.forEach((user_session) => {
    // Session 1 Row
    rowsHtml += `
      <tr class="border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
        <td class="py-4 px-6 font-medium text-gray-900">${user_session.user_id}</td>
        <td class="py-4 px-6 font-medium text-gray-900">${user_session.username}</td>
        <td class="py-4 px-6 text-gray-900">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-blue-500 mr-2"></div>
            <span class="font-medium">Session 1</span>
          </div>
        </td>
        <td class="py-4 px-6">
          ${getStatusBadge(user_session.session1, user_session.session1_id)}
        </td>
        <td class="py-4 px-6 text-gray-900">
          ${getPHQBadge(user_session.session1_phq_score)}
        </td>
        <td class="py-4 px-6 w-48">
          <div class="flex items-center justify-start space-x-1 min-w-0">
            ${getActionButtons(user_session.session1, user_session.session1_id, user_session.user_id, user_session.username, 1)}
          </div>
        </td>
      </tr>
      
      <!-- Session 2 Row -->
      <tr class="border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
        <td class="py-4 px-6 font-medium text-gray-900">${user_session.user_id}</td>
        <td class="py-4 px-6 font-medium text-gray-900">${user_session.username}</td>
        <td class="py-4 px-6 text-gray-900">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-purple-500 mr-2"></div>
            <span class="font-medium">Session 2</span>
          </div>
        </td>
        <td class="py-4 px-6">
          ${getStatusBadge(user_session.session2, user_session.session2_id)}
        </td>
        <td class="py-4 px-6 text-gray-900">
          ${getPHQBadge(user_session.session2_phq_score)}
        </td>
        <td class="py-4 px-6 w-48">
          <div class="flex items-center justify-start space-x-1 min-w-0">
            ${getActionButtons(user_session.session2, user_session.session2_id, user_session.user_id, user_session.username, 2)}
          </div>
        </td>
      </tr>
      
      <!-- User Separator -->
      <tr class="border-b-2 border-gray-200">
        <td colspan="6" class="py-2 px-6 bg-gradient-to-r from-gray-50 to-gray-100"></td>
      </tr>
    `;
  });

  bodyEl.innerHTML = rowsHtml;

  // Set up event delegation for delete buttons
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".delete-session-btn");
    if (!btn) return;

    // Extract data from attributes
    const sessionId = btn.dataset.sessionId;
    const username = decodeURIComponent(btn.dataset.username || "");
    const sessionNumber = parseInt(btn.dataset.sessionNumber || "0", 10);

    // Call confirmDelete function
    confirmDelete(sessionId, username, sessionNumber);
  });
}

// Helper function to get status badge
function getStatusBadge(sessionStatus, sessionId) {
  if (sessionStatus === "COMPLETED" && sessionId) {
    return `<span class="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">${sessionStatus}</span>`;
  } else if (sessionStatus === "Not done") {
    return `<span class="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Not Started</span>`;
  } else {
    return `<span class="px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">${sessionStatus}</span>`;
  }
}

// Helper function to get PHQ badge
function getPHQBadge(phqScore) {
  if (phqScore !== null && phqScore !== undefined) {
    return `<span class="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">${phqScore}</span>`;
  } else {
    return `<span class="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">N/A</span>`;
  }
}

// Helper function to get action buttons
function getActionButtons(sessionStatus, sessionId, userId, username, sessionNumber) {
  if (sessionStatus === "COMPLETED" && sessionId) {
    return `
      <a href="/admin/export/session/${sessionId}" 
         class="inline-flex items-center justify-center px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm flex-shrink-0 w-20">
        <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
        </svg>
        Download
      </a>
      <button class="inline-flex items-center justify-center px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm flex-shrink-0 w-16 delete-session-btn"
              data-session-id="${sessionId}" 
              data-username="${encodeURIComponent(username)}" 
              data-session-number="${sessionNumber}">
        <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
        </svg>
        Delete
      </button>
    `;
  } else {
    return `
      <div class="flex items-center justify-start w-full">
        <span class="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
          <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          Disabled
        </span>
      </div>
    `;
  }
}

// Update pagination
function updatePagination(pagination) {
  const containerEl = document.getElementById("pagination-container");
  const infoEl = document.getElementById("pagination-info");
  const controlsEl = document.getElementById("pagination-controls");

  if (pagination.total === 0) {
    containerEl.classList.add("hidden");
    return;
  }

  containerEl.classList.remove("hidden");

  // Update info text
  const start = (pagination.page - 1) * pagination.per_page + 1;
  const end = Math.min(start + pagination.per_page - 1, pagination.total);
  infoEl.textContent = `Showing ${start} to ${end} of ${pagination.total} results`;

  // Build pagination controls
  let controls = "";

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

// Update assessment statistics
function updateAssessmentStats(phqStats, sessionStats, userStats) {
  // Update PHQ stats
  const phqStatsContent = document.getElementById("phq-stats-content");
  if (phqStatsContent) {
    let phqHtml = '';
    if (phqStats) {
      phqHtml += `
        <div class="flex justify-between items-center">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-blue-500 mr-2"></div>
            <span class="text-sm text-blue-700">Minimal (0-4)</span>
          </div>
          <span class="font-medium text-blue-900">${phqStats.minimal || 0}</span>
        </div>
        <div class="flex justify-between items-center">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-green-500 mr-2"></div>
            <span class="text-sm text-blue-700">Mild (5-9)</span>
          </div>
          <span class="font-medium text-blue-900">${phqStats.mild || 0}</span>
        </div>
        <div class="flex justify-between items-center">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
            <span class="text-sm text-blue-700">Moderate (10-14)</span>
          </div>
          <span class="font-medium text-blue-900">${phqStats.moderate || 0}</span>
        </div>
        <div class="flex justify-between items-center">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-orange-500 mr-2"></div>
            <span class="text-sm text-blue-700">Moderately Severe (15-19)</span>
          </div>
          <span class="font-medium text-blue-900">${phqStats.moderate_severe || 0}</span>
        </div>
        <div class="flex justify-between items-center">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full bg-red-500 mr-2"></div>
            <span class="text-sm text-blue-700">Severe (20-27)</span>
          </div>
          <span class="font-medium text-blue-900">${phqStats.severe || 0}</span>
        </div>
      `;
      if (phqStats.total_scores > 0) {
        phqHtml += `
          <div class="mt-3 pt-3 border-t border-blue-200">
            <div class="text-xs text-blue-600">Average Score: <span class="font-medium">${phqStats.average_score}</span></div>
          </div>
        `;
      }
    } else {
      phqHtml = '<div class="text-sm text-gray-500">No PHQ data available</div>';
    }
    phqStatsContent.innerHTML = phqHtml;
  }

  // Update session stats
  const sessionStatsContent = document.getElementById("session-stats-content");
  if (sessionStatsContent && sessionStats) {
    sessionStatsContent.innerHTML = `
      <div class="flex justify-between items-center">
        <span class="text-sm text-green-700">Total Sessions</span>
        <span class="font-medium text-green-900">${sessionStats.total_sessions || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-green-700">Completed</span>
        <span class="font-medium text-green-900">${sessionStats.completed_sessions || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-green-700">Completion Rate</span>
        <span class="font-medium text-green-900">${sessionStats.completion_rate || 0}%</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-green-700">Session 1 Only</span>
        <span class="font-medium text-green-900">${sessionStats.session1_only || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-green-700">Both Sessions</span>
        <span class="font-medium text-green-900">${sessionStats.both_sessions || 0}</span>
      </div>
    `;
  }

  // Update user engagement stats
  const userEngagementContent = document.getElementById("user-engagement-content");
  if (userEngagementContent && userStats) {
    userEngagementContent.innerHTML = `
      <div class="flex justify-between items-center">
        <span class="text-sm text-purple-700">Total Users</span>
        <span class="font-medium text-purple-900">${userStats.total_users || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-purple-700">Active Users</span>
        <span class="font-medium text-purple-900">${userStats.active_users || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-purple-700">Avg Sessions/User</span>
        <span class="font-medium text-purple-900">${userStats.avg_sessions_per_user || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-purple-700">High Engagement</span>
        <span class="font-medium text-purple-900">${userStats.high_engagement || 0}</span>
      </div>
      <div class="flex justify-between items-center">
        <span class="text-sm text-purple-700">Low Engagement</span>
        <span class="font-medium text-purple-900">${userStats.low_engagement || 0}</span>
      </div>
    `;
  }
}

// Update user count display
function updateUserCount(pagination, searchQuery) {
  const userCountElement = document.getElementById("user-count");
  if (userCountElement && pagination) {
    const countText = searchQuery
      ? `${pagination.total} users found for "${searchQuery}"`
      : `${pagination.total} total users`;
    userCountElement.textContent = countText;
  }
}

// UI Helper functions
function showLoading() {
  document.getElementById("loading-state").classList.remove("hidden");
  document.getElementById("content-area").classList.add("hidden");
  document.getElementById("error-state").classList.add("hidden");
}

function hideLoading() {
  document.getElementById("loading-state").classList.add("hidden");
}

function showError(message) {
  document.getElementById("error-message").textContent = message;
  document.getElementById("error-state").classList.remove("hidden");
  showContent();
}

function hideError() {
  document.getElementById("error-state").classList.add("hidden");
}

function showContent() {
  document.getElementById("content-area").classList.remove("hidden");
}

// Change page
function changePage(page) {
  currentPage = page;

  // Update URL parameters
  updateUrlParams();

  // Load dashboard data for new page
  loadDashboardData();
}

// Change per page
function changePerPage(perPage) {
  currentPerPage = parseInt(perPage);
  currentPage = 1; // Reset to first page

  // Update URL parameters
  updateUrlParams();

  // Load dashboard data for new per page value
  loadDashboardData();
}

// Apply sort filter function
function applySortFilter() {
  const sortBySelect = document.getElementById("sortBySelect");
  const sortOrderSelect = document.getElementById("sortOrderSelect");

  if (sortBySelect && sortOrderSelect) {
    currentSortBy = sortBySelect.value;
    currentSortOrder = sortOrderSelect.value;
    currentPage = 1; // Reset to first page when sorting changes

    // Update URL parameters
    updateUrlParams();

    // Load dashboard data with new sort
    loadDashboardData();
  }
}

// Add event listeners for sort controls
function initializeSortControls() {
  const sortBySelect = document.getElementById("sortBySelect");
  const sortOrderSelect = document.getElementById("sortOrderSelect");

  if (sortBySelect) {
    sortBySelect.addEventListener("change", applySortFilter);
  }

  if (sortOrderSelect) {
    sortOrderSelect.addEventListener("change", applySortFilter);
  }
}

// Delete session confirmation and execution (keeping original functionality)
function confirmDelete(sessionId, username, sessionNumber) {
  console.log(
    `confirmDelete called with: ${sessionId}, ${username}, ${sessionNumber}`
  );
  if (
    confirm(
      `Are you sure you want to delete Session ${sessionNumber} for ${username}?\n\nThis will permanently delete:\n- All PHQ responses\n- All LLM conversations\n- All camera captures\n- All related data\n\nThis action cannot be undone.`
    )
  ) {
    deleteSession(sessionId, username, sessionNumber);
  }
}

function deleteSession(sessionId, username, sessionNumber) {
  // Show loading state on the delete button - use data attribute selector
  const deleteBtn = document.querySelector(
    `button[data-session-id="${sessionId}"]`
  );

  if (!deleteBtn) {
    console.error(`Delete button not found for session ${sessionId}`);
    alert("Delete button not found. Please refresh the page and try again.");
    return;
  }

  const originalContent = deleteBtn.innerHTML;
  deleteBtn.disabled = true;
  deleteBtn.innerHTML = `
        <svg class="animate-spin w-3.5 h-3.5 mr-1.5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Deleting...
    `;

  console.log(`Attempting to delete session ${sessionId}`);
  fetch(`/admin/export/session/${sessionId}/delete`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => {
      console.log("Delete response status:", response.status);
      console.log("Delete response headers:", response.headers);
      return response.json();
    })
    .then((data) => {
      console.log("Delete response data:", data);

      // Handle API response wrapper format
      const actualData = data.status === "OLKORECT" ? data.data : data;

      if (actualData.success) {
        // Update UI to show deleted state
        updateSessionStateToDeleted(sessionId, username, sessionNumber);

        // Show success message
        alert(`Session ${sessionNumber} for ${username} deleted successfully.`);
        
        // Reload dashboard data to reflect changes
        loadDashboardData();
      } else {
        // Restore button on error
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = originalContent;
        alert(`Failed to delete session: ${actualData.message}`);
      }
    })
    .catch((error) => {
      console.error("Delete error:", error);
      // Restore button on error
      deleteBtn.disabled = false;
      deleteBtn.innerHTML = originalContent;
      alert("Failed to delete session. Please try again.");
    });
}

function updateSessionStateToDeleted(sessionId, username, sessionNumber) {
  // Find the row containing this session
  const sessionRow = document
    .querySelector(`button[data-session-id="${sessionId}"]`)
    .closest("tr");

  // Update the status cell
  const statusCell = sessionRow.querySelector("td:nth-child(4)");
  statusCell.innerHTML = `
        <span class="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
            DELETED
        </span>
    `;

  // Update the actions cell
  const actionsCell = sessionRow.querySelector("td:nth-child(6)");
  actionsCell.innerHTML = `
        <div class="flex items-center space-x-1">
            <span class="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-red-100 text-red-600 border border-red-200">
                <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
                Deleted
            </span>
        </div>
    `;
  // Add visual feedback - fade out and red tint
  sessionRow.style.transition = "all 0.3s ease";
  sessionRow.style.backgroundColor = "#fef2f2";
  sessionRow.style.opacity = "0.7";
}

// Function to handle bulk download with loading indicator (keeping original functionality)
function downloadAllSessions() {
  // Note: This function relies on Flask template variable that needs to be passed from template
  const downloadBtn = document.querySelector(".bulk-download-btn");
  if (!downloadBtn) return;

  const originalText = downloadBtn.innerHTML;
  downloadBtn.innerHTML =
    '<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Preparing...';
  downloadBtn.disabled = true;

  // Start download
  setTimeout(() => {
    // Reset button after a short delay to allow download to start
    downloadBtn.innerHTML = originalText;
    downloadBtn.disabled = false;
  }, 2000);
}

// ============================================================================
// FACIAL ANALYSIS TAB FUNCTIONS
// ============================================================================

// Global state for facial analysis
let allFacialAnalysisSessions = [];
let filteredFacialAnalysisSessions = [];
let facialAnalysisSearchDebounceTimer = null;

// Load facial analysis sessions
async function loadFacialAnalysisSessions() {
  // Check gRPC health
  checkFacialAnalysisGrpcHealth();

  try {
    const response = await fetch('/admin/facial-analysis/eligible-sessions');
    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      allFacialAnalysisSessions = data.sessions;
      filteredFacialAnalysisSessions = allFacialAnalysisSessions;
      applyFacialAnalysisFilters();
      updateFacialAnalysisStats(data.stats);
    } else {
      console.error('Failed to load facial analysis sessions:', data.message);
    }
  } catch (error) {
    console.error('Error loading facial analysis sessions:', error);
  }
}

// Check gRPC health
async function checkFacialAnalysisGrpcHealth() {
  try {
    const response = await fetch('/admin/facial-analysis/health');
    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    const banner = document.getElementById('grpc-status-banner');
    if (!banner) return;

    if (data.healthy) {
      banner.innerHTML = `
        <div class="flex items-center justify-between p-4 bg-green-50 rounded-lg border border-green-200">
          <div class="flex items-center">
            <svg class="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <span class="text-sm font-medium text-green-700">gRPC Service Online (${data.config.host}:${data.config.port})</span>
          </div>
        </div>
      `;
    } else {
      banner.innerHTML = `
        <div class="flex items-center justify-between p-4 bg-red-50 rounded-lg border border-red-200">
          <div class="flex items-center">
            <svg class="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <span class="text-sm font-medium text-red-700">gRPC Service Offline - ${data.message}</span>
          </div>
        </div>
      `;
    }
  } catch (error) {
    console.error('Health check failed:', error);
  }
}

// Initialize facial analysis controls
function initializeFacialAnalysisControls() {
  const searchInput = document.getElementById('fa-searchInput');
  const statusFilter = document.getElementById('fa-statusFilter');
  const processAllButton = document.getElementById('fa-process-all-btn');

  if (!searchInput || !statusFilter) return;

  // Search with debounce (300ms)
  searchInput.addEventListener('input', function(e) {
    if (facialAnalysisSearchDebounceTimer) {
      clearTimeout(facialAnalysisSearchDebounceTimer);
    }

    facialAnalysisSearchDebounceTimer = setTimeout(() => {
      applyFacialAnalysisFilters();
    }, 300);
  });

  // Status filter
  statusFilter.addEventListener('change', function() {
    applyFacialAnalysisFilters();
  });

  if (processAllButton && !processAllButton.dataset.listenerAttached) {
    processAllButton.addEventListener('click', processAllFacialAnalysisSessions);
    processAllButton.dataset.listenerAttached = 'true';
  }
}

// Apply facial analysis filters
function applyFacialAnalysisFilters() {
  const searchInput = document.getElementById('fa-searchInput');
  const statusFilter = document.getElementById('fa-statusFilter');

  if (!searchInput || !statusFilter) return;

  const searchQuery = searchInput.value.trim().toLowerCase();
  const statusValue = statusFilter.value;

  filteredFacialAnalysisSessions = allFacialAnalysisSessions.filter(session => {
    // Search filter
    const matchesSearch = !searchQuery ||
      session.username.toLowerCase().includes(searchQuery) ||
      session.email.toLowerCase().includes(searchQuery);

    // Status filter
    let matchesStatus = true;
    if (statusValue !== 'all') {
      if (statusValue === 'not_started') {
        matchesStatus = session.phq_status === 'not_started' && session.llm_status === 'not_started';
      } else if (statusValue === 'processing') {
        matchesStatus = session.phq_status === 'processing' || session.llm_status === 'processing';
      } else if (statusValue === 'completed') {
        matchesStatus = session.phq_status === 'completed' && session.llm_status === 'completed';
      }
    }

    return matchesSearch && matchesStatus;
  });

  renderFacialAnalysisSessions();
}

// Render facial analysis sessions table
function renderFacialAnalysisSessions() {
  const tbody = document.getElementById('facial-analysis-table-body');
  const emptyState = document.getElementById('facial-analysis-empty-state');

  if (!tbody) return;

  if (!filteredFacialAnalysisSessions || filteredFacialAnalysisSessions.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  tbody.innerHTML = filteredFacialAnalysisSessions.map(session => `
    <tr class="hover:bg-gray-50 transition-colors">
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
        ${session.session_end ? new Date(session.session_end).toLocaleDateString() : 'N/A'}
      </td>
      <td class="px-6 py-4">
        ${getFacialAnalysisStatusBadge(session.phq_status)}
      </td>
      <td class="px-6 py-4">
        ${getFacialAnalysisStatusBadge(session.llm_status)}
      </td>
      <td class="px-6 py-4">
        <div class="text-sm">
          <span class="text-blue-600 font-medium">${session.phq_images_count}</span> PHQ |
          <span class="text-purple-600 font-medium">${session.llm_images_count}</span> LLM
        </div>
      </td>
      <td class="px-6 py-4">
        ${getFacialAnalysisActionButton(session)}
      </td>
    </tr>
  `).join('');
}

// Get facial analysis status badge
function getFacialAnalysisStatusBadge(status) {
  const colors = {
    'not_started': 'bg-gray-100 text-gray-700',
    'processing': 'bg-purple-100 text-purple-700 animate-pulse',
    'completed': 'bg-green-100 text-green-700',
    'failed': 'bg-red-100 text-red-700'
  };

  const color = colors[status] || 'bg-gray-100 text-gray-700';

  return `
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}">
      ${status.replace('_', ' ').toUpperCase()}
    </span>
  `;
}

// Get facial analysis action button
function getFacialAnalysisActionButton(session) {
  const phqStatus = normalizeFacialStatus(session.phq_status);
  const llmStatus = normalizeFacialStatus(session.llm_status);
  const canProcess = phqStatus === 'not_started' || llmStatus === 'not_started';
  const isProcessing = phqStatus === 'processing' || llmStatus === 'processing';
  const hasAnalysis = [phqStatus, llmStatus].some(status => status !== 'not_started');

  if (isProcessing) {
    return `
      <div class="flex flex-wrap gap-1">
        <button disabled class="inline-flex items-center px-3 py-2 bg-gray-300 text-gray-600 text-xs font-medium rounded-md cursor-not-allowed">
          <svg class="w-4 h-4 mr-1.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
          Processing...
        </button>
        <button onclick="cancelFacialAnalysisSession('${session.id}')"
                class="inline-flex items-center px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-md hover:bg-red-700 transition-colors">
          <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
          Cancel
        </button>
      </div>
    `;
  }

  const buttons = [];

  if (canProcess) {
    buttons.push(`
      <button onclick="processFacialAnalysisSession('${session.id}')"
              class="inline-flex items-center px-3 py-2 bg-indigo-600 text-white text-xs font-medium rounded-md hover:bg-indigo-700 transition-colors">
        <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        Process
      </button>
    `);
  }

  if (hasAnalysis) {
    buttons.push(`
      <button onclick="reanalyzeFacialAnalysisSession('${session.id}')"
              class="inline-flex items-center px-3 py-2 bg-blue-600 text-white text-xs font-medium rounded-md hover:bg-blue-700 transition-colors">
        Re-Analyze
      </button>
    `);
    buttons.push(`
      <button onclick="deleteFacialAnalysisSession('${session.id}')"
              class="inline-flex items-center px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-md hover:bg-red-700 transition-colors">
        Delete Results
      </button>
    `);
  }

  if (buttons.length === 0) {
    return `<span class="text-xs text-gray-400">No actions</span>`;
  }

  return `<div class="flex flex-wrap gap-1">${buttons.join("")}</div>`;
}

// Process facial analysis session
async function processFacialAnalysisSession(sessionId) {
  if (!confirm('Start facial analysis processing for this session?\n\nThis will process both PHQ and LLM assessments.')) {
    return;
  }

  try {
    const response = await fetch(`/admin/facial-analysis/process/${sessionId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert('Processing started successfully!\n\nPHQ: ' + (data.phq?.message || 'N/A') + '\nLLM: ' + (data.llm?.message || 'N/A'));
      loadFacialAnalysisSessions(); // Reload to show updated status
    } else {
      alert('Processing failed:\n\n' + (data.message || 'Unknown error'));
    }
  } catch (error) {
    alert('Error starting processing:\n\n' + error.message);
  }
}

async function reanalyzeFacialAnalysisSession(sessionId) {
  if (!confirm(`Re-analyze both PHQ and LLM assessments?\n\nThis will delete existing analysis files and reprocess all images for the session.`)) {
    return;
  }

  try {
    const assessments = ['PHQ', 'LLM'];
    const errors = [];

    for (const assessmentType of assessments) {
      const response = await fetch(`/admin/facial-analysis/reanalyze/${sessionId}/${assessmentType}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const httpStatus = response.status;
      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (!data.success || httpStatus >= 400) {
        errors.push(`${assessmentType}: ${data.message || 'Unknown error'}`);
      }
    }

    if (errors.length === 0) {
      alert('Re-analysis completed for PHQ and LLM!');
    } else {
      alert('Re-analysis completed with issues:\n\n' + errors.join('\n'));
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert(`Error re-analyzing session:\n\n${error.message}`);
  }
}

async function cancelFacialAnalysisSession(sessionId) {
  if (!confirm(`Cancel processing for this session?\n\nThis will:\n- Stop any ongoing processing\n- Mark the session as failed/cancelled\n- Delete any partial results\n\nYou can re-process the session afterwards.`)) {
    return;
  }

  try {
    const assessments = ['PHQ', 'LLM'];
    const errors = [];
    let cancelledCount = 0;

    for (const assessmentType of assessments) {
      const response = await fetch(`/admin/facial-analysis/cancel/${sessionId}/${assessmentType}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const httpStatus = response.status;
      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (data.success) {
        cancelledCount++;
      } else if (httpStatus !== 400) {
        // 400 means status was not 'processing' - this is expected
        errors.push(`${assessmentType}: ${data.message || 'Cancel failed'}`);
      }
    }

    if (cancelledCount > 0) {
      alert(`Processing cancelled successfully!\n\nCancelled ${cancelledCount} assessment(s).`);
    } else if (errors.length === 0) {
      alert('No processing to cancel - session is not in processing state.');
    } else {
      alert('Cancel failed:\n\n' + errors.join('\n'));
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert(`Error cancelling processing:\n\n${error.message}`);
  }
}

async function deleteFacialAnalysisSession(sessionId) {
  if (!confirm(`Delete PHQ and LLM analysis?\n\nThis will delete:\n- JSONL result files\n- Database records\n\nThis action cannot be undone!`)) {
    return;
  }

  try {
    const assessments = ['PHQ', 'LLM'];
    const errors = [];

    for (const assessmentType of assessments) {
      const response = await fetch(`/admin/facial-analysis/delete/${sessionId}/${assessmentType}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const httpStatus = response.status;
      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (!data.success && httpStatus !== 404) {
        errors.push(`${assessmentType}: ${data.message || 'Delete failed'}`);
      }
    }

    if (errors.length === 0) {
      alert('PHQ and LLM analysis deleted successfully!');
    } else if (errors.length < assessments.length) {
      alert('Some analysis deleted, but issues occurred:\n\n' + errors.join('\n'));
    } else {
      alert('Delete failed:\n\n' + errors.join('\n'));
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert(`Error deleting session analysis:\n\n${error.message}`);
  }
}

async function processAllFacialAnalysisSessions() {
  if (!confirm('Process facial analysis for all eligible sessions?\n\nThis will sequentially process both PHQ and LLM assessments for every eligible session. This may take a while.')) {
    return;
  }

  const button = document.getElementById('fa-process-all-btn');
  if (!button) {
    return;
  }

  const originalHtml = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `
    <span class="inline-flex items-center">
      <svg class="w-4 h-4 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
      </svg>
      Processing...
    </span>
  `;

  try {
    const response = await fetch('/admin/facial-analysis/process-all', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert(data.message);
    } else {
      const messageParts = [
        data.message || 'Batch processing completed with issues.',
        data.summary ? `Completed: ${data.summary.completed}, Partial: ${data.summary.partial}, Failed: ${data.summary.failed}` : ''
      ].filter(Boolean);
      alert(messageParts.join('\n'));
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert('Batch processing failed:\n\n' + error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = originalHtml;
  }
}

// Update facial analysis stats
function updateFacialAnalysisStats(stats) {
  const statTotal = document.getElementById('fa-stat-total');
  const statPending = document.getElementById('fa-stat-pending');
  const statProcessing = document.getElementById('fa-stat-processing');
  const statCompleted = document.getElementById('fa-stat-completed');

  if (statTotal) statTotal.textContent = stats.total || 0;
  if (statPending) statPending.textContent = stats.pending || 0;
  if (statProcessing) statProcessing.textContent = stats.processing || 0;
  if (statCompleted) statCompleted.textContent = stats.completed || 0;
}

// ============================================================================
// FACIAL ANALYSIS EXPORTS TAB FUNCTIONS
// ============================================================================

// Global state for facial analysis exports
let allFacialAnalysisExportSessions = [];
let filteredFacialAnalysisExportSessions = [];
let currentFacialExportPage = 1;
let currentFacialExportPerPage = 15;
let currentFacialExportSearchQuery = "";
let currentFacialExportSortBy = "user_id";
let currentFacialExportSortOrder = "asc";
let facialExportSearchDebounceTimer = null;
let selectedFacialExportSessions = new Set();

// Load facial analysis export sessions
async function loadFacialAnalysisExports() {
  try {
    const response = await fetch('/admin/export/facial-analysis/sessions-list');
    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.sessions) {
      allFacialAnalysisExportSessions = data.sessions;
      applyFacialExportFilters();
      updateFacialExportCount();
    } else {
      console.error('Failed to load facial analysis export sessions:', data.message);
    }
  } catch (error) {
    console.error('Error loading facial analysis export sessions:', error);
  }
}

// Initialize facial analysis exports controls
function initializeFacialAnalysisExportsControls() {
  const searchInput = document.getElementById('facialExportSearch');
  const sortBy = document.getElementById('facialExportSortBy');
  const sortOrder = document.getElementById('facialExportSortOrder');
  const perPage = document.getElementById('facial-export-per-page');
  const bulkButton = document.getElementById('bulk-download-facial-analysis');

  if (searchInput) {
    searchInput.addEventListener('input', function(e) {
      if (facialExportSearchDebounceTimer) {
        clearTimeout(facialExportSearchDebounceTimer);
      }
      facialExportSearchDebounceTimer = setTimeout(() => {
        currentFacialExportSearchQuery = e.target.value.trim().toLowerCase();
        currentFacialExportPage = 1;
        applyFacialExportFilters();
      }, 300);
    });
  }

  if (sortBy) {
    sortBy.addEventListener('change', function() {
      currentFacialExportSortBy = this.value;
      currentFacialExportPage = 1;
      applyFacialExportFilters();
    });
  }

  if (sortOrder) {
    sortOrder.addEventListener('change', function() {
      currentFacialExportSortOrder = this.value;
      currentFacialExportPage = 1;
      applyFacialExportFilters();
    });
  }

  if (perPage) {
    perPage.addEventListener('change', function() {
      currentFacialExportPerPage = parseInt(this.value);
      currentFacialExportPage = 1;
      applyFacialExportFilters();
    });
  }

  if (bulkButton) {
    bulkButton.addEventListener('click', downloadBulkFacialAnalysis);
  }
}

// Apply facial export filters
function applyFacialExportFilters() {
  // Filter sessions
  filteredFacialAnalysisExportSessions = allFacialAnalysisExportSessions.filter(session => {
    // Search filter
    if (currentFacialExportSearchQuery) {
      const matchesSearch = session.username.toLowerCase().includes(currentFacialExportSearchQuery);
      if (!matchesSearch) return false;
    }
    return true;
  });

  // Sort sessions
  filteredFacialAnalysisExportSessions.sort((a, b) => {
    let aVal, bVal;

    switch(currentFacialExportSortBy) {
      case 'username':
        aVal = a.username.toLowerCase();
        bVal = b.username.toLowerCase();
        break;
      case 'created_at':
        aVal = new Date(a.created_at);
        bVal = new Date(b.created_at);
        break;
      case 'user_id':
      default:
        aVal = a.user_id;
        bVal = b.user_id;
        break;
    }

    if (aVal < bVal) return currentFacialExportSortOrder === 'asc' ? -1 : 1;
    if (aVal > bVal) return currentFacialExportSortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  renderFacialExportSessions();
  updateFacialExportPagination();
  updateFacialExportCount();
}

// Render facial export sessions table
function renderFacialExportSessions() {
  const headerEl = document.getElementById('facial-export-table-header');
  const bodyEl = document.getElementById('facial-export-table-body');

  if (!headerEl || !bodyEl) return;

  // Set up table header
  headerEl.innerHTML = `
    <tr>
      <th class="px-6 py-3 text-left">
        <input type="checkbox" id="select-all-facial-exports" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
      </th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Session</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">PHQ Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">LLM Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
    </tr>
  `;

  // Calculate pagination
  const start = (currentFacialExportPage - 1) * currentFacialExportPerPage;
  const end = start + currentFacialExportPerPage;
  const paginatedSessions = filteredFacialAnalysisExportSessions.slice(start, end);

  if (paginatedSessions.length === 0) {
    bodyEl.innerHTML = `
      <tr>
        <td colspan="7" class="px-6 py-12 text-center text-sm text-gray-500">
          <div class="flex flex-col items-center justify-center">
            <svg class="w-12 h-12 text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <span class="text-lg font-medium text-gray-400">No facial analysis exports available</span>
            <p class="text-sm text-gray-500 mt-1">Sessions with completed facial analysis will appear here</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  let rowsHtml = '';
  paginatedSessions.forEach((session) => {
    const canDownload = session.can_download;
    const isChecked = selectedFacialExportSessions.has(session.id);

    rowsHtml += `
      <tr class="border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
        <td class="px-6 py-4">
          ${canDownload ? `<input type="checkbox" class="facial-export-checkbox rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" data-session-id="${session.id}" ${isChecked ? 'checked' : ''}>` : ''}
        </td>
        <td class="py-4 px-6 font-medium text-gray-900">${session.user_id}</td>
        <td class="py-4 px-6 font-medium text-gray-900">${session.username}</td>
        <td class="py-4 px-6 text-gray-900">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full ${session.session_number === 1 ? 'bg-blue-500' : 'bg-purple-500'} mr-2"></div>
            <span class="font-medium">Session ${session.session_number}</span>
          </div>
        </td>
        <td class="py-4 px-6">${getFacialStatusBadge(session.phq_analysis_status)}</td>
        <td class="py-4 px-6">${getFacialStatusBadge(session.llm_analysis_status)}</td>
        <td class="py-4 px-6">
          ${getFacialExportActionButtons(session)}
        </td>
      </tr>
    `;
  });

  bodyEl.innerHTML = rowsHtml;

  // Add event listener for select all checkbox
  const selectAllCheckbox = document.getElementById('select-all-facial-exports');
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function() {
      const checkboxes = document.querySelectorAll('.facial-export-checkbox');
      checkboxes.forEach(cb => {
        cb.checked = this.checked;
        const sessionId = cb.dataset.sessionId;
        if (this.checked) {
          selectedFacialExportSessions.add(sessionId);
        } else {
          selectedFacialExportSessions.delete(sessionId);
        }
      });
      updateBulkDownloadButton();
    });
  }

  // Add event listeners for individual checkboxes
  document.querySelectorAll('.facial-export-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      const sessionId = this.dataset.sessionId;
      if (this.checked) {
        selectedFacialExportSessions.add(sessionId);
      } else {
        selectedFacialExportSessions.delete(sessionId);
      }
      updateBulkDownloadButton();
    });
  });
}

// Get facial status badge
function getFacialStatusBadge(status) {
  const colors = {
    'completed': 'bg-green-100 text-green-800',
    'processing': 'bg-yellow-100 text-yellow-800',
    'failed': 'bg-red-100 text-red-800',
    'not_started': 'bg-gray-100 text-gray-600',
    'pending': 'bg-blue-100 text-blue-800'
  };

  const color = colors[status] || 'bg-gray-100 text-gray-600';
  const displayStatus = status.replace('_', ' ').toUpperCase();

  return `<span class="px-2 py-1 rounded-full text-xs font-medium ${color}">${displayStatus}</span>`;
}

// Get facial export action buttons
function getFacialExportActionButtons(session) {
  if (session.can_download) {
    return `
      <a href="/admin/export/facial-analysis/session/${session.id}"
         class="inline-flex items-center justify-center px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm">
        <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
        </svg>
        Download
      </a>
    `;
  } else {
    return `
      <span class="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
        <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        Processing
      </span>
    `;
  }
}

// Update facial export pagination
function updateFacialExportPagination() {
  const containerEl = document.getElementById("facial-export-pagination-container");
  const infoEl = document.getElementById("facial-export-pagination-info");
  const controlsEl = document.getElementById("facial-export-pagination-controls");

  if (!containerEl || !infoEl || !controlsEl) return;

  const total = filteredFacialAnalysisExportSessions.length;
  const totalPages = Math.ceil(total / currentFacialExportPerPage);

  if (total === 0) {
    containerEl.classList.add("hidden");
    return;
  }

  containerEl.classList.remove("hidden");

  // Update info text
  const start = (currentFacialExportPage - 1) * currentFacialExportPerPage + 1;
  const end = Math.min(start + currentFacialExportPerPage - 1, total);
  infoEl.textContent = `Showing ${start} to ${end} of ${total} results`;

  // Build pagination controls
  let controls = "";

  // Previous button
  if (currentFacialExportPage > 1) {
    controls += `<button onclick="changeFacialExportPage(${currentFacialExportPage - 1})" class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">Previous</button>`;
  } else {
    controls += `<button disabled class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">Previous</button>`;
  }

  // Page numbers
  for (let i = 1; i <= totalPages; i++) {
    if (i === currentFacialExportPage) {
      controls += `<button onclick="changeFacialExportPage(${i})" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-indigo-50 text-sm font-medium text-indigo-600">${i}</button>`;
    } else {
      controls += `<button onclick="changeFacialExportPage(${i})" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">${i}</button>`;
    }
  }

  // Next button
  if (currentFacialExportPage < totalPages) {
    controls += `<button onclick="changeFacialExportPage(${currentFacialExportPage + 1})" class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">Next</button>`;
  } else {
    controls += `<button disabled class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">Next</button>`;
  }

  controlsEl.innerHTML = controls;
}

// Change facial export page
function changeFacialExportPage(page) {
  currentFacialExportPage = page;
  renderFacialExportSessions();
  updateFacialExportPagination();
}

// Update facial export count
function updateFacialExportCount() {
  const countEl = document.getElementById("facial-export-count");
  if (countEl) {
    const readyCount = allFacialAnalysisExportSessions.filter(s => s.can_download).length;
    countEl.textContent = `${readyCount} sessions ready`;
  }
}

// Update bulk download button
function updateBulkDownloadButton() {
  const bulkButton = document.getElementById('bulk-download-facial-analysis');
  if (bulkButton) {
    bulkButton.disabled = selectedFacialExportSessions.size === 0;
  }
}

// Download bulk facial analysis
async function downloadBulkFacialAnalysis() {
  if (selectedFacialExportSessions.size === 0) {
    alert('Please select at least one session to download.');
    return;
  }

  const sessionIds = Array.from(selectedFacialExportSessions);

  try {
    const response = await fetch('/admin/export/facial-analysis/bulk', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ session_ids: sessionIds })
    });

    if (response.ok) {
      // Trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bulk_facial_analysis_export_${new Date().getTime()}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      // Clear selection
      selectedFacialExportSessions.clear();
      renderFacialExportSessions();
      updateBulkDownloadButton();
    } else {
      const error = await response.json();
      alert(`Bulk download failed: ${error.error || 'Unknown error'}`);
    }
  } catch (error) {
    alert(`Error downloading bulk facial analysis: ${error.message}`);
  }
}
