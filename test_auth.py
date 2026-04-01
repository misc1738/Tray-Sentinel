#!/usr/bin/env python3
"""Test authentication system - debug invalid credentials issue."""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.auth import verify_password, _load_users, hash_password, USERS
from app.jwt_auth import authenticate_user

def test_auth():
    print("=" * 80)
    print("AUTHENTICATION SYSTEM DEBUG")
    print("=" * 80)
    
    # Test 1: Check demo users
    print("\n1. Available Demo Users:")
    print("-" * 80)
    for user_id, user_data in USERS.items():
        print(f"   {user_id:20} role={user_data['role']:20} hash={user_data['password_hash'][:20]}...")
    
    # Test 2: Check loaded users
    print("\n2. Loaded Users (from _load_users()):")
    print("-" * 80)
    users = _load_users()
    for user_id, user_data in users.items():
        print(f"   {user_id:20} role={user_data.get('role', 'N/A'):20} hash={user_data.get('password_hash', 'N/A')[:20]}...")
    
    # Test 3: Password verification
    print("\n3. Password Verification Tests:")
    print("-" * 80)
    test_password = "pass123"
    test_hash = "$2b$12$QixTHz.HU3X7XWvJL9.CZuKo8IzDX0YeYK5d/QL0WQJiqJhzC5cti"
    
    is_valid = verify_password(test_password, test_hash)
    print(f"   verify_password('pass123', hash) = {is_valid}")
    
    # Test 4: Authenticate user
    print("\n4. User Authentication Tests:")
    print("-" * 80)
    
    test_cases = [
        ("officer1", "pass123", True),
        ("officer1", "wrong", False),
        ("analyst1", "pass123", True),
        ("nonexistent", "pass123", False),
        ("invalid", "", False),
    ]
    
    for user_id, password, should_succeed in test_cases:
        result = authenticate_user(user_id, password)
        status = "✓ PASS" if (result is not None) == should_succeed else "✗ FAIL"
        print(f"   {status}: authenticate_user('{user_id}', '{password}') = {result}")
    
    # Test 5: Hash a test password
    print("\n5. Password Hash Generation:")
    print("-" * 80)
    new_hash = hash_password("pass123")
    print(f"   hash_password('pass123') = {new_hash}")
    
    # Test 6: Verify the new hash
    print("\n6. Verify Generated Hash:")
    print("-" * 80)
    is_valid = verify_password("pass123", new_hash)
    print(f"   verify_password('pass123', new_hash) = {is_valid}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_auth()
