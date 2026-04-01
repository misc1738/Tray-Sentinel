from app.auth import verify_password
from app.jwt_auth import authenticate_user

pwd_hash = "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO"
print("=" * 60)
print("AUTHENTICATION TEST")
print("=" * 60)
print(f"verify_password('pass123'): {verify_password('pass123', pwd_hash)}")
print(f"authenticate_user('officer1', 'pass123'): {authenticate_user('officer1', 'pass123')}")
print(f"authenticate_user('officer1', 'wrong'): {authenticate_user('officer1', 'wrong')}")
print("=" * 60)
