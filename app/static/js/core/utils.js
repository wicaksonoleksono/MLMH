// app/static/js/core/utils.js
// Common utility functions used across the application

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  const bgColor =
    type === "success"
      ? "bg-green-500"
      : type === "error"
      ? "bg-red-500"
      : "bg-blue-500";

  toast.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 transform translate-x-full transition-transform duration-300`;
  toast.textContent = message;

  document.body.appendChild(toast);

  // Slide in
  setTimeout(() => {
    toast.classList.remove("translate-x-full");
  }, 100);

  // Slide out after 4 seconds
  setTimeout(() => {
    toast.classList.add("translate-x-full");
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 300);
  }, 4000);
}
// ss
