// app/static/js/admin/session-management.js
// Session management functionality for admin

// Global function to send Session 2 notification
function sendSession2Notification(userId) {
  fetch("/admin/session-management/send-notification", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: userId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === "success") {
        alert("Notifikasi berhasil dikirim!");
        // Refresh the page to update the UI
        location.reload();
      } else {
        alert("Gagal mengirim notifikasi: " + data.message);
      }
    })
    .catch((error) => {
      alert("Terjadi kesalahan saat mengirim notifikasi");
    });
}

// Global function to send all pending notifications
function sendAllPendingNotifications() {
  if (confirm("Apakah Anda yakin ingin mengirim semua notifikasi tertunda?")) {
    fetch("/admin/session-management/send-all-pending", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          alert(data.message);
          // Refresh the page to update the UI
          location.reload();
        } else {
          alert("Gagal mengirim notifikasi: " + data.message);
        }
      })
      .catch((error) => {
        alert("Terjadi kesalahan saat mengirim notifikasi");
      });
  }
}