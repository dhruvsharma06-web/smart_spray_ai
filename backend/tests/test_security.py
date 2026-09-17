from app.auth.security import hash_password, verify_password, create_access_token, decode_token

def test_password_and_jwt():
    h=hash_password("password123")
    assert verify_password("password123",h)
    token=create_access_token("42")
    assert decode_token(token)=="42"
