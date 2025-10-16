// Facial Analysis Sessions - Image Viewer
// Lists all sessions with camera captures for image viewing

document.addEventListener('DOMContentLoaded', function() {
  loadSessions();
});

async function loadSessions() {
  showLoading();
  hideError();

  try {
    const response = await fetch('/admin/facial-analysis/sessions-data');
    const result = await response.json();

    // Handle @api_response decorator wrapper
    const data = result.status === 'OLKORECT' ? result.data : result;

    if (data.success) {
      hideLoading();
      renderSessions(data.sessions);
      updateStats(data.total);
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

  tbody.innerHTML = sessions.map(session => `
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
  `).join('');
}

function updateStats(total) {
  document.getElementById('total-count').textContent = total;
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
