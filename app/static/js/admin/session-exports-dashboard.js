// app/static/js/admin/session-exports-dashboard.js
// Session Exports tab functionality for admin dashboard

// Global state for session exports
let allSessionExportSessions = [];
let filteredSessionExportSessions = [];
let currentSessionExportPage = 1;
let currentSessionExportPerPage = 15;
let currentSessionExportSearchQuery = "";
let currentSessionExportSortBy = "user_id";
let currentSessionExportSortOrder = "asc";
let sessionExportSearchDebounceTimer = null;
let selectedSessionExportSessions = new Set();

// Load session export sessions with pagination and search
async function loadSessionExportSessions() {
  try {
    let url = `/admin/ajax-dashboard-data?tab=session-exports&page=${currentSessionExportPage}&per_page=${currentSessionExportPerPage}`;
    if (currentSessionExportSearchQuery) {
      url += `&q=${encodeURIComponent(currentSessionExportSearchQuery)}`;
    }
    url += `&sort_by=${currentSessionExportSortBy}&sort_order=${currentSessionExportSortOrder}`;

    const response = await fetch(url);
    const result = await response.json();
    console.log('[SESSION-EXPORTS] API URL:', url);
    console.log('[SESSION-EXPORTS] Full response tab:', result?.data?.tab || result?.tab);
    let data = result.status === 'OLKORECT' ? result.data : result;
    // The response is double-wrapped: outer wrapper has 'data' and 'status', inner has the actual data
    if (data.data) {
      data = data.data;
    }

    if (data && data.status === 'success' && data.user_sessions) {
      // Extract session export data from user sessions
      allSessionExportSessions = [];

      for (const item of data.user_sessions.items) {
        // Process Session 1
        if (item.session1_id && item.session1_facial_analysis) {
          allSessionExportSessions.push({
            id: item.session1_id,
            user_id: item.user_id,
            username: item.username,
            session_number: 1,
            phq_status: item.session1_facial_analysis.phq_status,
            llm_status: item.session1_facial_analysis.llm_status,
            can_download: item.session1_facial_analysis.can_download
          });
        }

        // Process Session 2
        if (item.session2_id && item.session2_facial_analysis) {
          allSessionExportSessions.push({
            id: item.session2_id,
            user_id: item.user_id,
            username: item.username,
            session_number: 2,
            phq_status: item.session2_facial_analysis.phq_status,
            llm_status: item.session2_facial_analysis.llm_status,
            can_download: item.session2_facial_analysis.can_download
          });
        }
      }

      filteredSessionExportSessions = allSessionExportSessions;
      currentSessionExportPage = 1;  // Reset to page 1 when data reloads
      renderSessionExportSessions();
      // Calculate pagination based on FILTERED sessions, not API pagination
      updateSessionExportPagination();
      updateSessionExportCount();
    } else {
      console.error('[SESSION-EXPORTS] Failed to load:', {
        status: data?.status,
        hasUserSessions: !!data?.user_sessions,
        message: data?.message,
        fullData: data
      });
    }
  } catch (error) {
    console.error('Error loading session export sessions:', error);
  }
}

// Initialize session export controls
function initializeSessionExportControls() {
  const searchInput = document.getElementById('facialExportSearch');
  const sortBy = document.getElementById('facialExportSortBy');
  const sortOrder = document.getElementById('facialExportSortOrder');
  const perPage = document.getElementById('facial-export-per-page');
  const bulkButton = document.getElementById('bulk-download-facial-analysis');

  if (searchInput) {
    searchInput.addEventListener('input', function(e) {
      if (sessionExportSearchDebounceTimer) {
        clearTimeout(sessionExportSearchDebounceTimer);
      }
      sessionExportSearchDebounceTimer = setTimeout(() => {
        currentSessionExportSearchQuery = e.target.value.trim().toLowerCase();
        currentSessionExportPage = 1;
        loadSessionExportSessions();
      }, 300);
    });
  }

  if (sortBy) {
    sortBy.addEventListener('change', function() {
      currentSessionExportSortBy = this.value;
      currentSessionExportPage = 1;
      loadSessionExportSessions();
    });
  }

  if (sortOrder) {
    sortOrder.addEventListener('change', function() {
      currentSessionExportSortOrder = this.value;
      currentSessionExportPage = 1;
      loadSessionExportSessions();
    });
  }

  if (perPage) {
    perPage.addEventListener('change', function() {
      currentSessionExportPerPage = parseInt(this.value);
      currentSessionExportPage = 1;
      loadSessionExportSessions();
    });
  }

  if (bulkButton) {
    bulkButton.addEventListener('click', downloadBulkSessions);
  }
}

// Render session export sessions table
function renderSessionExportSessions() {
  const headerEl = document.getElementById('facial-export-table-header');
  const bodyEl = document.getElementById('facial-export-table-body');

  if (!headerEl || !bodyEl) return;

  headerEl.innerHTML = `
    <tr>
      <th class="px-6 py-3 text-left">
        <input type="checkbox" id="select-all-sessions" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
      </th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Session</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">PHQ Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">LLM Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
    </tr>
  `;

  const start = (currentSessionExportPage - 1) * currentSessionExportPerPage;
  const end = start + currentSessionExportPerPage;
  const paginatedSessions = filteredSessionExportSessions.slice(start, end);

  if (paginatedSessions.length === 0) {
    bodyEl.innerHTML = `
      <tr>
        <td colspan="7" class="px-6 py-12 text-center text-sm text-gray-500">
          <div class="flex flex-col items-center justify-center">
            <svg class="w-12 h-12 text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <span class="text-lg font-medium text-gray-400">No sessions available</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  let rowsHtml = '';
  paginatedSessions.forEach((session) => {
    const canDownload = session.can_download;
    const isChecked = selectedSessionExportSessions.has(session.id);

    rowsHtml += `
      <tr class="border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150">
        <td class="px-6 py-4">
          ${canDownload ? `<input type="checkbox" class="session-export-checkbox rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" data-session-id="${session.id}" ${isChecked ? 'checked' : ''}>` : ''}
        </td>
        <td class="py-4 px-6 font-medium text-gray-900">${session.user_id}</td>
        <td class="py-4 px-6 font-medium text-gray-900">${session.username}</td>
        <td class="py-4 px-6 text-gray-900">
          <div class="flex items-center">
            <div class="w-3 h-3 rounded-full ${session.session_number === 1 ? 'bg-blue-500' : 'bg-purple-500'} mr-2"></div>
            <span class="font-medium">Session ${session.session_number}</span>
          </div>
        </td>
        <td class="py-4 px-6">${getSessionExportStatusBadge(session.phq_status)}</td>
        <td class="py-4 px-6">${getSessionExportStatusBadge(session.llm_status)}</td>
        <td class="py-4 px-6">
          ${getSessionExportActionButtons(session)}
        </td>
      </tr>
    `;
  });

  bodyEl.innerHTML = rowsHtml;

  // Add event listener for select all checkbox
  const selectAllCheckbox = document.getElementById('select-all-sessions');
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function() {
      const checkboxes = document.querySelectorAll('.session-export-checkbox');
      checkboxes.forEach(cb => {
        cb.checked = this.checked;
        const sessionId = cb.dataset.sessionId;
        if (this.checked) {
          selectedSessionExportSessions.add(sessionId);
        } else {
          selectedSessionExportSessions.delete(sessionId);
        }
      });
      updateBulkDownloadButton();
    });
  }

  // Add event listeners for individual checkboxes
  document.querySelectorAll('.session-export-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      const sessionId = this.dataset.sessionId;
      if (this.checked) {
        selectedSessionExportSessions.add(sessionId);
      } else {
        selectedSessionExportSessions.delete(sessionId);
      }
      updateBulkDownloadButton();
    });
  });
}

// Get session export status badge
function getSessionExportStatusBadge(status) {
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

// Get session export action buttons
function getSessionExportActionButtons(session) {
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

// Update session export pagination
function updateSessionExportPagination() {
  const containerEl = document.getElementById("facial-export-pagination-container");
  const infoEl = document.getElementById("facial-export-pagination-info");
  const controlsEl = document.getElementById("facial-export-pagination-controls");

  if (!containerEl || !infoEl || !controlsEl) return;

  // Calculate pagination based on FILTERED sessions only
  const total = filteredSessionExportSessions.length;
  const totalPages = Math.ceil(total / currentSessionExportPerPage);

  if (total === 0) {
    containerEl.classList.add("hidden");
    return;
  }

  containerEl.classList.remove("hidden");

  const start = (currentSessionExportPage - 1) * currentSessionExportPerPage + 1;
  const end = Math.min(start + currentSessionExportPerPage - 1, total);
  infoEl.textContent = `Showing ${start} to ${end} of ${total} results`;

  let controls = "";

  if (currentSessionExportPage > 1) {
    controls += `<button onclick="changeSessionExportPage(${currentSessionExportPage - 1})" class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">Previous</button>`;
  } else {
    controls += `<button disabled class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">Previous</button>`;
  }

  for (let i = 1; i <= totalPages; i++) {
    if (i === currentSessionExportPage) {
      controls += `<button onclick="changeSessionExportPage(${i})" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-indigo-50 text-sm font-medium text-indigo-600">${i}</button>`;
    } else {
      controls += `<button onclick="changeSessionExportPage(${i})" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">${i}</button>`;
    }
  }

  if (currentSessionExportPage < totalPages) {
    controls += `<button onclick="changeSessionExportPage(${currentSessionExportPage + 1})" class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">Next</button>`;
  } else {
    controls += `<button disabled class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">Next</button>`;
  }

  controlsEl.innerHTML = controls;
}

// Change session export page
function changeSessionExportPage(page) {
  currentSessionExportPage = page;
  loadSessionExportSessions();
}

// Update session export count
function updateSessionExportCount() {
  const countEl = document.getElementById("facial-export-count");
  if (countEl) {
    const readyCount = allSessionExportSessions.filter(s => s.can_download).length;
    countEl.textContent = `${readyCount} sessions ready`;
  }
}

// Update bulk download button
function updateBulkDownloadButton() {
  const bulkButton = document.getElementById('bulk-download-facial-analysis');
  if (bulkButton) {
    bulkButton.disabled = selectedSessionExportSessions.size === 0;
  }
}

// Download bulk sessions
async function downloadBulkSessions() {
  if (selectedSessionExportSessions.size === 0) {
    alert('Please select at least one session to download.');
    return;
  }

  const sessionIds = Array.from(selectedSessionExportSessions);

  try {
    const response = await fetch('/admin/facial-analysis/export/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_ids: sessionIds })
    });

    if (response.ok) {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bulk_sessions_export_${new Date().getTime()}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      selectedSessionExportSessions.clear();
      renderSessionExportSessions();
      updateBulkDownloadButton();
    } else {
      const error = await response.json();
      alert(`Download failed: ${error.error || 'Unknown error'}`);
    }
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}
