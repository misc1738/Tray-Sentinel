"""Test the login API endpoint directly."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_login_endpoint():
    """Test login endpoint using httpx async client."""
    try:
        import httpx
    except ImportError:
        print("httpx not installed, testing locally instead...")
        from app.jwt_auth import authenticate_user, create_token_pair
        
        print("=" * 70)
        print("LOCAL AUTHENTICATION TEST")
        print("=" * 70)
        
        # Test login
        result = authenticate_user("officer1", "pass123")
        if result:
            user_id, role = result
            print(f"\n✓ Authentication PASSED for officer1/pass123")
            print(f"  User ID: {user_id}")
            print(f"  Role: {role}")
            
            # Create tokens
            tokens = create_token_pair(user_id, role)
            print(f"\n✓ Token Generation PASSED")
            print(f"  Access Token: {tokens.access_token[:60]}...")
            print(f"  Refresh Token: {tokens.refresh_token[:60]}...")
        else:
            print(f"\n✗ Authentication FAILED for officer1/pass123")
        
        print("\n" + "=" * 70)
        return

    # Try HTTP test if httpx available
    import asyncio
    
    async with httpx.AsyncClient() as client:
        print("=" * 70)
        print("API LOGIN TEST")
        print("=" * 70)
        
        test_cases = [
            ("officer1", "pass123", True),
            ("analyst1", "pass123", True),
            ("officer1", "wrong", False),
        ]
        
        for user_id, password, should_succeed in test_cases:
            try:
                response = await client.post(
                    "http://127.0.0.1:9999/auth/login",
                    json={"user_id": user_id, "password": password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"\n✓ {user_id}/{password}: SUCCESS")
                    print(f"  Token: {data['access_token'][:50]}...")
                elif response.status_code == 401:
                    print(f"\n✗ {user_id}/{password}: INVALID CREDENTIALS")
                else:
                    print(f"\n! {user_id}/{password}: HTTP {response.status_code}")
                    print(f"  {response.text}")
            except Exception as e:
                print(f"\n! {user_id}/{password}: ERROR - {e}")
        
        print("\n" + "=" * 70)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_login_endpoint())
