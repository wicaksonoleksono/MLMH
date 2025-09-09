// Registration form functionality
let usernameCheckTimeout;
let isUsernameAvailable = false;
let currentUserId = null;
let countdownTimer = null;

// Real-time username availability checking
document.addEventListener('DOMContentLoaded', function() {
  
  document.getElementById('username').addEventListener('input', function(e) {
    const username = e.target.value.trim();
    const statusDiv = document.getElementById('usernameStatus');
    const input = e.target;
    
    // Clear previous timeout
    clearTimeout(usernameCheckTimeout);
    
    if (username.length < 3) {
      statusDiv.className = 'mt-1 text-xs text-gray-500';
      statusDiv.textContent = 'Minimal 3 karakter';
      statusDiv.classList.remove('hidden');
      input.className = input.className.replace(/(border-red-300|border-green-300)/, 'border-gray-300');
      isUsernameAvailable = false;
      updateRegistrationButton();
      return;
    }
    
    // Show checking status
    statusDiv.className = 'mt-1 text-xs text-blue-600';
    statusDiv.textContent = 'Mengecek ketersediaan...';
    statusDiv.classList.remove('hidden');
    input.className = input.className.replace(/(border-red-300|border-green-300)/, 'border-blue-300');
    
    // Check availability after 500ms delay
    usernameCheckTimeout = setTimeout(async () => {
      try {
        const response = await fetch('/auth/check-username', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: username })
        });
        
        const response_data = await response.json();
        const result = response_data.data || response_data;
        
        if (result.available) {
          statusDiv.className = 'mt-1 text-xs text-green-600';
          statusDiv.textContent = '✓ Username tersedia';
          input.className = input.className.replace(/(border-red-300|border-blue-300|border-gray-300)/, 'border-green-300');
          isUsernameAvailable = true;
        } else {
          statusDiv.className = 'mt-1 text-xs text-red-600';
          if (result.message === "Username sudah digunakan") {
            statusDiv.textContent = '✗ Nama pengguna sudah pernah didaftarkan';
          } else {
            statusDiv.textContent = '✗ ' + (result.message || 'Gagal mengecek username');
          }
          input.className = input.className.replace(/(border-green-300|border-blue-300|border-gray-300)/, 'border-red-300');
          isUsernameAvailable = false;
        }
        
        updateRegistrationButton();
      } catch (error) {
        console.error('Username check error:', error);
        statusDiv.className = 'mt-1 text-xs text-red-600';
        statusDiv.textContent = '✗ Gagal mengecek username';
        input.className = input.className.replace(/(border-green-300|border-blue-300|border-gray-300)/, 'border-red-300');
        isUsernameAvailable = false;
        updateRegistrationButton();
      }
    }, 500);
  });

  // Update registration button state
  function updateRegistrationButton() {
    const submitBtn = document.querySelector('button[type="submit"]');
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    
    // Check if passwords match
    const passwordsMatch = password === confirmPassword && password.length > 0;
    
    // Check if all required fields are filled
    const requiredFields = ['username', 'email', 'phone', 'password', 'confirm_password', 'age', 'gender', 'educational_level', 'cultural_background'];
    let allFieldsFilled = true;
    
    for (const fieldName of requiredFields) {
      const field = document.getElementById(fieldName);
      if (!field || !field.value.trim()) {
        allFieldsFilled = false;
        break;
      }
    }
    
    // Button is enabled only when username is valid AND all fields are filled AND passwords match
    if (username.length >= 3 && isUsernameAvailable && allFieldsFilled && passwordsMatch) {
      submitBtn.disabled = false;
      submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
      submitBtn.disabled = true;
      submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
    
    // Always show "Buat Akun"
    submitBtn.textContent = 'Buat Akun';
  }

  // Form submission validation
  document.getElementById('registerForm').addEventListener('submit', function(e) {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    
    // Check username availability
    if (!isUsernameAvailable && username.length >= 3) {
      e.preventDefault();
      alert('Username tidak tersedia atau belum dicek. Silakan tunggu atau pilih username lain.');
      return false;
    }
    
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
    const requiredFields = ['username', 'email', 'phone', 'password', 'confirm_password', 'age', 'gender', 'educational_level', 'cultural_background'];
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

  // Initialize reusable OTP component
  new OTPComponent();

  // Password confirmation validation
  const passwordField = document.getElementById('password');
  const confirmPasswordField = document.getElementById('confirm_password');
  
  function validatePasswordMatch() {
    const password = passwordField.value;
    const confirmPassword = confirmPasswordField.value;
    const confirmPasswordDiv = confirmPasswordField.parentNode;
    
    // Remove existing status messages
    const existingStatus = confirmPasswordDiv.querySelector('.password-status');
    if (existingStatus) {
      existingStatus.remove();
    }
    
    if (confirmPassword.length > 0) {
      const statusDiv = document.createElement('div');
      statusDiv.className = 'password-status mt-1 text-xs';
      
      if (password === confirmPassword) {
        statusDiv.className += ' text-green-600';
        statusDiv.textContent = '✓ Kata sandi cocok';
        confirmPasswordField.className = confirmPasswordField.className.replace(/(border-red-300|border-gray-300)/, 'border-green-300');
      } else {
        statusDiv.className += ' text-red-600';
        statusDiv.textContent = '✗ Kata sandi tidak cocok';
        confirmPasswordField.className = confirmPasswordField.className.replace(/(border-green-300|border-gray-300)/, 'border-red-300');
      }
      
      confirmPasswordDiv.appendChild(statusDiv);
    } else {
      // Reset border when field is empty
      confirmPasswordField.className = confirmPasswordField.className.replace(/(border-green-300|border-red-300)/, 'border-gray-300');
    }
    
    updateRegistrationButton();
  }
  
  if (passwordField && confirmPasswordField) {
    passwordField.addEventListener('input', validatePasswordMatch);
    confirmPasswordField.addEventListener('input', validatePasswordMatch);
  }

  // Add event listeners to all required fields to update button state
  const requiredFields = ['username', 'email', 'phone', 'password', 'confirm_password', 'age', 'gender', 'educational_level', 'cultural_background'];
  requiredFields.forEach(fieldName => {
    const field = document.getElementById(fieldName);
    if (field) {
      field.addEventListener('input', updateRegistrationButton);
      field.addEventListener('change', updateRegistrationButton);
    }
  });
  
  // Initialize registration button state
  updateRegistrationButton();
});