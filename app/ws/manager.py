
#Registro de las placas conectadas


import asyncio
import logging
import asyncpg
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.services.configuracion import build_config

log = logging.getLogger(__name__)


"""Hacer esto equivale a:"""
# @dataclass
# class Conexion:
#     ws:WebSocket
#     cliente_id: int
#     lock: asyncio.Lock = field(default_factory=asyncio.Lock)
"""Esto:"""
class Conexion:
    def __init__(self, ws, cliente_id, lock = None):
        self.ws = ws
        self.cliente_id = cliente_id
        self.lock = lock if lock is not None else asyncio.Lock()

class ConnectionManager:
    def __init__(self) -> None:
        self._conexiones: dict[int, Conexion] = {} # controlador_id -> Conexion

    async def registrar(self, controlador_id: int, ws: WebSocket, cliente_id: int) -> Conexion:
        nueva = Conexion(ws, cliente_id)
        vieja = self._conexiones.get(controlador_id)
        self._conexiones[controlador_id] = nueva
        if vieja is not None:
            try:
                await vieja.ws.close(code = 4000)
            except Exception:
                pass
        return nueva
    def quitar(self, controlador_id: int, conexion: Conexion) -> None:
        # Solo si sigue siendo la misma: si la placa ya se reconectó, no borramos la nueva.
        if self._conexiones.get(controlador_id) is conexion:
            del self._conexiones[controlador_id]

    async def enviar(self, conexion: Conexion, data: dict) -> None:
        async with conexion.lock:                    # un mensaje a la vez por socket
            await conexion.ws.send_json(data)

    async def enviar_config(self, pool: asyncpg.Pool, controlador_id: int) -> None:
        conexion = self._conexiones.get(controlador_id)
        if conexion is None:
            return                                   # no está conectada: recibirá la config al conectarse
        config = await build_config(pool, conexion.cliente_id, controlador_id)
        try:
            await self.enviar(conexion, config)
        except Exception:
            log.warning("No se pudo enviar la config al controlador %s", controlador_id)


manager = ConnectionManager()