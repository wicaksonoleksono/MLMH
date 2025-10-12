// app/static/js/admin/navbar.js
// Admin navigation Alpine.js component

function navbar() {
  return {
    mobileOpen: false,
    navItems: [
      { name: "Dasbor", href: "/admin" },
      {
        name: "Manajemen Sesi",
        href: "/admin/session-management",
      },
      {
        name: "Analisis Wajah",
        href: "/admin/facial-analysis",
      },
      { name: "Informed Consent", href: "/admin/consent" },
      { name: "Pengaturan PHQ", href: "/admin/phq" },
      { name: "Pengaturan LLM", href: "/admin/llm" },
      { name: "Pengaturan Kamera", href: "/admin/camera" },
    ],
    // sss
    isActive(href) {
      // Normalize paths by removing trailing slashes
      const currentPath = window.location.pathname.replace(/\/$/, "");
      const targetPath = href.replace(/\/$/, "");

      // Special case for dashboard - only exact match
      if (targetPath === "/admin") {
        return currentPath === "/admin";
      }

      // For other routes, allow exact match or nested routes
      return (
        currentPath === targetPath || currentPath.startsWith(targetPath + "/")
      );
    },
  };
}
