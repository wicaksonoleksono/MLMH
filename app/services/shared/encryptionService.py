# app/services/shared/encryptionService.py
import os
from cryptography.fernet import Fernet
from typing import Optional


class EncryptionService:
    """Service for encrypting and decrypting sensitive data like API keys"""
    
    @staticmethod
    def _get_encryption_key() -> bytes:
        """Get encryption key from environment"""
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        return key.encode()
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key (for setup/migration)"""
        return Fernet.generate_key().decode()
    
    @staticmethod
    def encrypt_api_key(api_key: str) -> str:
        """Encrypt an API key for secure storage"""
        if not api_key or not api_key.strip():
            return ""
        
        try:
            fernet = Fernet(EncryptionService._get_encryption_key())
            encrypted = fernet.encrypt(api_key.encode())
            return encrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to encrypt API key: {str(e)}")
    
    @staticmethod
    def decrypt_api_key(encrypted_key: str) -> str:
        """Decrypt an API key for use"""
        if not encrypted_key or not encrypted_key.strip():
            return ""
        
        try:
            fernet = Fernet(EncryptionService._get_encryption_key())
            decrypted = fernet.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key: {str(e)}")
    
    @staticmethod
    def mask_api_key(api_key: str, show_chars: int = 4) -> str:
        """Create a masked version of API key for UI display"""
        if not api_key or not api_key.strip():
            return ""
        
        if len(api_key) <= show_chars + 4:
            # If key is too short, just show dots
            return "••••••••••••"
        
        # Show first 3 chars + dots + last show_chars
        prefix = api_key[:3] if api_key.startswith('sk-') else api_key[:2]
        suffix = api_key[-show_chars:]
        dots = "••••••••••••"
        
        return f"{prefix}{dots}{suffix}"
    
    @staticmethod
    def is_encrypted(value: str) -> bool:
        """Check if a string appears to be encrypted (not plain text API key)"""
        if not value:
            return False
        
        # Plain text API keys start with sk- and have specific patterns
        if value.startswith('sk-'):
            return False
        
        # Encrypted values are base64-like and longer
        try:
            # Try to decrypt - if successful, it was encrypted
            EncryptionService.decrypt_api_key(value)
            return True
        except:
            # Could be a masked key or other format
            return "••••" in value