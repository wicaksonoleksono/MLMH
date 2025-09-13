// app/static/js/admin/dashboard.js
// Admin dashboard JavaScript functions

// We don't need the downloadBothSessions function anymore since we're showing sessions separately
// But we'll keep it in case we want to add a \"Download Both\" button later
function downloadBothSessions(session1Id, session2Id) {
  // Use the existing bulk export endpoint
  fetch("/admin/export/bulk", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_ids: [session1Id, session2Id],
    }),
  })
    .then((response) => {
      if (response.ok) {
        // Create download link
        const filename =
          response.headers.get("Content-Disposition") || "bulk_export.zip";
        response.blob().then((blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.style.display = "none";
          a.href = url;
          a.download = filename.includes("filename=")
            ? filename.split("filename=")[1].replace(/\"/g, "")
            : "bulk_export.zip";
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        });
      } else {
        alert("Export failed. Please try again.");
      }
    })
    .catch((error) => {
      // Export failed
      alert("Export failed. Please try again.");
    });
}

// Function to handle bulk download with loading indicator
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

// Debug function to check delete buttons
function debugDeleteButtons() {
  const allDeleteButtons = document.querySelectorAll(
    'button[onclick*="confirmDelete"]'
  );
  console.log(
    `Found ${allDeleteButtons.length} delete buttons:`,
    allDeleteButtons
  );
  allDeleteButtons.forEach((btn, index) => {
    console.log(
      `Button ${index}:`,
      btn,
      "onclick:",
      btn.onclick,
      "disabled:",
      btn.disabled
    );
  });
}

// Delete session confirmation and execution
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
  const deleteBtn = document.querySelector(`button[data-session-id="${sessionId}"]`);

  if (!deleteBtn) {
    console.error(`Delete button not found for session ${sessionId}`);
    alert("Delete button not found. Please refresh the page and try again.");
    return;
  }

  const originalContent = deleteBtn.innerHTML;
  deleteBtn.disabled = true;
  deleteBtn.innerHTML = `
        <svg class=\"animate-spin w-3.5 h-3.5 mr-1.5\" fill=\"none\" viewBox=\"0 0 24 24\">
            <circle class=\"opacity-25\" cx=\"12\" cy=\"12\" r=\"10\" stroke=\"currentColor\" stroke-width=\"4\"></circle>
            <path class=\"opacity-75\" fill=\"currentColor\" d=\"M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z\"></path>
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
        <span class=\"px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800\">
            DELETED
        </span>
    `;

  // Update the actions cell
  const actionsCell = sessionRow.querySelector("td:nth-child(6)");
  actionsCell.innerHTML = `
        <div class=\"flex items-center space-x-1\">
            <span class=\"inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-red-100 text-red-600 border border-red-200\">
                <svg class=\"w-3.5 h-3.5 mr-1.5\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                    <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16\"></path>
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

// AJAX Search Functionality
let searchTimeout;
const searchInput = document.getElementById("userSearch");
const searchSpinner = document.getElementById("searchSpinner");
const userTable = document.getElementById("userTable");
const userCount = document.getElementById("userCount");
const paginationControls = document.querySelector(".pagination-controls"); // You'll need to add this class to your pagination div

function debounceSearch(query) {
  // Clear previous timeout
  clearTimeout(searchTimeout);

  // Show spinner
  if (searchSpinner) {
    searchSpinner.classList.remove("hidden");
  }

  // Set new timeout for 500ms (faster feedback)
  searchTimeout = setTimeout(() => {
    performSearchAjax(query.trim());
  }, 500);
}

function performSearchAjax(query, page = 1) {
  // Get current pagination and per_page params
  const urlParams = new URLSearchParams(window.location.search);
  const currentPage = page || urlParams.get("page") || 1;
  const perPage = urlParams.get("per_page") || 15;

  // Build AJAX URL - use ajax-data endpoint
  const ajaxUrl = `/admin/ajax-data?q=${encodeURIComponent(
    query
  )}&page=${currentPage}&per_page=${perPage}`;

  // Perform AJAX request
  fetch(ajaxUrl, {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      // Hide spinner
      if (searchSpinner) {
        searchSpinner.classList.add("hidden");
      }

      // Handle API response wrapper format from @api_response decorator
      const actualData = data.status === "OLKORECT" ? data.data : data;
      
      if (actualData.status === "success" || actualData.data) {
        const responseData = actualData.data || actualData;
        
        // Update table content
        updateUserTable(responseData);

        // Update user count
        if (userCount) {
          const countText = query
            ? `${responseData.pagination.total} users found for \"${query}\"`
            : `${responseData.pagination.total} total users`;
          userCount.textContent = countText;
        }

        // Update pagination controls
        updatePaginationControls(responseData.pagination, query);

        // Update URL without full reload (browser history)
        const newUrlParams = new URLSearchParams(window.location.search);
        if (query) {
          newUrlParams.set("q", query);
          newUrlParams.set("page", responseData.pagination.page);
        } else {
          newUrlParams.delete("q");
          newUrlParams.set("page", responseData.pagination.page);
        }
        newUrlParams.set("per_page", responseData.pagination.per_page);
        window.history.replaceState(
          {},
          "",
          `${window.location.pathname}?${newUrlParams.toString()}`
        );
      }
    })
    .catch((error) => {
      console.error("Search error:", error);
      if (searchSpinner) {
        searchSpinner.classList.add("hidden");
      }
      // Fallback to full page reload on error
      const urlParams = new URLSearchParams(window.location.search);
      if (query && query.length > 0) {
        urlParams.set("q", query);
        urlParams.set("page", 1); // Reset to first page
      } else {
        urlParams.delete("q");
        urlParams.delete("page");
      }
      window.location.search = urlParams.toString();
    });
}

function updateUserTable(data) {
  // Find the tbody element in the user table
  const tbody = userTable ? userTable.querySelector("tbody") : null;
  if (!tbody) return;

  // Clear existing rows (except the last \"separator\" row if it exists)
  while (tbody.firstChild && tbody.children.length > 1) {
    tbody.removeChild(tbody.firstChild);
  }

  // If no results, show empty state
  if (!data.items || data.items.length === 0) {
    tbody.innerHTML = `
            <tr>
                <td colspan=\"6\" class=\"py-12 text-center text-gray-500\">
                    <div class=\"flex flex-col items-center justify-center\">
                        <svg class=\"w-12 h-12 text-gray-300 mb-3\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z\"></path>
                        </svg>
                        <span class=\"text-lg font-medium text-gray-400\">No user sessions found</span>
                        <p class=\"text-sm text-gray-500 mt-1\">Try adjusting your search terms</p>
                    </div>
                </td>
            </tr>
        `;
    return;
  }

  // Build new rows
  let newRows = "";
  data.items.forEach((user_session) => {
    // Session 1 Row
    newRows += `
            <tr class=\"border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150\">
                <td class=\"py-4 px-6 font-medium text-gray-900\">${
                  user_session.user_id
                }</td>
                <td class=\"py-4 px-6 font-medium text-gray-900\">${
                  user_session.username
                }</td>
                <td class=\"py-4 px-6 text-gray-900\">
                    <div class=\"flex items-center\">
                        <div class=\"w-3 h-3 rounded-full bg-blue-500 mr-2\"></div>
                        <span class=\"font-medium\">Session 1</span>
                    </div>
                </td>
                <td class=\"py-4 px-6\">
                    ${
                      user_session.session1 === "COMPLETED" &&
                      user_session.session1_id
                        ? `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800\">${user_session.session1}</span>`
                        : user_session.session1 === "Not done"
                        ? `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600\">Not Started</span>`
                        : `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800\">${user_session.session1}</span>`
                    }
                </td>
                <td class=\"py-4 px-6 text-gray-900\">
                    ${
                      user_session.session1_phq_score !== null &&
                      user_session.session1_phq_score !== undefined
                        ? `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800\">${user_session.session1_phq_score}</span>`
                        : `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600\">N/A</span>`
                    }
                </td>
                <td class=\"py-4 px-6 w-48\">
                    <div class=\"flex items-center justify-start space-x-1 min-w-0\">
                        ${
                          user_session.session1 === "COMPLETED" &&
                          user_session.session1_id
                            ? `<a href=\"/admin/export/session/${user_session.session1_id}\" 
                               class=\"inline-flex items-center justify-center px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm flex-shrink-0 w-20\">
                                <svg class=\"w-3.5 h-3.5 mr-1.5\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                                    <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4\"></path>
                                </svg>
                                Download
                            </a>
                            <button class="inline-flex items-center justify-center px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm flex-shrink-0 w-16 delete-session-btn" 
                                    data-session-id="${user_session.session1_id}" 
                                    data-username="${encodeURIComponent(user_session.username)}" 
                                    data-session-number="1">
                                <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                                Delete
                            </button>`
                            : `<div class=\"flex items-center justify-start w-full\">
                                <span class=\"inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200\">
                                    <svg class=\"w-3.5 h-3.5 mr-1.5\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                                        <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z\"></path>
                                    </svg>
                                    Disabled
                                </span>
                            </div>`
                        }
                    </div>
                </td>
            </tr>
            
            <!-- Session 2 Row -->
            <tr class=\"border-b border-gray-100 hover:bg-blue-50 transition-colors duration-150\">
                <td class=\"py-4 px-6 font-medium text-gray-900\">${
                  user_session.user_id
                }</td>
                <td class=\"py-4 px-6 font-medium text-gray-900\">${
                  user_session.username
                }</td>
                <td class=\"py-4 px-6 text-gray-900\">
                    <div class=\"flex items-center\">
                        <div class=\"w-3 h-3 rounded-full bg-purple-500 mr-2\"></div>
                        <span class=\"font-medium\">Session 2</span>
                    </div>
                </td>
                <td class=\"py-4 px-6\">
                    ${
                      user_session.session2 === "COMPLETED" &&
                      user_session.session2_id
                        ? `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800\">${user_session.session2}</span>`
                        : user_session.session2 === "Not done"
                        ? `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600\">Not Started</span>`
                        : `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800\">${user_session.session2}</span>`
                    }
                </td>
                <td class=\"py-4 px-6 text-gray-900\">
                    ${
                      user_session.session2_phq_score !== null &&
                      user_session.session2_phq_score !== undefined
                        ? `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800\">${user_session.session2_phq_score}</span>`
                        : `<span class=\"px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600\">N/A</span>`
                    }
                </td>
                <td class=\"py-4 px-6 w-48\">
                    <div class=\"flex items-center justify-start space-x-1 min-w-0\">
                        ${
                          user_session.session2 === "COMPLETED" &&
                          user_session.session2_id
                            ? `<a href=\"/admin/export/session/${user_session.session2_id}\" 
                               class=\"inline-flex items-center justify-center px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm flex-shrink-0 w-20\">
                                <svg class=\"w-3.5 h-3.5 mr-1.5\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                                    <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4\"></path>
                                </svg>
                                Download
                            </a>
                            <button class="inline-flex items-center justify-center px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 transition-colors duration-200 shadow-sm flex-shrink-0 w-16 delete-session-btn" 
                                    data-session-id="${user_session.session2_id}" 
                                    data-username="${encodeURIComponent(user_session.username)}" 
                                    data-session-number="2">
                                <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                                Delete
                            </button>`
                            : `<div class=\"flex items-center justify-start w-full\">
                                <span class=\"inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200\">
                                    <svg class=\"w-3.5 h-3.5 mr-1.5\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">
                                        <path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z\"></path>
                                    </svg>
                                    Disabled
                                </span>
                            </div>`
                        }
                    </div>
                </td>
            </tr>
            
            <!-- User Separator -->
            <tr class=\"border-b-2 border-gray-200\">
                <td colspan=\"6\" class=\"py-2 px-6 bg-gradient-to-r from-gray-50 to-gray-100\"></td>
            </tr>
        `;
  });

  // Insert new rows
  tbody.innerHTML = newRows;
}

function updatePaginationControls(pagination, searchQuery = "") {
  console.log('updatePaginationControls called with:', { pagination, searchQuery });
  
  const paginationContainer = document.querySelector('.pagination-controls') || 
                              document.getElementById('paginationContainer');
  
  if (!paginationContainer) {
    console.warn('Pagination container not found');
    return;
  }
  
  // Show/hide pagination based on page count
  if (pagination.pages <= 1) {
    paginationContainer.style.display = 'none';
    return;
  } else {
    paginationContainer.style.display = 'flex';
  }
  
  // Build pagination HTML
  const startItem = ((pagination.page - 1) * pagination.per_page + 1);
  const endItem = Math.min(pagination.page * pagination.per_page, pagination.total);
  
  let buttonsHTML = '';
  
  // Previous button
  if (pagination.has_prev) {
    buttonsHTML += `<button onclick="loadPage(${pagination.prev_num})" 
       class="px-3 py-2 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
        Previous
    </button>`;
  }
  
  // Page numbers
  for (let pageNum = 1; pageNum <= pagination.pages; pageNum++) {
    if (pageNum === pagination.page) {
      buttonsHTML += `<span class="px-3 py-2 text-sm bg-blue-600 text-white border border-blue-600 rounded-md">
        ${pageNum}
      </span>`;
    } else if (pageNum <= 2 || pageNum >= pagination.pages - 1 || 
               (pageNum >= pagination.page - 1 && pageNum <= pagination.page + 1)) {
      buttonsHTML += `<button onclick="loadPage(${pageNum})" 
         class="px-3 py-2 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
          ${pageNum}
      </button>`;
    } else if (pageNum === 3 && pagination.page > 4) {
      buttonsHTML += '<span class="px-3 py-2 text-sm text-gray-500">...</span>';
    } else if (pageNum === pagination.pages - 2 && pagination.page < pagination.pages - 3) {
      buttonsHTML += '<span class="px-3 py-2 text-sm text-gray-500">...</span>';
    }
  }
  
  // Next button
  if (pagination.has_next) {
    buttonsHTML += `<button onclick="loadPage(${pagination.next_num})" 
       class="px-3 py-2 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
        Next
    </button>`;
  }
  
  // Update container with pagination HTML
  paginationContainer.innerHTML = `
    <div class="flex items-center">
      <p class="text-sm text-gray-700">
        Showing ${startItem} to ${endItem} of ${pagination.total} results
      </p>
    </div>
    <div class="flex items-center space-x-2">
      ${buttonsHTML}
    </div>
  `;
}

// AJAX pagination function
function loadPage(pageNum) {
  const urlParams = new URLSearchParams(window.location.search);
  const searchQuery = urlParams.get('q') || '';
  const perPage = urlParams.get('per_page') || 15;
  
  // Always use AJAX for pagination, regardless of search state
  const ajaxUrl = `/admin/ajax-data?page=${pageNum}&per_page=${perPage}${searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : ''}`;
  
  fetch(ajaxUrl)
    .then(response => response.json())
    .then(data => {
      const actualData = data.status === "OLKORECT" ? data.data : data;
      
      if (actualData.status === "success" || actualData.data) {
        const responseData = actualData.data || actualData;
        
        // Update table content
        updateUserTable(responseData);
        
        // Update pagination controls
        updatePaginationControls(responseData.pagination, searchQuery);
        
        // Update URL without refresh
        urlParams.set('page', pageNum);
        window.history.replaceState({}, '', `?${urlParams.toString()}`);
        
        // Update user count
        const userCount = document.getElementById('userCount');
        if (userCount) {
          const countText = searchQuery
            ? `${responseData.pagination.total} users found for "${searchQuery}"`
            : `${responseData.pagination.total} total users`;
          userCount.textContent = countText;
        }
      }
    })
    .catch(error => {
      console.error('Error loading page:', error);
      // Fallback to page reload if AJAX fails
      urlParams.set('page', pageNum);
      window.location.search = urlParams.toString();
    });
}

// Initialize dashboard when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Global event delegation for delete buttons using data attributes
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('.delete-session-btn');
    if (!btn) return;

    console.log('Delete button clicked via data attributes:', btn);
    
    // Extract data from attributes
    const sessionId = btn.dataset.sessionId;
    const username = decodeURIComponent(btn.dataset.username || '');
    const sessionNumber = parseInt(btn.dataset.sessionNumber || '0', 10);

    console.log('Extracted data:', { sessionId, username, sessionNumber });
    
    // Call confirmDelete function
    confirmDelete(sessionId, username, sessionNumber);
  });
  
  console.log('Data-attribute delete button handler set up');
  
  // Add event listener to bulk download button
  const bulkDownloadBtn = document.querySelector(".bulk-download-btn");
  if (bulkDownloadBtn) {
    bulkDownloadBtn.addEventListener("click", function (e) {
      // Show confirmation dialog
      if (
        confirm(
          "This will download all completed sessions organized by session number. This may take a while. Continue?"
        )
      ) {
        downloadAllSessions();
      } else {
        e.preventDefault();
      }
    });
  }

  // Add event listeners for search input
  if (searchInput) {
    // Search input listener
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.trim();

      if (!query) {
        // Clear search if input is empty
        clearSearch();
        return;
      }

      debounceSearch(query);
    });

    // Clear search button listener
    const clearButton = document.getElementById("clearSearch");
    if (clearButton) {
      clearButton.addEventListener("click", clearSearch);
    }

    // Clear search on escape key
    searchInput.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.target.value = "";
        clearSearch();
      }
    });
  }
});

// Clear search function
function clearSearch() {
  if (searchInput) {
    searchInput.value = "";
  }

  // Perform search with empty query to reset
  performSearchAjax("");
}
