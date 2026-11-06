# Sin verificar aun

from fastapi import APIRouter, HTTPException, status

from app.core.db import get_pool
from app.core.security import create_jwt, verify_password, hash_password
from app.repositories import usuarios
from app.schemas.api import LoginIn, TokenOut, SignupOut, SignupIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(datos: LoginIn):
    async with get_pool().acquire() as conn:
        fila = await usuarios.get_activo_por_email(conn, datos.email)
    hash_guardado = fila["password_hash"] if fila else None
    # Mismo mensaje si el email no existe o la clave está mal: no revela qué emails hay.
    if not verify_password(hash_guardado, datos.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Credenciales inválidas")
    return TokenOut(access_token=create_jwt(fila["id"]))


@router.post("/register", response_model=SignupOut)
async def signup(datos: SignupIn):
    async with get_pool().acquire() as conn:
        create_password_hash = hash_password(datos.password)
        fila = await usuarios.create(conn, datos.email, create_password_hash, datos.rol)
        if not fila:
            raise
