## Verificar

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import get_pool
from app.core.security import decode_jwt
from app.repositories import usuarios

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UsuarioActual:
    id: int
    cliente_id: int | None   # None = superadmin
    rol: str


def _no_autenticado() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado",
                         headers={"WWW-Authenticate": "Bearer"})


async def usuario_actual(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UsuarioActual:
    if cred is None:
        raise _no_autenticado()
    try:
        usuario_id = decode_jwt(cred.credentials)
    except (jwt.PyJWTError, ValueError):
        raise _no_autenticado()
    # Se relee de la DB en cada request: si lo desactivan, pierde acceso al instante.
    async with get_pool().acquire() as conn:
        fila = await usuarios.get_activo(conn, usuario_id)
    if fila is None:
        raise _no_autenticado()
    return UsuarioActual(fila["id"], fila["cliente_id"], fila["rol"])


async def usuario_de_cliente(u: Annotated[UsuarioActual, Depends(usuario_actual)]) -> UsuarioActual:
    """Endpoints de datos de un cliente: el superadmin no tiene cliente, así que no aplica."""
    if u.cliente_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere un usuario de cliente")
    return u


async def admin_de_cliente(u: Annotated[UsuarioActual, Depends(usuario_de_cliente)]) -> UsuarioActual:
    if u.rol != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere rol admin")
    return u


# Atajos para usar en las rutas
UsuarioCliente = Annotated[UsuarioActual, Depends(usuario_de_cliente)]
AdminCliente = Annotated[UsuarioActual, Depends(admin_de_cliente)]