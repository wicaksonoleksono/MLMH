// app/static/js/admin/facial-analysis-dashboard.js
// Facial Analysis tab functionality for admin dashboard

// Global state for facial analysis
let allFacialAnalysisSessions = [];
let filteredFacialAnalysisSessions = [];
let currentFacialPage = 1;
let currentFacialPerPage = 15;
let currentFacialSearchQuery = "";
let currentFacialSortBy = "user_id";
let currentFacialSortOrder = "asc";
let facialAnalysisSearchDebounceTimer = null;

function normalizeFacialStatus(status) {
  if (!status) {
    return "not_started";
  }
  return String(status).trim().toLowerCase();
}

// Load facial analysis sessions with pagination and search
async function loadFacialAnalysisSessions() {
  checkFacialAnalysisGrpcHealth();
  updateFacialAnalysisStats(); // Update stats cards

  try {
    // Build URL with pagination, search, and sort parameters
    let url = `/admin/ajax-dashboard-data?tab=facial-analysis&page=${currentFacialPage}&per_page=${currentFacialPerPage}`;
    if (currentFacialSearchQuery) {
      url += `&q=${encodeURIComponent(currentFacialSearchQuery)}`;
    }
    url += `&sort_by=${currentFacialSortBy}&sort_order=${currentFacialSortOrder}`;

    const response = await fetch(url);
    const result = await response.json();
    let data = result.status === 'OLKORECT' ? result.data : result;
    // The response is double-wrapped: outer wrapper has 'data' and 'status', inner has the actual data
    if (data.data) {
      data = data.data;
    }

    if (data && data.status === 'success' && data.user_sessions) {
      // Extract facial analysis data from user sessions
      allFacialAnalysisSessions = [];

      for (const item of data.user_sessions.items) {
        // Process Session 1
        if (item.session1_id && item.session1_facial_analysis) {
          allFacialAnalysisSessions.push({
            id: item.session1_id,
            user_id: item.user_id,
            username: item.username,
            session_number: 1,
            phq_status: item.session1_facial_analysis.phq_status,
            llm_status: item.session1_facial_analysis.llm_status,
            phq_images_count: item.session1_facial_analysis.phq_images || 0,
            llm_images_count: item.session1_facial_analysis.llm_images || 0,
            total_images: (item.session1_facial_analysis.phq_images || 0) + (item.session1_facial_analysis.llm_images || 0)
          });
        }

        // Process Session 2
        if (item.session2_id && item.session2_facial_analysis) {
          allFacialAnalysisSessions.push({
            id: item.session2_id,
            user_id: item.user_id,
            username: item.username,
            session_number: 2,
            phq_status: item.session2_facial_analysis.phq_status,
            llm_status: item.session2_facial_analysis.llm_status,
            phq_images_count: item.session2_facial_analysis.phq_images || 0,
            llm_images_count: item.session2_facial_analysis.llm_images || 0,
            total_images: (item.session2_facial_analysis.phq_images || 0) + (item.session2_facial_analysis.llm_images || 0)
          });
        }
      }

      filteredFacialAnalysisSessions = allFacialAnalysisSessions;
      renderFacialAnalysisSessions();
      updateFacialAnalysisPagination(data.user_sessions.pagination);
    } else {
      console.error('Failed to load facial analysis sessions. Response:', {
        status: data?.status,
        hasUserSessions: !!data?.user_sessions,
        message: data?.message
      });
    }
  } catch (error) {
    console.error('Error loading facial analysis sessions:', error);
  }
}

// Update stats cards (Total, Pending, Processing, Completed)
async function updateFacialAnalysisStats() {
  try {
    const response = await fetch('/admin/facial-analysis/process-all/status');
    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (!data.success) {
      console.error('Failed to load stats:', data.message);
      return;
    }

    const stats = data.stats;

    // Update stat cards
    const totalEl = document.getElementById('fa-stat-total');
    const pendingEl = document.getElementById('fa-stat-pending');
    const processingEl = document.getElementById('fa-stat-processing');
    const completedEl = document.getElementById('fa-stat-completed');

    if (totalEl) totalEl.textContent = data.total || 0;
    if (pendingEl) pendingEl.textContent = stats.queued || 0;
    if (processingEl) processingEl.textContent = stats.processing || 0;
    if (completedEl) completedEl.textContent = stats.completed || 0;

  } catch (error) {
    console.error('Error loading stats:', error);
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
  const deleteAllButton = document.getElementById('fa-delete-all-btn');

  if (searchInput) {
    searchInput.addEventListener('input', function(e) {
      if (facialAnalysisSearchDebounceTimer) {
        clearTimeout(facialAnalysisSearchDebounceTimer);
      }
      facialAnalysisSearchDebounceTimer = setTimeout(() => {
        currentFacialSearchQuery = e.target.value.trim().toLowerCase();
        currentFacialPage = 1;
        loadFacialAnalysisSessions();
      }, 300);
    });
  }

  if (statusFilter) {
    statusFilter.addEventListener('change', function() {
      currentFacialPage = 1;
      applyFacialAnalysisFilters();
    });
  }

  if (processAllButton && !processAllButton.dataset.listenerAttached) {
    processAllButton.addEventListener('click', processAllFacialAnalysisSessions);
    processAllButton.dataset.listenerAttached = 'true';
  }

  if (deleteAllButton && !deleteAllButton.dataset.listenerAttached) {
    deleteAllButton.addEventListener('click', deleteAllFacialAnalysisResults);
    deleteAllButton.dataset.listenerAttached = 'true';
  }
}

// Apply facial analysis filters
function applyFacialAnalysisFilters() {
  const statusFilter = document.getElementById('fa-statusFilter');
  const statusValue = statusFilter ? statusFilter.value : 'all';

  filteredFacialAnalysisSessions = allFacialAnalysisSessions.filter(session => {
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

    return matchesStatus;
  });

  currentFacialPage = 1;
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

  let rowsHtml = '';
  let previousUserId = null;

  filteredFacialAnalysisSessions.forEach((session, index) => {
    const isNewUser = session.user_id !== previousUserId;
    const isLastOfUser = (index === filteredFacialAnalysisSessions.length - 1) || (filteredFacialAnalysisSessions[index + 1].user_id !== session.user_id);

    let rowClasses = 'transition-colors';

    if (isNewUser && isLastOfUser) {
      rowClasses += ' bg-white hover:bg-gray-50';
    } else if (isNewUser) {
      rowClasses += ' bg-indigo-50/30 hover:bg-indigo-50/50 border-t-2 border-indigo-200';
    } else if (isLastOfUser) {
      rowClasses += ' bg-indigo-50/30 hover:bg-indigo-50/50 border-b-2 border-indigo-200';
    } else {
      rowClasses += ' bg-indigo-50/30 hover:bg-indigo-50/50';
    }

    rowsHtml += `
      <tr class="${rowClasses}">`;

    if (isNewUser) {
      const rowspanValue = (isLastOfUser) ? 1 : 2;
      rowsHtml += `
        <td class="px-6 py-4 font-medium" rowspan="${rowspanValue}">
          <div class="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-lg p-3 border border-indigo-200">
            <div class="text-sm font-semibold text-gray-900">${session.username}</div>
            ${rowspanValue === 2 ? `<div class="text-xs text-indigo-600 mt-2 font-medium">2 Sessions</div>` : ''}
          </div>
        </td>`;
    }

    rowsHtml += `
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
            Session ${session.session_number}
          </span>
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
    `;

    previousUserId = session.user_id;
  });

  tbody.innerHTML = rowsHtml;
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
  const hasImages = (session.phq_images_count > 0) || (session.llm_images_count > 0);
  const canProcess = hasImages && (phqStatus === 'not_started' || llmStatus === 'not_started');
  const isProcessing = phqStatus === 'processing' || llmStatus === 'processing';
  const hasAnalysis = [phqStatus, llmStatus].some(status => status !== 'not_started');

  // No images captured - session incomplete, disable button
  if (!hasImages) {
    return `
      <button disabled class="inline-flex items-center px-3 py-2 bg-gray-200 text-gray-400 text-xs font-medium rounded-md cursor-not-allowed" title="No images captured for this session">
        <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>
        </svg>
        No Images
      </button>
    `;
  }

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
  if (!confirm('Start facial analysis processing for this session?\n\nThis will process both PHQ and LLM assessments in the background.')) {
    return;
  }

  try {
    const response = await fetch(`/admin/facial-analysis/process/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      alert('Server error: Expected JSON response but got HTML.');
      return;
    }

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert('Processing queued successfully!');
      loadFacialAnalysisSessions();
      pollProcessingStatus(sessionId, data.phq_task_id, data.llm_task_id);
    } else {
      alert('Processing failed:\n\n' + (data.message || 'Unknown error'));
    }
  } catch (error) {
    alert('Error starting processing:\n\n' + error.message);
  }
}

// Poll for processing status
async function pollProcessingStatus(sessionId, phqTaskId, llmTaskId, maxPollCount = 720) {
  let pollCount = 0;

  const pollInterval = setInterval(async () => {
    pollCount++;

    try {
      const phqStatus = await fetch(`/admin/facial-analysis/task-status/${sessionId}/PHQ`).then(r => r.json());
      const llmStatus = await fetch(`/admin/facial-analysis/task-status/${sessionId}/LLM`).then(r => r.json());

      const phqData = phqStatus.status === 'OLKORECT' ? phqStatus.data : phqStatus;
      const llmData = llmStatus.status === 'OLKORECT' ? llmStatus.data : llmStatus;

      const phqDone = ['completed', 'failed'].includes(phqData.details?.status);
      const llmDone = ['completed', 'failed'].includes(llmData.details?.status);

      if (phqDone && llmDone) {
        clearInterval(pollInterval);
        const phqMsg = phqData.details?.status === 'completed' ? '✓ PHQ completed' : '✗ PHQ failed';
        const llmMsg = llmData.details?.status === 'completed' ? '✓ LLM completed' : '✗ LLM failed';
        alert(`Processing finished!\n\n${phqMsg}\n${llmMsg}`);
        loadFacialAnalysisSessions();
        return;
      }

      if (pollCount >= maxPollCount) {
        clearInterval(pollInterval);
        alert('Polling timeout.');
        loadFacialAnalysisSessions();
        return;
      }
    } catch (error) {
      console.error('Error polling status:', error);
    }
  }, 5000);
}

async function reanalyzeFacialAnalysisSession(sessionId) {
  if (!confirm(`Re-analyze both PHQ and LLM assessments?`)) {
    return;
  }

  try {
    const assessments = ['PHQ', 'LLM'];
    const errors = [];

    for (const assessmentType of assessments) {
      const response = await fetch(`/admin/facial-analysis/reanalyze/${sessionId}/${assessmentType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (!data.success) {
        errors.push(`${assessmentType}: ${data.message || 'Unknown error'}`);
      }
    }

    if (errors.length === 0) {
      alert('Re-analysis completed!');
    } else {
      alert('Re-analysis completed with issues:\n\n' + errors.join('\n'));
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function cancelFacialAnalysisSession(sessionId) {
  if (!confirm(`Cancel processing for this session?`)) {
    return;
  }

  try {
    const assessments = ['PHQ', 'LLM'];
    let cancelledCount = 0;

    for (const assessmentType of assessments) {
      const response = await fetch(`/admin/facial-analysis/cancel/${sessionId}/${assessmentType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (data.success) {
        cancelledCount++;
      }
    }

    if (cancelledCount > 0) {
      alert(`Processing cancelled successfully!`);
    } else {
      alert('No processing to cancel.');
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function deleteFacialAnalysisSession(sessionId) {
  if (!confirm(`Delete PHQ and LLM analysis?\n\nThis action cannot be undone!`)) {
    return;
  }

  try {
    const assessments = ['PHQ', 'LLM'];
    let deletedCount = 0;

    for (const assessmentType of assessments) {
      const response = await fetch(`/admin/facial-analysis/delete/${sessionId}/${assessmentType}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (data.success) {
        deletedCount++;
      }
    }

    if (deletedCount > 0) {
      alert('Analysis deleted successfully!');
    } else {
      alert('Delete failed.');
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function processAllFacialAnalysisSessions() {
  if (!confirm('Process facial analysis for all eligible sessions?\n\nThis will queue all sessions and process them sequentially.')) {
    return;
  }

  const button = document.getElementById('fa-process-all-btn');
  if (!button) return;

  const originalHtml = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span>Queueing...</span>`;

  try {
    const response = await fetch('/admin/facial-analysis/process-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert('✅ ' + data.message + '\n\nProcessing will continue in the background.\nRefresh the page to see progress.');

      // Start polling for overall progress
      pollProcessAllProgress(button, originalHtml);
    } else {
      alert('⚠️ ' + (data.message || 'Failed to queue sessions.'));
      button.disabled = false;
      button.innerHTML = originalHtml;
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert('Error: ' + error.message);
    button.disabled = false;
    button.innerHTML = originalHtml;
  }
}

async function pollProcessAllProgress(button, originalHtml) {
  /**
   * Poll /process-all/status to show real-time progress
   * Updates button text with progress stats
   */
  let pollCount = 0;
  const maxPolls = 1200; // 1200 * 10s = 200 minutes max

  const pollInterval = setInterval(async () => {
    pollCount++;

    try {
      const response = await fetch('/admin/facial-analysis/process-all/status');
      const result = await response.json();
      const data = result.status === 'OLKORECT' ? result.data : result;

      if (!data.success) {
        console.error('Failed to get progress:', data.message);
        return;
      }

      const stats = data.stats;
      const completed = stats.completed + stats.failed;
      const total = data.total;
      const percentage = data.progress_percentage;

      // Update button with progress
      button.innerHTML = `
        <span>Processing ${completed}/${total} (${percentage}%)</span>
      `;

      // Check if done
      if (!data.is_running || completed >= total) {
        clearInterval(pollInterval);
        button.disabled = false;
        button.innerHTML = originalHtml;

        alert(`✅ Batch processing complete!\n\nCompleted: ${stats.completed}\nFailed: ${stats.failed}\nTotal: ${total}`);
        loadFacialAnalysisSessions();
        return;
      }

      // Timeout check
      if (pollCount >= maxPolls) {
        clearInterval(pollInterval);
        button.disabled = false;
        button.innerHTML = originalHtml;
        alert('⚠️ Progress polling timeout. Processing may still be running in the background.');
        loadFacialAnalysisSessions();
        return;
      }

      // Refresh table periodically
      if (pollCount % 6 === 0) { // Every minute (6 * 10s)
        loadFacialAnalysisSessions();
      }

    } catch (error) {
      console.error('Error polling progress:', error);
    }
  }, 10000); // Poll every 10 seconds
}

async function deleteAllFacialAnalysisResults() {
  if (!confirm('Delete ALL facial analysis results and JSONL files?\n\nThis action cannot be undone!')) {
    return;
  }

  const button = document.getElementById('fa-delete-all-btn');
  if (!button) return;

  const originalHtml = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span>Deleting...</span>`;

  try {
    const response = await fetch('/admin/facial-analysis/delete-all', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    });

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert('✅ ' + data.message);
    } else {
      alert('⚠️ ' + (data.message || 'Failed to delete results.'));
    }

    loadFacialAnalysisSessions();
  } catch (error) {
    alert('Error: ' + error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = originalHtml;
  }
}

// Update facial analysis pagination
function updateFacialAnalysisPagination(pagination) {
  const paginationContainer = document.getElementById('facial-analysis-pagination');
  const paginationInfo = document.getElementById('fa-pagination-info');
  const paginationControls = document.getElementById('fa-pagination-controls');

  if (!paginationContainer || !pagination) return;

  // Hide pagination if no results or only one page
  if (pagination.total === 0 || pagination.pages <= 1) {
    paginationContainer.classList.add('hidden');
    return;
  }

  // Show pagination
  paginationContainer.classList.remove('hidden');

  // Update pagination info
  const start = (pagination.page - 1) * pagination.per_page + 1;
  const end = Math.min(pagination.page * pagination.per_page, pagination.total);

  if (paginationInfo) {
    paginationInfo.innerHTML = `
      Showing <span class="font-medium">${start}</span> to <span class="font-medium">${end}</span> of
      <span class="font-medium">${pagination.total}</span> results
    `;
  }

  // Build pagination controls
  if (paginationControls) {
    let controlsHtml = '';

    // Previous button
    if (pagination.has_prev) {
      controlsHtml += `
        <button onclick="changeFacialAnalysisPage(${pagination.prev_num})"
                class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">
          <span class="sr-only">Previous</span>
          <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
        </button>
      `;
    } else {
      controlsHtml += `
        <button disabled class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">
          <span class="sr-only">Previous</span>
          <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
        </button>
      `;
    }

    // Page numbers (show max 7 pages)
    const maxPages = 7;
    let startPage = Math.max(1, pagination.page - Math.floor(maxPages / 2));
    let endPage = Math.min(pagination.pages, startPage + maxPages - 1);

    if (endPage - startPage + 1 < maxPages) {
      startPage = Math.max(1, endPage - maxPages + 1);
    }

    // First page
    if (startPage > 1) {
      controlsHtml += `
        <button onclick="changeFacialAnalysisPage(1)"
                class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">
          1
        </button>
      `;
      if (startPage > 2) {
        controlsHtml += `<span class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">...</span>`;
      }
    }

    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
      if (i === pagination.page) {
        controlsHtml += `
          <button aria-current="page"
                  class="z-10 bg-indigo-50 border-indigo-500 text-indigo-600 relative inline-flex items-center px-4 py-2 border text-sm font-medium">
            ${i}
          </button>
        `;
      } else {
        controlsHtml += `
          <button onclick="changeFacialAnalysisPage(${i})"
                  class="bg-white border-gray-300 text-gray-500 hover:bg-gray-50 relative inline-flex items-center px-4 py-2 border text-sm font-medium">
            ${i}
          </button>
        `;
      }
    }

    // Last page
    if (endPage < pagination.pages) {
      if (endPage < pagination.pages - 1) {
        controlsHtml += `<span class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">...</span>`;
      }
      controlsHtml += `
        <button onclick="changeFacialAnalysisPage(${pagination.pages})"
                class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">
          ${pagination.pages}
        </button>
      `;
    }

    // Next button
    if (pagination.has_next) {
      controlsHtml += `
        <button onclick="changeFacialAnalysisPage(${pagination.next_num})"
                class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">
          <span class="sr-only">Next</span>
          <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
          </svg>
        </button>
      `;
    } else {
      controlsHtml += `
        <button disabled class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-300 cursor-not-allowed">
          <span class="sr-only">Next</span>
          <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
          </svg>
        </button>
      `;
    }

    paginationControls.innerHTML = controlsHtml;
  }
}

// Change facial analysis page
function changeFacialAnalysisPage(page) {
  currentFacialPage = page;
  loadFacialAnalysisSessions();
}
