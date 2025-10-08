// app/static/js/admin/session-management.js
// Session management functionality for admin

// Global state
let currentTab = "eligible";
let currentPage = 1;
let currentPerPage = 15;
let currentSearchQuery = "";
let searchDebounceTimer = null;
let currentSortBy = "session_end";
let currentSortOrder = "desc";
let selectedUsers = new Set(); // Track selected user IDs

// Tab configuration
const tabConfig = {
  eligible: {
    title: "Pengguna yang Memenuhi Syarat untuk Sesi 2",
    tableTitle: "Semua Pengguna Sesi 1",
    tableDescription:
      "Semua pengguna yang telah menyelesaikan Sesi 1 dengan status kelayakan untuk Sesi 2",
    endpoint: "/admin/session-management/ajax-eligible-users",
    statsTitle: "Statistik",
  },
  unstarted: {
    title: "Pengguna yang Belum Memulai Assessment",
    tableTitle: "Pengguna dengan Email Terverifikasi - Belum Assessment",
    tableDescription:
      "Pengguna yang sudah mendaftar dan memverifikasi email tetapi belum memulai assessment",
    endpoint: "/admin/session-management/ajax-unstarted-users",
    statsTitle: "Statistik First Session Reminders",
  },
  pending: {
    title: "Notifikasi Tertunda",
    tableTitle: "Notifikasi Session 2 Tertunda",
    tableDescription: "Daftar notifikasi Session 2 yang belum dikirim",
    endpoint: "/admin/session-management/ajax-pending-notifications",
    statsTitle: "Statistik Notifikasi",
  },
};
// ss
// Initialize page
document.addEventListener("DOMContentLoaded", function () {
  // Get URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const urlSearchQuery = urlParams.get("q") || "";
  const urlPage = parseInt(urlParams.get("page")) || 1;
  const urlPerPage = parseInt(urlParams.get("per_page")) || 15;

  // Get tab from URL hash or default to 'eligible'
  const urlHash = window.location.hash.substring(1); // Remove the '#'
  const initialTab = urlHash && tabConfig[urlHash] ? urlHash : "eligible";

  // Set initial state from URL parameters
  currentTab = initialTab;
  currentPage = urlPage;
  currentPerPage = urlPerPage;
  currentSearchQuery = urlSearchQuery;

  // Update search input with URL value
  const searchInput = document.getElementById("search-input");
  if (searchInput && urlSearchQuery) {
    searchInput.value = urlSearchQuery;
  }

  // Update per page select with URL value
  const perPageSelect = document.getElementById("per-page-select");
  if (perPageSelect) {
    perPageSelect.value = currentPerPage;
  }

  window.sessionManagement.currentTab = currentTab;

  // Update tab styling
  updateTabStyling(currentTab);

  // Show/hide batch actions for initial tab
  const batchActions = document.getElementById("batch-actions");
  if (batchActions) {
    if (currentTab === "unstarted" || currentTab === "eligible") {
      batchActions.classList.remove("hidden");
    } else {
      batchActions.classList.add("hidden");
    }
  }

  // Load the initial tab data
  loadTabData(currentTab);

  // Initialize search functionality
  initializeSearch();

  // Listen for hash changes (back/forward navigation)
  window.addEventListener("hashchange", function () {
    const newHash = window.location.hash.substring(1);
    const newTab = newHash && tabConfig[newHash] ? newHash : "eligible";

    if (newTab !== currentTab) {
      currentTab = newTab;
      currentPage = 1; // Reset to first page
      window.sessionManagement.currentTab = currentTab;
      updateTabStyling(currentTab);
      loadTabData(currentTab);
    }
  });
});

// Initialize search functionality
function initializeSearch() {
  const searchInput = document.getElementById("search-input");
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

  // Clear search when tab changes
  searchInput.addEventListener("focus", function () {
    this.select(); // Select all text when focused for easy clearing
  });
}

// Perform search with debounce
function performSearch(query) {
  // Update search query state
  currentSearchQuery = query;
  currentPage = 1; // Reset to first page when searching

  // Update URL without refresh (like dashboard.js)
  updateUrlParams();

  // ONLY update table data, not entire page (like dashboard.js)
  loadTableDataOnly(currentTab);
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
  if (currentPerPage !== 15) {
    // 15 is default
    urlParams.set("per_page", currentPerPage);
  } else {
    urlParams.delete("per_page");
  }

  // Update URL with hash
  const newUrl = urlParams.toString()
    ? `${window.location.pathname}?${urlParams.toString()}${
        window.location.hash
      }`
    : `${window.location.pathname}${window.location.hash}`;

  window.history.replaceState({}, "", newUrl);
}

// Update tab styling
function updateTabStyling(tabName) {
  document.querySelectorAll(".tab-button").forEach((btn) => {
    btn.className =
      "tab-button whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300";
  });
  document.getElementById(`tab-${tabName}`).className =
    "tab-button whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm border-indigo-500 text-indigo-600";
}

// Switch tabs
function switchTab(tabName) {
  if (currentTab === tabName) return;

  currentTab = tabName;
  currentPage = 1; // Reset to first page

  // Clear search when switching tabs
  currentSearchQuery = "";
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.value = "";
  }

  // Show/hide batch actions for unstarted and eligible tabs
  const batchActions = document.getElementById("batch-actions");
  if (batchActions) {
    if (tabName === "unstarted" || tabName === "eligible") {
      batchActions.classList.remove("hidden");
    } else {
      batchActions.classList.add("hidden");
    }
  }

  // Update global object
  window.sessionManagement.currentTab = currentTab;

  // Update URL hash to make tab persistent
  window.location.hash = tabName;

  // Update tab styling
  updateTabStyling(tabName);

  loadTabData(tabName);
}

// Load data for current tab (full page setup)
function loadTabData(tabName) {
  const config = tabConfig[tabName];
  if (!config) return;

  showLoading();
  hideError();

  // Update static content
  document.getElementById("content-title").textContent = config.title;
  document.getElementById("table-title").textContent = config.tableTitle;
  document.getElementById("table-description").textContent =
    config.tableDescription;
  document.getElementById("stats-title").textContent = config.statsTitle;

  // Load the actual data
  loadTableDataOnly(tabName);

  // Update button text for current tab
  updateSelectedCount();
}

// Load ONLY table data (for search - no page refresh)
function loadTableDataOnly(tabName) {
  const config = tabConfig[tabName];
  if (!config) return;

  // Build URL with pagination, search, and sort
  let url = `${config.endpoint}?page=${currentPage}&per_page=${currentPerPage}`;
  if (currentSearchQuery) {
    url += `&q=${encodeURIComponent(currentSearchQuery)}`;
  }
  // Add sort params for eligible tab
  if (tabName === "eligible") {
    url += `&sort_by=${currentSortBy}&sort_order=${currentSortOrder}`;
  }

  fetch(url, {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      console.log(`[DEBUG] ${tabName} response:`, data);

      // Handle API response wrapper format from @api_response decorator (like dashboard.js)
      const actualData = data.status === "OLKORECT" ? data.data : data;

      if (
        actualData.status === "success" ||
        actualData.data ||
        data.status === "OLKORECT"
      ) {
        const responseData = actualData.data || actualData;

        console.log(`[DEBUG] ${tabName} responseData:`, responseData);
        console.log(`[DEBUG] ${tabName} items:`, responseData.items);

        // Update ONLY table content (no page elements)
        updateTable(tabName, responseData);
        updatePagination(responseData.pagination);
        updateStats(tabName, responseData.stats);

        // Make sure content is visible and loading is hidden
        hideLoading();
        showContent();

        // Update search count display
        updateSearchCount(responseData.pagination, currentSearchQuery);
      } else {
        hideLoading();
        console.error(`[ERROR] ${tabName} failed:`, actualData);
        showError(actualData.message || data.error || "Unknown error");
      }
    })
    .catch((error) => {
      hideLoading();
      console.error(`[ERROR] ${tabName} request failed:`, error);
      showError(error.message);
    });
}

// Update search count display (like dashboard.js)
function updateSearchCount(pagination, searchQuery) {
  const totalCountElement = document.getElementById("total-count");
  if (totalCountElement && pagination) {
    const countText = searchQuery
      ? `${pagination.total} items found for "${searchQuery}"`
      : `${pagination.total} total items`;
    totalCountElement.textContent = countText;
  }
}

// Update selected users count for batch actions
function updateSelectedCount() {
  // Handle both unstarted and eligible users checkboxes
  let selectedCheckboxes, selectedCount;

  if (currentTab === "unstarted") {
    selectedCheckboxes = document.querySelectorAll(
      'input[name="user-select"]:checked'
    );
    selectedCount = selectedCheckboxes.length;
  } else if (currentTab === "eligible") {
    selectedCheckboxes = document.querySelectorAll(
      'input[name="eligible-user-select"]:checked'
    );
    selectedCount = selectedCheckboxes.length;
  } else {
    selectedCount = 0;
  }

  const selectedCountElement = document.getElementById("selected-count");
  const batchButton = document.getElementById("send-batch-reminders-btn");

  if (selectedCountElement) {
    selectedCountElement.textContent = selectedCount;
  }

  if (batchButton) {
    batchButton.disabled = selectedCount === 0;

    // Update button text based on current tab
    if (currentTab === "eligible") {
      batchButton.textContent =
        selectedCount > 0
          ? "Send Selected Session 2 Notifications"
          : "Send Selected Session 2 Notifications";
    } else {
      batchButton.textContent =
        selectedCount > 0
          ? "Send Selected Reminders"
          : "Send Selected Reminders";
    }
  }

  // Update "Send All" button text
  const sendAllBtn = document.getElementById("send-all-reminders-btn");
  if (sendAllBtn) {
    if (currentTab === "eligible") {
      sendAllBtn.textContent = "Send All Session 2 Notifications";
    } else {
      sendAllBtn.textContent = "Send All Reminders";
    }
  }
}

// Handle checkbox selection for batch actions
function handleUserSelection() {
  updateSelectedCount();
}

// Select/deselect all users (for unstarted tab)
function toggleSelectAll(selectAllCheckbox) {
  const userCheckboxes = document.querySelectorAll('input[name="user-select"]');
  userCheckboxes.forEach((checkbox) => {
    checkbox.checked = selectAllCheckbox.checked;
  });
  updateSelectedCount();
}

// Global session management object for external access
window.sessionManagement = {
  currentTab: currentTab,
  loadTabData: loadTabData,
};

// Global function to send Session 2 notification
async function sendSession2Notification(userId) {
  try {
    const response = await fetch(
      "/admin/session-management/send-notification",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: userId,
        }),
      }
    );

    const data = await response.json();

    if (data.status === "success") {
      alert("Notifikasi berhasil dikirim!");
      // Refresh current tab data instead of page reload
      if (window.sessionManagement) {
        loadTabData(window.sessionManagement.currentTab);
      }
    } else {
      alert("Gagal mengirim notifikasi: " + data.message);
    }
  } catch (error) {
    console.error("Error sending notification:", error);
    alert("Terjadi kesalahan saat mengirim notifikasi");
  }
}

// Global function to send all pending notifications
async function sendAllPendingNotifications() {
  if (confirm("Apakah Anda yakin ingin mengirim semua notifikasi tertunda?")) {
    try {
      const response = await fetch(
        "/admin/session-management/send-all-pending",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      if (data.status === "success") {
        alert(data.message);
        // Refresh current tab data instead of page reload
        if (window.sessionManagement) {
          loadTabData(window.sessionManagement.currentTab);
        }
      } else {
        alert("Gagal mengirim notifikasi: " + data.message);
      }
    } catch (error) {
      console.error("Error sending all pending notifications:", error);
      alert("Terjadi kesalahan saat mengirim notifikasi");
    }
  }
}
async function sendFirstSessionReminder(userId) {
  try {
    const response = await fetch(
      "/admin/session-management/send-first-session-reminder",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_id: userId,
        }),
      }
    );

    const data = await response.json();

    if (data.status === "success") {
      alert("Reminder email berhasil dikirim!");
      // Refresh current tab data instead of page reload
      if (window.sessionManagement) {
        loadTabData(window.sessionManagement.currentTab);
      }
    } else {
      alert("Gagal mengirim reminder: " + data.message);
    }
  } catch (error) {
    console.error("Error sending first session reminder:", error);
    alert("Terjadi kesalahan saat mengirim reminder");
  }
}

// Send batch reminders to selected users
async function sendBatchFirstSessionReminders() {
  // Get selected user checkboxes
  const selectedCheckboxes = document.querySelectorAll(
    'input[name="user-select"]:checked'
  );
  const selectedUserIds = Array.from(selectedCheckboxes).map((cb) =>
    parseInt(cb.value)
  );

  if (selectedUserIds.length === 0) {
    alert("Pilih minimal satu pengguna untuk dikirim reminder");
    return;
  }

  if (
    !confirm(
      `Kirim reminder ke ${selectedUserIds.length} pengguna yang dipilih?`
    )
  ) {
    return;
  }

  try {
    const response = await fetch(
      "/admin/session-management/send-batch-first-session-reminders",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_ids: selectedUserIds,
        }),
      }
    );

    const data = await response.json();

    if (data.status === "OLKORECT") {
      const result = data.data;
      alert(
        `Batch reminder selesai!\nBerhasil: ${result.success_count}\nGagal: ${result.failed_count}\nTotal: ${result.total_requested}`
      );

      // Refresh table
      if (window.sessionManagement) {
        loadTabData(window.sessionManagement.currentTab);
      }
    } else {
      alert("Gagal mengirim batch reminder: " + (data.error || data.message));
    }
  } catch (error) {
    console.error("Error sending batch first session reminders:", error);
    alert("Terjadi kesalahan saat mengirim batch reminder");
  }
}

// Send reminders to ALL unstarted users
async function sendAllUnstartedReminders() {
  if (
    !confirm(
      "Kirim reminder ke SEMUA pengguna yang belum memulai assessment?\n\nIni akan mengirim email ke semua pengguna yang terverifikasi tapi belum mulai assessment."
    )
  ) {
    return;
  }

  try {
    const response = await fetch(
      "/admin/session-management/send-all-unstarted-reminders",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    const data = await response.json();

    if (data.status === "OLKORECT") {
      const result = data.data;
      alert(
        `Reminder ke semua pengguna selesai!\nBerhasil: ${result.success_count}\nGagal: ${result.failed_count}\nTotal: ${result.total_requested}`
      );

      // Refresh table
      if (window.sessionManagement) {
        loadTabData(window.sessionManagement.currentTab);
      }
    } else {
      alert(
        "Gagal mengirim reminder ke semua pengguna: " +
          (data.error || data.message)
      );
    }
  } catch (error) {
    console.error("Send all reminders error:", error);
    alert("Terjadi kesalahan saat mengirim reminder ke semua pengguna");
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

// Update table content
function updateTable(tabName, data) {
  const headerEl = document.getElementById("table-header");
  const bodyEl = document.getElementById("table-body");

  if (tabName === "eligible") {
    updateEligibleUsersTable(headerEl, bodyEl, data.items);
  } else if (tabName === "unstarted") {
    updateUnstartedUsersTable(headerEl, bodyEl, data.items);
  } else if (tabName === "pending") {
    updatePendingNotificationsTable(headerEl, bodyEl, data.items);
  } else {
    // Handle unknown tab
    headerEl.innerHTML =
      '<tr><th class="px-6 py-4 text-center text-sm text-gray-500">Tab tidak dikenal</th></tr>';
    bodyEl.innerHTML =
      '<tr><td class="px-6 py-4 text-center text-sm text-gray-500">Data tidak tersedia</td></tr>';
  }

  // Update total count
  document.getElementById(
    "total-count"
  ).textContent = `${data.pagination.total} total users`;
}

// Update eligible users table
function updateEligibleUsersTable(headerEl, bodyEl, users) {
  headerEl.innerHTML = `
    <tr>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
        <div class="flex items-center space-x-2">
          <input type="checkbox" id="select-all-eligible" onchange="toggleSelectAllEligible(this)" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
          <span>Pilih Semua Pada Halaman</span>
        </div>
      </th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Telepon</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal Sesi 1</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Hari Sejak</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
    </tr>
  `;

  if (users.length === 0) {
    bodyEl.innerHTML =
      '<tr><td colspan="8" class="px-6 py-4 text-center text-sm text-gray-500">Tidak ada pengguna yang menyelesaikan Sesi 1</td></tr>';
    return;
  }

  bodyEl.innerHTML = users
    .map(
      (user) => `
    <tr>
      <td class="px-6 py-4 whitespace-nowrap">
        <input type="checkbox" name="eligible-user-select" value="${
          user.user_id
        }" onchange="handleEligibleUserSelection()" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
      </td>
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${
        user.username || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.email || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.phone || "-"
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.session_1_completion_date || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.days_since_session_1 || 0
      } hari</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        ${getStatusBadge(user.status)}
      </td>
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
        <button onclick="sendSession2Notification(${
          user.user_id
        })" class="text-indigo-600 hover:text-indigo-900">
          Kirim Sekarang
        </button>
      </td>
    </tr>
  `
    )
    .join("");
}

// Update unstarted users table
function updateUnstartedUsersTable(headerEl, bodyEl, users) {
  headerEl.innerHTML = `
    <tr>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
        <div class="flex items-center space-x-2">
          <input type="checkbox" id="select-all" onchange="toggleSelectAll(this)" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
          <span>Pilih Semua Pada Halaman</span>
        </div>
      </th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Telepon</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal Daftar</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Hari Sejak Daftar</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
    </tr>
  `;

  if (users.length === 0) {
    bodyEl.innerHTML =
      '<tr><td colspan="8" class="px-6 py-4 text-center text-sm text-gray-500">Tidak ada pengguna yang memenuhi kriteria</td></tr>';
    return;
  }

  bodyEl.innerHTML = users
    .map(
      (user) => `
    <tr>
      <td class="px-6 py-4 whitespace-nowrap">
        <input type="checkbox" name="user-select" value="${
          user.user_id
        }" onchange="handleUserSelection()" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500">
      </td>
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${
        user.username || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.email || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.phone || "-"
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.registration_date || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        user.days_since_registration || 0
      } hari</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
        ${getUnstartedStatusBadge(user.status)}
      </td>
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
        <button onclick="sendFirstSessionReminder(${
          user.user_id
        })" class="text-green-600 hover:text-green-900 font-medium">
          Kirim Reminder
        </button>
      </td>
    </tr>
  `
    )
    .join("");

  // Reset selected count after table update
  updateSelectedCount();
}

// Update pending notifications table
function updatePendingNotificationsTable(headerEl, bodyEl, notifications) {
  headerEl.innerHTML = `
    <tr>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal Sesi 1</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Hari Sejak</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
      <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
    </tr>
  `;

  if (notifications.length === 0) {
    bodyEl.innerHTML =
      '<tr><td colspan="6" class="px-6 py-4 text-center text-sm text-gray-500">Tidak ada notifikasi tertunda</td></tr>';
    return;
  }

  bodyEl.innerHTML = notifications
    .map(
      (notification) => `
    <tr>
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${
        notification.username || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        notification.email || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        notification.session_1_completion_date || ""
      }</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${
        notification.days_since_session_1 || 0
      } hari</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">Tertunda</td>
      <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
        <button onclick="sendSession2Notification(${
          notification.user_id
        })" class="text-indigo-600 hover:text-indigo-900">
          Kirim Sekarang
        </button>
      </td>
    </tr>
  `
    )
    .join("");
}

// Get status badge for eligible users
function getStatusBadge(status) {
  const badges = {
    "Memenuhi Syarat": "bg-green-100 text-green-800",
    "Sudah Sesi 2": "bg-blue-100 text-blue-800",
    "Tidak Ada Email": "bg-red-100 text-red-800",
  };
  const colorClass = badges[status] || "bg-yellow-100 text-yellow-800";
  return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}">${status}</span>`;
}

// Get status badge for unstarted users
function getUnstartedStatusBadge(status) {
  const badges = {
    "Baru Mendaftar": "bg-blue-100 text-blue-800",
    "Perlu Diingatkan": "bg-yellow-100 text-yellow-800",
    "Butuh Dorongan": "bg-orange-100 text-orange-800",
    "Perlu Perhatian": "bg-red-100 text-red-800",
  };
  const colorClass = badges[status] || "bg-gray-100 text-gray-800";
  return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}">${status}</span>`;
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

// Update stats
function updateStats(tabName, stats) {
  const statsEl = document.getElementById("stats-content");
  let statsHtml = "";

  if (tabName === "eligible") {
    statsHtml = `
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Total Pengguna Eligible</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.eligible_count || 0
        }</dd>
      </div>
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Notifikasi Tertunda</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.pending_count || 0
        }</dd>
      </div>
    `;
  } else if (tabName === "unstarted") {
    statsHtml = `
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Total Belum Assessment</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.total_without_assessments || 0
        }</dd>
      </div>
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Baru Mendaftar (1 hari)</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.new_users_1_day || 0
        }</dd>
      </div>
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">1-7 hari yang lalu</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.users_1_week || 0
        }</dd>
      </div>
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">1-30 hari yang lalu</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.users_1_month || 0
        }</dd>
      </div>
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Lebih dari 30 hari</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.users_very_old || 0
        }</dd>
      </div>
    `;
  } else if (tabName === "pending") {
    statsHtml = `
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Total Notifikasi Tertunda</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.total_pending || 0
        }</dd>
      </div>
      <div class="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6">
        <dt class="text-sm font-medium text-gray-500">Ditampilkan di Halaman Ini</dt>
        <dd class="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">${
          stats.shown_pending || 0
        }</dd>
      </div>
    `;
  }

  statsEl.innerHTML = statsHtml;
}

// Change page
function changePage(page) {
  currentPage = page;

  // Update URL parameters
  updateUrlParams();

  loadTableDataOnly(currentTab);
}

// Change per page
function changePerPage(perPage) {
  currentPerPage = parseInt(perPage);
  currentPage = 1; // Reset to first page

  // Update URL parameters
  updateUrlParams();

  loadTableDataOnly(currentTab);
}

// ============= DYNAMIC BATCH HANDLERS =============

// Dynamic handler for batch send button
function handleBatchSend() {
  if (currentTab === "eligible") {
    sendBatchSession2Notifications();
  } else if (currentTab === "unstarted") {
    sendBatchFirstSessionReminders();
  }
}

// Dynamic handler for send all button
function handleSendAll() {
  if (currentTab === "eligible") {
    sendAllEligibleNotifications();
  } else if (currentTab === "unstarted") {
    sendAllUnstartedReminders();
  }
}

// ============= ELIGIBLE USERS BATCH FUNCTIONS =============

// Toggle select all for eligible users
function toggleSelectAllEligible(checkbox) {
  const userCheckboxes = document.querySelectorAll(
    'input[name="eligible-user-select"]'
  );
  userCheckboxes.forEach((cb) => {
    cb.checked = checkbox.checked;
  });
  handleEligibleUserSelection();
}

// Handle eligible user selection (just call the unified function)
function handleEligibleUserSelection() {
  updateSelectedCount();
}

// Send batch Session 2 notifications for eligible users
async function sendBatchSession2Notifications() {
  const selectedCheckboxes = document.querySelectorAll(
    'input[name="eligible-user-select"]:checked'
  );
  const userIds = Array.from(selectedCheckboxes).map((cb) =>
    parseInt(cb.value)
  );

  if (userIds.length === 0) {
    alert("Please select at least one user");
    return;
  }

  if (
    !confirm(
      `Send Session 2 notifications to ${userIds.length} selected users?`
    )
  ) {
    return;
  }

  const btn = document.getElementById("send-batch-reminders-btn");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Sending...";

  try {
    // Send all requests in parallel using Promise.allSettled
    const promises = userIds.map(async (userId) => {
      try {
        const response = await fetch(
          "/admin/session-management/send-notification",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ user_id: userId }),
          }
        );

        const data = await response.json();
        return {
          userId: userId,
          success: data.status === "success",
          error: data.status !== "success" ? data.message : null,
        };
      } catch (error) {
        console.error("Error sending to user", userId, ":", error);
        return {
          userId: userId,
          success: false,
          error: error.message,
        };
      }
    });

    const results = await Promise.allSettled(promises);
    const processedResults = results.map((result) =>
      result.status === "fulfilled"
        ? result.value
        : { success: false, error: "Promise rejected" }
    );

    const successCount = processedResults.filter((r) => r.success).length;
    const failedCount = processedResults.length - successCount;

    alert(
      `Batch notifications completed:\n${successCount} sent\n${failedCount} failed`
    );

    // Uncheck all checkboxes
    document
      .querySelectorAll('input[name="eligible-user-select"]')
      .forEach((cb) => (cb.checked = false));
    const selectAllCheckbox = document.getElementById("select-all-eligible");
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    handleEligibleUserSelection();

    // Reload data
    loadTableDataOnly(currentTab);
  } catch (error) {
    console.error("Error in batch sending:", error);
    alert("Failed to send batch notifications");
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

// Send all Session 2 notifications for eligible users
async function sendAllEligibleNotifications() {
  if (!confirm("Send Session 2 notifications to ALL eligible users?")) {
    return;
  }

  const btn = document.getElementById("send-all-reminders-btn");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Sending All...";

  try {
    // Use existing send-all-pending endpoint
    const response = await fetch("/admin/session-management/send-all-pending", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await response.json();

    if (data.status === "success") {
      alert("All pending notifications sent: " + data.message);

      // Reload data
      loadTableDataOnly(currentTab);
    } else {
      alert("Error: " + (data.message || "Unknown error"));
    }
  } catch (error) {
    console.error("Error:", error);
    alert("Failed to send all notifications");
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

// Apply sort filter function
function applySortFilter() {
  const sortBySelect = document.getElementById("sort-by-select");
  const sortOrderSelect = document.getElementById("sort-order-select");

  if (sortBySelect && sortOrderSelect) {
    currentSortBy = sortBySelect.value;
    currentSortOrder = sortOrderSelect.value;
    currentPage = 1; // Reset to first page when sorting changes

    // Reload data with new sort
    loadTableDataOnly(currentTab);
  }
}

// Toggle user selection
function toggleUserSelection(userId, checkbox) {
  if (checkbox.checked) {
    selectedUsers.add(userId);
  } else {
    selectedUsers.delete(userId);
  }
  updateSelectedCount();
}

// Toggle all users selection
function toggleSelectAll(checkbox) {
  const allCheckboxes = document.querySelectorAll('.user-checkbox');
  allCheckboxes.forEach(cb => {
    cb.checked = checkbox.checked;
    const userId = parseInt(cb.dataset.userId);
    if (checkbox.checked) {
      selectedUsers.add(userId);
    } else {
      selectedUsers.delete(userId);
    }
  });
  updateSelectedCount();
}

// Update selected count display
function updateSelectedCount() {
  const selectedCountElement = document.getElementById("selected-count");
  const batchSendBtn = document.getElementById("send-batch-reminders-btn");

  if (selectedCountElement) {
    selectedCountElement.textContent = selectedUsers.size;
  }

  if (batchSendBtn) {
    batchSendBtn.disabled = selectedUsers.size === 0;
  }
}
