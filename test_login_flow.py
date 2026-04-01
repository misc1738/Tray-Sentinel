"""Simulate the exact login flow that the API would execute."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Simulate the FastAPI login endpoint
def test_login_api_flow():
    """Test the complete login flow exactly as the API would execute."""
    from app.jwt_auth import authenticate_user, create_token_pair
    from app.auth import USERS, _load_users
    
    print("=" * 70)
    print("SIMULATING LOGIN API FLOW")
    print("=" * 70)
    
    # Check what users are available
    print("\n1. Users in USERS dict:")
    for uid in USERS.keys():
        print(f"   - {uid} (hash: {USERS[uid]['password_hash'][:30]}...)")
    
    # Check what _load_users returns
    print("\n2. Users returned by _load_users():")
    loaded = _load_users()
    for uid in loaded.keys():
        print(f"   - {uid} (hash: {loaded[uid].get('password_hash', 'N/A')[:30]}...)")
    
    # Test cases that the API would receive
    test_cases = [
        {"user_id": "officer1", "password": "pass123"},
        {"user_id": " officer1 ", "password": "pass123"},  # With spaces
        {"user_id": "officer1", "password": "pass123 "},   # Password with space
        {"user_id": "officer1", "password": "PASS123"},    # Wrong case
        {"user_id": "nonexistent", "password": "pass123"},
    ]
    
    print("\n3. Testing authenticate_user() for each case:")
    print("-" * 70)
    for i, test_data in enumerate(test_cases, 1):
        # API endpoint does: request_data.get("user_id", "").strip()
        user_id = test_data.get("user_id", "").strip()
        password = test_data.get("password", "")
        
        result = authenticate_user(user_id, password)
        status = "OK" if result else "FAIL"
        print(f"   [{i}] {status}: user_id='{user_id}', password='{password}'")
        print(f"       Result: {result}")
    
    # Test the full token creation flow for successful login
    print("\n4. Full token creation flow for successful login:")
    print("-" * 70)
    auth_result = authenticate_user("officer1", "pass123")
    if auth_result:
        user_id, role = auth_result
        print(f"   authenticate_user returned: ({user_id}, {role})")
        
        token_response = create_token_pair(user_id, role)
        print(f"   create_token_pair returned:")
        print(f"     - access_token: {token_response.access_token[:50]}...")
        print(f"     - refresh_token: {token_response.refresh_token[:50]}...")
        print(f"     - expires_in: {token_response.expires_in}")
    else:
        print(f"   AUTHENTICATION FAILED!")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_login_api_flow()
