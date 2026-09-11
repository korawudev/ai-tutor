"""Unit tests for shared security utilities."""

from datetime import timedelta
from uuid import uuid4

from shared.utils.security import (
    create_access_token,
    decode_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        result = hash_password("test123")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestJWT:
    def test_create_and_decode_token(self):
        uid = uuid4()
        token = create_access_token(uid)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == str(uid)

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None

    def test_decode_expired_token(self):
        uid = uuid4()
        token = create_access_token(uid, expires_delta=timedelta(seconds=-1))
        assert decode_access_token(token) is None

    def test_get_user_id_from_token_valid(self):
        uid = uuid4()
        token = create_access_token(uid)
        result = get_user_id_from_token(token)
        assert result == uid

    def test_get_user_id_from_token_invalid(self):
        assert get_user_id_from_token("bad") is None
