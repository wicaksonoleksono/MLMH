// app/static/js/auth/register.js
// Registration form validation JavaScript

document.addEventListener('DOMContentLoaded', function() {
  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    registerForm.addEventListener('submit', function(e) {
      const password = document.getElementById('password').value;
      const confirmPassword = document.getElementById('confirm_password').value;
      
      if (password !== confirmPassword) {
        e.preventDefault();
        alert('Kata sandi dan konfirmasi kata sandi tidak cocok.');
        return false;
      }
      
      if (password.length < 6) {
        e.preventDefault();
        alert('Kata sandi harus minimal 6 karakter.');
        return false;
      }
      
      // Check required fields
      const requiredFields = ['username', 'email', 'password', 'confirm_password', 'age', 'gender', 'educational_level', 'cultural_background'];
      for (let i = 0; i < requiredFields.length; i++) {
        const field = document.getElementById(requiredFields[i]);
        if (!field.value.trim()) {
          e.preventDefault();
          alert('Harap isi semua field yang wajib diisi.');
          field.focus();
          return false;
        }
      }
    });
  }
});