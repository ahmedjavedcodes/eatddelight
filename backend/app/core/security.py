"""Password hashing. Plan 05 extends this module with JWT encode/decode.

Uses ``bcrypt`` directly: ``passlib`` 1.7.x is unmaintained and its bcrypt
backend self-test crashes against bcrypt >= 4.1 / 5.x.
"""

import bcrypt


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False
