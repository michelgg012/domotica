# SIN VERIFICAR AUN
from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminCliente, UsuarioActual, UsuarioCliente
from app.core.db import get_pool
from app.repositories import zonas
from app.schemas.api import ZonaEstadoOut, ZonaOut
from app.services.alarma import ZonaNoEncontrada, cambiar_armado

router = APIRouter(prefix="/api/zonas", tags=["zonas"])


@router.get("", response_model=list[ZonaOut])
async def listar(usuario: UsuarioCliente):
    async with get_pool().acquire() as conn:
        filas = await zonas.list_activas(conn, usuario.cliente_id)
    return [dict(f) for f in filas]


async def _cambiar(usuario: UsuarioActual, zona_id: int, armar: bool) -> ZonaEstadoOut:
    try:
        await cambiar_armado(get_pool(), usuario.cliente_id, usuario.id, zona_id, armar)
    except ZonaNoEncontrada:
        # 404 también si la zona es de OTRO cliente: no revelamos que existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zona no encontrada")
    return ZonaEstadoOut(id=zona_id, armada=armar)


@router.post("/{zona_id}/armar", response_model=ZonaEstadoOut)
async def armar(zona_id: int, usuario: AdminCliente):
    return await _cambiar(usuario, zona_id, True)


@router.post("/{zona_id}/desarmar", response_model=ZonaEstadoOut)
async def desarmar(zona_id: int, usuario: AdminCliente):
    return await _cambiar(usuario, zona_id, False)
