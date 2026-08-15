"""Password hashing and verification.

Isolated behind this module so the hashing algorithm can change without
touching registration or login orchestration.
"""

from __future__ import annotations

import bcrypt

_BCRYPT_ROUNDS = 12
MIN_PASSWORD_LENGTH = 12


def hash_password(plaintext: str) -> str:
    encoded = bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt(_BCRYPT_ROUNDS))
    return encoded.decode("ascii")


def verify_password(plaintext: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False
