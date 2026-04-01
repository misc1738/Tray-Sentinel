#!/usr/bin/env python3
"""Generate valid bcrypt hash for pass123."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.auth import hash_password, verify_password

password = "pass123"
print(f"Generating bcrypt hash for password: '{password}'")
new_hash = hash_password(password)
print(f"Generated hash: {new_hash}")

# Verify it
is_valid = verify_password(password, new_hash)
print(f"Verification: {is_valid}")

# Also test the old hash
old_hash = "$2b$12$QixTHz.HU3X7XWvJL9.CZuKo8IzDX0YeYK5d/QL0WQJiqJhzC5cti"
print(f"\nTesting old hash: {old_hash}")
is_valid_old = verify_password(password, old_hash)
print(f"Old hash verification: {is_valid_old}")

if not is_valid_old:
    print("\n✓ Old hash is invalid. Use the generated hash above.")
    print(f"Replace in app/auth.py USERS dict with:\n   \"password_hash\": \"{new_hash}\",")
