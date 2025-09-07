// app/static/js/admin/dashboard.js
// Admin dashboard JavaScript functions

// We don't need the downloadBothSessions function anymore since we're showing sessions separately
// But we'll keep it in case we want to add a "Download Both" button later
function downloadBothSessions(session1Id, session2Id) {
    // Use the existing bulk export endpoint
    fetch('/admin/export/bulk', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_ids: [session1Id, session2Id]
        })
    })
    .then(response => {
        if (response.ok) {
            // Create download link
            const filename = response.headers.get('Content-Disposition') || 'bulk_export.zip';
            response.blob().then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename.includes('filename=') ? 
                    filename.split('filename=')[1].replace(/"/g, '') : 
                    'bulk_export.zip';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            });
        } else {
            alert('Export failed. Please try again.');
        }
    })
    .catch(error => {
        // Export failed
        alert('Export failed. Please try again.');
    });
}

// Function to handle bulk download with loading indicator
function downloadAllSessions() {
    // Note: This function relies on Flask template variable that needs to be passed from template
    const downloadBtn = document.querySelector('.bulk-download-btn');
    if (!downloadBtn) return;
    
    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = '<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Preparing...';
    downloadBtn.disabled = true;
    
    // Start download
    setTimeout(() => {
        // Reset button after a short delay to allow download to start
        downloadBtn.innerHTML = originalText;
        downloadBtn.disabled = false;
    }, 2000);
}

// Delete session confirmation and execution
function confirmDelete(sessionId, username, sessionNumber) {
    if (confirm(`Are you sure you want to delete Session ${sessionNumber} for ${username}?\n\nThis will permanently delete:\n- All PHQ responses\n- All LLM conversations\n- All camera captures\n- All related data\n\nThis action cannot be undone.`)) {
        deleteSession(sessionId, username, sessionNumber);
    }
}

function deleteSession(sessionId, username, sessionNumber) {
    // Show loading state on the delete button
    const deleteBtn = document.querySelector(`button[onclick*="${sessionId}"]`);
    const originalContent = deleteBtn.innerHTML;
    deleteBtn.disabled = true;
    deleteBtn.innerHTML = `
        <svg class="animate-spin w-3.5 h-3.5 mr-1.5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Deleting...
    `;

    fetch(`/admin/export/session/${sessionId}/delete`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update UI to show deleted state
            updateSessionStateToDeleted(sessionId, username, sessionNumber);
            
            // Show success message
            showToast(`Session ${sessionNumber} for ${username} deleted successfully.`, 'success');
        } else {
            // Restore button on error
            deleteBtn.disabled = false;
            deleteBtn.innerHTML = originalContent;
            showToast(`Failed to delete session: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Delete error:', error);
        // Restore button on error
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = originalContent;
        showToast('Failed to delete session. Please try again.', 'error');
    });
}

function updateSessionStateToDeleted(sessionId, username, sessionNumber) {
    // Find the row containing this session
    const sessionRow = document.querySelector(`button[onclick*="${sessionId}"]`).closest('tr');
    
    // Update the status cell
    const statusCell = sessionRow.querySelector('td:nth-child(4)');
    statusCell.innerHTML = `
        <span class="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
            DELETED
        </span>
    `;
    
    // Update the actions cell
    const actionsCell = sessionRow.querySelector('td:nth-child(6)');
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
    sessionRow.style.transition = 'all 0.3s ease';
    sessionRow.style.backgroundColor = '#fef2f2';
    sessionRow.style.opacity = '0.7';
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add event listener to bulk download button
    const bulkDownloadBtn = document.querySelector('.bulk-download-btn');
    if (bulkDownloadBtn) {
        bulkDownloadBtn.addEventListener('click', function(e) {
            // Show confirmation dialog
            if (confirm('This will download all completed sessions organized by session number. This may take a while. Continue?')) {
                downloadAllSessions();
            } else {
                e.preventDefault();
            }
        });
    }
});