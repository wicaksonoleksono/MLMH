// Facial Analysis Processing - Session management with debounce
// Process facial expression analysis for eligible sessions

let allSessions = [];
let filteredSessions = [];
let searchDebounceTimer = null;

document.addEventListener('DOMContentLoaded', function() {
  checkGrpcHealth();
  loadSessions();
  initializeEventListeners();
});

function normalizeStatus(status) {
  if (!status) {
    return 'not_started';
  }
  return String(status).trim().toLowerCase();
}

// Check gRPC service health
async function checkGrpcHealth() {
  try {
    const response = await fetch('/admin/facial-analysis/health');

    // Check if response is JSON
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      console.error('Health check: Expected JSON, got', contentType);
      const banner = document.getElementById('grpc-status-banner');
      banner.innerHTML = `
        <div class="flex items-center justify-between p-4 bg-red-50 rounded-lg border border-red-200">
          <div class="flex items-center">
            <svg class="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <span class="text-sm font-medium text-red-700">Health check failed - server error</span>
          </div>
        </div>
      `;
      return;
    }

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    const banner = document.getElementById('grpc-status-banner');

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

// Load all eligible sessions
async function loadSessions() {
  showLoading();
  hideError();

  try {
    const response = await fetch('/admin/ajax-dashboard-data?tab=facial-analysis');

    // Check if response is JSON
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      hideLoading();
      showError('Server error: Expected JSON response but got ' + (contentType || 'unknown content type'));
      return;
    }

    const result = await response.json();

    // Handle @api_response decorator wrapper
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.status === 'success') {
      // Extract facial analysis sessions from user_sessions data
      allSessions = [];

      for (const item of data.user_sessions.items) {
        // Process Session 1
        if (item.session1_id && item.session1_facial_analysis) {
          allSessions.push({
            id: item.session1_id,
            user_id: item.user_id,
            username: item.username,
            email: item.email || '',
            session_number: 1,
            session_end: item.session1_end,
            phq_status: item.session1_facial_analysis.phq_status,
            llm_status: item.session1_facial_analysis.llm_status,
            phq_images_count: item.session1_facial_analysis.phq_images || 0,
            llm_images_count: item.session1_facial_analysis.llm_images || 0,
            total_images: (item.session1_facial_analysis.phq_images || 0) + (item.session1_facial_analysis.llm_images || 0)
          });
        }

        // Process Session 2
        if (item.session2_id && item.session2_facial_analysis) {
          allSessions.push({
            id: item.session2_id,
            user_id: item.user_id,
            username: item.username,
            email: item.email || '',
            session_number: 2,
            session_end: item.session2_end,
            phq_status: item.session2_facial_analysis.phq_status,
            llm_status: item.session2_facial_analysis.llm_status,
            phq_images_count: item.session2_facial_analysis.phq_images || 0,
            llm_images_count: item.session2_facial_analysis.llm_images || 0,
            total_images: (item.session2_facial_analysis.phq_images || 0) + (item.session2_facial_analysis.llm_images || 0)
          });
        }
      }

      filteredSessions = allSessions;
      hideLoading();
      applyFilters();
      updateStats(data.stats);
    } else {
      hideLoading();
      showError(data.message || 'Failed to load sessions');
    }
  } catch (error) {
    hideLoading();
    showError('Error loading sessions: ' + error.message);
  }
}

// Initialize event listeners
function initializeEventListeners() {
  const searchInput = document.getElementById('searchInput');
  const statusFilter = document.getElementById('statusFilter');
  const processAllButton = document.getElementById('process-all-btn');

  // Search with debounce
  searchInput.addEventListener('input', function(e) {
    const query = e.target.value.trim();

    // Clear previous timer
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }

    // Set new timer with 300ms debounce
    searchDebounceTimer = setTimeout(() => {
      applyFilters();
    }, 300);
  });

  // Status filter
  statusFilter.addEventListener('change', function() {
    applyFilters();
  });

  if (processAllButton) {
    processAllButton.addEventListener('click', processAllSessions);
  }
}

// Apply search and filter
function applyFilters() {
  const searchQuery = document.getElementById('searchInput').value.trim().toLowerCase();
  const statusFilter = document.getElementById('statusFilter').value;

  filteredSessions = allSessions.filter(session => {
    const phqStatus = normalizeStatus(session.phq_status);
    const llmStatus = normalizeStatus(session.llm_status);

    // Search filter
    const matchesSearch = !searchQuery ||
      session.username.toLowerCase().includes(searchQuery) ||
      session.email.toLowerCase().includes(searchQuery);

    // Status filter
    let matchesStatus = true;
    if (statusFilter !== 'all') {
      if (statusFilter === 'not_started') {
        matchesStatus = phqStatus === 'not_started' && llmStatus === 'not_started';
      } else if (statusFilter === 'processing') {
        matchesStatus = phqStatus === 'processing' || llmStatus === 'processing';
      } else if (statusFilter === 'completed') {
        matchesStatus = phqStatus === 'completed' && llmStatus === 'completed';
      }
    }

    return matchesSearch && matchesStatus;
  });

  renderSessions();
}

// Render sessions table
function renderSessions() {
  const tbody = document.getElementById('sessions-table-body');
  const emptyState = document.getElementById('empty-state');
  const contentArea = document.getElementById('content-area');

  contentArea.classList.remove('hidden');

  if (!filteredSessions || filteredSessions.length === 0) {
    tbody.innerHTML = '';
    emptyState.classList.remove('hidden');
    return;
  }

  emptyState.classList.add('hidden');

  tbody.innerHTML = filteredSessions.map(session => `
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
        ${getStatusBadge(session.phq_status, 'PHQ', session.id)}
      </td>
      <td class="px-6 py-4">
        ${getStatusBadge(session.llm_status, 'LLM', session.id)}
      </td>
      <td class="px-6 py-4">
        <div class="text-sm">
          <span class="text-blue-600 font-medium">${session.phq_images_count}</span> PHQ |
          <span class="text-purple-600 font-medium">${session.llm_images_count}</span> LLM
        </div>
      </td>
      <td class="px-6 py-4">
        ${getActionButton(session)}
      </td>
    </tr>
  `).join('');
}

// Get status badge HTML with action button
function getStatusBadge(status, type, sessionId) {
  const normalizedStatus = normalizeStatus(status);
  const colors = {
    'not_started': 'bg-gray-100 text-gray-700',
    'processing': 'bg-purple-100 text-purple-700 animate-pulse',
    'completed': 'bg-green-100 text-green-700',
    'failed': 'bg-red-100 text-red-700'
  };

  const color = colors[normalizedStatus] || 'bg-gray-100 text-gray-700';
  const label = (status || 'not_started').toString().replace(/_/g, ' ').toUpperCase();

  return `
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}">
      ${label}
    </span>
  `;
}

// Get action button HTML
function getActionButton(session) {
  const phqStatus = normalizeStatus(session.phq_status);
  const llmStatus = normalizeStatus(session.llm_status);
  const canProcess = phqStatus === 'not_started' || llmStatus === 'not_started';
  const isProcessing = phqStatus === 'processing' || llmStatus === 'processing';

  if (isProcessing) {
    return `
      <button disabled class="inline-flex items-center px-3 py-2 bg-gray-300 text-gray-600 text-xs font-medium rounded-md cursor-not-allowed">
        <svg class="w-4 h-4 mr-1.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Processing...
      </button>
    `;
  }

  // Build action buttons based on status
  let buttons = [];

  // Process button if any assessment not started
  if (canProcess) {
    buttons.push(`
      <button onclick="processSession('${session.id}')"
              class="inline-flex items-center px-2 py-1 bg-indigo-600 text-white text-xs font-medium rounded hover:bg-indigo-700 transition-colors">
        <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
        </svg>
        Process
      </button>
    `);
  }

  // Re-analyze PHQ button (only when completed)
  if (phqStatus === 'completed') {
    buttons.push(`
      <button onclick="reanalyzeAssessment('${session.id}', 'PHQ')"
              class="inline-flex items-center px-2 py-1 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors">
        <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Re-PHQ
      </button>
    `);
  }

  // Re-analyze LLM button (only when completed)
  if (llmStatus === 'completed') {
    buttons.push(`
      <button onclick="reanalyzeAssessment('${session.id}', 'LLM')"
              class="inline-flex items-center px-2 py-1 bg-purple-600 text-white text-xs font-medium rounded hover:bg-purple-700 transition-colors">
        <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Re-LLM
      </button>
    `);
  }

  // Delete buttons (only if completed or failed)
  if (phqStatus === 'completed' || phqStatus === 'failed') {
    buttons.push(`
      <button onclick="deleteAnalysis('${session.id}', 'PHQ')"
              class="inline-flex items-center px-2 py-1 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors">
        <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
        </svg>
        Del PHQ
      </button>
    `);
  }

  if (llmStatus === 'completed' || llmStatus === 'failed') {
    buttons.push(`
      <button onclick="deleteAnalysis('${session.id}', 'LLM')"
              class="inline-flex items-center px-2 py-1 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors">
        <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
        </svg>
        Del LLM
      </button>
    `);
  }

  // If no actions available
  if (buttons.length === 0) {
    return `<span class="text-xs text-gray-400">No actions</span>`;
  }

  return `<div class="flex flex-wrap gap-1">${buttons.join('')}</div>`;
}

// Process a session (async background processing)
async function processSession(sessionId) {
  if (!confirm('Start facial analysis processing for this session?\n\nThis will process both PHQ and LLM assessments in the background.\n\nYou can close this page, the processing will continue.')) {
    return;
  }

  try {
    const response = await fetch(`/admin/facial-analysis/process/${sessionId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Check if response is JSON
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await response.text();
      console.error('Expected JSON response, got:', contentType, text.substring(0, 200));
      alert('Server error: Expected JSON response but got HTML.\n\nThis usually means the server encountered an internal error.\n\nPlease check server logs.');
      return;
    }

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert('Processing queued successfully!\n\nPHQ Task ID: ' + (data.phq_task_id || 'N/A') + '\nLLM Task ID: ' + (data.llm_task_id || 'N/A') + '\n\nProcessing happens in background. Refresh to see updated status.');
      loadSessions(); // Reload to show updated status

      // Start polling for status updates
      startStatusPolling(sessionId);
    } else {
      alert('Processing failed:\n\n' + (data.message || 'Unknown error'));
    }
  } catch (error) {
    alert('Error starting processing:\n\n' + error.message);
  }
}

// Start polling for processing status
let activePollingIntervals = {};

function startStatusPolling(sessionId, maxPollCount = 720) {
  // Don't start multiple polls for same session
  if (activePollingIntervals[sessionId]) {
    return;
  }

  let pollCount = 0;
  const pollInterval = setInterval(async () => {
    pollCount++;

    try {
      // Fetch status for both assessments
      const phqResponse = await fetch(`/admin/facial-analysis/task-status/${sessionId}/PHQ`);
      const llmResponse = await fetch(`/admin/facial-analysis/task-status/${sessionId}/LLM`);

      const phqData = (await phqResponse.json()).details || {};
      const llmData = (await llmResponse.json()).details || {};

      const phqStatus = phqData.status || 'unknown';
      const llmStatus = llmData.status || 'unknown';

      console.log(`[Poll #${pollCount}] Session ${sessionId.substring(0, 8)}: PHQ=${phqStatus}, LLM=${llmStatus}`);

      // Check if both are done
      const phqDone = ['completed', 'failed'].includes(phqStatus);
      const llmDone = ['completed', 'failed'].includes(llmStatus);

      if (phqDone && llmDone) {
        clearInterval(pollInterval);
        delete activePollingIntervals[sessionId];
        console.log('Processing complete for session:', sessionId);

        // Build summary
        const phqMsg = phqStatus === 'completed' ? '✓ PHQ completed' : '✗ PHQ failed';
        const llmMsg = llmStatus === 'completed' ? '✓ LLM completed' : '✗ LLM failed';

        console.log(`Processing finished!\n\n${phqMsg}\n${llmMsg}`);
        loadSessions(); // Refresh to show final status
        return;
      }

      // Stop polling after timeout
      if (pollCount >= maxPollCount) {
        clearInterval(pollInterval);
        delete activePollingIntervals[sessionId];
        console.log('Polling timeout for session:', sessionId);
        loadSessions();
        return;
      }

    } catch (error) {
      console.error('Error polling status:', error);
    }
  }, 5000); // Poll every 5 seconds

  activePollingIntervals[sessionId] = pollInterval;
}

// Re-analyze an assessment
async function reanalyzeAssessment(sessionId, assessmentType) {
  if (!confirm(`Re-analyze ${assessmentType} assessment?\n\nThis will delete existing analysis and reprocess all images.`)) {
    return;
  }

  try {
    const response = await fetch(`/admin/facial-analysis/reanalyze/${sessionId}/${assessmentType}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert(`${assessmentType} re-analysis completed!\n\n${data.message}`);
      loadSessions(); // Reload to show updated status
    } else {
      alert(`Re-analysis failed:\n\n${data.message}`);
    }
  } catch (error) {
    alert(`Error re-analyzing ${assessmentType}:\n\n${error.message}`);
  }
}

// Delete analysis
async function deleteAnalysis(sessionId, assessmentType) {
  if (!confirm(`Delete ${assessmentType} analysis?\n\nThis will delete:\n- JSONL results file\n- Database record\n\nThis action cannot be undone!`)) {
    return;
  }

  try {
    const response = await fetch(`/admin/facial-analysis/delete/${sessionId}/${assessmentType}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const result = await response.json();
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      alert(`${assessmentType} analysis deleted successfully!`);
      loadSessions(); // Reload to show updated status
    } else {
      alert(`Delete failed:\n\n${data.message}`);
    }
  } catch (error) {
    alert(`Error deleting ${assessmentType} analysis:\n\n${error.message}`);
  }
}

// Update stats
function updateStats(stats) {
  document.getElementById('stat-total').textContent = stats.total || 0;
  document.getElementById('stat-pending').textContent = stats.pending || 0;
  document.getElementById('stat-processing').textContent = stats.processing || 0;
  document.getElementById('stat-completed').textContent = stats.completed || 0;
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

// Batch processing handler
async function processAllSessions() {
  if (!confirm('Process facial analysis for all eligible sessions?\n\nThis will sequentially process both PHQ and LLM assessments for every eligible session. This may take a while.')) {
    return;
  }

  const button = document.getElementById('process-all-btn');
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
      const errorMessage = [
        data.message || 'Batch processing completed with issues.',
        data.summary ? `Completed: ${data.summary.completed}, Partial: ${data.summary.partial}, Failed: ${data.summary.failed}` : ''
      ].filter(Boolean).join('\n');
      alert(errorMessage);
    }
    loadSessions();
  } catch (error) {
    alert('Batch processing failed:\n\n' + error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = originalHtml;
  }
}
