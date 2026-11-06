# Imports

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

# Tokens

def generate_token() -> str:
    return secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

# Contraseñas de usuarios

_ph = PasswordHasher()
# Hash de relleno: se verifica contra él cuando el email no existe, así el login
# tarda lo mismo y no revela qué emails están registrados.
_HASH_RELLENO = _ph.hash("relleno-no-es-una-clave")

def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    # password_hash = None significa que el mail no existe 
    existe = password_hash is not None
    try:
        _ph.verify(password_hash if existe else _HASH_RELLENO, password)
        return existe
    except (VerifyMismatchError, InvalidHashError):
        return False


    # JWT de usuarios

    
JWT_ALG = "HS256"


def create_jwt(usuario_id: int) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.jwt_expira_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALG)


def decode_jwt(token: str) -> int:
    """Devuelve el id de usuario. Lanza jwt.PyJWTError si el token es inválido o venció."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALG], options={"require": ["sub", "exp"]})
    return int(payload["sub"])

