// app/static/js/admin/navbar.js
// Admin navigation Alpine.js component

function navbar() {
  return {
    mobileOpen: false,
    navItems: [
      { name: "Dasbor", href: "/" },
      {
        name: "Manajemen Sesi",
        href: "/admin/session-management/eligible-users",
      },
      { name: "Informed Consent", href: "/admin/consent" },
      { name: "Pengaturan PHQ", href: "/admin/phq" },
      { name: "Pengaturan LLM", href: "/admin/llm" },
      { name: "Pengaturan Kamera", href: "/admin/camera" },
    ],

    isActive(href) {
      return window.location.pathname === href;
    },
  };
}