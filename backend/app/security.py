from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def session_version(password_hash: str) -> str:
    """改密码后哈希会变，旧 Cookie 里记的版本就对不上，从而让其他设备的登录失效。"""
    return password_hash[-16:]
