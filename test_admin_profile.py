#!/usr/bin/env python3
"""
Test script for admin profile functionality.
This script demonstrates how to use the new admin profile update features.
"""

import os
import sys
import json
from getpass import getpass

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.shared.user_service import UserService


def test_profile_update():
    """Test profile update functionality."""
    print("=== Admin Profile Update Test ===")
    
    # This would normally be done in a Flask context with a logged-in user
    # For testing purposes, we'll simulate a user ID
    user_id = 1  # Admin user ID
    
    print(f"Testing profile update for user ID: {user_id}")
    
    # Test profile update
    result = UserService.update_profile(
        user_id=user_id,
        username="test_admin",
        email="admin@test.com"
    )
    
    print(f"Profile update result: {json.dumps(result, indent=2)}")
    
    # Test password update (this would require knowing the current password)
    # In a real scenario, this would be provided by the user in the UI
    current_password = getpass("Enter current password: ")
    new_password = getpass("Enter new password: ")
    
    result = UserService.update_password(
        user_id=user_id,
        current_password=current_password,
        new_password=new_password
    )
    
    print(f"Password update result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    test_profile_update()