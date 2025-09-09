// Reusable OTP Component
class OTPComponent {
  constructor(onSuccess = null) {
    this.currentUserId = null;
    this.countdownTimer = null;
    this.onSuccess = onSuccess || this.defaultOnSuccess;
    this.init();
  }

  init() {
    this.setupOTPInputs();
    this.setupVerifyButton();
    this.setupResendButton();
    this.checkForOTPUser();
  }

  setupOTPInputs() {
    // OTP Input Auto-focus and paste handling
    for (let i = 1; i <= 6; i++) {
      const otpInput = document.getElementById(`otp${i}`);
      if (otpInput) {
        otpInput.addEventListener('input', (e) => {
          // Limit to single digit
          if (e.target.value.length > 1) {
            e.target.value = e.target.value.slice(0, 1);
          }
          
          if (e.target.value.length === 1 && i < 6) {
            document.getElementById(`otp${i + 1}`).focus();
          }
        });
        
        otpInput.addEventListener('keydown', (e) => {
          if (e.key === 'Backspace' && e.target.value === '' && i > 1) {
            document.getElementById(`otp${i - 1}`).focus();
          }
        });

        // Handle paste functionality
        otpInput.addEventListener('paste', (e) => {
          e.preventDefault();
          const pasteData = e.clipboardData.getData('text');
          
          // Extract only digits and limit to 6
          const digits = pasteData.replace(/\D/g, '').slice(0, 6);
          
          if (digits.length > 0) {
            // Fill the OTP inputs with pasted digits
            for (let j = 0; j < Math.min(digits.length, 6); j++) {
              const targetInput = document.getElementById(`otp${j + 1}`);
              if (targetInput) {
                targetInput.value = digits[j];
              }
            }
            
            // Focus on the next empty input or the last filled one
            const nextIndex = Math.min(digits.length + 1, 6);
            const nextInput = document.getElementById(`otp${nextIndex}`);
            if (nextInput) {
              nextInput.focus();
            }
          }
        });
      }
    }
  }

  setupVerifyButton() {
    const verifyBtn = document.getElementById('verifyOtpBtn');
    if (verifyBtn) {
      verifyBtn.addEventListener('click', () => this.verifyOTP());
    }
  }

  setupResendButton() {
    const resendBtn = document.getElementById('resendOtpBtn');
    if (resendBtn) {
      resendBtn.addEventListener('click', () => this.resendOTP());
    }
  }

  checkForOTPUser() {
    const urlParams = new URLSearchParams(window.location.search);
    const userId = urlParams.get('otp_user_id');
    if (userId) {
      this.showModal(parseInt(userId));
    }
  }

  showModal(userId) {
    this.currentUserId = userId;
    document.getElementById('otpModal').classList.remove('hidden');
    document.getElementById('otp1').focus();
    this.startResendCountdown();
  }

  hideModal() {
    document.getElementById('otpModal').classList.add('hidden');
    this.clearOTPInputs();
    if (this.countdownTimer) clearInterval(this.countdownTimer);
  }

  clearOTPInputs() {
    for (let i = 1; i <= 6; i++) {
      document.getElementById(`otp${i}`).value = '';
    }
    document.getElementById('otpError').classList.add('hidden');
    document.getElementById('otpSuccess').classList.add('hidden');
  }

  getOTPCode() {
    let otp = '';
    for (let i = 1; i <= 6; i++) {
      otp += document.getElementById(`otp${i}`).value;
    }
    return otp;
  }

  async verifyOTP() {
    const otpCode = this.getOTPCode();
    const errorDiv = document.getElementById('otpError');
    const successDiv = document.getElementById('otpSuccess');
    const verifyBtn = document.getElementById('verifyOtpBtn');
    
    if (otpCode.length !== 6) {
      errorDiv.textContent = 'Masukkan kode OTP 6 digit lengkap';
      errorDiv.classList.remove('hidden');
      return;
    }

    verifyBtn.disabled = true;
    verifyBtn.textContent = 'Memverifikasi...';

    try {
      const response = await fetch('/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.currentUserId,
          otp_code: otpCode
        })
      });

      const result = await response.json();

      if (response.ok) {
        successDiv.textContent = result.message || result.data?.message || 'Email berhasil diverifikasi!';
        successDiv.classList.remove('hidden');
        errorDiv.classList.add('hidden');
        
        setTimeout(() => {
          this.onSuccess(result);
        }, 2000);
      } else {
        const errorMessage = result.message || result.data?.message || 'Verifikasi gagal';
        errorDiv.textContent = errorMessage;
        errorDiv.classList.remove('hidden');
        successDiv.classList.add('hidden');
      }
    } catch (error) {
      errorDiv.textContent = 'Terjadi kesalahan. Silakan coba lagi.';
      errorDiv.classList.remove('hidden');
    } finally {
      verifyBtn.disabled = false;
      verifyBtn.textContent = 'Verifikasi';
    }
  }

  async resendOTP() {
    const resendBtn = document.getElementById('resendOtpBtn');
    resendBtn.disabled = true;

    try {
      const response = await fetch('/auth/resend-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: this.currentUserId })
      });

      const result = await response.json();

      if (response.ok) {
        const successMessage = result.message || result.data?.message || 'Kode OTP baru telah dikirim';
        document.getElementById('otpSuccess').textContent = successMessage;
        document.getElementById('otpSuccess').classList.remove('hidden');
        document.getElementById('otpError').classList.add('hidden');
        this.clearOTPInputs();
        this.startResendCountdown();
      } else {
        const errorMessage = result.message || result.data?.message || 'Gagal mengirim ulang OTP';
        document.getElementById('otpError').textContent = errorMessage;
        document.getElementById('otpError').classList.remove('hidden');
      }
    } catch (error) {
      document.getElementById('otpError').textContent = 'Gagal mengirim ulang OTP. Silakan coba lagi.';
      document.getElementById('otpError').classList.remove('hidden');
    }
  }

  startResendCountdown() {
    let timeLeft = 300; // 5 minutes
    const resendBtn = document.getElementById('resendOtpBtn');
    const resendText = document.getElementById('resendText');
    const countdown = document.getElementById('countdown');
    const countdownTime = document.getElementById('countdownTime');

    resendBtn.disabled = true;
    resendText.classList.add('hidden');
    countdown.classList.remove('hidden');

    this.countdownTimer = setInterval(() => {
      timeLeft--;
      countdownTime.textContent = timeLeft;

      if (timeLeft <= 0) {
        clearInterval(this.countdownTimer);
        resendBtn.disabled = false;
        resendText.classList.remove('hidden');
        countdown.classList.add('hidden');
      }
    }, 1000);
  }

  defaultOnSuccess(result) {
    // Default behavior: redirect to login page
    this.hideModal();
    window.location.href = '/auth/login';
  }
}

// Make it globally available
window.OTPComponent = OTPComponent;