"""비밀번호 해시 (표준 라이브러리 PBKDF2)"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 260_000
_ALGO = "sha256"


def hash_password(plain_password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(_ALGO, plain_password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        algo, iterations_str, salt, expected_hex = password_hash.split("$")
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    digest = hashlib.pbkdf2_hmac(algo, plain_password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return hmac.compare_digest(digest.hex(), expected_hex)
